"""Token-bucket rate limiter for the Android transport.

Stdlib only (time + threading + asyncio for async_acquire). Disabled by
default, so existing callers of AndroidTransport/AndroidClient see no
behavior change unless they opt in."""
from __future__ import annotations

import asyncio
import threading
import time


class _Bucket:
    """A single token bucket. Not thread-safe on its own; callers lock."""

    __slots__ = ("rate", "burst", "tokens", "last", "lock")

    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last
        if elapsed > 0:
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last = now

    def try_acquire(self) -> bool:
        with self.lock:
            self._refill_locked()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    def acquire(self) -> None:
        while True:
            with self.lock:
                self._refill_locked()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            time.sleep(wait)

    async def async_acquire(self) -> None:
        """Same as acquire() but yields to the event loop instead of blocking."""
        while True:
            with self.lock:
                self._refill_locked()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait)


class RateLimiter:
    """Token bucket rate limiter.

    rate: tokens (requests) added per second.
    burst: bucket capacity, i.e. the max requests that can fire back-to-back
        before waiting starts.

    With per_endpoint=True, each distinct `endpoint` key passed to acquire()/
    try_acquire() gets its own independent bucket (e.g. one per API path),
    instead of all requests sharing a single global bucket.

    Thread-safe: safe to share one RateLimiter across multiple threads.
    """

    def __init__(self, rate: float = 2.0, burst: int = 5, per_endpoint: bool = False):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        if burst < 1:
            raise ValueError("burst must be >= 1")
        self.rate = rate
        self.burst = burst
        self.per_endpoint = per_endpoint
        self._buckets_lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}
        self._default_bucket = _Bucket(rate, burst)

    def _bucket_for(self, endpoint: str | None) -> _Bucket:
        if not self.per_endpoint or endpoint is None:
            return self._default_bucket
        bucket = self._buckets.get(endpoint)
        if bucket is not None:
            return bucket
        with self._buckets_lock:
            bucket = self._buckets.get(endpoint)
            if bucket is None:
                bucket = _Bucket(self.rate, self.burst)
                self._buckets[endpoint] = bucket
            return bucket

    def acquire(self, endpoint: str | None = None) -> None:
        """Block (via time.sleep) until a token is available, then consume it."""
        self._bucket_for(endpoint).acquire()

    async def async_acquire(self, endpoint: str | None = None) -> None:
        """Async variant: yields to the event loop instead of blocking."""
        await self._bucket_for(endpoint).async_acquire()

    def try_acquire(self, endpoint: str | None = None) -> bool:
        """Non-blocking. Returns True and consumes a token if one is available."""
        return self._bucket_for(endpoint).try_acquire()
