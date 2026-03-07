import asyncio
import time


class AsyncRateLimiter:
    """
    A simple asynchronous rate limiter using a sliding window.
    Ensures that no more than `calls` are made in `period` seconds.
    """

    def __init__(self, calls: int, period: float):
        self.calls = calls
        self.period = period
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary to respect the rate limit."""
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps older than period
            self._timestamps = [t for t in self._timestamps if now - t < self.period]

            if len(self._timestamps) >= self.calls:
                # Need to wait until the oldest timestamp falls out of the window
                sleep_time = self.period - (now - self._timestamps[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < self.period]

            self._timestamps.append(now)
