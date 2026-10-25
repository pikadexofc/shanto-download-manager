"""Dynamic Segment Allocation and Real-Time Tail-Splitting Engine.
Reverse-Engineered from Internet Download Manager (IDM)'s Core Dispatcher.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Dict, List, Optional
import aiohttp

from .models import DownloadTask, SegmentState, TaskStatus
from .rate_limiter import TokenBucketRateLimiter
from .storage import SparseFileWriter

CHUNK_READ_SIZE = 64 * 1024  # 64 KB read buffer
MIN_SPLIT_THRESHOLD = 2 * 1024 * 1024  # Minimum 2 MB remaining to warrant a split


class SegmentDownloadEngine:
    """High-throughput multi-connection dynamic segment download engine.

    Emulates IDM's proprietary dynamic segment splitting:
    When a thread finishes its byte-range early, it inspects remaining active
    threads, dynamically splits the largest remaining tail, and continues
    pulling data without waiting for the slower threads.
    """

    def __init__(
        self,
        task: DownloadTask,
        max_connections: int = 8,
        progress_callback: Optional[Callable[[DownloadTask], None]] = None,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
    ):
        self.task = task
        self.max_connections = max(1, min(max_connections, 32))
        self.progress_callback = progress_callback
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter(
            task.speed_limit_kbps * 1024 if task.speed_limit_kbps > 0 else 0
        )
        self.writer: Optional[SparseFileWriter] = None
        self._stop_event = asyncio.Event()
        self._session: Optional[aiohttp.ClientSession] = None
        self._active_workers: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._segment_counter = 0

    async def probe_url(self) -> tuple[int, bool, str]:
        """Probe URL to determine Content-Length, Accept-Ranges, and target filename."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "*/*",
            **self.task.headers,
        }

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Try HEAD first
            try:
                async with session.head(self.task.url, headers=headers, allow_redirects=True) as resp:
                    if resp.status < 400:
                        size = int(resp.headers.get("Content-Length", 0))
                        accepts_ranges = "bytes" in resp.headers.get("Accept-Ranges", "").lower()
                        # Extract filename if available
                        cd = resp.headers.get("Content-Disposition", "")
                        fname = self._extract_filename(cd, str(resp.url))
                        if accepts_ranges and size > 0:
                            return size, True, fname
            except Exception:
                pass

            # Fallback to GET with range: bytes=0-0 to test range support
            headers["Range"] = "bytes=0-0"
            try:
                async with session.get(self.task.url, headers=headers, allow_redirects=True) as resp:
                    cr = resp.headers.get("Content-Range", "")
                    # Content-Range: bytes 0-0/123456
                    size = 0
                    accepts_ranges = resp.status == 206
                    if cr and "/" in cr:
                        try:
                            size = int(cr.split("/")[1])
                        except ValueError:
                            size = 0
                    if size == 0:
                        size = int(resp.headers.get("Content-Length", 0))

                    fname = self._extract_filename(resp.headers.get("Content-Disposition", ""), str(resp.url))
                    return size, accepts_ranges, fname
            except Exception as e:
                raise RuntimeError(f"Failed to probe URL {self.task.url}: {e}")

    @staticmethod
    def _extract_filename(content_disposition: str, url: str) -> str:
        if content_disposition and "filename=" in content_disposition:
            parts = content_disposition.split("filename=")
            raw = parts[1].split(";")[0].strip("\"' ")
            if raw:
                return raw
        # From URL path
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path).rstrip("/")
        name = path.split("/")[-1] if "/" in path else ""
        return name or "download.bin"

    async def start(self) -> None:
        """Start or resume the multi-segment download."""
        self._stop_event.clear()
        self.task.status = TaskStatus.CONNECTING
        self._notify_progress()

        # Probe headers and file size if not known
        if self.task.total_size <= 0:
            size, resumable, fname = await self.probe_url()
            self.task.total_size = size
            self.task.resumable = resumable
            if not self.task.filename:
                self.task.filename = fname

        # Initialize sparse file writer
        self.writer = SparseFileWriter(self.task.save_path, self.task.total_size)
        self.writer.open()

        # Build initial segments if not already resuming existing segments
        if not self.task.segments:
            self._create_initial_segments()

        self._segment_counter = max([s.segment_id for s in self.task.segments], default=0) + 1
        self.task.status = TaskStatus.DOWNLOADING

        # Create persistent high-throughput TCP connector
        conn = aiohttp.TCPConnector(
            limit=self.max_connections * 2,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            force_close=False,
        )
        timeout = aiohttp.ClientTimeout(total=None, sock_read=60, sock_connect=30)
        self._session = aiohttp.ClientSession(connector=conn, timeout=timeout)

        # Launch background telemetry updater
        telemetry_worker = asyncio.create_task(self._telemetry_loop())

        try:
            # Launch workers for all unfinished segments up to max_connections
            await self._dispatch_workers()

            # Wait until either stopped or all segments are finished
            while not self._stop_event.is_set():
                if self._is_all_finished():
                    self.task.status = TaskStatus.COMPLETED
                    break

                # IDM dynamic tail-splitting check
                await self._check_dynamic_tail_splitting()
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            self.task.status = TaskStatus.PAUSED
        except Exception as e:
            self.task.status = TaskStatus.ERROR
            self.task.error_message = str(e)
        finally:
            telemetry_worker.cancel()
            await self._cleanup()
            self._notify_progress()

    def _create_initial_segments(self) -> None:
        total = self.task.total_size
        if not self.task.resumable or total <= 0:
            # Single non-segmented stream
            self.task.segments = [
                SegmentState(segment_id=1, start_byte=0, current_byte=0, end_byte=max(0, total - 1))
            ]
            return

        conns = min(self.max_connections, max(1, total // MIN_SPLIT_THRESHOLD))
        conns = max(1, conns)
        chunk_size = total // conns
        segments = []

        for i in range(conns):
            s_start = i * chunk_size
            s_end = (i + 1) * chunk_size - 1 if i < conns - 1 else total - 1
            segments.append(
                SegmentState(segment_id=i + 1, start_byte=s_start, current_byte=s_start, end_byte=s_end)
            )

        self.task.segments = segments

    async def _dispatch_workers(self) -> None:
        async with self._lock:
            for seg in self.task.segments:
                if seg.status not in ("FINISHED", "ACTIVE") and seg.current_byte <= seg.end_byte:
                    if len(self._active_workers) < self.max_connections:
                        seg.status = "ACTIVE"
                        worker = asyncio.create_task(self._download_segment(seg))
                        self._active_workers[seg.segment_id] = worker

    async def _download_segment(self, segment: SegmentState) -> None:
        """Worker task downloading a specific byte-range slice."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "*/*",
            **self.task.headers,
        }

        if self.task.resumable and self.task.total_size > 0:
            headers["Range"] = f"bytes={segment.current_byte}-{segment.end_byte}"

        try:
            assert self._session is not None
            async with self._session.get(self.task.url, headers=headers) as resp:
                if resp.status not in (200, 206):
                    segment.status = "ERROR"
                    return

                last_tick = time.monotonic()
                bytes_in_tick = 0

                while not self._stop_event.is_set():
                    # Stop if current_byte exceeded dynamically reduced end_byte
                    if segment.current_byte > segment.end_byte and self.task.total_size > 0:
                        break

                    needed = min(CHUNK_READ_SIZE, max(1, segment.end_byte - segment.current_byte + 1))
                    chunk = await resp.content.read(needed)
                    if not chunk:
                        break

                    # Acquire bandwidth token
                    await self.rate_limiter.acquire(len(chunk))

                    # Direct write to sparse offset
                    assert self.writer is not None
                    self.writer.write_at(segment.current_byte, chunk)

                    chunk_len = len(chunk)
                    segment.current_byte += chunk_len
                    bytes_in_tick += chunk_len

                    # Measure per-segment speed
                    now = time.monotonic()
                    delta = now - last_tick
                    if delta >= 0.5:
                        segment.speed_bps = bytes_in_tick / delta
                        bytes_in_tick = 0
                        last_tick = now

                segment.status = "FINISHED"

        except asyncio.CancelledError:
            segment.status = "PAUSED"
        except Exception:
            segment.status = "ERROR"
        finally:
            async with self._lock:
                self._active_workers.pop(segment.segment_id, None)

    async def _check_dynamic_tail_splitting(self) -> None:
        """IDM Core Algorithm:

        Find idle worker slots, locate slowest/largest remaining segment,
        and dynamically split its remaining tail to saturate bandwidth.
        """
        async with self._lock:
            if len(self._active_workers) >= self.max_connections:
                return

            # Find active segments with remaining bytes > MIN_SPLIT_THRESHOLD
            candidates = [
                s for s in self.task.segments
                if s.status == "ACTIVE" and (s.end_byte - s.current_byte) >= MIN_SPLIT_THRESHOLD
            ]
            if not candidates:
                # Also check any pending unstarted segments
                for s in self.task.segments:
                    if s.status == "PENDING" and s.current_byte <= s.end_byte:
                        s.status = "ACTIVE"
                        self._active_workers[s.segment_id] = asyncio.create_task(self._download_segment(s))
                        return
                return

            # Pick segment with the largest remaining byte distance
            target = max(candidates, key=lambda s: (s.end_byte - s.current_byte))
            remaining = target.end_byte - target.current_byte
            if remaining < MIN_SPLIT_THRESHOLD:
                return

            # Dynamic split: original keeps lower half, new segment takes upper half
            mid_point = target.current_byte + (remaining // 2)
            original_end = target.end_byte
            target.end_byte = mid_point

            self._segment_counter += 1
            new_seg = SegmentState(
                segment_id=self._segment_counter,
                start_byte=mid_point + 1,
                current_byte=mid_point + 1,
                end_byte=original_end,
                status="ACTIVE",
            )
            self.task.segments.append(new_seg)

            # Immediately launch worker for newly carved segment
            worker = asyncio.create_task(self._download_segment(new_seg))
            self._active_workers[new_seg.segment_id] = worker

    def _is_all_finished(self) -> bool:
        if not self.task.segments:
            return False
        return all(s.status == "FINISHED" for s in self.task.segments)

    async def _telemetry_loop(self) -> None:
        """Periodically compute aggregate downloaded bytes, speed, ETA, and fire callback."""
        last_downloaded = sum(s.downloaded_bytes for s in self.task.segments)
        last_time = time.monotonic()

        while not self._stop_event.is_set():
            await asyncio.sleep(0.3)
            now = time.monotonic()
            current_downloaded = sum(s.downloaded_bytes for s in self.task.segments)
            self.task.downloaded_bytes = current_downloaded

            delta_t = now - last_time
            delta_b = current_downloaded - last_downloaded

            if delta_t > 0:
                inst_speed = delta_b / delta_t
                # EMA smoothing
                self.task.speed_bps = (0.7 * self.task.speed_bps) + (0.3 * inst_speed)
                last_downloaded = current_downloaded
                last_time = now

                # Compute ETA
                if self.task.total_size > 0 and self.task.speed_bps > 0:
                    remaining_bytes = self.task.total_size - self.task.downloaded_bytes
                    self.task.eta_seconds = max(0.0, remaining_bytes / self.task.speed_bps)

            self._notify_progress()

    def _notify_progress(self) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(self.task)
            except Exception:
                pass

    def pause(self) -> None:
        self._stop_event.set()
        for worker in list(self._active_workers.values()):
            worker.cancel()
        self.task.status = TaskStatus.PAUSED

    async def _cleanup(self) -> None:
        if self.writer:
            self.writer.flush()
            self.writer.close()
        if self._session and not self._session.closed:
            await self._session.close()
