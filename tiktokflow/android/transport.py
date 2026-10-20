"""Android mobile API transport (public, hosted-signing).

Every request is signed by the hosted signing service through
:class:`RemoteSigner` — the mobile signing algorithm is kept server-side
and never leaves it. This public transport is a thin HTTP wrapper that:

  1. merges device params into the query string,
  2. asks the signing server for the request headers,
  3. sends the request through httpx (reads) or curl_cffi (writes), and
  4. parses TikTok's JSON/protobuf envelopes.

A :class:`RemoteSigner` is required — pass it via the ``signer=`` kwarg
(the :func:`tiktokflow.TikTokAPI` factory wires one up for you).
"""
from __future__ import annotations

import json as _json
import random
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from ..errors import (AuthError, InvalidRequest, RateLimitError, ServerError,
                      TikTokError)
from .device import API_BASE, YCRU_BASE, Device
from .ratelimit import RateLimiter

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
WRITE_MAX_RETRIES = 10

# Response-header keys that must never surface in the dict returned to callers
# or in exception messages. Cookies are still captured for the session via
# _harvest_cookies (which reads the raw response headers directly), so dropping
# them here does not affect login/session state.
_SENSITIVE_RESPONSE_HEADERS = frozenset({
    "set-cookie",
    "cookie",
    "authorization",
    "proxy-authorization",
    "x-tt-token",
    "x-ms-token",
    "x-tt-passport-csrf-token",
    "x-tt-passport-session-id",
})


def _scrub_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of ``headers`` with session/cookie values stripped."""
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_RESPONSE_HEADERS:
            continue
        out[k] = v
    return out


class AndroidTransport:
    def __init__(
        self,
        device: Device,
        *,
        base_url: str = API_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        client: httpx.Client | None = None,
        full_sign: bool = True,
        rate_limiter: RateLimiter | None = None,
        rate_limit: float | None = None,
        proxy: str | None = None,
        proxies: list[str] | None = None,
        proxy_rotate: str = "round_robin",
        write_retries: int = WRITE_MAX_RETRIES,
        signer: Any | None = None,
        **_ignored: Any,
    ):
        if signer is None:
            raise ValueError(
                "AndroidTransport requires a signer (RemoteSigner). "
                "Use tiktokflow.TikTokAPI(api_key=..., signing_server=...) "
                "to construct a client with a wired-up signer."
            )
        self.device = device
        self._remote_signer = signer
        if base_url == API_BASE and device.is_authenticated:
            base_url = YCRU_BASE
        self.base_url = base_url.rstrip("/")
        self._impersonate = "chrome_android"
        self.max_retries = max_retries
        self.write_retries = write_retries
        self.full_sign = full_sign
        self._timeout = timeout
        self._proxy_rotate = proxy_rotate
        self._proxy_lock = threading.Lock()
        self._proxy_index = 0

        if proxies:
            self._proxy_list: list[str] = list(proxies)
        elif proxy:
            self._proxy_list = [proxy]
        else:
            self._proxy_list = []

        self._clients: dict[str | None, httpx.Client] = {}
        if client is not None:
            self._clients[None] = client
        else:
            base_hdrs = {"User-Agent": device.user_agent, "Accept-Encoding": "gzip, deflate"}
            kw: dict[str, Any] = {"timeout": timeout, "headers": base_hdrs}
            if len(self._proxy_list) == 1:
                kw["proxy"] = self._proxy_list[0]
                self._clients[self._proxy_list[0]] = httpx.Client(**kw)
            else:
                self._clients[None] = httpx.Client(**kw)

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
        with self._proxy_lock:
            self._proxy_list = [proxy] if proxy else []
            self._proxy_index = 0

    def set_proxies(self, proxies: list[str]) -> None:
        with self._proxy_lock:
            self._proxy_list = list(proxies)
            self._proxy_index = 0

    def _next_proxy(self) -> str | None:
        if not self._proxy_list:
            return None
        with self._proxy_lock:
            if self._proxy_rotate == "random":
                return random.choice(self._proxy_list)
            idx = self._proxy_index % len(self._proxy_list)
            self._proxy_index += 1
            return self._proxy_list[idx]

    def _get_client(self, proxy: str | None) -> httpx.Client:
        try:
            return self._clients[proxy]
        except KeyError:
            base_hdrs = {"User-Agent": self.device.user_agent, "Accept-Encoding": "gzip, deflate"}
            kw: dict[str, Any] = {"timeout": self._timeout, "headers": base_hdrs}
            if proxy is not None:
                kw["proxy"] = proxy
            client = httpx.Client(**kw)
            self._clients[proxy] = client
            return client

    @property
    def _client(self) -> httpx.Client:
        if None in self._clients:
            return self._clients[None]
        return next(iter(self._clients.values()))

    def close(self) -> None:
        for c in self._clients.values():
            c.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------
    # Signing via the hosted service
    # ------------------------------------------------------------------

    def _sign_and_guard(
        self,
        *,
        query_string: str,
        body: bytes | None,
        path: str,
        method: str = "GET",
        use_full_sign: bool = True,
        skip_app_id: bool = False,
    ) -> tuple[dict[str, str], int]:
        """Ask the signing server for the full set of request headers."""
        api_path = path.split("?")[0] if "?" in path else path
        hdrs, ts = self._remote_signer.sign(
            query_string=query_string,
            body=body,
            cookie_string=self.device.cookie_string(),
            path=api_path,
            method=method,
            full_sign=use_full_sign,
            skip_app_id=skip_app_id,
            device_id=self.device.device_id,
            install_id=self.device.install_id,
            device_type=self.device.device_type,
            device_brand=self.device.device_brand,
            channel=self.device.channel,
            app_version=self.device.app_version,
            version_code=self.device.version_code,
            manifest_version_code=self.device.manifest_version_code,
            device_token=self.device.device_token,
            dtoken_sign=self.device.dtoken_sign,
            token=self.device.token,
            ts_sign=self.device.ts_sign,
        )
        return hdrs, ts

    # ------------------------------------------------------------------
    # Cookie harvesting
    # ------------------------------------------------------------------

    def _harvest_cookies(self, resp_headers: Mapping[str, str]) -> None:
        cookies: dict[str, str] = {}
        for k, v in resp_headers.items():
            if k.lower() == "set-cookie":
                for part in v.split("\n"):
                    name_val = part.split(";")[0].strip()
                    if "=" in name_val:
                        cname, cval = name_val.split("=", 1)
                        cookies[cname.strip()] = cval.strip()
        if cookies:
            self.device.update_session(cookies=cookies)

    # ------------------------------------------------------------------
    # curl_cffi read request (TLS fingerprint match)
    # ------------------------------------------------------------------

    def _cffi_read(self, method: str, url: str, hdrs: dict, body: bytes | None, json_data: Any = None):
        from curl_cffi.requests import Session as CffiSession

        proxy = self._next_proxy()
        sess = CffiSession(impersonate=self._impersonate)
        try:
            if proxy:
                sess.proxies = {"http": proxy, "https": proxy}
            content = body
            if content is None and json_data is not None:
                content = _json.dumps(json_data).encode()
                hdrs = {**hdrs, "Content-Type": "application/json"}
            resp = sess.request(method, url, headers=hdrs, content=content, timeout=self._timeout)
            self._harvest_cookies(resp.headers)
            return resp
        finally:
            sess.close()

    # ------------------------------------------------------------------
    # Write path via curl_cffi (TLS impersonation)
    # ------------------------------------------------------------------

    def _write_request_cffi(
        self,
        method: str,
        path: str,
        *,
        query_params: dict[str, str],
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        skip_app_id: bool = False,
        max_retries: int | None = None,
        proto_mode: str = "feed",
        raw: bool = False,
    ) -> Any:
        from curl_cffi.requests import Session as CffiSession

        retries = max_retries if max_retries is not None else self.write_retries
        is_abs = path.startswith("http://") or path.startswith("https://")
        if is_abs:
            api_path = path.split("?", 1)[0].split("//", 1)[-1]
            api_path = "/" + api_path.split("/", 1)[1] if "/" in api_path else "/"
        else:
            api_path = path.split("?")[0] if "?" in path else path

        last_resp = None
        for attempt in range(retries):
            merged = dict(self.device.common_params())
            if skip_app_id:
                merged.pop("aid", None)
                merged.pop("app_name", None)
            merged.update(query_params)
            qs = urlencode(merged)
            full_url = f"{path}?{qs}" if is_abs else f"{self.base_url}{path}?{qs}"

            sign_hdrs, _ts = self._sign_and_guard(
                query_string=qs, body=body, path=api_path,
                method=method, use_full_sign=True, skip_app_id=skip_app_id,
            )
            hdrs = dict(self.device.headers(method=method))
            if skip_app_id:
                hdrs.pop("x-ss-dp", None)
            hdrs.update(sign_hdrs)
            if body is None:
                hdrs.pop("x-ss-stub", None)
            if extra_headers:
                hdrs.update(extra_headers)

            sess = CffiSession(impersonate=self._impersonate)
            try:
                _wproxy = self._next_proxy()
                if _wproxy:
                    sess.proxies = {"http": _wproxy, "https": _wproxy}
                write_timeout = min(self._timeout, 15.0)
                if method.upper() == "POST":
                    resp = sess.post(full_url, headers=hdrs, content=body, timeout=write_timeout)
                else:
                    resp = sess.get(full_url, headers=hdrs, timeout=write_timeout)
                last_resp = resp
                self._harvest_cookies(resp.headers)

                if resp.status_code == 200 and resp.content:
                    if raw:
                        return resp
                    return _parse_aweme_envelope_raw(
                        resp.status_code, resp.content, dict(resp.headers), proto_mode=proto_mode)

                if resp.status_code == 429:
                    time.sleep(min(8.0, 1.0 * (2 ** attempt)))
                    continue
                if resp.status_code >= 500:
                    time.sleep(1.0)
                    continue
                time.sleep(1.0 + random.random() * 0.5)
                continue
            except Exception:
                time.sleep(1.0)
                continue
            finally:
                try:
                    sess.close()
                except Exception:
                    pass

        if last_resp is not None and last_resp.content:
            if raw:
                return last_resp
            return _parse_aweme_envelope_raw(
                last_resp.status_code, last_resp.content,
                dict(last_resp.headers), proto_mode=proto_mode)
        return {"_empty": True, "status_code": -1, "_write_bypass_failed": True}

    # ------------------------------------------------------------------
    # Main request method
    # ------------------------------------------------------------------

    def request(
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
        skip_app_id: bool = False,
        bare: bool = False,
        write: bool = False,
        proto_mode: str = "feed",
    ) -> Any:
        if self.rate_limiter is not None:
            self.rate_limiter.acquire(path if self.rate_limiter.per_endpoint else None)

        url = path if path.startswith("http") else f"{self.base_url}{path}"

        if bare:
            merged_params: dict[str, str] = {}
            if params:
                merged_params.update({k: str(v) for k, v in params.items()})
            query_string = urlencode(merged_params) if merged_params else ""
            full_url = f"{url}?{query_string}" if query_string else url
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
            hdrs: dict[str, str] = {
                "User-Agent": self.device.user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
            cookie = self.device.cookie_string()
            if cookie:
                hdrs["Cookie"] = cookie
            if headers:
                hdrs.update(headers)
        else:
            merged_params = dict(self.device.common_params())
            if skip_app_id:
                merged_params.pop("aid", None)
                merged_params.pop("app_name", None)
            if params:
                merged_params.update({k: str(v) for k, v in params.items()})
            query_string = urlencode(merged_params)
            full_url = f"{url}?{query_string}"

            body_bytes = None
            if content is not None:
                body_bytes = content
            elif data is not None:
                if isinstance(data, str):
                    body_bytes = data.encode()
                elif isinstance(data, bytes):
                    body_bytes = data
                else:
                    body_bytes = urlencode(data).encode()

            use_full_sign = self.full_sign if full_sign is None else full_sign
            api_path = path.split("?")[0] if "?" in path else path
            if not api_path.startswith("/"):
                from urllib.parse import urlparse
                api_path = urlparse(api_path).path
            sign_headers, _ts = self._sign_and_guard(
                query_string=query_string,
                body=body_bytes,
                path=api_path,
                method=method,
                use_full_sign=use_full_sign,
                skip_app_id=skip_app_id,
            )

            hdrs = dict(self.device.headers(method=method))
            if skip_app_id:
                hdrs.pop("x-ss-dp", None)
            hdrs.update(sign_headers)
            if headers:
                hdrs.update(headers)

        if write and method.upper() == "POST":
            write_params: dict[str, str] = {}
            if params:
                write_params.update({k: str(v) for k, v in params.items()})
            return self._write_request_cffi(
                method, path if not path.startswith("http") else path,
                query_params=write_params,
                body=body_bytes,
                extra_headers=dict(headers) if headers else None,
                skip_app_id=skip_app_id,
                proto_mode=proto_mode,
                raw=raw,
            )

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._cffi_read(method, full_url, hdrs, body_bytes, json)
            except Exception as e:
                last_exc = ServerError(f"transport error: {e}")
                self._sleep(attempt, None)
                continue

            if resp is None:
                self._sleep(attempt, None)
                continue

            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < self.max_retries:
                    self._sleep(attempt, retry_after)
                    continue
                raise RateLimitError("rate limited", retry_after=retry_after, http_status=429)

            if 500 <= resp.status_code < 600:
                if attempt < self.max_retries:
                    self._sleep(attempt, None)
                    continue
                raise ServerError(f"server error {resp.status_code}", http_status=resp.status_code)

            if (resp.status_code == 200 and not resp.content
                    and attempt < self.max_retries):
                self._sleep(attempt, None)
                continue

            if raw:
                if resp.status_code >= 400:
                    raise _map_http(resp.status_code, "")
                return resp

            return _parse_aweme_envelope_raw(
                resp.status_code, resp.content, dict(resp.headers), proto_mode=proto_mode)

        raise last_exc or TikTokError("request failed after retries")

    def get(self, path: str, *, full_sign: bool | None = None, skip_app_id: bool = False, bare: bool = False, **kw) -> Any:
        return self.request("GET", path, full_sign=full_sign, skip_app_id=skip_app_id, bare=bare, **kw)

    def post(self, path: str, *, full_sign: bool | None = True, skip_app_id: bool = False, bare: bool = False, write: bool = False, **kw) -> Any:
        return self.request("POST", path, full_sign=full_sign, skip_app_id=skip_app_id, bare=bare, write=write, **kw)

    def _sleep(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            time.sleep(retry_after)
            return
        time.sleep(min(8.0, 0.5 * (2 ** attempt)) + random.random() * 0.25)


def _parse_retry_after(resp: Any) -> float | None:
    v = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_aweme_envelope_raw(status_code: int, content: bytes, headers: dict[str, str], *, proto_mode: str = "feed") -> Any:
    """Parse TikTok's JSON/protobuf response envelope."""
    ct = headers.get("content-type", "")

    if "protobuf" in ct:
        if status_code >= 400:
            raise _map_http(status_code, "")
        if not content:
            raise TikTokError("empty protobuf response", http_status=status_code)
        if proto_mode == "generic":
            from .proto_decode import decode_generic
            return decode_generic(content)
        from .proto_decode import parse_feed_response
        return parse_feed_response(content)

    try:
        body = _json.loads(content)
    except ValueError:
        if status_code >= 400:
            raise _map_http(status_code, "")
        if not content:
            return {"_empty": True, "status_code": -1}
        raise TikTokError(f"non-JSON response ({status_code})", http_status=status_code)

    if not isinstance(body, dict):
        return body

    body.setdefault("_headers", _scrub_headers(headers))
    body.setdefault("_http_status", status_code)

    sc = body.get("status_code")

    if status_code in (401, 403) or sc in (2154, 2096):
        msg = body.get("status_msg") or body.get("message") or f"auth error {status_code}"
        raise AuthError(msg, http_status=status_code, code=str(sc or ""))

    if status_code == 429 or sc == 6:
        raise RateLimitError(
            body.get("status_msg") or "rate limited",
            http_status=status_code,
            code=str(sc or ""),
        )

    if status_code >= 500:
        raise ServerError(
            body.get("status_msg") or f"server error {status_code}",
            http_status=status_code,
        )

    if status_code >= 400:
        raise _map_http(status_code, body.get("status_msg") or "")

    if sc is not None and sc != 0:
        msg = body.get("status_msg") or body.get("message") or f"status_code={sc}"
        if sc == 2146:
            raise InvalidRequest(f"app version too old: {msg}", code="2146", http_status=status_code)
        if sc == 8:
            raise AuthError(msg or "login expired", http_status=status_code, code="8")
        raise InvalidRequest(msg, code=str(sc), http_status=status_code)

    return body


def _parse_aweme_envelope(resp: httpx.Response, *, proto_mode: str = "feed") -> Any:
    """httpx.Response variant of :func:`_parse_aweme_envelope_raw`."""
    return _parse_aweme_envelope_raw(
        resp.status_code, resp.content, dict(resp.headers), proto_mode=proto_mode,
    )


def _map_http(status: int, text: str) -> TikTokError:
    if status in (401, 403):
        return AuthError(text or "unauthorized", http_status=status)
    if status == 429:
        return RateLimitError(text or "rate limited", http_status=status)
    if status >= 500:
        return ServerError(text or "server error", http_status=status)
    return InvalidRequest(text or f"http {status}", http_status=status)
