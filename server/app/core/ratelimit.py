"""Sliding-window rate limiting.

In-process memory is enough for the single API process used today; Phase 2 moves the
counters to Redis together with the background worker.
"""
import math
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class RateLimiter:
    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int) -> None:
        """Record a hit for `key`; raise 429 if it exceeds `limit` hits per window."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, math.ceil(self.window - (now - hits[0])))
            raise HTTPException(429, "Too many requests. Please slow down.", headers={"Retry-After": str(retry_after)})
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()
