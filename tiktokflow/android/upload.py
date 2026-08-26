"""Video/photo upload for the hosted TikTok API.

The mobile upload pipeline (ByteDance VOD/ImageX apply/commit signing + the
create/aweme publish call) runs server-side in the hosted signing service, the
same way request signing does — you never handle the upload internals locally.
Call `upload_video()` / `upload_photo()` with a normal client and the hosted
backend performs the full flow and returns the created aweme.

This public package ships the interface only; the signing/upload internals are
kept server-side.
"""
from __future__ import annotations

from typing import Any, Iterable

from ..errors import InvalidRequest
from .transport import AndroidTransport

UPLOAD_AUTHKEY = "/aweme/v1/upload/authkey/"
CREATE_AWEME = "/aweme/v1/create/aweme/"
CREATE_PHOTO = "/aweme/v1/create/photo/"

# Kept for backward import compatibility with async_endpoints.py.
CHUNK = 10 * 1024 * 1024
MIN_SINGLE_CHUNK = 5 * 1024 * 1024
UPLOAD_VIDEO_INIT = "/aweme/v1/upload/video/"
UPLOAD_IMAGE_INIT = "/aweme/v1/upload/image/"
_UPLOAD_URL_KEYS = ("upload_url", "video_upload_url", "url")
_UPLOAD_ID_KEYS = ("upload_id", "video_id", "vid")

_HOSTED = (
    "Uploading runs on the hosted signing service. Use a hosted client "
    "(TikTokAPI(api_key=...)) — the upload pipeline is performed server-side. "
    "See https://github.com/molkex/tiktok-private-api#get-access"
)


def _extract(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for k in keys:
        v = data.get(k)
        if v:
            return str(v)
    return ""


def _chunking(size: int) -> tuple[int, int]:
    if size <= MIN_SINGLE_CHUNK:
        return size, 1
    return CHUNK, max(1, size // CHUNK)


def _build_text(title: str, hashtags: Iterable[str]) -> str:
    tags = " ".join(f"#{h.lstrip('#')}" for h in hashtags if h)
    return f"{title} {tags}".strip() if tags else title


class UploadAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def creator_info(self) -> "dict[str, Any]":
        """Upload/posting configuration the app fetches before composing."""
        return self._t.get(UPLOAD_AUTHKEY, bare=True)

    def upload_video(self, path: str, *, title: str, hashtags: Iterable[str] = (),
                     music_id: str = "", privacy: int = 0, disable_comment: bool = False,
                     disable_duet: bool = False, disable_stitch: bool = False,
                     cover_ts_ms: int = 0) -> dict[str, Any]:
        """Upload and publish a video. Performed server-side by the hosted service."""
        raise InvalidRequest(_HOSTED)

    def upload_photo(self, paths: list[str], *, title: str, hashtags: Iterable[str] = (),
                     music_id: str = "", privacy: int = 0, cover_index: int = 0,
                     disable_comment: bool = False) -> dict[str, Any]:
        """Upload and publish a photo carousel. Performed server-side."""
        raise InvalidRequest(_HOSTED)
