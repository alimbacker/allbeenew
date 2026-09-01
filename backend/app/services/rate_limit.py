"""In-memory sliding-window rate limiting.

Scoped to a single process, which is the right trade for the MVP. The interface
is deliberately narrow so a Redis-backed implementation can replace it without
touching the routes.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds_until_retry)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, max(1, int(bucket[0] + self.window - now) + 1)
            bucket.append(now)
            # Opportunistic cleanup so idle keys do not accumulate forever.
            if len(self._hits) > 10_000:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request, prefix: str = "") -> str:
    """Identify the caller.

    Honours X-Forwarded-For because the documented deployment puts Nginx in
    front of the API; without it every guest would share one bucket.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{prefix}:{ip}"


def enforce(limiter: SlidingWindowLimiter, request: Request, prefix: str) -> None:
    allowed, retry_after = limiter.check(client_key(request, prefix))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Wait a moment and try again.",
            headers={"Retry-After": str(retry_after)},
        )


from app.config import settings  # noqa: E402

search_limiter = SlidingWindowLimiter(
    settings.search_rate_limit, settings.search_rate_window_seconds
)
upload_limiter = SlidingWindowLimiter(
    settings.upload_rate_limit, settings.upload_rate_window_seconds
)
