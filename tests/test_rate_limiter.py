"""Unit test for TokenBucketRateLimiter."""

import asyncio
import time
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sdm.core.rate_limiter import TokenBucketRateLimiter


async def run_rate_limiter_test():
    target_rate = 200 * 1024  # 200 KB/s
    limiter = TokenBucketRateLimiter(target_rate)

    total_bytes = 400 * 1024  # 400 KB
    chunk = 64 * 1024  # 64 KB per chunk

    start = time.monotonic()
    sent = 0
    while sent < total_bytes:
        step = min(chunk, total_bytes - sent)
        await limiter.acquire(step)
        sent += step
    elapsed = time.monotonic() - start

    actual_rate = sent / elapsed
    print(f"Target Rate: {target_rate / 1024:.1f} KB/s")
    print(f"Actual Rate: {actual_rate / 1024:.1f} KB/s across {elapsed:.2f}s")

    # Should be close to target (allowing burst head)
    assert elapsed >= 1.0, f"Limiter ran too fast: {elapsed}s"
    print("✅ TokenBucketRateLimiter test PASSED!")


if __name__ == "__main__":
    asyncio.run(run_rate_limiter_test())
