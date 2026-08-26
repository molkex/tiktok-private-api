"""Device registration: obtain real device_id / install_id from TikTok.

Calls POST /service/2/device_register/ on log.snssdk.com with a TTEncrypt-
encrypted payload.  Returns a Device instance with server-assigned IDs.

Usage:
    device = register_device()                       # sync
    device = await register_device_async()           # async
    device = register_device(device=my_seed_device)  # bring your own seed
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .device import (
    Device,
    DEVICE_REGISTER_URL,
    TIKTOK_AID,
    TIKTOK_APP_NAME,
    TIKTOK_APP_VERSION,
    TIKTOK_CHANNEL,
    TIKTOK_VERSION_CODE,
    TIKTOK_MANIFEST_VERSION_CODE,
)
from .signing import sign_request
from .ttencrypt import tt_encrypt

TIKTOK_PACKAGE = "com.zhiliaoapp.musically"

# Fixed values matching what a real TikTok Android client sends.
_SIG_HASH = "aea615ab910015038f73c47e45d21466"


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
            "resolution": device.resolution.replace("x", "*"),
            "dpi": device.dpi,
            "timezone": -4,
            "timezone_name": "America/New_York",
            "timezone_offset": -14400,
            "carrier": device.carrier or "",
            "mcc_mnc": "",
            "locale": f"{device.language}_{device.region}",
            "app_language": device.language,
            "sys_region": device.region,
            "carrier_region": device.region,
            "not_request_sender": 0,
            "rom": "unknown",
            "rom_version": "",
            "sig_hash": _SIG_HASH,
            "gaid_limited": 0,
            "google_aid": "",
            "ac": "wifi",
            "_gen_i": 1,
        },
        "_gen_ts": ts,
    }


def _build_query_params(device: Device) -> dict[str, str]:
    """Query-string params sent alongside the registration POST."""
    ts_ms = str(int(time.time() * 1000))
    return {
        "aid": TIKTOK_AID,
        "app_name": TIKTOK_APP_NAME,
        "version_code": device.version_code,
        "version_name": device.app_version,
        "manifest_version_code": device.manifest_version_code,
        "channel": device.channel,
        "device_type": device.device_type,
        "device_brand": device.device_brand,
        "device_platform": "android",
        "os_version": device.os_version,
        "os_api": device.os_api,
        "resolution": device.resolution,
        "dpi": str(device.dpi),
        "language": device.language,
        "region": device.region,
        "carrier_region": device.region,
        "app_language": device.language,
        "sys_region": device.region,
        "timezone_name": "America/New_York",
        "timezone_offset": "-14400",
        "ac": "wifi",
        "openudid": device.openudid,
        "cdid": device.cdid,
        "uuid": device.openudid,
        "_rticket": ts_ms,
        "ts": str(int(time.time())),
    }


def _make_seed_device() -> Device:
    """Create a seed Device with random fingerprint params but no real IDs."""
    return Device(
        device_id="0",
        install_id="0",
        iid="0",
    )


def _sign_and_build_request(
    device: Device,
) -> tuple[str, bytes, dict[str, str]]:
    """Prepare full URL, body, and headers for the registration request."""
    from urllib.parse import urlencode

    payload = _build_register_payload(device)
    payload_json = json.dumps(payload, separators=(",", ":"))

    # TTEncrypt the JSON payload
    body = tt_encrypt(payload_json.encode())

    params = _build_query_params(device)
    query_string = urlencode(params)
    full_url = f"{DEVICE_REGISTER_URL}?{query_string}"

    ts = round(time.time())
    sign_headers = sign_request(
        query_string=query_string,
        body=body,
        cookie_string=device.cookie_string(),
        ts=ts,
    )

    headers = dict(device.headers())
    headers.update(sign_headers)
    headers["Content-Type"] = "application/octet-stream"
    headers["X-SS-REQ-TICKET"] = str(int(time.time() * 1000))

    return full_url, body, headers


def _parse_register_response(resp: httpx.Response, device: Device) -> Device:
    """Parse the server response and update the Device with real IDs."""
    if resp.status_code != 200:
        raise RuntimeError(
            f"device_register failed: HTTP {resp.status_code} "
            f"{resp.text[:300]}"
        )

    data = resp.json()

    # The response may have device_id_str / install_id_str (string) or
    # device_id / install_id (int).  Handle both.
    device_id = data.get("device_id_str") or str(data.get("device_id", 0))
    install_id = data.get("install_id_str") or str(data.get("install_id", 0))

    if device_id in ("0", "", "None", None):
        raise RuntimeError(
            f"device_register returned no device_id: "
            f"{json.dumps(data)[:300]}"
        )

    device.device_id = device_id
    device.install_id = install_id
    device.iid = install_id
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
    device: Device | None = None,
    timeout: float = 30.0,
) -> Device:
    """Register a new device with TikTok (synchronous).

    Args:
        device:  Optional seed Device. If omitted a random one is generated.
        timeout: HTTP timeout in seconds.

    Returns:
        The same Device instance, updated with real device_id / install_id.

    Raises:
        RuntimeError: registration failed (HTTP error or missing device_id).
    """
    d = device or _make_seed_device()
    url, body, headers = _sign_and_build_request(d)

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, content=body, headers=headers)

    return _parse_register_response(resp, d)


async def register_device_async(
    *,
    device: Device | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30.0,
) -> Device:
    """Register a new device with TikTok (async).

    Args:
        device:  Optional seed Device. If omitted a random one is generated.
        client:  Optional reusable httpx.AsyncClient.
        timeout: HTTP timeout in seconds.

    Returns:
        The same Device instance, updated with real device_id / install_id.

    Raises:
        RuntimeError: registration failed (HTTP error or missing device_id).
    """
    d = device or _make_seed_device()
    url, body, headers = _sign_and_build_request(d)

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
        close_client = True

    try:
        resp = await client.post(url, content=body, headers=headers)
    finally:
        if close_client:
            await client.aclose()

    return _parse_register_response(resp, d)
