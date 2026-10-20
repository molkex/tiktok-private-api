"""Device registration against TikTok (public, hosted-signing).

The /service/2/device_register/ body is a TTEncrypt-wrapped blob, and
TTEncrypt is part of the signing algorithm — it only runs server-side,
inside the hosted signing service. This module therefore delegates both
the body encryption and the request signing to :class:`RemoteSigner`
(via its ``register()`` entry point) and performs just the HTTP POST
locally.

Usage::

    from tiktokflow.android.remote_signer import RemoteSigner
    from tiktokflow.android.register import register_device

    signer = RemoteSigner("https://sign.example.com", "sk_...")
    device = register_device(signer=signer)
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from .device import (
    Device,
    DEVICE_REGISTER_URL,
    TIKTOK_AID,
    TIKTOK_APP_NAME,
)

TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
_SIG_HASH = "aea615ab910015038f73c47e45d21466"

_HOSTED_HINT = (
    "register_device requires a RemoteSigner — TTEncrypt and the signing "
    "algorithm run server-side only. Pass signer=RemoteSigner(url, api_key)."
)


def _build_register_payload(device: Device) -> dict[str, Any]:
    """Build the app-log JSON payload for /service/2/device_register/."""
    ts = int(time.time())
    return {
        "magic_tag": "ss_app_log",
        "header": {
            "display_name": "TikTok",
            "update_version_code": int(device.manifest_version_code),
            "manifest_version_code": int(device.manifest_version_code),
            "app_version_minor": "",
            "aid": int(TIKTOK_AID),
            "channel": device.channel,
            "package": TIKTOK_PACKAGE,
            "app_name": TIKTOK_APP_NAME,
            "version_code": int(device.version_code),
            "version_name": device.app_version,
            "device_id": 0,
            "os": "Android",
            "os_version": device.os_version,
            "os_api": int(device.os_api),
            "device_model": device.device_type,
            "device_brand": device.device_brand,
            "device_type": device.device_type,
            "device_manufacturer": device.device_brand,
            "language": device.language,
            "region": device.region,
            "openudid": device.openudid,
            "cdid": device.cdid,
            "clientudid": device.clientudid,
            "resolution": device.resolution_qs,
            "dpi": device.dpi,
            "timezone": device.timezone_offset // 3600,
            "timezone_name": device.timezone_name,
            "timezone_offset": device.timezone_offset,
            "carrier": device.carrier,
            "mcc_mnc": device.mcc_mnc,
            "locale": f"{device.language}_{device.region}",
            "app_language": device.language,
            "sys_region": device.region,
            "carrier_region": device.region,
            "not_request_sender": 0,
            "rom": device.rom or "unknown",
            "rom_version": device.rom_version,
            "cpu_abi": device.cpu_abi,
            "host_abi": device.cpu_abi,
            "sig_hash": _SIG_HASH,
            "gaid_limited": 0,
            "google_aid": device.google_aid,
            "ac": "wifi",
            "_gen_i": 1,
        },
        "_gen_ts": ts,
    }


def _build_query_params(device: Device) -> dict[str, str]:
    ts_ms = str(int(time.time() * 1000))
    return {
        "aid": TIKTOK_AID,
        "app_name": TIKTOK_APP_NAME,
        "version_code": device.version_code,
        "version_name": device.app_version,
        "manifest_version_code": device.manifest_version_code,
        "update_version_code": device.manifest_version_code,
        "channel": device.channel,
        "device_type": device.device_type,
        "device_brand": device.device_brand,
        "device_platform": "android",
        "os": "android",
        "os_version": device.os_version,
        "os_api": device.os_api,
        "resolution": device.resolution_qs,
        "dpi": str(device.dpi),
        "language": device.language,
        "region": device.region,
        "carrier_region": device.region,
        "app_language": device.language,
        "sys_region": device.region,
        "timezone_name": device.timezone_name,
        "timezone_offset": str(device.timezone_offset),
        "ac": "wifi",
        "openudid": device.openudid,
        "cdid": device.cdid,
        "uuid": device.openudid,
        "mcc_mnc": device.mcc_mnc,
        "carrier_region_v2": device.carrier_region_v2,
        "_rticket": ts_ms,
        "ts": str(int(time.time())),
    }


def _make_seed_device() -> Device:
    return Device(device_id="0", install_id="0", iid="0")


def _sign_and_build_request(
    device: Device,
    signer: Any,
) -> tuple[str, bytes, dict[str, str]]:
    """Ask the signing server to TTEncrypt the body and sign the request."""
    if signer is None or not hasattr(signer, "register"):
        raise RuntimeError(_HOSTED_HINT)

    payload = _build_register_payload(device)
    payload_json = json.dumps(payload, separators=(",", ":"))

    params = _build_query_params(device)
    query_string = urlencode(params)
    full_url = f"{DEVICE_REGISTER_URL}?{query_string}"

    body, sign_headers, _ts = signer.register(
        payload_json=payload_json,
        query_string=query_string,
        cookie_string=device.cookie_string(),
    )

    headers = dict(device.headers())
    headers.update(sign_headers)
    headers["Content-Type"] = "application/octet-stream"
    headers["X-SS-REQ-TICKET"] = str(int(time.time() * 1000))

    return full_url, body, headers


_COOKIE_TO_ATTR: dict[str, str] = {
    "ttreq": "ttreq",
    "odin_tt": "odin_tt",
    "ttwid": "ttwid",
    "msToken": "msToken",
    "d_ticket": "d_ticket",
    "cmpl_token": "cmpl_token",
    "store-country-code": "store_country_code",
    "passport_csrf_token": "passport_csrf_token",
    "sessionid": "session_id",
    "sid_tt": "sid_tt",
    "uid_tt": "uid_tt",
    "sid_guard": "sid_guard",
    "multi_sids": "multi_sids",
    "sid_ucp_v1": "sid_ucp_v1",
    "ssid_ucp_v1": "ssid_ucp_v1",
}


def parse_all_cookies(resp: httpx.Response) -> dict[str, str]:
    """Return {cookie_name: cookie_value} for every Set-Cookie header."""
    cookies: dict[str, str] = {}
    for cookie_str in resp.headers.get_list("set-cookie"):
        name_val = cookie_str.split(";")[0].strip()
        if "=" in name_val:
            name, _, val = name_val.partition("=")
            cookies[name.strip()] = val.strip()
    return cookies


def persist_register_cookies(resp: httpx.Response, device: Device) -> dict[str, str]:
    """Persist every known cookie from a device_register response onto Device."""
    cookies = parse_all_cookies(resp)
    for cookie_name, value in cookies.items():
        attr = _COOKIE_TO_ATTR.get(cookie_name)
        if attr and value:
            setattr(device, attr, value)
    return cookies


def _parse_register_response(resp: httpx.Response, device: Device) -> Device:
    if resp.status_code != 200:
        raise RuntimeError(
            f"device_register failed: HTTP {resp.status_code} {resp.text[:300]}"
        )

    data = resp.json()
    device_id = data.get("device_id_str") or str(data.get("device_id", 0))
    install_id = data.get("install_id_str") or str(data.get("install_id", 0))

    if device_id in ("0", "", "None", None):
        raise RuntimeError(
            f"device_register returned no device_id: {json.dumps(data)[:300]}"
        )

    device.device_id = str(device_id)
    device.install_id = str(install_id)
    device.iid = str(install_id)
    device.device_token = data.get("device_token", "")

    for cookie_str in resp.headers.get_list("set-cookie"):
        if cookie_str.startswith("ttreq="):
            device.ttreq = cookie_str.split("=", 1)[1].split(";")[0].strip()

    return device


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_device(
    *,
    signer: Any | None = None,
    device: Device | None = None,
    proxy: str | None = None,
    proxies: list[str] | None = None,
    timeout: float = 30.0,
    max_retries: int = 4,
    client: httpx.Client | None = None,
    persist_cookies: bool = False,
) -> Device:
    """Register a fresh device with TikTok (sync).

    Args:
        signer: ``RemoteSigner`` (required — TTEncrypt and signing run
            server-side).
        device: Optional seed Device; a fresh one is generated otherwise.
        proxy / proxies: HTTP/SOCKS5 proxies.
        timeout: HTTP timeout in seconds.
        max_retries: Retries on flaky server responses.
        client: Optional persistent ``httpx.Client``.
        persist_cookies: If True, persist all Set-Cookie headers to Device.

    Returns:
        The Device, with server-assigned device_id, install_id, device_token.
    """
    if signer is None:
        raise ValueError(_HOSTED_HINT)

    last_err: Exception | None = None
    for attempt in range(max_retries):
        if device is not None:
            d = device if attempt == 0 else Device(
                device_id="0", install_id="0", iid="0",
                region=device.region, language=device.language,
            )
        else:
            d = _make_seed_device()
        url, body, headers = _sign_and_build_request(d, signer=signer)

        try:
            if client is not None:
                resp = client.post(url, content=body, headers=headers)
            else:
                client_kwargs: dict[str, Any] = {"timeout": timeout}
                sel_proxy = proxy or (random.choice(proxies) if proxies else None)
                if sel_proxy:
                    client_kwargs["proxy"] = sel_proxy
                with httpx.Client(**client_kwargs) as c:
                    resp = c.post(url, content=body, headers=headers)
            result = _parse_register_response(resp, d)
            if persist_cookies:
                persist_register_cookies(resp, d)
            return result
        except RuntimeError as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise

    raise last_err or RuntimeError("device_register failed")


async def register_device_async(
    *,
    signer: Any | None = None,
    device: Device | None = None,
    proxy: str | None = None,
    proxies: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
    max_retries: int = 4,
) -> Device:
    """Register a fresh device with TikTok (async)."""
    if signer is None:
        raise ValueError(_HOSTED_HINT)

    last_err: Exception | None = None
    for attempt in range(max_retries):
        if device is not None:
            d = device if attempt == 0 else Device(
                device_id="0", install_id="0", iid="0",
                region=device.region, language=device.language,
            )
        else:
            d = _make_seed_device()
        url, body, headers = await asyncio.to_thread(
            _sign_and_build_request, d, signer,
        )

        close_client = False
        sel_client = client
        if sel_client is None:
            client_kwargs: dict[str, Any] = {"timeout": timeout}
            sel_proxy = proxy or (random.choice(proxies) if proxies else None)
            if sel_proxy:
                client_kwargs["proxy"] = sel_proxy
            sel_client = httpx.AsyncClient(**client_kwargs)
            close_client = True

        try:
            resp = await sel_client.post(url, content=body, headers=headers)
            return _parse_register_response(resp, d)
        except RuntimeError as e:
            last_err = e
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise
        finally:
            if close_client:
                await sel_client.aclose()

    raise last_err or RuntimeError("device_register failed")
