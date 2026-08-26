"""High-level iOS SDK client: one object, all APIs.

Mirrors tiktokflow/android/client.py. Uses IOSDevice + IOSTransport but
otherwise reuses every Android API module (feed, user, video, upload,
search, comment, social, music, notice, passport, live, dm) as-is — they
only talk to the transport's request()/get()/post(), which is
transport-agnostic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..android.ratelimit import RateLimiter
from ..android.feed import FeedAPI
from ..android.user import UserAPI
from ..android.video import VideoAPI
from ..android.upload import UploadAPI
from ..android.search import SearchAPI
from ..android.comment import CommentAPI
from ..android.social import SocialAPI
from ..android.music import MusicAPI
from ..android.notice import NoticeAPI
from ..android.passport import PassportAPI
from ..android.live import LiveAPI
from ..android.dm import DMAPI
from ..android.effect import EffectAPI
from .device import IOSDevice
from .transport import IOSTransport


class IOSClient:
    """Single entry point for the iOS mobile API.

    Usage:
        device = IOSDevice.load("device_ios.json")
        with IOSClient(device) as tt:
            feed = tt.feed.for_you(count=10)
            profile = tt.user.profile_self()
    """

    def __init__(
        self,
        device: IOSDevice,
        *,
        base_url: str = "",
        timeout: float = 30.0,
        max_retries: int = 3,
        full_sign: bool = True,
        rate_limit: float | None = None,
        rate_limiter: RateLimiter | None = None,
        proxy: str | None = None,
        proxies: list[str] | None = None,
        proxy_rotate: str = "round_robin",
    ):
        kwargs: dict[str, Any] = {"device": device, "timeout": timeout, "max_retries": max_retries, "full_sign": full_sign}
        if base_url:
            kwargs["base_url"] = base_url
        if rate_limit is not None:
            kwargs["rate_limit"] = rate_limit
        if rate_limiter is not None:
            kwargs["rate_limiter"] = rate_limiter
        if proxy is not None:
            kwargs["proxy"] = proxy
        if proxies is not None:
            kwargs["proxies"] = proxies
        if proxy_rotate != "round_robin":
            kwargs["proxy_rotate"] = proxy_rotate
        self.transport = IOSTransport(**kwargs)
        self.device = device

        self.feed = FeedAPI(self.transport)
        self.user = UserAPI(self.transport)
        self.video = VideoAPI(self.transport)
        self.upload = UploadAPI(self.transport)
        self.search = SearchAPI(self.transport)
        self.comment = CommentAPI(self.transport)
        self.social = SocialAPI(self.transport)
        self.music = MusicAPI(self.transport)
        self.notice = NoticeAPI(self.transport)
        self.passport = PassportAPI(self.transport)
        self.live = LiveAPI(self.transport)
        self.dm = DMAPI(self.transport)
        self.effect = EffectAPI(self.transport)

    @property
    def is_authenticated(self) -> bool:
        return self.device.is_authenticated

    def login_email(self, email: str, password: str) -> dict[str, Any]:
        """Login with email/password and capture session cookies."""
        return self.passport.email_login(email, password)

    def login_sms(self, mobile: str, code: str) -> dict[str, Any]:
        """Login with SMS code and capture session cookies."""
        return self.passport.sms_login(mobile, code)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "IOSClient":
        return cls(IOSDevice.load(path), **kwargs)

    @classmethod
    def from_session_env(cls, path: str = "~/.secrets.env", **kwargs) -> "IOSClient":
        """Build a pure-HTTP iOS client from a captured session in an env file.

        Loads TIKTOK_IOS_* cookies + device_id/install_id (as written by
        frida/ios_session_extract.py) and signs requests as that device. Reads
        and normal writes (e.g. follow) work over plain HTTP; no device attached.
        """
        device = IOSDevice()
        device.load_session_env(path)
        return cls(device, **kwargs)
