"""Sliding-window rate limiting.

Counters live in Redis when REDIS_URL is set, so limits hold across API processes; otherwise (and if
Redis is briefly unreachable) they fall back to in-process memory.
"""
import math
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from .config import get_settings


class RateLimiter:
    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._redis = None
        self._redis_url: str | None = None

    def _client(self):
        url = get_settings().redis_url
        if not url:
            return None
        if self._redis is None or self._redis_url != url:
            import redis
            self._redis = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
            self._redis_url = url
        return self._redis

    def check(self, key: str, limit: int) -> None:
        """Record a hit for `key`; raise 429 if it exceeds `limit` hits per window."""
        client = self._client()
        if client is not None:
            try:
                retry_after = self._check_redis(client, key, limit)
            except Exception:  # Redis unreachable: degrade to per-process limits
                retry_after = self._check_memory(key, limit)
        else:
            retry_after = self._check_memory(key, limit)
        if retry_after is not None:
            raise HTTPException(429, "Too many requests. Please slow down.", headers={"Retry-After": str(retry_after)})

    def _check_memory(self, key: str, limit: int) -> int | None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, math.ceil(self.window - (now - hits[0])))
        hits.append(now)
        return None

    def _check_redis(self, client, key: str, limit: int) -> int | None:
        now = time.time()
        redis_key = f"indusmind:ratelimit:{key}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - self.window)
        pipe.zcard(redis_key)
        pipe.zrange(redis_key, 0, 0, withscores=True)
        _, count, oldest = pipe.execute()
        if count >= limit:
            first = oldest[0][1] if oldest else now
            return max(1, math.ceil(self.window - (now - first)))
        client.zadd(redis_key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        client.expire(redis_key, int(self.window) + 1)
        return None

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter()
