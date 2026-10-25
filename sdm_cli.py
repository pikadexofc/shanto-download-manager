"""Standalone High-Speed CLI for Shanto Download Manager.
Runs IDM dynamic segment splitting directly in terminal.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from sdm.core.models import DownloadTask, TaskCategory, TaskStatus, detect_category
from sdm.core.rate_limiter import TokenBucketRateLimiter
from sdm.core.segment_engine import SegmentDownloadEngine
from sdm.core.storage import SparseFileWriter


def render_cli_progress(task: DownloadTask) -> None:
    pct = task.progress * 100
    speed = task.format_speed(task.speed_bps)
    eta = f"{int(task.eta_seconds)}s" if task.eta_seconds > 0 else "--"
    downloaded = task.format_size(task.downloaded_bytes)
    total = task.format_size(task.total_size)
    bar_len = 25
    filled = int(bar_len * (task.progress))
    bar = "█" * filled + "░" * (bar_len - filled)

    segments_info = f"[{len(task.segments)} segs]" if task.segments else ""
    sys.stdout.write(
        f"\r[{task.status.value}] {bar} {pct:5.1f}% | {downloaded}/{total} | {speed} | ETA: {eta} {segments_info}   "
    )
    sys.stdout.flush()


async def run_cli_download(url: str, output: str, connections: int, limit_kbps: int) -> None:
    clean_url = url.strip()
    out_path = Path(output).resolve() if output else Path("sdm/downloads") / clean_url.split("?")[0].split("/")[-1]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    task = DownloadTask(
        task_id="cli",
        url=clean_url,
        filename=out_path.name,
        save_path=str(out_path),
        category=detect_category(out_path.name),
        speed_limit_kbps=limit_kbps,
    )

    print("\n" + "=" * 65)
    print("  SHANTO DOWNLOAD MANAGER — TURBO CLI")
    print("=" * 65)
    print(f"Target URL:    {clean_url}")
    print(f"Output File:   {out_path}")
    print(f"Connections:   {connections} dynamic threads")
    print(f"Speed Limit:   {limit_kbps} KB/s" if limit_kbps > 0 else "Speed Limit:   Unlimited")
    print("=" * 65 + "\n")

    rate_limiter = TokenBucketRateLimiter(limit_kbps * 1024 if limit_kbps > 0 else 0)
    engine = SegmentDownloadEngine(
        task=task,
        max_connections=connections,
        progress_callback=render_cli_progress,
        rate_limiter=rate_limiter,
    )

    t0 = time.time()
    await engine.start()
    t1 = time.time()
    print("\n")

    if task.status == TaskStatus.COMPLETED:
        sha256 = SparseFileWriter.compute_sha256(str(out_path))
        print(f"✅ Download Finished in {t1 - t0:.2f}s!")
        print(f"📁 Saved to: {out_path}")
        print(f"🔒 SHA-256:  {sha256}")
    else:
        print(f"❌ Download terminated with status: {task.status.value}")
        if task.error_message:
            print(f"Error: {task.error_message}")


def main():
    parser = argparse.ArgumentParser(description="SDM Turbo CLI Downloader")
    parser.add_argument("url", help="Download link or video URL")
    parser.add_argument("-o", "--output", default="", help="Output filepath")
    parser.add_argument("-c", "--connections", type=int, default=8, help="Max parallel connections (1-32)")
    parser.add_argument("-l", "--limit", type=int, default=0, help="Speed limit in KB/s (0 = unlimited)")
    args = parser.parse_args()

    asyncio.run(run_cli_download(args.url, args.output, args.connections, args.limit))


if __name__ == "__main__":
    main()
