"""End-to-End Test for Dynamic Segment Allocation and Zero-Merge Engine."""

import asyncio
import hashlib
from pathlib import Path
import sys
import aiohttp
from aiohttp import web

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sdm.core.models import DownloadTask, TaskStatus
from sdm.core.segment_engine import SegmentDownloadEngine
from sdm.core.storage import SparseFileWriter

# 8 MB synthetic test payload
PAYLOAD_SIZE = 8 * 1024 * 1024
TEST_DATA = bytearray((i * 41) % 256 for i in range(PAYLOAD_SIZE))
EXPECTED_SHA = hashlib.sha256(TEST_DATA).hexdigest()


async def handle_download(request: web.Request) -> web.Response:
    # Handle range requests
    range_header = request.headers.get("Range")

    if request.method == "HEAD":
        return web.Response(
            status=200,
            headers={
                "Content-Length": str(PAYLOAD_SIZE),
                "Accept-Ranges": "bytes",
                "Content-Disposition": 'attachment; filename="turbo_sample.bin"',
            },
        )

    if range_header and range_header.startswith("bytes="):
        # bytes=start-end
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else PAYLOAD_SIZE - 1
        end = min(end, PAYLOAD_SIZE - 1)

        length = end - start + 1
        chunk_data = bytes(TEST_DATA[start : end + 1])

        return web.Response(
            body=chunk_data,
            status=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{PAYLOAD_SIZE}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    # Full body
    return web.Response(
        body=bytes(TEST_DATA),
        headers={
            "Content-Length": str(PAYLOAD_SIZE),
            "Accept-Ranges": "bytes",
        },
    )


async def run_e2e_test():
    # Setup mock server
    app = web.Application()
    app.router.add_route("*", "/download", handle_download)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 49199)
    await site.start()

    download_url = "http://127.0.0.1:49199/download"
    dest_file = Path("sdm/downloads/turbo_downloaded.bin")
    if dest_file.exists():
        dest_file.unlink()

    task = DownloadTask(
        task_id="test_e2e",
        url=download_url,
        filename="turbo_downloaded.bin",
        save_path=str(dest_file),
    )

    engine = SegmentDownloadEngine(task=task, max_connections=8)

    print("\n[Test] Starting dynamic multi-segment download...")
    await engine.start()

    print(f"[Test] Finished. Status: {task.status.value}")
    assert task.status == TaskStatus.COMPLETED, f"Expected COMPLETED, got {task.status.value}"
    assert len(task.segments) >= 4, f"Expected >= 4 segments, got {len(task.segments)}"

    # Check file size & SHA-256
    assert dest_file.exists(), "Target file does not exist"
    assert dest_file.stat().st_size == PAYLOAD_SIZE, f"Size mismatch: {dest_file.stat().st_size} vs {PAYLOAD_SIZE}"

    actual_sha = SparseFileWriter.compute_sha256(str(dest_file))
    print(f"Expected SHA-256: {EXPECTED_SHA}")
    print(f"Actual SHA-256:   {actual_sha}")
    assert EXPECTED_SHA == actual_sha, "Bit-integrity SHA-256 mismatch!"

    print(f"✅ Dynamic Segment Engine E2E Test PASSED with {len(task.segments)} parallel chunks!")

    # Cleanup
    await runner.cleanup()
    if dest_file.exists():
        dest_file.unlink()


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
