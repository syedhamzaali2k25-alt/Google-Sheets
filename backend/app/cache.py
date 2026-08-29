"""Small in-process caches that avoid re-hitting Google APIs for data that
hasn't actually changed.

Single-process, in-memory only — this is enough for a single dev/demo
backend instance. A multi-worker production deployment would need a shared
store (e.g. Redis) so all workers see the same cache; call sites here
wouldn't need to change, only where RevisionCache stores its entries.

Security note: every cache key used against these caches MUST incorporate
a fingerprint of the caller's own access token (see token_fingerprint),
never just the spreadsheet id alone. Without that, one user's cached data
would be readable by any other caller who happens to name the same
spreadsheet id, bypassing Google's own per-user authorization check
entirely. token_fingerprint() is one-way (SHA-256), so a cache key never
holds a usable copy of the token itself.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Generic, TypeVar

T = TypeVar("T")

_MAX_ENTRIES = 1000


def token_fingerprint(access_token: str) -> str:
    """A short, one-way fingerprint of an access token, safe to use as part
    of a cache key without retaining the token itself any longer than the
    request already needs it for."""
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()[:16]


class _Entry(Generic[T]):
    __slots__ = ("value", "revision", "expires_at")

    def __init__(self, value: T, revision: str | None, expires_at: float):
        self.value = value
        self.revision = revision
        self.expires_at = expires_at


class RevisionCache(Generic[T]):
    """Caches one value per key. A cached value is only served if it hasn't
    expired *and* — when a revision is supplied on both sides — the stored
    revision still matches (e.g. a Google Drive file's modifiedTime), so a
    real edit invalidates the cache immediately instead of waiting out the
    TTL. Passing revision=None on get()/set() skips revision checking and
    falls back to pure TTL expiry.
    """

    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._store: dict[str, _Entry[T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, revision: str | None = None) -> T | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                del self._store[key]
                return None
            if revision is not None and entry.revision != revision:
                return None
            return entry.value

    def set(self, key: str, value: T, revision: str | None = None) -> None:
        with self._lock:
            if key not in self._store and len(self._store) >= _MAX_ENTRIES:
                self._store.pop(next(iter(self._store)))
            self._store[key] = _Entry(value, revision, time.monotonic() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
