"""iOS mobile API transport: thin subclass of AndroidTransport.

Everything — retries, X-Gorgon/X-Argus/X-Ladon signing, device-guard/
ticket-guard headers, rate limiting, proxy rotation, and the curl_cffi
write-bypass with edge-IP pinning against Janus-Mini(fast)/Envoy SC — is
inherited unchanged from tiktokflow/android/transport.py: none of that logic
is platform-specific, it only depends on device.common_params()/headers().

The one real iOS difference is the TLS fingerprint used for the write-bypass
path: real iOS TikTok traffic looks like Safari/CFNetwork, not Chrome, so we
impersonate "safari18_0_ios" instead of "chrome120" (see the `_impersonate`
attribute added to AndroidTransport.__init__ for this purpose)."""
from __future__ import annotations

from ..android.transport import AndroidTransport
from .device import API_BASE, IOSDevice

IOS_IMPERSONATE = "safari18_0_ios"


class IOSTransport(AndroidTransport):
    """AndroidTransport configured for an IOSDevice + Safari TLS impersonation."""

    def __init__(self, device: IOSDevice, *, base_url: str = API_BASE, **kwargs):
        super().__init__(device, base_url=base_url, **kwargs)
        self._impersonate = IOS_IMPERSONATE
