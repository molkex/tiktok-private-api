"""High-level Android SDK client: one object, all APIs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .device import Device
from .ratelimit import RateLimiter
from .transport import AndroidTransport
from .feed import FeedAPI
from .user import UserAPI
from .video import VideoAPI
from .upload import UploadAPI
from .search import SearchAPI
from .comment import CommentAPI
from .social import SocialAPI
from .music import MusicAPI
from .notice import NoticeAPI
from .passport import PassportAPI
from .live import LiveAPI
from .dm import DMAPI
from .effect import EffectAPI
try:
    from .activation import activate_device, ActivationResult
    _HAS_ACTIVATION = True
except ImportError:
    _HAS_ACTIVATION = False


class AndroidClient:
    """Single entry point for the Android mobile API.

    Usage:
        device = Device.load("device.json")
        with AndroidClient(device) as tt:
            feed = tt.feed.for_you(count=10)
            profile = tt.user.profile_self()
    """

    def __init__(
        self,
        device: Device,
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
        signer: Any | None = None,
        ttnet_pid: int | None = None,
    ):
        kwargs: dict[str, Any] = {"device": device, "timeout": timeout, "max_retries": max_retries, "full_sign": full_sign}
        if signer is not None:
            kwargs["signer"] = signer
        if ttnet_pid is not None:
            kwargs["ttnet_pid"] = ttnet_pid
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
        self.transport = AndroidTransport(**kwargs)
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

    def refresh_session(self) -> bool:
        """Try to refresh expired session via passport/token/beat.
        Returns True if refresh succeeded and session is valid."""
        try:
            result = self.passport.token_beat()
            if isinstance(result, dict) and result.get("status_code") == 0:
                data = result.get("data", {})
                if data.get("token"):
                    self.device.token = data["token"]
                if data.get("cookies"):
                    self.device.update_session(data, data.get("cookies", {}))
                self.device.save_session_env()
                return True
        except Exception:
            pass
        return False

    def close(self) -> None:
        self.transport.close()
        if self.transport._ttnet_bridge:
            self.transport._ttnet_bridge.stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def activate(self, *, timeout: float = 15.0) -> "ActivationResult":
        """Run the full device activation sequence.

        Discovers runtime host, sends dsign, runs MSSDK handshake.
        If a runtime host is discovered, updates the transport base_url.
        """
        if not _HAS_ACTIVATION:
            raise RuntimeError("activation requires the full package with signing modules")
        result = activate_device(self.device, timeout=timeout)
        if result.runtime_host:
            self.transport.base_url = f"https://{result.runtime_host}"
        return result

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "AndroidClient":
        return cls(Device.load(path), **kwargs)

    @classmethod
    def from_emulator(
        cls,
        *,
        device_serial: str = "emulator-5554",
        load_env: bool = False,
        use_app_session: bool = True,
        **kwargs,
    ) -> "AndroidClient":
        """Create client connected to a running TikTok instance on an Android emulator.

        Auto-detects TikTok PID and routes requests through the app's own TTNet
        (Cronet) stack, bypassing Janus/SC.

        When ``use_app_session`` is True (default) the client sends NO Cookie
        header, so the emulator app's native CookieManager supplies the logged-in
        session. Device fingerprint, session and signing are then all the app's
        own and fully consistent — this is what makes auth reads AND SC-protected
        writes (like/comment/follow) work reliably at ~0.8s. Requires the emulator
        app to be logged in.

        Set ``use_app_session=False`` + ``load_env=True`` to instead drive a
        Python-side session (device-bound to whatever created it).
        """
        import subprocess
        pid = int(subprocess.check_output(
            ["adb", "-s", device_serial, "shell", "pidof", "com.zhiliaoapp.musically"],
            text=True, timeout=5,
        ).strip())

        device = Device()
        if load_env and not use_app_session:
            device.load_session_env()
        if use_app_session:
            # No injected cookies — let the app's native session authenticate.
            device._raw_cookies = ""
            device.session_id = ""
            device.sid_tt = ""
        kwargs.setdefault("base_url", "https://api-h2.tiktokv.com")
        kwargs.setdefault("full_sign", True)
        return cls(device, ttnet_pid=pid, **kwargs)
