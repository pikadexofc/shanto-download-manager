"""Token Bucket Bandwidth Limiter and Traffic Shaper.
Reverse-Engineered from FDM's Traffic Management and IDM's Speed Limiter.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Asynchronous Token Bucket rate limiter.

    Provides smooth byte-rate shaping across concurrent segment workers.
    """

    def __init__(self, rate_bytes_per_sec: float = 0.0):
        """rate_bytes_per_sec: 0 or negative means unlimited."""
        self.rate = max(0.0, rate_bytes_per_sec)
        self.capacity = max(65536.0, self.rate)  # Burst allowance up to 1s rate or 64KB
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def set_rate(self, rate_bytes_per_sec: float) -> None:
        self.rate = max(0.0, rate_bytes_per_sec)
        self.capacity = max(65536.0, self.rate)
        self.tokens = min(self.tokens, self.capacity)

    async def acquire(self, num_bytes: int) -> None:
        """Wait until enough tokens are available to consume num_bytes."""
        if self.rate <= 0.0:
            return  # Unlimited bandwidth

        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now

                # Replenish tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= num_bytes:
                    self.tokens -= num_bytes
                    return

                # Calculate required sleep duration
                needed = num_bytes - self.tokens
                wait_time = needed / self.rate

            # Sleep outside the lock so other tasks aren't blocked
            await asyncio.sleep(min(wait_time, 0.5))
