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
TIKTOK_APP_VERSION = "46.7.3"
TIKTOK_VERSION_CODE = "460703"
TIKTOK_MANIFEST_VERSION_CODE = "2024607030"
TIKTOK_CHANNEL = "googleplay"

API_HOST = "api16-normal-c-useast2a.tiktokv.com"
API_BASE = f"https://{API_HOST}"
YCRU_HOST = "api16-normal-ycru.tiktokv.com"
YCRU_BASE = f"https://{YCRU_HOST}"
SEARCH_HOST = "search.tiktokv.com"
SEARCH_BASE = f"https://{SEARCH_HOST}"

DEVICE_REGISTER_URL = "https://log.snssdk.com/service/2/device_register/"

DEVICE_PROFILES: dict[str, dict] = {
    "SM-S928B":  {"brand": "samsung", "res": "1440x3120", "dpi": 510},
    "SM-S926B":  {"brand": "samsung", "res": "1080x2340", "dpi": 393},
    "SM-S916B":  {"brand": "samsung", "res": "1080x2340", "dpi": 393},
    "SM-S921B":  {"brand": "samsung", "res": "1080x2340", "dpi": 402},
    "SM-G998B":  {"brand": "samsung", "res": "1440x3200", "dpi": 515},
    "SM-A546B":  {"brand": "samsung", "res": "1080x2400", "dpi": 403},
    "SM-A356B":  {"brand": "samsung", "res": "1080x2340", "dpi": 401},
    "SM-A346E":  {"brand": "samsung", "res": "1080x2340", "dpi": 450, "os": "16"},  # Galaxy A34 — REAL ref device (getprop: samsung/a34xdxx/a34x:16/BP4A.251205.006/A346EXXUEFZE6, dpi 450)
    "SM-A156B":  {"brand": "samsung", "res": "1080x2400", "dpi": 393},
    "Pixel 9 Pro":  {"brand": "google", "res": "1280x2856", "dpi": 489},
    "Pixel 9":      {"brand": "google", "res": "1080x2424", "dpi": 422},
    "Pixel 8 Pro":  {"brand": "google", "res": "1344x2992", "dpi": 489},
    "Pixel 8":      {"brand": "google", "res": "1080x2400", "dpi": 428},
    "Pixel 7":      {"brand": "google", "res": "1080x2400", "dpi": 416},
    "Pixel 7a":     {"brand": "google", "res": "1080x2400", "dpi": 429},
    "OnePlus 12":   {"brand": "OnePlus", "res": "1440x3168", "dpi": 525},
    "CPH2581":      {"brand": "OnePlus", "res": "1264x2780", "dpi": 450},
    "22101316G":    {"brand": "Xiaomi",  "res": "1440x3200", "dpi": 522},
    "2312DRA50G":   {"brand": "Xiaomi",  "res": "1220x2712", "dpi": 446},
    "V2254A":       {"brand": "vivo",    "res": "1260x2800", "dpi": 480},
}
DEVICE_MODELS = list(DEVICE_PROFILES.keys())

OS_VERSION_MAP: dict[str, tuple[str, str]] = {
    "12": ("31", "SP1A.210812.016"),
    "13": ("33", "TQ3A.230901.001"),
    "14": ("34", "UP1A.231005.007"),
    "15": ("35", "AP3A.240905.015"),
    "16": ("36", "BP4A.251205.006"),  # real Samsung A34 (SM-A346E) build, 2026
}

CARRIER_PROFILES: list[dict[str, str]] = [
    {"mcc_mnc": "310260", "carrier": "T-Mobile",    "region": "US"},
    {"mcc_mnc": "310410", "carrier": "AT&T",         "region": "US"},
    {"mcc_mnc": "311480", "carrier": "Verizon",      "region": "US"},
    {"mcc_mnc": "310120", "carrier": "Sprint",       "region": "US"},
    {"mcc_mnc": "302720", "carrier": "Rogers",       "region": "CA"},
    {"mcc_mnc": "234150", "carrier": "Vodafone",     "region": "GB"},
    {"mcc_mnc": "234100", "carrier": "EE",           "region": "GB"},
    {"mcc_mnc": "262020", "carrier": "Vodafone DE",  "region": "DE"},
    {"mcc_mnc": "208010", "carrier": "Orange",       "region": "FR"},
    {"mcc_mnc": "222010", "carrier": "Vodafone IT",  "region": "IT"},
    {"mcc_mnc": "214010", "carrier": "Movistar",     "region": "ES"},
    {"mcc_mnc": "440100", "carrier": "docomo",       "region": "JP"},
    {"mcc_mnc": "450050", "carrier": "SK Telecom",   "region": "KR"},
    {"mcc_mnc": "520010", "carrier": "AIS",          "region": "TH"},
    {"mcc_mnc": "510100", "carrier": "Telkomsel",    "region": "ID"},
    {"mcc_mnc": "515020", "carrier": "Globe",        "region": "PH"},
    {"mcc_mnc": "334020", "carrier": "Telcel",       "region": "MX"},
    {"mcc_mnc": "724060", "carrier": "Vivo BR",      "region": "BR"},
    {"mcc_mnc": "410010", "carrier": "Mobilink",     "region": "PK"},
    {"mcc_mnc": "404100", "carrier": "Airtel",       "region": "IN"},
    {"mcc_mnc": "25002",  "carrier": "MegaFon",      "region": "RU"},
    {"mcc_mnc": "25001",  "carrier": "MTS",          "region": "RU"},
    {"mcc_mnc": "25099",  "carrier": "Beeline",      "region": "RU"},
    {"mcc_mnc": "25020",  "carrier": "Tele2",        "region": "RU"},
    {"mcc_mnc": "40101",  "carrier": "Beeline KZ",   "region": "KZ"},
    {"mcc_mnc": "40102",  "carrier": "Kcell",        "region": "KZ"},
    {"mcc_mnc": "40177",  "carrier": "Tele2 KZ",     "region": "KZ"},
    {"mcc_mnc": "40107",  "carrier": "Altel",        "region": "KZ"},
]

# timezone_name -> UTC offset in seconds (matches what TikTok's device params send).
TZ_OFFSET: dict[str, int] = {
    "America/New_York": -14400, "America/Chicago": -18000, "America/Denver": -21600,
    "America/Los_Angeles": -25200, "America/Toronto": -14400, "America/Vancouver": -25200,
    "Europe/London": 3600, "Europe/Berlin": 7200, "Europe/Paris": 7200, "Europe/Rome": 7200,
    "Europe/Madrid": 7200, "Europe/Moscow": 10800, "Asia/Almaty": 18000, "Asia/Tokyo": 32400, "Asia/Seoul": 32400,
    "Asia/Bangkok": 25200, "Asia/Jakarta": 25200, "Asia/Manila": 28800, "America/Mexico_City": -21600,
    "America/Sao_Paulo": -10800, "Asia/Karachi": 18000, "Asia/Kolkata": 19800,
}

# device_model -> hardware (SoC/ABI/ROM) so register carries real chipset fields
# instead of "unknown". Keyed by exact model, with a samsung/pixel fallback.
SOC_MAP: dict[str, dict[str, str]] = {
    "SM-A346E": {"soc": "mt6877", "board": "mt6877", "rom": "ONEUI",
                 "abilist": "arm64-v8a,armeabi-v7a,armeabi",
                 "rom_version": "A346EXXUEFZE6"},  # Dimensity 900 (real A34, getprop-verified)
}
_SOC_DEFAULT_SAMSUNG = {"soc": "exynos", "board": "universal", "rom": "ONEUI",
                        "abilist": "arm64-v8a,armeabi-v7a,armeabi"}
_SOC_DEFAULT_PIXEL = {"soc": "tensor", "board": "tensor", "rom": "",
                      "abilist": "arm64-v8a,armeabi-v7a,armeabi"}

TIMEZONE_MAP: dict[str, list[str]] = {
    "US": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"],
    "CA": ["America/Toronto", "America/Vancouver"],
    "GB": ["Europe/London"],
    "DE": ["Europe/Berlin"],
    "FR": ["Europe/Paris"],
    "IT": ["Europe/Rome"],
    "ES": ["Europe/Madrid"],
    "JP": ["Asia/Tokyo"],
    "KR": ["Asia/Seoul"],
    "TH": ["Asia/Bangkok"],
    "ID": ["Asia/Jakarta"],
    "PH": ["Asia/Manila"],
    "MX": ["America/Mexico_City"],
    "BR": ["America/Sao_Paulo"],
    "PK": ["Asia/Karachi"],
    "IN": ["Asia/Kolkata"],
    "RU": ["Europe/Moscow"],
    "KZ": ["Asia/Almaty"],
}

# Cronet build + date and the tt-ok (TTNet-over-OkHttp) wrapper version, as
# they appear in the User-Agent header. The Cronet pair is sourced from a
# real, recent device_register capture in this repo
# (frida/startup_capture.log: "cronet_version=45466851_2026-07-20").
# tt-ok/3.12.13.4-tiktok is sourced from an older real capture
# (tests/test_real_url.py's REAL_UA) — TikTok bumps this occasionally, so
# treat it as a best-effort value to refresh from a fresh capture rather
# than an exact constant.
UA_CRONET_BUILD = "45466851"
UA_CRONET_DATE = "2026-07-20"
UA_TTOK_VERSION = "3.12.13.4"


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
    build_id: str = ""
    app_version: str = TIKTOK_APP_VERSION
    version_code: str = TIKTOK_VERSION_CODE
    manifest_version_code: str = TIKTOK_MANIFEST_VERSION_CODE
    channel: str = TIKTOK_CHANNEL
    resolution: str = "1080x2400"
    dpi: int = 420
    language: str = "en"
    region: str = "US"
    carrier: str = ""
    mcc_mnc: str = ""
    timezone_name: str = ""
    timezone_offset: int = 0
    rom: str = ""
    rom_version: str = ""
    cpu_abi: str = "arm64-v8a"
    cpu_abilist: str = ""
    soc: str = ""
    google_aid: str = ""
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
    ttwid: str = ""
    sid_ucp_v1: str = ""
    ssid_ucp_v1: str = ""
    passport_csrf_token: str = ""
    dtoken_sign: str = ""
    ts_sign: str = ""
    opti_ut: str = ""
    bd_client_key: str = ""
    last_install_time: int = 0
    mssdk_seed: str = ""
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
        profile = DEVICE_PROFILES.get(self.device_type, {})
        if not self.device_brand:
            self.device_brand = profile.get("brand", "samsung")
        if self.resolution == "1080x2400" and profile.get("res"):
            self.resolution = profile["res"]
        if self.dpi == 420 and profile.get("dpi"):
            self.dpi = profile["dpi"]
        if not self.os_version:
            self.os_version = profile.get("os") or random.choice(["14", "14", "15", "15", "16"])
        os_info = OS_VERSION_MAP.get(self.os_version, ("34", "UP1A.231005.007"))
        if not self.os_api:
            self.os_api = os_info[0]
        if not self.build_id:
            self.build_id = os_info[1]
        matching_carriers = [c for c in CARRIER_PROFILES if c["region"] == self.region]
        carrier_profile = (random.choice(matching_carriers) if matching_carriers else random.choice(CARRIER_PROFILES)) if not self.mcc_mnc else None
        if not self.mcc_mnc and carrier_profile:
            self.mcc_mnc = carrier_profile["mcc_mnc"]
        if not self.carrier and carrier_profile:
            self.carrier = carrier_profile["carrier"]
        if not self.store_country_code:
            self.store_country_code = self.region
        # Geo-consistent timezone (was hardcoded America/New_York in register.py —
        # a glaring mismatch on a non-US device/account).
        if not self.timezone_name:
            self.timezone_name = random.choice(TIMEZONE_MAP.get(self.region, ["America/New_York"]))
        if not self.timezone_offset:
            self.timezone_offset = TZ_OFFSET.get(self.timezone_name, 0)
        # Real chipset/ROM/ABI so register carries hardware fields, not "unknown".
        hw = SOC_MAP.get(self.device_type) or (
            _SOC_DEFAULT_PIXEL if self.device_brand == "google" else _SOC_DEFAULT_SAMSUNG)
        if not self.soc:
            self.soc = hw["soc"]
        if not self.cpu_abilist:
            self.cpu_abilist = hw.get("abilist", self.cpu_abi)
        if not self.rom:
            self.rom = hw.get("rom", "")
        if not self.rom_version:
            self.rom_version = hw.get("rom_version", "")
        if not self.google_aid:
            self.google_aid = str(uuid.uuid4())
        if not self.last_install_time:
            self.last_install_time = int(time.time()) - random.randint(86400, 2592000)
        if not self.mssdk_seed:
            import struct
            self.mssdk_seed = struct.pack(">I", self.last_install_time).hex()
        # Non-field attribute: persistent HTTP client for state-drop Fix A (audit f002812)
        self._http_client = None

    @property
    def persistent_client(self):
        """Lazy persistent httpx.Client (http2=True) scoped to this Device.
        Opt-in only — audit f002812 Fix A."""
        import httpx as _httpx
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = _httpx.Client(http2=True)
        return self._http_client

    def close_client(self) -> None:
        """Close the persistent HTTP client if open."""
        if self._http_client is not None and not self._http_client.is_closed:
            self._http_client.close()
            self._http_client = None

    @property
    def user_agent(self) -> str:
        # Format matches a real captured genuine-app UA (tests/test_real_url.py
        # REAL_UA / frida/startup_capture.log), which previously diverged in
        # several ways: it used manifest_version_code (a 10-digit build
        # number) instead of version_code as the leading version, dropped the
        # "_{region}" suffix on locale, invented a "QuicVersion:..." segment
        # the real UA does not have, and omitted the trailing "tt-ok/x-tiktok"
        # TTNet-wrapper tag every real client sends.
        return (
            f"com.zhiliaoapp.musically/{self.version_code} "
            f"(Linux; U; Android {self.os_version}; {self.language}_{self.region}; "
            f"{self.device_type}; Build/{self.build_id}; "
            f"Cronet/TTNetVersion:{UA_CRONET_BUILD} {UA_CRONET_DATE}; "
            f"tt-ok/{UA_TTOK_VERSION}-tiktok)"
        )

    @property
    def resolution_qs(self) -> str:
        """Resolution with a '*' separator ("1080*2400"), as sent in query
        strings and the device_register JSON body. We store WxH internally
        for readability; every real capture (frida/startup_capture.log,
        tests/test_isolate_fix.py) uses '*', never 'x'."""
        return self.resolution.replace("x", "*")

    @property
    def carrier_region_v2(self) -> str:
        return self.mcc_mnc[:3] if len(self.mcc_mnc) >= 3 else ""

    @property
    def _timezone_name(self) -> str:
        # Prefer the stored, geo-consistent value set in __post_init__ (same one
        # register.py sends) so register and later requests never disagree.
        if self.timezone_name:
            return self.timezone_name
        zones = TIMEZONE_MAP.get(self.region, ["America/New_York"])
        return zones[0]

    @property
    def _timezone_offset(self) -> int:
        if self.timezone_offset:
            return self.timezone_offset
        return TZ_OFFSET.get(self._timezone_name, -14400)

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
        if self.ttwid:
            parts.append(f"ttwid={self.ttwid}")
        if self.sid_ucp_v1:
            parts.append(f"sid_ucp_v1={self.sid_ucp_v1}")
        if self.ssid_ucp_v1:
            parts.append(f"ssid_ucp_v1={self.ssid_ucp_v1}")
        if self.passport_csrf_token:
            parts.append(f"passport_csrf_token={self.passport_csrf_token}")
            parts.append(f"passport_csrf_token_default={self.passport_csrf_token}")
        parts.append(f"store-country-code={self.store_country_code}")
        parts.append("store-country-code-src=uid")
        parts.append("store-idc=useast2a")
        parts.append("tt-target-idc=useast2a")
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
            if "ttwid" in cookies:
                self.ttwid = cookies["ttwid"]
            if "sid_ucp_v1" in cookies:
                self.sid_ucp_v1 = cookies["sid_ucp_v1"]
            if "ssid_ucp_v1" in cookies:
                self.ssid_ucp_v1 = cookies["ssid_ucp_v1"]
            if "passport_csrf_token" in cookies:
                self.passport_csrf_token = cookies["passport_csrf_token"]
            if "msToken" in cookies:
                self.msToken = cookies["msToken"]
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
            "resolution": self.resolution_qs,
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
            "last_install_time": str(self.last_install_time),
            "mcc_mnc": self.mcc_mnc,
            "timezone_name": self._timezone_name,
            "carrier_region_v2": self.carrier_region_v2,
            "app_language": self.language,
            "carrier_region": self.region,
            "timezone_offset": str(self._timezone_offset),
            "host_abi": "arm64-v8a",
            "locale": self.language,
            "ac2": "unknown",
            "uoo": "1",
            "op_region": self.region,
            "build_number": self.app_version,
            "region": self.region,
            "ts": ts_s,
            "device_id": self.device_id,
            "iid": self.iid,
            "openudid": self.openudid,
            "uuid": self.openudid,
            "current_region": self.region,
            "residence": self.region,
        }

    def headers(self, *, method: str = "GET") -> dict[str, str]:
        ts_ms = str(int(time.time() * 1000))
        trace_hex = _random_hex(32)
        region_code = f"{self.region}|6252001"

        tag_nr = random.choice(["011", "010", "001", "000"])
        tag_s = random.choice(["-1", "0", "1"])
        req_tag = f"n=0;nr={tag_nr};bg=0;s={tag_s};p=0"

        from collections import OrderedDict
        hdrs = OrderedDict()

        if self.token:
            hdrs["x-tt-token"] = self.token
        hdrs["x-tt-trace-id"] = f"00-{trace_hex}-{trace_hex[:16]}-01"
        hdrs["X-SS-REQ-TICKET"] = ts_ms
        hdrs["x-ss-dp"] = TIKTOK_AID
        hdrs["x-bd-kmsv"] = "0"
        hdrs["x-tt-pba-encode"] = "0020"
        hdrs["x-vc-bdturing-sdk-version"] = "2.4.2.i18n"
        hdrs["oec-cs-si-a"] = "2"
        hdrs["oec-cs-sdk-version"] = "v10.02.11-ov-android_V34"
        hdrs["x-tt-request-tag"] = req_tag
        hdrs["rpc-persist-pyxis-policy-v-tnc"] = "1"
        hdrs["get-svc"] = "1"
        hdrs["x-tt-store-region"] = self.store_country_code.lower()
        hdrs["x-tt-store-region-src"] = "uid"
        if method == "POST":
            hdrs["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        hdrs["rpc-persist-pns-region-1"] = region_code
        hdrs["rpc-persist-pns-region-2"] = region_code
        hdrs["rpc-persist-pns-region-3"] = region_code
        if self.opti_ut:
            hdrs["x-opti-ut"] = self.opti_ut
        if self.bd_client_key:
            hdrs["x-bd-client-key"] = self.bd_client_key
        hdrs["sdk-version"] = "2"
        hdrs["passport-sdk-version"] = "1"
        hdrs["User-Agent"] = self.user_agent
        hdrs["Accept-Encoding"] = "gzip, deflate"
        cookie = self.cookie_string()
        if cookie:
            hdrs["Cookie"] = cookie
        return dict(hdrs)

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

    @classmethod
    def mint(
        cls,
        *,
        region: str = "US",
        language: str = "en",
        device_type: str | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> Device:
        """Mint a fresh unique Android device and register it with TikTok servers.

        Generates fresh hardware fingerprints, unique IDs (openudid, cdid, clientudid, google_aid),
        cohesive carrier and timezone attributes, and invokes TikTok's /service/2/device_register/
        to acquire authentic, server-assigned device_id, install_id, and device_token.
        """
        from .register import register_device

        seed = cls(
            device_id="0",
            install_id="0",
            iid="0",
            region=region,
            language=language,
            device_type=device_type or "",
        )
        registered = register_device(device=seed, proxy=proxy, timeout=timeout)
        return registered

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
        import os
        import re
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
