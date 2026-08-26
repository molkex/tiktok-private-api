"""iOS mobile API layer: iOS device fingerprint + transport, Android signing/guard reused.

Alternative path alongside tiktokflow/android — same aweme/v1 endpoints, same
X-Gorgon/X-Argus/X-Ladon signing (tiktokflow/android/signing.py) and
device-guard/ticket-guard (tiktokflow/android/guard.py), just an iPhone
device identity and a Safari-flavored curl_cffi TLS fingerprint instead of
Chrome's for the write-bypass path."""
from .device import IOSDevice
from .transport import IOSTransport
from .client import IOSClient

__all__ = ["IOSDevice", "IOSTransport", "IOSClient"]
