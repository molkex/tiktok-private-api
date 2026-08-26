"""Async Android mobile API transport: httpx.AsyncClient + auto-signing.

Drop-in async replacement for AndroidTransport. Same signing, retry,
envelope parsing, proxy rotation, and rate limiting — but all I/O is
non-blocking and sleeps use ``asyncio.sleep``."""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from ..errors import (AuthError, InvalidRequest, RateLimitError, ServerError,
                      TikTokError)
from .device import API_BASE, Device
from .ratelimit import RateLimiter
from .signing import sign_request, sign_request_full
from .transport import _map_http, _parse_aweme_envelope, _parse_retry_after

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class AsyncAndroidTransport:
    """Async variant of :class:`AndroidTransport`.

    Uses ``httpx.AsyncClient`` instead of ``httpx.Client``. API surface
    mirrors the sync version so async endpoint classes can call
    ``await self._t.get(...)`` / ``await self._t.post(...)`` with the
    same arguments.
    """

    def __init__(
        self,
        device: Device,
        *,
        base_url: str = API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        client: httpx.AsyncClient | None = None,
        full_sign: bool = True,
        rate_limiter: RateLimiter | None = None,
        rate_limit: float | None = None,
        proxy: str | None = None,
        proxies: list[str] | None = None,
        proxy_rotate: str = "round_robin",
    ):
        self.device = device
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.full_sign = full_sign
        self._timeout = timeout
        self._proxy_rotate = proxy_rotate
        self._proxy_index = 0

        # Build proxy list: explicit list takes priority over single proxy.
        if proxies:
            self._proxy_list: list[str] = list(proxies)
        elif proxy:
            self._proxy_list = [proxy]
        else:
            self._proxy_list = []

        # Client pool keyed by proxy URL (None = direct connection).
        self._clients: dict[str | None, httpx.AsyncClient] = {}
        if client is not None:
            self._clients[None] = client
        else:
            kw: dict[str, Any] = {"timeout": timeout, "headers": device.headers()}
            if len(self._proxy_list) == 1:
                kw["proxy"] = self._proxy_list[0]
                self._clients[self._proxy_list[0]] = httpx.AsyncClient(**kw)
            else:
                self._clients[None] = httpx.AsyncClient(**kw)

        # Rate limiter.
        if rate_limiter is not None:
            self.rate_limiter = rate_limiter
        elif rate_limit is not None:
            self.rate_limiter = RateLimiter(rate=rate_limit)
        else:
            self.rate_limiter = None

    # ------------------------------------------------------------------
    # Proxy management
    # ------------------------------------------------------------------

    def set_proxy(self, proxy: str | None) -> None:
        """Set a single proxy (or *None* to go direct)."""
        self._proxy_list = [proxy] if proxy else []
        self._proxy_index = 0

    def set_proxies(self, proxies: list[str]) -> None:
        """Replace the proxy rotation list at runtime."""
        self._proxy_list = list(proxies)
        self._proxy_index = 0

    def _next_proxy(self) -> str | None:
        if not self._proxy_list:
            return None
        if self._proxy_rotate == "random":
            return random.choice(self._proxy_list)
        idx = self._proxy_index % len(self._proxy_list)
        self._proxy_index += 1
        return self._proxy_list[idx]

    def _get_client(self, proxy: str | None) -> httpx.AsyncClient:
        try:
            return self._clients[proxy]
        except KeyError:
            kw: dict[str, Any] = {
                "timeout": self._timeout,
                "headers": self.device.headers(),
            }
            if proxy is not None:
                kw["proxy"] = proxy
            client = httpx.AsyncClient(**kw)
            self._clients[proxy] = client
            return client

    @property
    def _client(self) -> httpx.AsyncClient:
        """Return the first available client (for tests / compat)."""
        if None in self._clients:
            return self._clients[None]
        return next(iter(self._clients.values()))

    async def close(self) -> None:
        for c in self._clients.values():
            await c.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        raw: bool = False,
        full_sign: bool | None = None,
        proto_mode: str = "feed",
    ) -> Any:
        if self.rate_limiter is not None:
            await self.rate_limiter.async_acquire(
                path if self.rate_limiter.per_endpoint else None
            )

        url = path if path.startswith("http") else f"{self.base_url}{path}"

        merged_params = dict(self.device.common_params())
        if params:
            merged_params.update({k: str(v) for k, v in params.items()})
        query_string = urlencode(merged_params)
        full_url = f"{url}?{query_string}"

        body_bytes: bytes | None = None
        if content is not None:
            body_bytes = content
        elif data is not None:
            if isinstance(data, str):
                body_bytes = data.encode()
            elif isinstance(data, bytes):
                body_bytes = data
            else:
                body_bytes = urlencode(data).encode()

        ts = round(time.time())
        use_full_sign = self.full_sign if full_sign is None else full_sign
        if use_full_sign:
            sign_headers = sign_request_full(
                self.device,
                query_string=query_string,
                body=body_bytes,
                ts=ts,
            )
        else:
            sign_headers = sign_request(
                query_string=query_string,
                body=body_bytes,
                cookie_string=self.device.cookie_string(),
                ts=ts,
            )

        hdrs: dict[str, str] = dict(self.device.headers())
        hdrs.update(sign_headers)
        if headers:
            hdrs.update(headers)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            proxy_tries = max(len(self._proxy_list), 1)
            resp: httpx.Response | None = None
            for _ in range(proxy_tries):
                proxy = self._next_proxy()
                client = self._get_client(proxy)
                try:
                    resp = await client.request(
                        method, full_url,
                        json=json if body_bytes is None and json is not None else None,
                        content=body_bytes,
                        headers=hdrs,
                    )
                    break
                except httpx.TransportError as e:
                    last_exc = ServerError(f"transport error: {e}")
                    continue

            if resp is None:
                await self._sleep(attempt, None)
                continue

            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < self.max_retries:
                    await self._sleep(attempt, retry_after)
                    continue
                raise RateLimitError("rate limited", retry_after=retry_after, http_status=429)

            if 500 <= resp.status_code < 600:
                if attempt < self.max_retries:
                    await self._sleep(attempt, None)
                    continue
                raise ServerError(f"server error {resp.status_code}", http_status=resp.status_code)

            if raw:
                if resp.status_code >= 400:
                    raise _map_http(resp.status_code, resp.text)
                return resp

            return _parse_aweme_envelope(resp, proto_mode=proto_mode)

        raise last_exc or TikTokError("request failed after retries")

    async def get(self, path: str, *, full_sign: bool | None = None, **kw) -> Any:
        return await self.request("GET", path, full_sign=full_sign, **kw)

    async def post(self, path: str, *, full_sign: bool | None = True, **kw) -> Any:
        return await self.request("POST", path, full_sign=full_sign, **kw)

    async def _sleep(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            await asyncio.sleep(retry_after)
            return
        await asyncio.sleep(min(8.0, 0.5 * (2 ** attempt)) + random.random() * 0.25)
