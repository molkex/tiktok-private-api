"""Multi-account fleet manager for the Android mobile SDK.

Pools multiple AndroidClient instances (one Device/session each) behind a
single object: round-robin / random selection, cooldown after rate limits,
auto-ban after repeated errors, and bulk save/load of device state. Mirrors
the AccountFleet pattern used by the official API client (see
tiktokflow/client.py's TikTokClient account management) but for the
Android mobile SDK, where each "account" is a signed-in Device rather than
an OAuth token.

Usage:
    fleet = AccountFleet()
    fleet.add_from_file("acc1.json")
    fleet.add_from_file("acc2.json")
    with fleet:
        client = fleet.next()
        try:
            feed = client.feed.for_you()
            fleet.mark_success(client.device.device_id)
        except Exception as e:
            fleet.mark_error(client.device.device_id)
            raise

Or, for a single "just give me a working session" call surface:

    transport = FleetTransport(fleet)
    body = transport.get("/aweme/v1/feed/")
"""
from __future__ import annotations

import random as _random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..errors import AuthError, RateLimitError, TikTokError
from .client import AndroidClient
from .device import Device


@dataclass
class AccountHealth:
    """Per-account health / rate-limit bookkeeping."""

    last_request_time: float = 0.0
    total_requests: int = 0
    total_successes: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    rate_limit_hits: int = 0
    cooldown_until: float = 0.0
    banned: bool = False

    def is_cooling_down(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.cooldown_until

    def is_healthy(self, now: float | None = None) -> bool:
        return not self.banned and not self.is_cooling_down(now)


class AccountFleet:
    """Pool of AndroidClient accounts with rotation and health tracking.

    Thread-safe: all pool mutation and health bookkeeping happens under a
    single lock, so `next()` / `mark_error()` / `mark_success()` can be
    called concurrently from multiple worker threads.
    """

    def __init__(self, *, cooldown: float = 60.0, ban_threshold: int = 5):
        self.cooldown = cooldown
        self.ban_threshold = ban_threshold
        self._clients: dict[str, AndroidClient] = {}
        self._health: dict[str, AccountHealth] = {}
        self._order: list[str] = []  # insertion order, used for round-robin
        self._rr_index = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    def add(self, device: Device, **client_kwargs: Any) -> AndroidClient:
        """Add an account (Device) to the fleet, wrapping it in an AndroidClient.

        Re-adding a device_id already in the fleet replaces its client but
        keeps the existing health stats.
        """
        device_id = device.device_id
        client = AndroidClient(device, **client_kwargs)
        with self._lock:
            old = self._clients.get(device_id)
            if device_id not in self._order:
                self._order.append(device_id)
                self._health[device_id] = AccountHealth()
            self._clients[device_id] = client
        if old is not None:
            old.close()
        return client

    def add_from_file(self, path: str | Path, **client_kwargs: Any) -> AndroidClient:
        """Load a Device from a JSON file and add it to the fleet."""
        device = Device.load(str(path))
        return self.add(device, **client_kwargs)

    def remove(self, device_id: str) -> None:
        """Remove an account from the fleet and close its client."""
        with self._lock:
            client = self._clients.pop(device_id, None)
            self._health.pop(device_id, None)
            if device_id in self._order:
                self._order.remove(device_id)
        if client is not None:
            client.close()

    def get(self, device_id: str) -> AndroidClient:
        """Fetch a specific account's client by device_id."""
        with self._lock:
            client = self._clients.get(device_id)
        if client is None:
            raise KeyError(f"no account with device_id={device_id!r} in fleet")
        return client

    def all(self) -> list[AndroidClient]:
        """All clients in the fleet, in insertion order."""
        with self._lock:
            return [self._clients[d] for d in self._order]

    def __len__(self) -> int:
        return len(self._clients)

    def __contains__(self, device_id: str) -> bool:
        return device_id in self._clients

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def healthy(self) -> list[AndroidClient]:
        """Accounts that are neither banned nor currently in cooldown."""
        now = time.time()
        with self._lock:
            return [
                self._clients[d] for d in self._order
                if self._health[d].is_healthy(now)
            ]

    def next(self) -> AndroidClient:
        """Round-robin through accounts, auto-skipping cooldown/banned ones."""
        now = time.time()
        with self._lock:
            n = len(self._order)
            if n == 0:
                raise RuntimeError("fleet is empty")
            for _ in range(n):
                device_id = self._order[self._rr_index % n]
                self._rr_index += 1
                if self._health[device_id].is_healthy(now):
                    return self._clients[device_id]
            raise RuntimeError(
                "no healthy accounts in fleet (all cooling down or banned)"
            )

    def random(self) -> AndroidClient:
        """Pick a uniformly random healthy account."""
        pool = self.healthy()
        if not pool:
            raise RuntimeError(
                "no healthy accounts in fleet (all cooling down or banned)"
            )
        return _random.choice(pool)

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    def mark_success(self, device_id: str) -> None:
        """Record a successful request for this account, resetting its
        consecutive-error streak."""
        with self._lock:
            h = self._health.get(device_id)
            if h is None:
                return
            h.last_request_time = time.time()
            h.total_requests += 1
            h.total_successes += 1
            h.consecutive_errors = 0

    def mark_error(
        self,
        device_id: str,
        *,
        rate_limited: bool = False,
        retry_after: float | None = None,
    ) -> None:
        """Record a failed request. Rate-limited errors put the account in
        cooldown; enough consecutive errors mark it banned."""
        with self._lock:
            h = self._health.get(device_id)
            if h is None:
                return
            now = time.time()
            h.last_request_time = now
            h.total_requests += 1
            h.error_count += 1
            h.consecutive_errors += 1
            if rate_limited:
                h.rate_limit_hits += 1
                h.cooldown_until = max(
                    h.cooldown_until,
                    now + (retry_after if retry_after is not None else self.cooldown),
                )
            if h.consecutive_errors >= self.ban_threshold:
                h.banned = True

    def mark_exception(self, device_id: str, exc: Exception) -> None:
        """Convenience wrapper: classify exc and call mark_error() with the
        right flags. RateLimitError -> cooldown, everything else -> plain
        error (contributes toward ban_threshold)."""
        if isinstance(exc, RateLimitError):
            self.mark_error(device_id, rate_limited=True, retry_after=exc.retry_after)
        else:
            self.mark_error(device_id)

    def unban(self, device_id: str) -> None:
        """Manually clear banned/cooldown state, e.g. after re-authenticating."""
        with self._lock:
            h = self._health.get(device_id)
            if h is not None:
                h.banned = False
                h.consecutive_errors = 0
                h.cooldown_until = 0.0

    def health_of(self, device_id: str) -> AccountHealth:
        with self._lock:
            h = self._health.get(device_id)
        if h is None:
            raise KeyError(f"no account with device_id={device_id!r} in fleet")
        return h

    def status(self) -> dict[str, dict[str, Any]]:
        """Snapshot of every account's health, keyed by device_id — handy
        for logging/monitoring/dashboards."""
        now = time.time()
        with self._lock:
            return {
                d: {
                    "banned": h.banned,
                    "cooling_down": h.is_cooling_down(now),
                    "cooldown_remaining": max(0.0, h.cooldown_until - now),
                    "error_count": h.error_count,
                    "consecutive_errors": h.consecutive_errors,
                    "rate_limit_hits": h.rate_limit_hits,
                    "total_requests": h.total_requests,
                    "total_successes": h.total_successes,
                    "last_request_time": h.last_request_time,
                }
                for d, h in self._health.items()
            }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_all(self, directory: str | Path) -> None:
        """Save every account's Device state to <directory>/<device_id>.json."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for client in self.all():
            client.device.save(str(directory / f"{client.device.device_id}.json"))

    def load_all(self, directory: str | Path, **client_kwargs: Any) -> list[AndroidClient]:
        """Load every *.json device file from a directory and add each to the fleet."""
        directory = Path(directory)
        added = []
        for path in sorted(directory.glob("*.json")):
            added.append(self.add_from_file(path, **client_kwargs))
        return added

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close every client's transport (HTTP connections)."""
        with self._lock:
            clients = list(self._clients.values())
        for client in clients:
            client.close()

    def __enter__(self) -> "AccountFleet":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class FleetTransport:
    """Single transport-like façade over an AccountFleet.

    Lets calling code that only knows how to speak "transport.get/post"
    (e.g. the *API classes in this package) run against a rotating pool of
    accounts without knowing about the fleet at all. Each request picks a
    healthy account, tracks success/failure against it, and — for auth or
    rate-limit errors specifically — automatically retries on a different
    account before giving up.
    """

    def __init__(
        self,
        fleet: AccountFleet,
        *,
        max_account_retries: int = 3,
        selector: Callable[[], AndroidClient] | None = None,
    ):
        self.fleet = fleet
        self.max_account_retries = max_account_retries
        self._selector = selector or fleet.next

    def request(self, method: str, path: str, **kw: Any) -> Any:
        last_exc: Exception | None = None
        attempts = max(self.max_account_retries, 1)
        for _ in range(attempts):
            client = self._selector()  # raises RuntimeError if none healthy
            device_id = client.device.device_id
            try:
                result = client.transport.request(method, path, **kw)
            except TikTokError as e:
                self.fleet.mark_exception(device_id, e)
                last_exc = e
                if isinstance(e, (AuthError, RateLimitError)):
                    continue  # try a different account
                raise
            else:
                self.fleet.mark_success(device_id)
                return result
        raise last_exc or RuntimeError("FleetTransport: no accounts available")

    def get(self, path: str, **kw: Any) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.request("POST", path, **kw)

    def close(self) -> None:
        self.fleet.close()

    def __enter__(self) -> "FleetTransport":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
