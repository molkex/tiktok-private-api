"""iOS device identity: device_id, install_id, openudid, fingerprint params.

Mirrors tiktokflow/android/device.py field-for-field so the same signing
pipeline (tiktokflow/android/signing.py X-Gorgon/X-Argus/X-Ladon, guard.py
device-guard/ticket-guard) can sign it unmodified — those algorithms only
care about the field values, not which OS they describe.

Key differences from Device: device_platform=iphone, os=iOS, channel=App
Store, iPhone device_type strings (iPhoneNN,M model identifiers), no
os_api/host_abi (Android-only concepts), and the iOS Cronet user-agent
format ("iPhone OS X.Y" instead of "Android X")."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, asdict
from typing import Any

from ..android.device import (
    TIKTOK_AID,
    TIKTOK_APP_NAME,
    TIKTOK_APP_VERSION,
    TIKTOK_VERSION_CODE,
    TIKTOK_MANIFEST_VERSION_CODE,
    API_HOST,
    API_BASE,
    YCRU_HOST,
    YCRU_BASE,
    SEARCH_HOST,
    SEARCH_BASE,
    DEVICE_REGISTER_URL,
)

TIKTOK_CHANNEL = "App Store"

# device_type -> (resolution, dpi). Covers the Pro Max / Pro / non-Pro tiers
# named in the task brief.
IPHONE_MODELS: dict[str, tuple[str, int]] = {
    "iPhone16,2": ("1290x2796", 460),  # iPhone 15 Pro Max
    "iPhone15,3": ("1290x2796", 460),  # iPhone 14 Pro Max
    "iPhone14,5": ("1170x2532", 460),  # iPhone 13
}
OS_VERSIONS = ["18.1", "17.6", "18.0"]


def _random_hex(length: int) -> str:
    return "".join(random.choices("0123456789abcdef", k=length))


def _random_digits(length: int) -> str:
    return "".join(random.choices("0123456789", k=length))


@dataclass
class IOSDevice:
    device_id: str = ""
    install_id: str = ""
    iid: str = ""
    openudid: str = ""
    cdid: str = ""
    clientudid: str = ""
    device_type: str = ""
    device_brand: str = "Apple"
    os_version: str = ""
    os_api: str = ""  # unused on iOS, kept for field parity with Device
    app_version: str = TIKTOK_APP_VERSION
    version_code: str = TIKTOK_VERSION_CODE
    manifest_version_code: str = TIKTOK_MANIFEST_VERSION_CODE
    channel: str = TIKTOK_CHANNEL
    resolution: str = ""
    dpi: int = 460
    language: str = "en"
    region: str = "US"
    carrier: str = ""
    session_id: str = ""
    sid_tt: str = ""
    uid_tt: str = ""
    multi_sids: str = ""
    token: str = ""
    user_id: str = ""
    device_token: str = ""
    ttreq: str = ""
    odin_tt: str = ""
    msToken: str = ""
    d_ticket: str = ""
    cmpl_token: str = ""
    sid_guard: str = ""
    store_country_code: str = "US"
    dtoken_sign: str = ""
    ts_sign: str = ""
    opti_ut: str = ""
    _raw_cookies: str = ""

    def __post_init__(self):
        if not self.device_id:
            self.device_id = _random_digits(19)
        if not self.install_id:
            self.install_id = _random_digits(19)
        if not self.iid:
            self.iid = self.install_id
        if not self.openudid:
            self.openudid = _random_hex(16)
        if not self.cdid:
            self.cdid = _random_hex(16)
        if not self.clientudid:
            self.clientudid = _random_hex(20)
        if not self.device_type:
            self.device_type = random.choice(list(IPHONE_MODELS))
        if not self.os_version:
            self.os_version = random.choice(OS_VERSIONS)
        if not self.resolution:
            res, dpi = IPHONE_MODELS.get(self.device_type, ("1290x2796", 460))
            self.resolution = res
            if self.dpi == 460:  # only fill in if left at the dataclass default
                self.dpi = dpi

    @property
    def user_agent(self) -> str:
        locale_tag = f"{self.language}_{self.region}"
        return (
            f"com.zhiliaoapp.musically/{self.manifest_version_code} "
            f"(Linux; U; iPhone OS {self.os_version}; {locale_tag}; "
            f"{self.device_type}; Build/UE1A.230829.050; "
            f"Cronet/TTNetVersion:45466851 2026-07-20 QuicVersion:c3b23989 2026-06-25)"
        )

    def cookie_string(self) -> str:
        if self._raw_cookies:
            return self._raw_cookies
        parts = [f"install_id={self.install_id}"]
        if self.ttreq:
            parts.append(f"ttreq={self.ttreq}")
        if self.odin_tt:
            parts.append(f"odin_tt={self.odin_tt}")
        if self.d_ticket:
            parts.append(f"d_ticket={self.d_ticket}")
        if self.session_id:
            parts.append(f"sessionid={self.session_id}")
            parts.append(f"sessionid_ss={self.session_id}")
        if self.sid_tt:
            parts.append(f"sid_tt={self.sid_tt}")
        if self.sid_guard:
            parts.append(f"sid_guard={self.sid_guard}")
        if self.uid_tt:
            parts.append(f"uid_tt={self.uid_tt}")
            parts.append(f"uid_tt_ss={self.uid_tt}")
        if self.multi_sids:
            parts.append(f"multi_sids={self.multi_sids}")
        if self.cmpl_token:
            parts.append(f"cmpl_token={self.cmpl_token}")
        if self.msToken:
            parts.append(f"msToken={self.msToken}")
        parts.append(f"store-country-code={self.store_country_code}")
        parts.append("store-country-code-src=uid")
        parts.append("store-idc=alisg")
        parts.append("tt-target-idc=alisg")
        return "; ".join(parts)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.session_id)

    def update_session(
        self,
        response_data: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        """Update session fields from login response body and Set-Cookie values."""
        if cookies:
            if "sessionid" in cookies:
                self.session_id = cookies["sessionid"]
            if "sid_tt" in cookies:
                self.sid_tt = cookies["sid_tt"]
            if "uid_tt" in cookies:
                self.uid_tt = cookies["uid_tt"]
            if "multi_sids" in cookies:
                self.multi_sids = cookies["multi_sids"]
        if response_data:
            if not self.session_id and response_data.get("session_key"):
                self.session_id = response_data["session_key"]
            if response_data.get("user_id"):
                self.user_id = str(response_data["user_id"])
            if response_data.get("user_id_str"):
                self.user_id = response_data["user_id_str"]
            if response_data.get("token"):
                self.token = response_data["token"]

    def common_params(self) -> dict[str, str]:
        now = time.time()
        ts_ms = str(int(now * 1000))
        ts_s = str(int(now))
        return {
            "device_platform": "iphone",
            "os": "iOS",
            "ssmix": "a",
            "_rticket": ts_ms,
            "cdid": self.cdid,
            "channel": self.channel,
            "aid": TIKTOK_AID,
            "app_name": TIKTOK_APP_NAME,
            "version_code": self.version_code,
            "version_name": self.app_version,
            "manifest_version_code": self.manifest_version_code,
            "update_version_code": self.manifest_version_code,
            "ab_version": self.app_version,
            "resolution": self.resolution,
            "dpi": str(self.dpi),
            "device_type": self.device_type,
            "device_brand": self.device_brand,
            "language": self.language,
            "os_version": self.os_version,
            "ac": "wifi",
            "is_pad": "0",
            "app_type": "normal",
            "sys_region": self.region,
            "last_install_time": str(int(now) - 60),
            "timezone_name": "America/New_York",
            "app_language": self.language,
            "carrier_region": self.region,
            "timezone_offset": "-14400",
            "locale": self.language,
            "ac2": "wifi",
            "uoo": "1",
            "op_region": self.region,
            "build_number": self.app_version,
            "region": self.region,
            "ts": ts_s,
            "device_id": self.device_id,
            "iid": self.iid,
            "openudid": self.openudid,
        }

    def headers(self, *, method: str = "GET") -> dict[str, str]:
        ts_ms = str(int(time.time() * 1000))
        hdrs = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "X-SS-REQ-TICKET": ts_ms,
            "x-ss-dp": TIKTOK_AID,
            "x-bd-kmsv": "0",
            "x-tt-pba-encode": "0020",
            "x-vc-bdturing-sdk-version": "2.4.2.i18n",
            "oec-cs-si-a": "2",
            "oec-cs-sdk-version": "v10.02.11-ov-android_V34",
            "x-tt-request-tag": "n=0;nr=011;bg=0;s=-1;p=0",
            "rpc-persist-pyxis-policy-v-tnc": "1",
            "get-svc": "1",
            "x-tt-store-region": self.store_country_code.lower(),
            "x-tt-store-region-src": "uid",
        }
        if method == "POST":
            hdrs["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        region_code = f"{self.region}|6252001"
        hdrs["rpc-persist-pns-region-1"] = region_code
        hdrs["rpc-persist-pns-region-2"] = region_code
        hdrs["rpc-persist-pns-region-3"] = region_code

        trace_hex = _random_hex(32)
        hdrs["x-tt-trace-id"] = f"00-{trace_hex}-{trace_hex[:16]}-01"

        if self.token:
            hdrs["x-tt-token"] = self.token

        cookie = self.cookie_string()
        if cookie:
            hdrs["Cookie"] = cookie
        return hdrs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IOSDevice":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: str) -> None:
        import os
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "IOSDevice":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def load_session_env(self, path: str = "~/.secrets.env") -> None:
        """Load session credentials from env file.

        Tries TIKTOK_IOS_* keys first (a distinct iOS session/device can
        coexist with the Android one in the same secrets file), then falls
        back to the plain Android TIKTOK_*/TK_* keys."""
        import os
        path = os.path.expanduser(path)
        secrets: dict[str, str] = {}
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    if v.startswith("'") and v.endswith("'"):
                        v = v[1:-1]
                    secrets[k] = v
        except FileNotFoundError:
            return

        def pick(ios_key: str, android_key: str) -> str:
            return secrets.get(ios_key) or secrets.get(android_key) or ""

        # Whether a dedicated iOS session exists in this env file.
        _has_ios = bool(
            secrets.get("TIKTOK_IOS_COOKIE_STRING")
            or secrets.get("TIKTOK_IOS_SESSIONID")
        )
        # Bind to the iOS session's own device FIRST (a session is device-bound;
        # __post_init__ made a random device_id we must override). Do this before
        # any TK_*/Android fallback so it can't clobber the right device.
        if _has_ios:
            _did = secrets.get("TIKTOK_IOS_SAFEMODE_CACHE_DEVICE_ID") or secrets.get("TIKTOK_IOS_DEVICE_ID")
            if _did:
                self.device_id = _did
            if secrets.get("TIKTOK_IOS_INSTALL_ID"):
                self.install_id = secrets["TIKTOK_IOS_INSTALL_ID"]
                self.iid = self.install_id

        cookie = secrets.get("TIKTOK_IOS_COOKIE_STRING", "")
        if not cookie and secrets.get("TIKTOK_IOS_SESSIONID"):
            # Assemble from individual TIKTOK_IOS_* keys (ios_session_extract.py).
            _ck = {
                "sessionid": secrets.get("TIKTOK_IOS_SESSIONID"),
                "sessionid_ss": secrets.get("TIKTOK_IOS_SESSIONID_SS"),
                "sid_tt": secrets.get("TIKTOK_IOS_SID_TT"),
                "sid_guard": secrets.get("TIKTOK_IOS_SID_GUARD"),
                "uid_tt": secrets.get("TIKTOK_IOS_UID_TT"),
                "odin_tt": secrets.get("TIKTOK_IOS_ODIN_TT"),
                "install_id": secrets.get("TIKTOK_IOS_INSTALL_ID"),
                "store-idc": secrets.get("TIKTOK_IOS_STORE_IDC"),
                "ttreq": secrets.get("TIKTOK_IOS_TTREQ"),
                "cmpl_token": secrets.get("TIKTOK_IOS_CMPL_TOKEN"),
                "msToken": secrets.get("TIKTOK_IOS_MSTOKEN"),
            }
            cookie = "; ".join(f"{k}={v}" for k, v in _ck.items() if v)
        if not cookie:
            cookie = secrets.get("TIKTOK_COOKIE_STRING", "")  # Android fallback
        if cookie:
            self.import_cookies(cookie)

        # For token/signing params, never fall back to Android TIKTOK_*/TK_* keys
        # when an iOS session is present — a stale Android X-Tt-Token would be
        # sent alongside the iOS session and trigger Login expired (code=8).
        def pick_tok(ios_key: str, android_key: str) -> str:
            if _has_ios:
                return secrets.get(ios_key) or ""
            return secrets.get(ios_key) or secrets.get(android_key) or ""

        token = pick_tok("TIKTOK_IOS_X_TT_TOKEN", "TIKTOK_X_TT_TOKEN")
        if token:
            self.token = token
        ts_sign = pick_tok("TIKTOK_IOS_TS_SIGN", "TIKTOK_TS_SIGN")
        if ts_sign:
            self.ts_sign = ts_sign
        device_token = pick_tok("TIKTOK_IOS_DEVICE_TOKEN", "TIKTOK_DEVICE_TOKEN")
        if device_token:
            self.device_token = device_token
        dtoken_sign = pick_tok("TIKTOK_IOS_DTOKEN_SIGN", "TIKTOK_DTOKEN_SIGN")
        if dtoken_sign:
            self.dtoken_sign = dtoken_sign
        # TK_* device fallback — only when an iOS session device wasn't already
        # loaded above (TK_DEVICE_ID may belong to a different, e.g. Android,
        # device and would break a TIKTOK_IOS_* session bound to its own device).
        if not secrets.get("TIKTOK_IOS_SAFEMODE_CACHE_DEVICE_ID") and not secrets.get("TIKTOK_IOS_DEVICE_ID"):
            device_id = pick("TK_IOS_DEVICE_ID", "TK_DEVICE_ID")
            if device_id:
                self.device_id = device_id
            install_id = pick("TK_IOS_INSTALL_ID", "TK_INSTALL_ID")
            if install_id:
                self.install_id = install_id
                self.iid = install_id

    def import_cookies(self, cookie_string: str) -> None:
        """Import cookies from a raw cookie header or TTNetCookieStore XML."""
        self._raw_cookies = cookie_string.strip()
        for part in cookie_string.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            key, _, value = part.partition("=")
            key = key.strip()
            value = value.strip()
            mapping = {
                "sessionid": "session_id",
                "sessionid_ss": "session_id",
                "sid_tt": "sid_tt",
                "uid_tt": "uid_tt",
                "odin_tt": "odin_tt",
                "msToken": "msToken",
                "d_ticket": "d_ticket",
                "cmpl_token": "cmpl_token",
                "sid_guard": "sid_guard",
                "multi_sids": "multi_sids",
                "install_id": "install_id",
                "ttreq": "ttreq",
                "store-country-code": "store_country_code",
            }
            attr = mapping.get(key)
            if attr and value:
                setattr(self, attr, value)

    def save_session_env(self, path: str = "~/.secrets.env") -> None:
        """Persist current session credentials to env file under TIKTOK_IOS_*
        keys (update in-place) so it doesn't clobber an Android session."""
        import os, re
        path = os.path.expanduser(path)
        try:
            with open(path) as f:
                content = f.read()
        except FileNotFoundError:
            content = "# Global secrets — auto-managed\n# DO NOT commit this file to git\n\n"

        updates = {
            "TIKTOK_IOS_COOKIE_STRING": self.cookie_string(),
            "TIKTOK_IOS_X_TT_TOKEN": self.token,
            "TK_IOS_DEVICE_ID": self.device_id,
            "TK_IOS_INSTALL_ID": self.install_id,
        }
        if self.ts_sign:
            updates["TIKTOK_IOS_TS_SIGN"] = self.ts_sign
        if self.device_token:
            updates["TIKTOK_IOS_DEVICE_TOKEN"] = self.device_token

        for key, value in updates.items():
            if not value:
                continue
            pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
            if pattern.search(content):
                content = pattern.sub(f"{key}={value}", content)
            else:
                content = content.rstrip("\n") + f"\n{key}={value}\n"

        with open(path, "w") as f:
            f.write(content)
