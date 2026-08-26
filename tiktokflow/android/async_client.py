"""Async high-level Android SDK client: one object, all APIs.

Drop-in async replacement for :class:`AndroidClient`. Same constructor
arguments, same attribute names — just use ``async with`` and ``await``::

    device = Device.load("device.json")
    async with AsyncAndroidClient(device) as tt:
        feed = await tt.feed.for_you(count=10)
        profile = await tt.user.profile_self()
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .async_endpoints import (
    AsyncCommentAPI,
    AsyncDMAPI,
    AsyncEffectAPI,
    AsyncFeedAPI,
    AsyncLiveAPI,
    AsyncMusicAPI,
    AsyncNoticeAPI,
    AsyncPassportAPI,
    AsyncSearchAPI,
    AsyncSocialAPI,
    AsyncUploadAPI,
    AsyncUserAPI,
    AsyncVideoAPI,
)
from .async_transport import AsyncAndroidTransport
from .device import Device
from .ratelimit import RateLimiter


class AsyncAndroidClient:
    """Async entry point for the Android mobile API.

    Usage::

        device = Device.load("device.json")
        async with AsyncAndroidClient(device) as tt:
            feed = await tt.feed.for_you(count=10)
            profile = await tt.user.profile_self()
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
    ):
        kwargs: dict[str, Any] = {
            "device": device, "timeout": timeout,
            "max_retries": max_retries, "full_sign": full_sign,
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

        self.transport = AsyncAndroidTransport(**kwargs)
        self.device = device

        self.feed = AsyncFeedAPI(self.transport)
        self.user = AsyncUserAPI(self.transport)
        self.video = AsyncVideoAPI(self.transport)
        self.upload = AsyncUploadAPI(self.transport)
        self.search = AsyncSearchAPI(self.transport)
        self.comment = AsyncCommentAPI(self.transport)
        self.social = AsyncSocialAPI(self.transport)
        self.music = AsyncMusicAPI(self.transport)
        self.notice = AsyncNoticeAPI(self.transport)
        self.passport = AsyncPassportAPI(self.transport)
        self.live = AsyncLiveAPI(self.transport)
        self.dm = AsyncDMAPI(self.transport)
        self.effect = AsyncEffectAPI(self.transport)

    @property
    def is_authenticated(self) -> bool:
        return self.device.is_authenticated

    async def login_email(self, email: str, password: str) -> dict[str, Any]:
        """Login with email/password and capture session cookies."""
        return await self.passport.email_login(email, password)

    async def login_sms(self, mobile: str, code: str) -> dict[str, Any]:
        """Login with SMS code and capture session cookies."""
        return await self.passport.sms_login(mobile, code)

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "AsyncAndroidClient":
        return cls(Device.load(path), **kwargs)
