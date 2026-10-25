"""Unit test for SparseFileWriter zero-merge direct-offset storage."""

import hashlib
import os
import random
import threading
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sdm.core.storage import SparseFileWriter


def test_concurrent_sparse_writing():
    test_file = Path("sdm/downloads/test_sparse.bin")
    if test_file.exists():
        test_file.unlink()

    total_size = 5 * 1024 * 1024  # 5 MB
    source_bytes = bytearray(total_size)
    for i in range(total_size):
        source_bytes[i] = (i * 37) % 256

    writer = SparseFileWriter(str(test_file), total_size)
    writer.open()

    num_threads = 8
    chunk_size = total_size // num_threads

    def worker(start: int, end: int):
        cur = start
        while cur <= end:
            step = min(65536, end - cur + 1)
            writer.write_at(cur, source_bytes[cur : cur + step])
            cur += step

    threads = []
    # Launch threads out of order to simulate random network arrival
    indices = list(range(num_threads))
    random.shuffle(indices)

    for i in indices:
        s = i * chunk_size
        e = (i + 1) * chunk_size - 1 if i < num_threads - 1 else total_size - 1
        t = threading.Thread(target=worker, args=(s, e))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    writer.close()

    # Verify size and hash
    assert test_file.stat().st_size == total_size
    expected_hash = hashlib.sha256(source_bytes).hexdigest()
    actual_hash = SparseFileWriter.compute_sha256(str(test_file))

    print(f"Expected SHA-256: {expected_hash}")
    print(f"Actual SHA-256:   {actual_hash}")
    assert expected_hash == actual_hash
    print("✅ SparseFileWriter concurrent write test PASSED!")
    test_file.unlink()


if __name__ == "__main__":
    test_concurrent_sparse_writing()
