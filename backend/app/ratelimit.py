"""Per-client rate limiting, weighted by images processed.

The public prototype is unauthenticated and every image triggers a paid vision call, so the
unit that matters is *images*, not requests — a 300-image batch spends 300 units. Sliding
window, in-memory (single-container deployment, so no shared store needed).

Defaults allow a real agent workflow (a 300-label batch plus singles inside 10 minutes)
while capping what an abuser can burn. Tune via RATE_LIMIT_IMAGES / RATE_LIMIT_WINDOW_S;
set RATE_LIMIT_IMAGES=0 to disable.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float, time_fn=time.monotonic) -> None:
        self.limit = limit
        self.window_s = window_s
        self._time = time_fn
        self._events: dict[str, deque[tuple[float, int]]] = {}
        self._lock = threading.Lock()

    def try_acquire(self, key: str, weight: int = 1) -> float | None:
        """Spend `weight` units for `key`. Returns None if allowed, else seconds to wait."""
        if self.limit <= 0:  # disabled
            return None
        now = self._time()
        with self._lock:
            q = self._events.setdefault(key, deque())
            while q and q[0][0] <= now - self.window_s:
                q.popleft()
            used = sum(w for _, w in q)
            if used + weight > self.limit:
                retry = (q[0][0] + self.window_s - now) if q else self.window_s
                return max(retry, 1.0)
            q.append((now, weight))
            return None


_limiter = SlidingWindowLimiter(settings.RATE_LIMIT_IMAGES, settings.RATE_LIMIT_WINDOW_S)


def client_key(request: Request) -> str:
    """Client identity: first X-Forwarded-For hop (set by the Lightsail LB) or peer IP."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, images: int) -> None:
    """Raise 429 when the client's image budget for the window is exhausted."""
    if settings.RATE_LIMIT_IMAGES > 0 and images > settings.RATE_LIMIT_IMAGES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"This batch ({images} images) exceeds the per-client limit of "
                f"{settings.RATE_LIMIT_IMAGES} images per "
                f"{int(settings.RATE_LIMIT_WINDOW_S // 60)} minutes. Split it up."
            ),
        )
    retry_after = _limiter.try_acquire(client_key(request), images)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=(
                "Rate limit reached — please wait about "
                f"{int(retry_after // 60) + 1} minute(s) and try again."
            ),
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
