"""Tiny in-memory sliding-window rate limiter (per process, per client IP).

Good enough for a single instance / local dev. For multiple workers or instances,
swap the storage for Redis (INCR + EXPIRE) behind the same `RateLimiter` interface.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimitError

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, scope: str) -> None:
        self.limit = limit
        self.window = window_seconds
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        key = (self.scope, ip)
        now = time.monotonic()
        hits = _hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = max(1, int(self.window - (now - hits[0])))
            raise RateLimitError(
                "Too many requests, please try again later",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
