"""Unit and integration test for Sequential Downloading and Live Stream Preview."""

import asyncio
import hashlib
from pathlib import Path
import sys
from aiohttp import web

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sdm.core.models import DownloadTask, TaskStatus
from sdm.core.segment_engine import SegmentDownloadEngine
from sdm.core.storage import SparseFileWriter

PAYLOAD_SIZE = 6 * 1024 * 1024  # 6 MB
TEST_DATA = bytearray((i * 19) % 256 for i in range(PAYLOAD_SIZE))
EXPECTED_SHA = hashlib.sha256(TEST_DATA).hexdigest()


async def handle_download(request: web.Request) -> web.Response:
    range_header = request.headers.get("Range")
    if request.method == "HEAD":
        return web.Response(
            status=200,
            headers={
                "Content-Length": str(PAYLOAD_SIZE),
                "Accept-Ranges": "bytes",
                "Content-Disposition": 'attachment; filename="sequential_sample.mp4"',
            },
        )

    if range_header and range_header.startswith("bytes="):
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else PAYLOAD_SIZE - 1
        end = min(end, PAYLOAD_SIZE - 1)
        length = end - start + 1
        return web.Response(
            body=bytes(TEST_DATA[start : end + 1]),
            status=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{PAYLOAD_SIZE}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    return web.Response(
        body=bytes(TEST_DATA),
        headers={"Content-Length": str(PAYLOAD_SIZE), "Accept-Ranges": "bytes"},
    )


async def run_sequential_test():
    app = web.Application()
    app.router.add_route("*", "/video.mp4", handle_download)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 49200)
    await site.start()

    dest_file = Path("sdm/downloads/sequential_test.mp4")
    if dest_file.exists():
        dest_file.unlink()

    task = DownloadTask(
        task_id="seq_test",
        url="http://127.0.0.1:49200/video.mp4",
        filename="sequential_test.mp4",
        save_path=str(dest_file),
        sequential=True,  # MAIN INGREDIENT ENABLED
    )

    engine = SegmentDownloadEngine(task=task, max_connections=4)

    print("[Sequential Test] Launching sequential stream engine...")
    await engine.start()

    assert task.status == TaskStatus.COMPLETED
    assert task.sequential is True
    
    # Segment 1 is Head (offset 0), Segment 2 is Tail (moov atom)
    assert task.segments[0].start_byte == 0
    assert task.segments[1].start_byte >= PAYLOAD_SIZE - (512 * 1024)
    # Remaining middle segments are strictly in ascending sequential order
    for idx in range(2, len(task.segments) - 1):
        s = task.segments[idx]
        next_s = task.segments[idx + 1]
        assert s.start_byte < next_s.start_byte, f"Middle segments out of order: {s.start_byte} >= {next_s.start_byte}"

    actual_sha = SparseFileWriter.compute_sha256(str(dest_file))
    print(f"Expected SHA-256: {EXPECTED_SHA}")
    print(f"Actual SHA-256:   {actual_sha}")
    assert EXPECTED_SHA == actual_sha, "Sequential download SHA mismatch!"
    print("✅ Sequential Downloading Engine & Order Verification PASSED!")

    await runner.cleanup()
    if dest_file.exists():
        dest_file.unlink()


if __name__ == "__main__":
    asyncio.run(run_sequential_test())
