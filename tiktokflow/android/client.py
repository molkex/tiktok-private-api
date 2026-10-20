"""High-level Android SDK client (public, hosted-signing).

Thin wrapper around :class:`AndroidTransport` that wires the per-endpoint
API classes. All signing is delegated to :class:`RemoteSigner` running
against the hosted signing service — pass one in via ``signer=``.
"""
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


class AndroidClient:
    """Single entry point for the Android mobile API.

    Usage::

        from tiktokflow import TikTokAPI
        api = TikTokAPI(api_key="sk_...", signing_server="https://sign.example.com")
        feed = api.feed.for_you(count=10)
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
        **_ignored: Any,
    ):
        if signer is None:
            raise ValueError(
                "AndroidClient requires a signer (RemoteSigner). "
                "Use tiktokflow.TikTokAPI(api_key=..., signing_server=...) "
                "to construct a client with a wired-up signer."
            )
        self._signer = signer

        kwargs: dict[str, Any] = {
            "device": device,
            "timeout": timeout,
            "max_retries": max_retries,
            "full_sign": full_sign,
            "signer": signer,
        }
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

    @property
    def is_authenticated(self) -> bool:
        return self.device.is_authenticated

    def login_email(self, email: str, password: str) -> dict[str, Any]:
        """Login with email/password and capture session cookies."""
        return self.passport.email_login(email, password)

    def login_sms(self, mobile: str, code: str) -> dict[str, Any]:
        """Login with SMS code and capture session cookies."""
        return self.passport.sms_login(mobile, code)

    def register_sms(
        self, mobile: str, code: str, *,
        password: str | None = None, captcha: str | None = None,
    ) -> dict[str, Any]:
        """Register a new account with phone number and SMS code."""
        return self.passport.mobile_register(
            mobile, code, password=password, captcha=captcha,
        )

    def send_sms_code(
        self, mobile: str, *, scene: str = "register",
        captcha: str | None = None,
    ) -> dict[str, Any]:
        """Request SMS verification code for registration or login."""
        return self.passport.send_sms_code(mobile, scene=scene, captcha=captcha)

    def setup_totp(self) -> dict[str, Any]:
        """Initiate TOTP enrollment (returns shared secret and URI)."""
        return self.passport.totp_register()

    def confirm_totp(self, code: str) -> dict[str, Any]:
        """Confirm and activate TOTP using the 6-digit authenticator code."""
        bind_res = self.passport.totp_bind_verify(code)
        if bind_res.get("message") == "success" or \
                bind_res.get("data", {}).get("error_code") == 0:
            try:
                self.passport.totp_enable_2sv()
            except Exception:
                pass
        return bind_res

    def set_username(self, username: str) -> dict[str, Any]:
        """Change public account handle (@username)."""
        return self.user.set_unique_id(username)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "AndroidClient":
        return cls(Device.load(path), **kwargs)

    @classmethod
    def from_session(
        cls,
        sessionid: str,
        cookies: dict[str, str] | str | None = None,
        *,
        device: Device | None = None,
        user_id: str | None = None,
        signer: Any | None = None,
        **client_kwargs: Any,
    ) -> "AndroidClient":
        """Build an authenticated client from an existing TikTok session.

        A fresh ``Device`` is minted via ``register_device`` when
        ``device`` is not supplied, which requires a ``signer`` just like
        the client itself.
        """
        if not sessionid:
            raise ValueError("from_session requires a non-empty sessionid")

        sign = signer or client_kwargs.get("signer")

        if device is None:
            from .register import register_device
            device = register_device(signer=sign)

        cookie_str: str | None = None
        if isinstance(cookies, dict):
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
        elif isinstance(cookies, str):
            cookie_str = cookies.strip() or None

        if cookie_str and "sessionid=" not in cookie_str:
            cookie_str = f"sessionid={sessionid}; " + cookie_str
        elif not cookie_str:
            cookie_str = f"sessionid={sessionid}; sessionid_ss={sessionid}"

        device.import_cookies(cookie_str)
        if not device.session_id:
            device.session_id = sessionid
        if user_id:
            device.user_id = str(user_id)

        if signer is not None and "signer" not in client_kwargs:
            client_kwargs["signer"] = signer
        return cls(device, **client_kwargs)
