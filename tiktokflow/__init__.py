"""tiktok-private-api — Unofficial TikTok Private API SDK for Python."""
from .errors import TikTokError, AuthError, RateLimitError, InvalidRequest, ServerError

__version__ = "0.4.3"

def TikTokAPI(
    api_key: str,
    *,
    signing_server: str = "http://151.80.58.79:8642",
    platform: str = "android",
    proxy: str | None = None,
    proxies: list[str] | None = None,
    proxy_rotate: str = "round_robin",
    rate_limit: float | None = None,
    device=None,
    timeout: float = 30.0,
):
    """Create a TikTok API client.

    Args:
        api_key: Signing server API key (get at tiktok-private-api.com)
        signing_server: Signing server URL (default: official server)
        platform: "android" or "ios"
        proxy: SOCKS5/HTTP proxy URL
        proxies: List of proxy URLs for rotation
        rate_limit: Max requests per second
        device: Device object (for session persistence)
        timeout: Request timeout in seconds
    """
    from .android.remote_signer import RemoteSigner
    from .android.device import Device

    if device is None:
        device = Device()

    signer = RemoteSigner(signing_server, api_key, timeout=min(timeout, 10.0))

    if platform == "ios":
        from .ios.client import IOSClient
        return IOSClient(device, signer=signer, proxy=proxy, proxies=proxies,
                        proxy_rotate=proxy_rotate, rate_limit=rate_limit, timeout=timeout)

    from .android.client import AndroidClient
    return AndroidClient(device, signer=signer, proxy=proxy, proxies=proxies,
                        proxy_rotate=proxy_rotate, rate_limit=rate_limit, timeout=timeout)

__all__ = ["TikTokAPI", "TikTokError", "AuthError", "RateLimitError", "InvalidRequest", "ServerError"]
