"""Unified Download Manager Orchestrator.
Coordinates Queue, Dynamic Engines, Persistence, and Telemetry.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import DownloadTask, StateDB, TaskCategory, TaskStatus, detect_category
from .rate_limiter import TokenBucketRateLimiter
from .segment_engine import SegmentDownloadEngine
from .stream_extractor import StreamExtractor


class DownloadManager:
    """Master controller managing queue, concurrency, state, and events."""

    def __init__(
        self,
        downloads_dir: str = "sdm/downloads",
        max_active_tasks: int = 3,
        default_connections_per_task: int = 8,
        db_path: str = "sdm/sdm.db",
    ):
        self.downloads_dir = Path(downloads_dir).resolve()
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.max_active_tasks = max_active_tasks
        self.default_connections = default_connections_per_task
        self.db = StateDB(db_path)

        self.tasks: Dict[str, DownloadTask] = {}
        self.engines: Dict[str, SegmentDownloadEngine] = {}
        self.running_jobs: Dict[str, asyncio.Task] = {}

        self.global_rate_limiter = TokenBucketRateLimiter(0)  # 0 = unlimited
        self.subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = asyncio.Lock()
        self._load_persisted_tasks()

    def _load_persisted_tasks(self) -> None:
        """Load tasks from database upon manager startup."""
        saved = self.db.list_tasks()
        for t in saved:
            # If was DOWNLOADING when app shut down, reset to PAUSED
            if t.status in (TaskStatus.DOWNLOADING, TaskStatus.CONNECTING):
                t.status = TaskStatus.PAUSED
                self.db.save_task(t)
            self.tasks[t.task_id] = t

    def add_subscriber(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self.subscribers.append(callback)

    def remove_subscriber(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def broadcast_telemetry(self, task: DownloadTask) -> None:
        """Save state and broadcast live telemetry to all connected WebSocket clients."""
        self.db.save_task(task)
        data = {"event": "task_updated", "task": task.to_dict()}
        for sub in list(self.subscribers):
            try:
                sub(data)
            except Exception:
                pass

    async def add_task(
        self,
        url: str,
        filename: Optional[str] = None,
        save_path: Optional[str] = None,
        category: Optional[TaskCategory] = None,
        headers: Optional[Dict[str, str]] = None,
        auto_start: bool = True,
        speed_limit_kbps: int = 0,
        sequential: bool = False,
    ) -> DownloadTask:
        task_id = str(uuid.uuid4())[:8]

        # Auto-detect category & filename
        clean_url = url.strip()
        guessed_name = filename or clean_url.split("?")[0].rstrip("/").split("/")[-1] or f"file_{task_id}.bin"
        cat = category or detect_category(guessed_name)
        target_path = save_path or str(self.downloads_dir / guessed_name)

        task = DownloadTask(
            task_id=task_id,
            url=clean_url,
            filename=guessed_name,
            save_path=target_path,
            category=cat,
            headers=headers or {},
            speed_limit_kbps=speed_limit_kbps,
            sequential=sequential,
        )

        async with self._lock:
            self.tasks[task_id] = task
            self.db.save_task(task)

        self.broadcast_telemetry(task)

        if auto_start:
            await self.start_task(task_id)

        return task

    async def start_task(self, task_id: str) -> bool:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status == TaskStatus.DOWNLOADING:
                return True

            task.status = TaskStatus.PENDING
            task.error_message = None

            # Check if active count reached
            active_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.DOWNLOADING)
            if active_count >= self.max_active_tasks:
                self.broadcast_telemetry(task)
                return True

            # Check if it's a media stream (YouTube, Vimeo, etc.)
            if StreamExtractor.is_media_url(task.url) and not task.url.endswith((".mp4", ".zip", ".iso", ".exe")):
                job = asyncio.create_task(self._run_media_stream_download(task))
            else:
                engine = SegmentDownloadEngine(
                    task=task,
                    max_connections=self.default_connections,
                    progress_callback=self.broadcast_telemetry,
                    rate_limiter=self.global_rate_limiter if self.global_rate_limiter.rate > 0 else None,
                )
                self.engines[task_id] = engine
                job = asyncio.create_task(self._run_engine_task(engine, task))

            self.running_jobs[task_id] = job
            return True

    async def _run_engine_task(self, engine: SegmentDownloadEngine, task: DownloadTask) -> None:
        try:
            await engine.start()
        except Exception as e:
            task.status = TaskStatus.ERROR
            task.error_message = str(e)
        finally:
            self.db.save_task(task)
            self.broadcast_telemetry(task)
            async with self._lock:
                self.running_jobs.pop(task.task_id, None)
                self.engines.pop(task.task_id, None)
            # Schedule next queued task
            await self._schedule_next_pending()

    async def _run_media_stream_download(self, task: DownloadTask) -> None:
        task.status = TaskStatus.DOWNLOADING
        self.broadcast_telemetry(task)

        def progress_hook(d: Dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed = d.get("speed") or 0.0
                task.total_size = total
                task.downloaded_bytes = downloaded
                task.speed_bps = speed
                task.eta_seconds = d.get("eta") or 0.0
                self.broadcast_telemetry(task)
            elif d.get("status") == "finished":
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                self.broadcast_telemetry(task)

        try:
            target_file = await StreamExtractor.download_media(
                task.url, task.save_path, progress_hook=progress_hook
            )
            task.save_path = target_file
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            task.status = TaskStatus.ERROR
            task.error_message = str(e)
        finally:
            self.db.save_task(task)
            self.broadcast_telemetry(task)
            async with self._lock:
                self.running_jobs.pop(task.task_id, None)
            await self._schedule_next_pending()

    async def pause_task(self, task_id: str) -> bool:
        async with self._lock:
            engine = self.engines.get(task_id)
            if engine:
                engine.pause()

            job = self.running_jobs.get(task_id)
            if job:
                job.cancel()

            task = self.tasks.get(task_id)
            if task:
                task.status = TaskStatus.PAUSED
                task.speed_bps = 0.0
                self.db.save_task(task)
                self.broadcast_telemetry(task)
                await self._schedule_next_pending()
                return True
            return False

    async def delete_task(self, task_id: str, delete_file: bool = False) -> bool:
        await self.pause_task(task_id)
        async with self._lock:
            task = self.tasks.pop(task_id, None)
            self.db.delete_task(task_id)
            if task and delete_file:
                try:
                    f = Path(task.save_path)
                    if f.exists():
                        f.unlink()
                except Exception:
                    pass

        # Broadcast deletion
        for sub in list(self.subscribers):
            try:
                sub({"event": "task_deleted", "task_id": task_id})
            except Exception:
                pass
        return True

    async def _schedule_next_pending(self) -> None:
        async with self._lock:
            active_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.DOWNLOADING)
            if active_count >= self.max_active_tasks:
                return

            for t in self.tasks.values():
                if t.status == TaskStatus.PENDING and t.task_id not in self.running_jobs:
                    asyncio.create_task(self.start_task(t.task_id))
                    break

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks.values()]

    def set_global_speed_limit(self, limit_kbps: int) -> None:
        bps = limit_kbps * 1024 if limit_kbps > 0 else 0
        self.global_rate_limiter.set_rate(bps)
