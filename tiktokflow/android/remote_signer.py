"""Remote signing client — calls the signing server instead of local crypto.

Usage:
    from tiktokflow.android.remote_signer import RemoteSigner
    signer = RemoteSigner("https://sign.example.com", "sk_abc123...")
    transport = AndroidTransport(device, signer=signer)
"""
from __future__ import annotations

import base64

import httpx


class RemoteSigner:
    def __init__(
        self,
        server_url: str,
        api_key: str,
        *,
        timeout: float = 5.0,
    ):
        self._url = server_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.Client(
            timeout=timeout,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )

    def sign(
        self,
        *,
        query_string: str = "",
        body: bytes | None = None,
        cookie_string: str = "",
        path: str = "/",
        method: str = "GET",
        full_sign: bool = True,
        skip_app_id: bool = False,
        device_id: str = "",
        install_id: str = "",
        device_type: str = "",
        device_brand: str = "",
        channel: str = "googleplay",
        app_version: str = "",
        version_code: str = "",
        manifest_version_code: str = "",
        device_token: str = "",
        dtoken_sign: str = "",
        token: str = "",
        ts_sign: str = "",
    ) -> tuple[dict[str, str], int]:
        """Request signed headers from the signing server.

        Returns (headers_dict, timestamp_used).
        """
        payload = {
            "query_string": query_string,
            "body_b64": base64.b64encode(body).decode() if body else None,
            "cookie_string": cookie_string,
            "path": path,
            "method": method,
            "full_sign": full_sign,
            "skip_app_id": skip_app_id,
            "device_id": device_id,
            "install_id": install_id,
            "device_type": device_type,
            "device_brand": device_brand,
            "channel": channel,
            "app_version": app_version,
            "version_code": version_code,
            "manifest_version_code": manifest_version_code,
            "device_token": device_token,
            "dtoken_sign": dtoken_sign,
            "token": token,
            "ts_sign": ts_sign,
        }
        resp = self._client.post(f"{self._url}/v1/sign", json=payload)
        if resp.status_code == 429:
            raise RuntimeError("signing server rate limit exceeded")
        if resp.status_code == 403:
            raise RuntimeError("signing server: invalid API key")
        resp.raise_for_status()
        data = resp.json()
        return data["headers"], data["ts"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
