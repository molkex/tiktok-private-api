"""Android device identity: device_id, install_id, openudid, fingerprint params.

Adapted from _ref/douyin-sign/sign/device.py for TikTok (not Douyin).
Key differences: aid=1233 (TikTok Android), app_name=musically,
domain api16-normal-c-useast2a.tiktokv.com (not api.douyin.com)."""
from __future__ import annotations

import json
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

TIKTOK_AID = "1233"
TIKTOK_APP_NAME = "musical_ly"
TIKTOK_APP_VERSION = "46.5.0"
TIKTOK_VERSION_CODE = "460500"
TIKTOK_MANIFEST_VERSION_CODE = "2024605000"
TIKTOK_CHANNEL = "googleplay"

API_HOST = "api16-normal-c-useast2a.tiktokv.com"
API_BASE = f"https://{API_HOST}"
YCRU_HOST = "api16-normal-ycru.tiktokv.com"
YCRU_BASE = f"https://{YCRU_HOST}"
SEARCH_HOST = "search.tiktokv.com"
SEARCH_BASE = f"https://{SEARCH_HOST}"

DEVICE_REGISTER_URL = "https://log.snssdk.com/service/2/device_register/"

DEVICE_MODELS = [
    "SM-S928B", "SM-S926B", "SM-S916B", "SM-G998B", "SM-A546B",
    "Pixel 9 Pro", "Pixel 8 Pro", "Pixel 8", "Pixel 7",
]
DEVICE_BRANDS = {
    "SM-": "samsung",
    "Pixel": "google",
}
OS_VERSIONS_API = ["30", "31", "32", "33", "34"]


def _random_hex(length: int) -> str:
    return "".join(random.choices("0123456789abcdef", k=length))


def _random_digits(length: int) -> str:
    return "".join(random.choices("0123456789", k=length))


@dataclass
class Device:
    device_id: str = ""
    install_id: str = ""
    iid: str = ""
    openudid: str = ""
    cdid: str = ""
    clientudid: str = ""
    device_type: str = ""
    device_brand: str = ""
    os_version: str = ""
    os_api: str = ""
    app_version: str = TIKTOK_APP_VERSION
    version_code: str = TIKTOK_VERSION_CODE
    manifest_version_code: str = TIKTOK_MANIFEST_VERSION_CODE
    channel: str = TIKTOK_CHANNEL
    resolution: str = "1080x2400"
    dpi: int = 420
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
    bd_client_key: str = ""
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
            self.device_type = random.choice(DEVICE_MODELS)
        if not self.device_brand:
            for prefix, brand in DEVICE_BRANDS.items():
                if self.device_type.startswith(prefix):
                    self.device_brand = brand
                    break
            else:
                self.device_brand = "samsung"
        if not self.os_version:
            self.os_version = "14"
        if not self.os_api:
            self.os_api = random.choice(OS_VERSIONS_API)

    @property
    def user_agent(self) -> str:
        return (
            f"com.zhiliaoapp.musically/{self.manifest_version_code} "
            f"(Linux; U; Android {self.os_version}; {self.language}; "
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
            "device_platform": "android",
            "os": "android",
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
            "os_api": self.os_api,
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
            "host_abi": "arm64-v8a",
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
        if self.opti_ut:
            hdrs["x-opti-ut"] = self.opti_ut
        if self.bd_client_key:
            hdrs["x-bd-client-key"] = self.bd_client_key

        cookie = self.cookie_string()
        if cookie:
            hdrs["Cookie"] = cookie
        return hdrs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Device:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: str) -> None:
        import os
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> Device:
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def load_session_env(self, path: str = "~/.secrets.env") -> None:
        """Load session credentials (cookies, x-tt-token, ts_sign, device_token) from env file."""
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
        if secrets.get("TIKTOK_COOKIE_STRING"):
            self.import_cookies(secrets["TIKTOK_COOKIE_STRING"])
        if secrets.get("TIKTOK_X_TT_TOKEN"):
            self.token = secrets["TIKTOK_X_TT_TOKEN"]
        if secrets.get("TIKTOK_TS_SIGN"):
            self.ts_sign = secrets["TIKTOK_TS_SIGN"]
        if secrets.get("TIKTOK_DEVICE_TOKEN"):
            self.device_token = secrets["TIKTOK_DEVICE_TOKEN"]
        if secrets.get("TIKTOK_DTOKEN_SIGN"):
            self.dtoken_sign = secrets["TIKTOK_DTOKEN_SIGN"]
        if secrets.get("TIKTOK_OPTI_UT"):
            self.opti_ut = secrets["TIKTOK_OPTI_UT"]
        if secrets.get("TIKTOK_BD_CLIENT_KEY"):
            self.bd_client_key = secrets["TIKTOK_BD_CLIENT_KEY"]
        if secrets.get("TK_DEVICE_ID"):
            self.device_id = secrets["TK_DEVICE_ID"]
        if secrets.get("TK_INSTALL_ID"):
            self.install_id = secrets["TK_INSTALL_ID"]
            self.iid = secrets["TK_INSTALL_ID"]

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
        """Persist current session credentials to env file (update in-place)."""
        import os, re
        path = os.path.expanduser(path)
        try:
            with open(path) as f:
                content = f.read()
        except FileNotFoundError:
            content = "# Global secrets — auto-managed\n# DO NOT commit this file to git\n\n"

        updates = {
            "TIKTOK_COOKIE_STRING": self.cookie_string(),
            "TIKTOK_X_TT_TOKEN": self.token,
            "TK_DEVICE_ID": self.device_id,
            "TK_INSTALL_ID": self.install_id,
        }
        if self.ts_sign:
            updates["TIKTOK_TS_SIGN"] = self.ts_sign
        if self.device_token:
            updates["TIKTOK_DEVICE_TOKEN"] = self.device_token
        if self.opti_ut:
            updates["TIKTOK_OPTI_UT"] = self.opti_ut
        if self.bd_client_key:
            updates["TIKTOK_BD_CLIENT_KEY"] = self.bd_client_key

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
