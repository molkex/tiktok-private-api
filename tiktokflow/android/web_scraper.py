"""Web scraping fallback for endpoints blocked on the mobile API.

Fetches public TikTok pages and extracts embedded JSON data from
__UNIVERSAL_DATA_FOR_REHYDRATION__ script tags. No authentication required.
Used as a fallback when mobile API returns empty responses for
video.detail, multi_detail, and user posts.
"""
from __future__ import annotations

import json
import re
from typing import Any

_UNIVERSAL_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _get_page(url: str, timeout: float = 15.0) -> str:
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146",
                      timeout=timeout, allow_redirects=True)
    except ImportError:
        import httpx
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200:
        return ""
    return resp.text


def _extract_universal(html: str) -> dict[str, Any]:
    m = _UNIVERSAL_RE.search(html)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        return data.get("__DEFAULT_SCOPE__", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def video_detail_web(aweme_id: str) -> dict[str, Any] | None:
    """Scrape video detail from tiktok.com.

    Returns a dict with aweme_detail-compatible structure, or None on failure.
    """
    html = _get_page(f"https://www.tiktok.com/@_/video/{aweme_id}")
    if not html:
        return None

    scope = _extract_universal(html)
    vd = scope.get("webapp.video-detail", {})
    item = vd.get("itemInfo", {}).get("itemStruct")
    if not item:
        return None

    return _web_item_to_aweme(item)


def user_detail_web(username: str) -> dict[str, Any] | None:
    """Scrape user profile from tiktok.com/@username."""
    html = _get_page(f"https://www.tiktok.com/@{username}")
    if not html:
        return None

    scope = _extract_universal(html)
    ud = scope.get("webapp.user-detail", {})
    info = ud.get("userInfo")
    if not info:
        return None

    user = info.get("user", {})
    stats = info.get("stats", {})
    return {
        "user": {
            "uid": user.get("id", ""),
            "unique_id": user.get("uniqueId", ""),
            "nickname": user.get("nickname", ""),
            "sec_uid": user.get("secUid", ""),
            "avatar_thumb": {"url_list": [user.get("avatarThumb", "")]},
            "signature": user.get("signature", ""),
            "verified": user.get("verified", False),
            "follower_count": stats.get("followerCount", 0),
            "following_count": stats.get("followingCount", 0),
            "aweme_count": stats.get("videoCount", 0),
            "total_favorited": stats.get("heartCount", 0),
        }
    }


def oembed(aweme_id: str) -> dict[str, Any] | None:
    """Fetch basic video info via TikTok oEmbed API (public, no auth)."""
    url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@_/video/{aweme_id}"
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers={"User-Agent": _DEFAULT_UA}, timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10) as c:
            resp = c.get(url, headers={"User-Agent": _DEFAULT_UA})
    if resp.status_code != 200 or not resp.content:
        return None
    return resp.json()


def comments_web(aweme_id: str, *, cursor: int = 0, count: int = 20) -> dict[str, Any] | None:
    """Fetch comments via TikTok public web API."""
    url = (f"https://www.tiktok.com/api/comment/list/"
           f"?aweme_id={aweme_id}&cursor={cursor}&count={count}")
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146", timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        return resp.json()
    except (ValueError, KeyError):
        return None


def music_detail_web(music_id: str) -> dict[str, Any] | None:
    """Fetch music detail via TikTok public web API."""
    html = _get_page(f"https://www.tiktok.com/music/-{music_id}")
    if not html:
        return None
    scope = _extract_universal(html)
    md = scope.get("webapp.music-detail", {})
    info = md.get("musicInfo")
    if not info:
        return None
    return info


def user_posts_web(sec_user_id: str, *, cursor: int = 0, count: int = 35) -> dict[str, Any] | None:
    """Fetch user posts via TikTok public web API."""
    url = (f"https://www.tiktok.com/api/post/item_list/"
           f"?aid=1988&count={count}&cursor={cursor}&secUid={sec_user_id}")
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146", timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        return resp.json()
    except (ValueError, KeyError):
        return None


def user_followers_web(sec_user_id: str, *, min_cursor: int = 0, max_cursor: int = 0, count: int = 30) -> dict[str, Any] | None:
    """Fetch followers via TikTok public web API (scene=67)."""
    url = (f"https://www.tiktok.com/api/user/list/"
           f"?scene=67&secUid={sec_user_id}&minCursor={min_cursor}"
           f"&maxCursor={max_cursor}&count={count}")
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146", timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        return resp.json()
    except (ValueError, KeyError):
        return None


def user_following_web(sec_user_id: str, *, min_cursor: int = 0, max_cursor: int = 0, count: int = 30) -> dict[str, Any] | None:
    """Fetch following via TikTok public web API (scene=21)."""
    url = (f"https://www.tiktok.com/api/user/list/"
           f"?scene=21&secUid={sec_user_id}&minCursor={min_cursor}"
           f"&maxCursor={max_cursor}&count={count}")
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146", timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        return resp.json()
    except (ValueError, KeyError):
        return None


def user_favorites_web(sec_user_id: str, *, cursor: int = 0, count: int = 35) -> dict[str, Any] | None:
    """Fetch liked videos via TikTok public web API."""
    url = (f"https://www.tiktok.com/api/favorite/item_list/"
           f"?aid=1988&count={count}&cursor={cursor}&secUid={sec_user_id}")
    try:
        from curl_cffi import requests as cr
        resp = cr.get(url, headers=_HEADERS, impersonate="chrome146", timeout=10)
    except ImportError:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            resp = c.get(url, headers=_HEADERS)
    if resp.status_code != 200 or not resp.content:
        return None
    try:
        return resp.json()
    except (ValueError, KeyError):
        return None


def multi_detail_web(aweme_ids: list[str]) -> dict[str, Any] | None:
    """Fetch multiple video details via individual web scraping."""
    items = []
    for aid in aweme_ids[:20]:
        detail = video_detail_web(aid)
        if detail and detail.get("aweme_detail"):
            items.append(detail["aweme_detail"])
    if not items:
        return None
    return {"aweme_details": items, "_source": "web_scraping"}


def _web_item_to_aweme(item: dict) -> dict[str, Any]:
    """Convert web itemStruct to mobile aweme_detail-like format."""
    video = item.get("video", {})
    author = item.get("author", {})
    stats = item.get("stats", {})
    music = item.get("music", {})

    play_addr = video.get("playAddr", "")
    if isinstance(play_addr, dict):
        play_url = play_addr.get("src", "") or ""
    else:
        play_url = play_addr or ""

    download_addr = video.get("downloadAddr", "")
    if isinstance(download_addr, dict):
        dl_url = download_addr.get("src", "") or ""
    else:
        dl_url = download_addr or ""

    cover = video.get("cover", "")
    if isinstance(cover, dict):
        cover_url = cover.get("src", "") or ""
    else:
        cover_url = cover or ""

    return {
        "aweme_detail": {
            "aweme_id": item.get("id", ""),
            "desc": item.get("desc", ""),
            "create_time": item.get("createTime", 0),
            "author": {
                "uid": author.get("id", ""),
                "unique_id": author.get("uniqueId", ""),
                "nickname": author.get("nickname", ""),
                "sec_uid": author.get("secUid", ""),
                "avatar_thumb": {"url_list": [author.get("avatarThumb", "")]},
                "verified": author.get("verified", False),
            },
            "video": {
                "play_addr": {"url_list": [play_url] if play_url else []},
                "download_addr": {"url_list": [dl_url] if dl_url else []},
                "cover": {"url_list": [cover_url] if cover_url else []},
                "duration": video.get("duration", 0) * 1000,
                "width": video.get("width", 0),
                "height": video.get("height", 0),
                "ratio": video.get("ratio", ""),
            },
            "statistics": {
                "digg_count": stats.get("diggCount", 0),
                "play_count": stats.get("playCount", 0),
                "comment_count": stats.get("commentCount", 0),
                "share_count": stats.get("shareCount", 0),
                "collect_count": int(stats.get("collectCount", 0)),
            },
            "music": {
                "title": music.get("title", ""),
                "author": music.get("authorName", ""),
                "album": music.get("album", ""),
            },
            "_source": "web_scraping",
        }
    }
