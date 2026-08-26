"""Android mobile API transport: httpx + auto-signing + device params.

Every request goes through sign_request() to get X-Gorgon/X-Khronos/X-SS-STUB,
then device.common_params() are merged into query params. This is the Android
analogue of tiktokflow/http.py (which handles the official OAuth API).

Write endpoints (follow, like, block, comment) use curl_cffi with TLS
impersonation and DNS edge-IP pinning to bypass Janus-Mini(fast) gateway
and Envoy SC response stripping."""
from __future__ import annotations

import random
import socket
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from ..errors import (AuthError, InvalidRequest, RateLimitError, ServerError,
                      TikTokError)
from .device import API_BASE, YCRU_BASE, Device
from .ratelimit import RateLimiter

try:
    from .signing import sign_request, sign_request_full, sign_request_v46
    from .guard import make_device_guard, make_ticket_guard
    _HAS_LOCAL_SIGNING = True
except ImportError:
    _HAS_LOCAL_SIGNING = False

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
WRITE_MAX_RETRIES = 25

_PUB_KEY_B64 = ""


def _guard_public_key(device: Device) -> str:
    global _PUB_KEY_B64
    if not _PUB_KEY_B64:
        if not _HAS_LOCAL_SIGNING:
            return ""
        import base64 as _b64
        from .guard import _pk
        pub_numbers = _pk().public_key().public_numbers()
        raw = b"\x04" + pub_numbers.x.to_bytes(32, "big") + pub_numbers.y.to_bytes(32, "big")
        _PUB_KEY_B64 = _b64.b64encode(raw).decode()
    return _PUB_KEY_B64


def _resolve_edge_ips(host: str) -> list[str]:
    """DNS-resolve host to all A-record IPs."""
    try:
        results = socket.getaddrinfo(host, 443, socket.AF_INET)
        return list(set(r[4][0] for r in results))
    except socket.gaierror:
        return []


class _EdgePool:
    """Maintains a ranked pool of edge IPs for write bypass.

    IPs that successfully bypass Janus-Mini/Envoy SC are promoted;
    IPs that consistently fail are demoted."""

    def __init__(self, host: str):
        self.host = host
        self._ips: list[str] = []
        self._scores: dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_resolve = 0.0

    def _ensure_resolved(self) -> None:
        now = time.time()
        if self._ips and now - self._last_resolve < 300:
            return
        ips = _resolve_edge_ips(self.host)
        if ips:
            with self._lock:
                for ip in ips:
                    if ip not in self._scores:
                        self._scores[ip] = 0.5
                self._ips = ips
                self._last_resolve = now

    def get_ranked(self) -> list[str]:
        """Return IPs sorted by success score (best first)."""
        self._ensure_resolved()
        with self._lock:
            return sorted(self._ips, key=lambda ip: self._scores.get(ip, 0.5), reverse=True)

    def report(self, ip: str, success: bool) -> None:
        with self._lock:
            old = self._scores.get(ip, 0.5)
            self._scores[ip] = old * 0.7 + (1.0 if success else 0.0) * 0.3


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
        ttnet_pid: int | None = None,
    ):
        self.device = device
        self._remote_signer = signer
        if base_url == API_BASE and device.is_authenticated:
            base_url = YCRU_BASE
        self.base_url = base_url.rstrip("/")
        self._impersonate = "chrome120"  # curl_cffi TLS fingerprint; overridden by IOSTransport
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
            base_hdrs = {"User-Agent": device.user_agent, "Accept-Encoding": "gzip, deflate, br"}
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

        from urllib.parse import urlparse
        write_host = urlparse(self.base_url).hostname or ""
        self._edge_pool = _EdgePool(write_host) if write_host else None

        self._ttnet_bridge = None
        self._ttnet_first = False
        if ttnet_pid is not None:
            from .ttnet_bridge import TTNetBridge
            self._ttnet_bridge = TTNetBridge(pid=ttnet_pid)
            self._ttnet_first = True

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
            transport = httpx.HTTPTransport(retries=0)
            base_hdrs = {"User-Agent": self.device.user_agent, "Accept-Encoding": "gzip, deflate, br"}
            kw: dict[str, Any] = {
                "timeout": self._timeout,
                "headers": base_hdrs,
                "transport": transport,
            }
            if proxy is not None:
                kw["proxy"] = proxy
            client = httpx.Client(**kw)
            self._clients[proxy] = client
            return client

    def _rotate_client(self, proxy: str | None) -> None:
        old = self._clients.pop(proxy, None)
        if old is not None:
            old.close()

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
    # Unified signing: local or remote
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
        """Produce all signing + guard headers. Returns (headers, ts).

        When a remote signer is configured, delegates to the signing server.
        Otherwise uses local crypto (signing.py, guard.py, argus.py, ladon.py).
        """
        ts = round(time.time())
        api_path = path.split("?")[0] if "?" in path else path

        if self._remote_signer:
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

        if not _HAS_LOCAL_SIGNING:
            raise RuntimeError(
                "No signing available — provide a RemoteSigner via signer= parameter "
                "or install the full package with signing modules"
            )

        # v46+ uses simplified signing: timestamp + body MD5 only.
        # x-opti-ut, x-bd-client-key, X-Tt-Token are static session tokens
        # already included in Device.headers().
        if self.device.opti_ut:
            hdrs = sign_request_v46(
                query_string=query_string,
                body=body,
                ts=ts,
            )
        elif use_full_sign:
            hdrs = sign_request_full(
                self.device,
                query_string=query_string,
                body=body,
                ts=ts,
                skip_aid=skip_app_id,
            )
        else:
            hdrs = sign_request(
                query_string=query_string,
                body=body,
                cookie_string=self.device.cookie_string(),
                ts=ts,
            )

        if self.device.device_token and self.device.dtoken_sign:
            try:
                hdrs["tt-device-guard-client-data"] = make_device_guard(
                    self.device, api_path, ts=ts,
                )
                hdrs["tt-device-guard-iteration-version"] = "1"
            except (ValueError, RuntimeError):
                pass
        if self.device.token and self.device.ts_sign:
            try:
                hdrs["tt-ticket-guard-client-data"] = make_ticket_guard(
                    self.device, api_path, ts=ts,
                )
                hdrs["tt-ticket-guard-public-key"] = _guard_public_key(self.device)
                hdrs["tt-ticket-guard-version"] = "3"
                hdrs["tt-ticket-guard-iteration-version"] = "0"
                hdrs["x-tt-request-tag"] = "n=0;nr=011;bg=0;rs=112;s=-1;p=0"
            except (ValueError, RuntimeError):
                pass

        return hdrs, ts

    # ------------------------------------------------------------------
    # curl_cffi write request with edge pinning
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
    ) -> Any:
        """Execute a write request using curl_cffi with TLS impersonation
        and edge-IP pinning to bypass Janus-Mini(fast) / Envoy SC.

        Re-signs the request on every retry so timestamps stay fresh."""
        from curl_cffi import CurlOpt
        from curl_cffi.requests import Session as CffiSession

        retries = max_retries if max_retries is not None else self.write_retries
        host = self._edge_pool.host if self._edge_pool else ""
        edge_ips = self._edge_pool.get_ranked() if self._edge_pool else []

        api_path = path.split("?")[0] if "?" in path else path

        for attempt in range(retries):
            edge_ip = edge_ips[attempt % len(edge_ips)] if edge_ips else None

            merged = dict(self.device.common_params())
            if skip_app_id:
                merged.pop("aid", None)
                merged.pop("app_name", None)
            merged.update(query_params)
            qs = urlencode(merged)
            full_url = f"{self.base_url}{path}?{qs}"

            sign_hdrs, ts = self._sign_and_guard(
                query_string=qs, body=body, path=api_path,
                method=method, use_full_sign=True, skip_app_id=skip_app_id,
            )
            hdrs = dict(self.device.headers(method=method))
            if skip_app_id:
                hdrs.pop("x-ss-dp", None)
            hdrs.update(sign_hdrs)
            hdrs["passport-sdk-version"] = "1"
            hdrs["sdk-version"] = "2"
            if body is None:
                hdrs.pop("x-ss-stub", None)
            if extra_headers:
                hdrs.update(extra_headers)

            try:
                sess = CffiSession(impersonate=self._impersonate)
                if edge_ip:
                    sess.curl.setopt(CurlOpt.RESOLVE, [f"{host}:443:{edge_ip}".encode()])

                write_timeout = min(self._timeout, 10.0)
                if method.upper() == "POST":
                    resp = sess.post(full_url, headers=hdrs, content=body, timeout=write_timeout)
                else:
                    resp = sess.get(full_url, headers=hdrs, timeout=write_timeout)

                if resp.status_code == 200 and resp.content:
                    if self._edge_pool and edge_ip:
                        self._edge_pool.report(edge_ip, True)
                    sess.close()
                    return _parse_aweme_envelope_raw(
                        resp.status_code, resp.content, dict(resp.headers), proto_mode=proto_mode)

                if self._edge_pool and edge_ip:
                    self._edge_pool.report(edge_ip, False)
                sess.close()

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
                try:
                    sess.close()
                except Exception:
                    pass
                continue

        # Fallback: try httpx (bypasses SC for some endpoints like comment/delete)
        try:
            merged = dict(self.device.common_params())
            if skip_app_id:
                merged.pop("aid", None)
                merged.pop("app_name", None)
            merged.update(query_params)
            qs = urlencode(merged)
            full_url = f"{self.base_url}{path}?{qs}"
            sign_hdrs, ts = self._sign_and_guard(
                query_string=qs, body=body, path=api_path,
                method=method, use_full_sign=True, skip_app_id=skip_app_id,
            )
            hdrs = dict(self.device.headers(method=method))
            if skip_app_id:
                hdrs.pop("x-ss-dp", None)
            hdrs.update(sign_hdrs)
            hdrs["passport-sdk-version"] = "1"
            hdrs["sdk-version"] = "2"
            if body is None:
                hdrs.pop("x-ss-stub", None)
            if extra_headers:
                hdrs.update(extra_headers)

            client = self._get_client(None)
            resp = client.request(method, full_url, content=body, headers=hdrs)
            if resp.status_code == 200 and resp.content:
                return _parse_aweme_envelope(resp, proto_mode=proto_mode)
        except Exception:
            pass

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
            merged_params = {}
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
                "Accept-Encoding": "gzip, deflate, br",
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
            sign_headers, ts = self._sign_and_guard(
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
            hdrs["passport-sdk-version"] = "1"
            hdrs["sdk-version"] = "2"

            if headers:
                hdrs.update(headers)

        # Write requests. Strategy depends on whether a TTNet bridge is available:
        #   With bridge (emulator app-session): the app's native stack is the
        #     reliable path — try it FIRST. The plain httpx attempt would only
        #     fail with code=8 (no injected cookies) and must not short-circuit.
        #   Without bridge (Python session): normal signed httpx POST works for
        #     most writes (follow, block...) at ~0.5s; SC-protected ones fall
        #     through to curl_cffi edge-pinning.
        if write and method.upper() == "POST":
            def _try_bridge():
                if not self._ttnet_bridge:
                    return None
                try:
                    ttnet_resp = self._ttnet_bridge.post(full_url, hdrs, body=body_bytes)
                except Exception:
                    return None
                # If the native transport got an HTTP 200 the request reached the
                # server and its answer is authoritative — return it (even an app
                # error code) instead of pointlessly retrying via curl_cffi, which
                # shares no session in app-session mode and would just hang.
                transport_ok = ttnet_resp.get("status") == 200 or ttnet_resp.get("body_bytes")
                try:
                    return self._parse_ttnet(ttnet_resp, raw=raw, proto_mode=proto_mode)
                except (TikTokError, ServerError) as e:
                    if transport_ok:
                        return {
                            "_empty": True,
                            "status_code": getattr(e, "status_code", None) or 4,
                            "status_msg": str(e),
                            "_bridge_server_error": True,
                        }
                    return None
                except Exception:
                    return None

            def _try_normal():
                try:
                    client = self._get_client(None)
                    resp = client.request(method, full_url, content=body_bytes, headers=hdrs)
                    if resp.status_code == 200 and resp.content:
                        parsed = _parse_aweme_envelope(resp, proto_mode=proto_mode)
                        if isinstance(parsed, dict) and not parsed.get("_empty") \
                                and parsed.get("status_code") == 0:
                            return parsed
                        if raw and resp.content:
                            return resp.content
                except (AuthError, RateLimitError, InvalidRequest):
                    if not self._ttnet_bridge:
                        raise
                except Exception:
                    pass
                return None

            order = (_try_bridge, _try_normal) if self._ttnet_bridge else (_try_normal, _try_bridge)
            for attempt in order:
                result = attempt()
                if result is not None:
                    return result
            write_params = {}
            if params:
                write_params.update({k: str(v) for k, v in params.items()})
            return self._write_request_cffi(
                method, path if not path.startswith("http") else path,
                query_params=write_params,
                body=body_bytes,
                extra_headers=dict(headers) if headers else None,
                skip_app_id=skip_app_id,
                proto_mode=proto_mode,
            )

        # TTNet-first: bypass TLS fingerprint checks entirely
        if self._ttnet_first and self._ttnet_bridge:
            try:
                if method.upper() == "POST":
                    ttnet_resp = self._ttnet_bridge.post(full_url, hdrs, body=body_bytes)
                else:
                    ttnet_resp = self._ttnet_bridge.get(full_url, hdrs)
                result = self._parse_ttnet(ttnet_resp, raw=raw, proto_mode=proto_mode)
                if result is not None:
                    return result
            except (TikTokError, AuthError, RateLimitError, InvalidRequest):
                raise
            except Exception:
                pass

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            proxy_tries = max(len(self._proxy_list), 1)
            resp: httpx.Response | None = None
            for _ in range(proxy_tries):
                proxy = self._next_proxy()
                client = self._get_client(proxy)
                try:
                    resp = client.request(
                        method, full_url,
                        json=json if body_bytes is None and json is not None else None,
                        content=body_bytes,
                        headers=hdrs,
                    )
                    break
                except httpx.DecodingError:
                    resp = client.send(
                        client.build_request(
                            method, full_url,
                            json=json if body_bytes is None and json is not None else None,
                            content=body_bytes,
                            headers={**hdrs, "Accept-Encoding": "identity"},
                        )
                    )
                    break
                except httpx.TransportError as e:
                    last_exc = ServerError(f"transport error: {e}")
                    continue

            if resp is None:
                self._sleep(attempt, None)
                continue

            if resp.status_code == 403 and self._ttnet_bridge:
                tt_block = resp.headers.get("tt_block", "")
                if tt_block:
                    try:
                        ttnet_resp = self._ttnet_bridge.get(full_url, hdrs)
                        result = self._parse_ttnet(ttnet_resp, raw=raw, proto_mode=proto_mode)
                        if result is not None:
                            return result
                    except Exception:
                        pass

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
                self._rotate_client(proxy)
                self._sleep(attempt, None)
                continue

            if raw:
                if resp.status_code >= 400:
                    raise _map_http(resp.status_code, resp.text)
                return resp

            return _parse_aweme_envelope(resp, proto_mode=proto_mode)

        raise last_exc or TikTokError("request failed after retries")

    def get(self, path: str, *, full_sign: bool | None = None, skip_app_id: bool = False, bare: bool = False, **kw) -> Any:
        return self.request("GET", path, full_sign=full_sign, skip_app_id=skip_app_id, bare=bare, **kw)

    def post(self, path: str, *, full_sign: bool | None = True, skip_app_id: bool = False, bare: bool = False, write: bool = False, **kw) -> Any:
        return self.request("POST", path, full_sign=full_sign, skip_app_id=skip_app_id, bare=bare, write=write, **kw)

    def _parse_ttnet(
        self, ttnet_resp: dict, *, raw: bool = False, proto_mode: str = "feed",
    ) -> Any | None:
        """Parse a TTNet bridge response. Returns parsed data or None on failure."""
        if ttnet_resp.get("status") != 200 and not ttnet_resp.get("body_bytes"):
            return None
        status = ttnet_resp.get("status", 0)
        body = ttnet_resp.get("body_bytes", b"")
        hdrs = ttnet_resp.get("headers", {})
        if not hdrs.get("content-type"):
            if body and body[:1] == b"{":
                hdrs["content-type"] = "application/json"
            elif body:
                hdrs["content-type"] = "application/x-protobuf"
        if raw:
            return body
        return _parse_aweme_envelope_raw(status, body, hdrs, proto_mode=proto_mode)

    def _sleep(self, attempt: int, retry_after: float | None) -> None:
        if retry_after is not None:
            time.sleep(retry_after)
            return
        time.sleep(min(8.0, 0.5 * (2 ** attempt)) + random.random() * 0.25)


def _parse_retry_after(resp: httpx.Response) -> float | None:
    v = resp.headers.get("Retry-After")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_aweme_envelope_raw(status_code: int, content: bytes, headers: dict[str, str], *, proto_mode: str = "feed") -> Any:
    """Parse response from curl_cffi (raw status/content/headers).

    proto_mode selects the protobuf decoder: "feed" assumes the
    aweme-feed field layout (status_code=1/has_more=4/aweme_list=5),
    "generic" makes no assumptions and returns a field-number-keyed dict
    (used for schemas like DM/IM we haven't reverse-engineered)."""
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

    import json as _json
    try:
        body = _json.loads(content)
    except ValueError:
        if status_code >= 400:
            raise _map_http(status_code, content.decode("utf-8", errors="replace"))
        if not content:
            return {"_empty": True, "status_code": -1}
        raise TikTokError(f"non-JSON response ({status_code})", http_status=status_code)

    if not isinstance(body, dict):
        return body

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
        raise _map_http(status_code, body.get("status_msg") or content.decode("utf-8", errors="replace"))

    if sc is not None and sc != 0:
        msg = body.get("status_msg") or body.get("message") or f"status_code={sc}"
        if sc == 2146:
            raise InvalidRequest(f"app version too old: {msg}", code="2146", http_status=status_code)
        if sc == 8:
            raise AuthError(msg or "login expired", http_status=status_code, code="8")
        raise InvalidRequest(msg, code=str(sc), http_status=status_code)

    return body


def _parse_aweme_envelope(resp: httpx.Response, *, proto_mode: str = "feed") -> Any:
    """Aweme mobile API envelope: JSON or protobuf.
    v2 endpoints return application/x-protobuf; v1 returns JSON.

    proto_mode="generic" skips the aweme-feed field assumptions and
    returns a raw field-number-keyed dict instead (see decode_generic)."""
    ct = resp.headers.get("content-type", "")

    if "protobuf" in ct:
        if resp.status_code >= 400:
            raise _map_http(resp.status_code, "")
        if not resp.content:
            raise TikTokError("empty protobuf response", http_status=resp.status_code)
        if proto_mode == "generic":
            from .proto_decode import decode_generic
            return decode_generic(resp.content)
        from .proto_decode import parse_feed_response
        return parse_feed_response(resp.content)

    try:
        body = resp.json()
    except ValueError:
        if resp.status_code >= 400:
            raise _map_http(resp.status_code, resp.text)
        if not resp.content:
            return {"_empty": True, "status_code": -1}
        raise TikTokError(f"non-JSON response ({resp.status_code})", http_status=resp.status_code)

    if not isinstance(body, dict):
        return body

    status_code = body.get("status_code")

    if resp.status_code in (401, 403) or status_code in (2154, 2096):
        msg = body.get("status_msg") or body.get("message") or f"auth error {resp.status_code}"
        raise AuthError(msg, http_status=resp.status_code, code=str(status_code or ""))

    if resp.status_code == 429 or status_code == 6:
        raise RateLimitError(
            body.get("status_msg") or "rate limited",
            http_status=resp.status_code,
            code=str(status_code or ""),
        )

    if resp.status_code >= 500:
        raise ServerError(
            body.get("status_msg") or f"server error {resp.status_code}",
            http_status=resp.status_code,
        )

    if resp.status_code >= 400:
        raise _map_http(resp.status_code, body.get("status_msg") or resp.text)

    if status_code is not None and status_code != 0:
        msg = body.get("status_msg") or body.get("message") or f"status_code={status_code}"
        if status_code == 2146:
            raise InvalidRequest(
                f"app version too old: {msg}",
                code="2146",
                http_status=resp.status_code,
            )
        if status_code == 8:
            raise AuthError(msg or "login expired", http_status=resp.status_code, code="8")
        raise InvalidRequest(
            msg,
            code=str(status_code),
            http_status=resp.status_code,
        )

    return body


def _map_http(status: int, text: str) -> TikTokError:
    if status in (401, 403):
        return AuthError(text or "unauthorized", http_status=status)
    if status == 429:
        return RateLimitError(text or "rate limited", http_status=status)
    if status >= 500:
        return ServerError(text or "server error", http_status=status)
    return InvalidRequest(text or f"http {status}", http_status=status)
