"""A simple in-process token-bucket rate limiter.

Single-process, in-memory only — like the caches in app/cache.py, this
protects one dev/demo backend instance from being hammered (accidentally
via a buggy retry loop, or deliberately) into exhausting the Google API
quota this backend shares across every user. A multi-worker production
deployment would need a shared store (e.g. Redis) to enforce one limit
across all workers.

RateLimiter is pure logic with no ASGI/Starlette dependency, so it's simple
to unit test directly (see tests/test_rate_limit.py). RateLimitMiddleware
is the thin adapter that plugs it into FastAPI.
"""

from __future__ import annotations

import os
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

DEFAULT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
DEFAULT_BURST = int(os.getenv("RATE_LIMIT_BURST", "20"))

# Liveness checks shouldn't count against a client's budget — nothing they
# do costs a Google API call, and monitoring tools poll them frequently.
DEFAULT_EXEMPT_PATHS = frozenset({"/health"})

_MAX_TRACKED_KEYS = 10_000


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, tokens: float, last_refill: float):
        self.tokens = tokens
        self.last_refill = last_refill


class RateLimiter:
    """A per-key token-bucket limiter. Each key gets `burst` tokens up
    front and refills at `requests_per_minute` tokens/minute, capped at
    `burst`. allow() consumes one token if available."""

    def __init__(self, requests_per_minute: int, burst: int, max_tracked_keys: int = _MAX_TRACKED_KEYS):
        if requests_per_minute <= 0 or burst <= 0:
            raise ValueError("requests_per_minute and burst must be positive.")
        self._refill_per_second = requests_per_minute / 60.0
        self._capacity = float(burst)
        self._max_tracked_keys = max_tracked_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds). retry_after_seconds is 0
        when allowed is True."""
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._max_tracked_keys:
                    self._buckets.pop(next(iter(self._buckets)))
                self._buckets[key] = _Bucket(tokens=self._capacity - 1, last_refill=now)
                return True, 0.0

            elapsed = max(0.0, now - bucket.last_refill)
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
            bucket.last_refill = now

            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, 0.0

            retry_after = (1 - bucket.tokens) / self._refill_per_second
            return False, retry_after

    def reset(self) -> None:
        """Clears all tracked buckets. Mainly for tests: the limiter used by
        the real app is a long-lived singleton, so a test suite that fires
        many requests at it across different test files needs a way to
        start each test with a full budget rather than accumulating state
        left over from unrelated tests."""
        with self._lock:
            self._buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RateLimiter | None = None,
        exempt_paths: frozenset[str] = DEFAULT_EXEMPT_PATHS,
    ):
        super().__init__(app)
        self._limiter = limiter or RateLimiter(DEFAULT_REQUESTS_PER_MINUTE, DEFAULT_BURST)
        self._exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        key = request.client.host if request.client else "unknown"
        allowed, retry_after = self._limiter.allow(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
                headers={"Retry-After": str(max(1, int(retry_after) + 1))},
            )
        return await call_next(request)
