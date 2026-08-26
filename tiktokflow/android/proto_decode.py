"""Generic protobuf decoder for TikTok API responses.

TikTok v2 endpoints return application/x-protobuf instead of JSON.
This module decodes raw protobuf into nested dicts keyed by field number."""
from __future__ import annotations

from typing import Any

from google.protobuf.internal.decoder import _DecodeVarint


def decode_raw(data: bytes, max_depth: int = 8, _depth: int = 0) -> dict[int, list[Any]]:
    """Decode raw protobuf bytes into {field_num: [values]}."""
    result: dict[int, list[Any]] = {}
    pos = 0
    while pos < len(data):
        try:
            tag, new_pos = _DecodeVarint(data, pos)
        except Exception:
            break
        field_num = tag >> 3
        wire_type = tag & 0x7
        pos = new_pos

        if wire_type == 0:
            val, pos = _DecodeVarint(data, pos)
            result.setdefault(field_num, []).append(val)
        elif wire_type == 1:
            val = int.from_bytes(data[pos:pos + 8], "little")
            pos += 8
            result.setdefault(field_num, []).append(val)
        elif wire_type == 2:
            length, pos = _DecodeVarint(data, pos)
            chunk = data[pos:pos + length]
            pos += length
            try:
                text = chunk.decode("utf-8")
                if all(c.isprintable() or c in "\n\r\t" for c in text):
                    result.setdefault(field_num, []).append(text)
                    continue
            except (UnicodeDecodeError, ValueError):
                pass
            if _depth < max_depth and len(chunk) > 1:
                try:
                    nested = decode_raw(chunk, max_depth, _depth + 1)
                    if nested:
                        result.setdefault(field_num, []).append(nested)
                        continue
                except Exception:
                    pass
            result.setdefault(field_num, []).append(chunk)
        elif wire_type == 5:
            val = int.from_bytes(data[pos:pos + 4], "little")
            pos += 4
            result.setdefault(field_num, []).append(val)
        else:
            break

    return result


def _first(d: dict[int, list], field: int, default: Any = None) -> Any:
    vals = d.get(field)
    return vals[0] if vals else default


# ---------------------------------------------------------------------------
# Feed response helpers
# ---------------------------------------------------------------------------

# Top-level feed response fields
_FEED_STATUS_CODE = 1
_FEED_HAS_MORE = 4
_FEED_AWEME_LIST = 5

# Aweme fields
_AW_ID = 1
_AW_DESC = 2
_AW_CREATE_TIME = 3
_AW_AUTHOR = 4
_AW_MUSIC = 5
_AW_VIDEO = 7
_AW_SHARE_URL = 8
_AW_STATISTICS = 10

# Author fields
_AUTH_UID = 1
_AUTH_NICKNAME = 3
_AUTH_SIGNATURE = 5
_AUTH_AVATAR_THUMB = 7
_AUTH_UNIQUE_ID = 26

# Video fields
_VID_PLAY_ADDR = 1
_VID_COVER = 2
_VID_WIDTH = 3
_VID_HEIGHT = 4
_VID_DYNAMIC_COVER = 5
_VID_ORIGIN_COVER = 6
_VID_RATIO = 7

# Image/URL container
_IMG_URI = 1
_IMG_URLS = 2

# Statistics fields
_STAT_COMMENT = 2
_STAT_DIGG = 3
_STAT_COLLECT = 4
_STAT_PLAY = 5
_STAT_SHARE = 6

# Music fields
_MUS_ID = 1
_MUS_TITLE = 3
_MUS_AUTHOR = 4
_MUS_COVER = 7
_MUS_PLAY_URL = 9
_MUS_DURATION = 12


def _parse_image(raw: dict | None) -> dict[str, Any] | None:
    if not raw or not isinstance(raw, dict):
        return None
    urls = raw.get(_IMG_URLS, [])
    return {
        "uri": _first(raw, _IMG_URI, ""),
        "url_list": [u for u in urls if isinstance(u, str)],
        "width": _first(raw, 3, 0),
        "height": _first(raw, 4, 0),
    }


def _to_str(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val) if val is not None else ""


def _parse_author(raw: dict | None) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return {}
    return {
        "uid": _to_str(_first(raw, _AUTH_UID)),
        "nickname": _to_str(_first(raw, _AUTH_NICKNAME)),
        "unique_id": _to_str(_first(raw, _AUTH_UNIQUE_ID)),
        "signature": _to_str(_first(raw, _AUTH_SIGNATURE)),
        "avatar_thumb": _parse_image(_first(raw, _AUTH_AVATAR_THUMB)),
    }


def _parse_statistics(raw: dict | None) -> dict[str, int]:
    if not raw or not isinstance(raw, dict):
        return {}
    return {
        "digg_count": _first(raw, _STAT_DIGG, 0),
        "comment_count": _first(raw, _STAT_COMMENT, 0),
        "share_count": _first(raw, _STAT_SHARE, 0),
        "play_count": _first(raw, _STAT_PLAY, 0),
        "collect_count": _first(raw, _STAT_COLLECT, 0),
    }


def _parse_music(raw: dict | None) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return {}
    return {
        "id": _first(raw, _MUS_ID, 0),
        "title": _to_str(_first(raw, _MUS_TITLE)),
        "author": _to_str(_first(raw, _MUS_AUTHOR)),
        "cover": _parse_image(_first(raw, _MUS_COVER)),
        "play_url": _parse_image(_first(raw, _MUS_PLAY_URL)),
        "duration": _first(raw, _MUS_DURATION, 0),
    }


def _parse_video(raw: dict | None) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return {}
    return {
        "play_addr": _parse_image(_first(raw, _VID_PLAY_ADDR)),
        "cover": _parse_image(_first(raw, _VID_COVER)),
        "dynamic_cover": _parse_image(_first(raw, _VID_DYNAMIC_COVER)),
        "origin_cover": _parse_image(_first(raw, _VID_ORIGIN_COVER)),
        "width": _first(raw, _VID_WIDTH, 0),
        "height": _first(raw, _VID_HEIGHT, 0),
        "ratio": _first(raw, _VID_RATIO, ""),
    }


def _parse_aweme(raw: dict) -> dict[str, Any]:
    return {
        "aweme_id": _to_str(_first(raw, _AW_ID)),
        "desc": _to_str(_first(raw, _AW_DESC)),
        "create_time": _first(raw, _AW_CREATE_TIME, 0),
        "author": _parse_author(_first(raw, _AW_AUTHOR)),
        "music": _parse_music(_first(raw, _AW_MUSIC)),
        "video": _parse_video(_first(raw, _AW_VIDEO)),
        "share_url": _to_str(_first(raw, _AW_SHARE_URL)),
        "statistics": _parse_statistics(_first(raw, _AW_STATISTICS)),
    }


def _jsonify(value: Any) -> Any:
    """Make a decode_raw() tree JSON-safe: int keys -> str, bytes -> hex."""
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


def decode_generic(data: bytes) -> dict[str, Any]:
    """Decode protobuf into a JSON-safe dict without assuming aweme-feed
    field semantics (status_code=1, has_more=4, aweme_list=5).

    Used for schemas we haven't reverse-engineered against real traffic
    (e.g. the DM/IM endpoints) where blindly reusing parse_feed_response()'s
    field mapping produces nonsense (an unrelated field ending up labelled
    "has_more", etc). Field numbers become string keys under "_raw" so the
    result round-trips through JSON; a best-effort "status_code"/"status_msg"
    are lifted to the top level when field 1/2 look like the common
    TikTok BaseResp pattern (varint status_code, string status_msg) --
    treat those two as a guess, everything else lives only under "_raw"
    until the real schema is confirmed."""
    raw = decode_raw(data)
    result: dict[str, Any] = {}

    sc = _first(raw, 1)
    result["status_code"] = sc if isinstance(sc, int) else 0

    msg = _first(raw, 2)
    if isinstance(msg, str):
        result["status_msg"] = msg

    result["_raw"] = _jsonify(raw)
    return result


def parse_feed_response(data: bytes) -> dict[str, Any]:
    """Parse a protobuf feed response into a JSON-like dict."""
    raw = decode_raw(data)
    aweme_list_raw = raw.get(_FEED_AWEME_LIST, [])
    aweme_list = [
        _parse_aweme(entry)
        for entry in aweme_list_raw
        if isinstance(entry, dict)
    ]
    return {
        "status_code": _first(raw, _FEED_STATUS_CODE, 0),
        "has_more": _first(raw, _FEED_HAS_MORE, 0),
        "aweme_list": aweme_list,
        "_raw": raw,
    }
