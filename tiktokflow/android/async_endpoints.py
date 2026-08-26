"""Async endpoint API classes for every Android mobile API surface.

Each class mirrors its sync counterpart (feed.py, user.py, ...) but methods
are ``async def`` and ``await`` the transport. All 12 classes live in one
file because each method is a thin 2-3 line wrapper — no reason to duplicate
12 modules.

Usage::

    transport = AsyncAndroidTransport(device)
    feed = AsyncFeedAPI(transport)
    data = await feed.for_you(count=10)
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Iterable

from ..errors import InvalidRequest, ServerError, TikTokError
from .async_transport import AsyncAndroidTransport
from .device import SEARCH_BASE
from .transport import _parse_aweme_envelope
from .upload import CHUNK, CREATE_AWEME, CREATE_PHOTO, MIN_SINGLE_CHUNK
from .upload import UPLOAD_AUTHKEY, UPLOAD_IMAGE_INIT, UPLOAD_VIDEO_INIT
from .upload import _build_text, _chunking, _extract
from .upload import _UPLOAD_ID_KEYS, _UPLOAD_URL_KEYS


# ── Feed ─────────────────────────────────────────────────────────────

class AsyncFeedAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def for_you(
        self,
        *,
        count: int = 6,
        pull_type: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v2/feed/ — For You page (protobuf response)."""
        return await self._t.post("/aweme/v2/feed/", params={
            "count": count,
            "pull_type": pull_type,
        }, headers={
            "Content-Type": "application/x-protobuf",
            "get-svc": "1",
        })

    async def following(
        self,
        *,
        count: int = 6,
        pull_type: int = 0,
        max_cursor: int = 0,
        min_cursor: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v2/follow/feed/ — feed of accounts you follow (requires auth)."""
        return await self._t.get("/aweme/v2/follow/feed/", params={
            "count": count,
            "pull_type": pull_type,
            "max_cursor": max_cursor,
            "min_cursor": min_cursor,
        })

    async def friends(self, *, count: int = 6, cursor: int = 0) -> dict[str, Any]:
        """/aweme/v1/friend/feed/ — DEPRECATED by TikTok (returns 'Url does not match')."""
        return await self._t.get("/aweme/v1/friend/feed/", params={
            "count": count,
            "cursor": cursor,
        })

    async def nearby(self, *, count: int = 6, longitude: float = 0, latitude: float = 0) -> dict[str, Any]:
        """/aweme/v1/nearby/feed/ — nearby feed. Often returns 502."""
        return await self._t.get("/aweme/v1/nearby/feed/", params={
            "count": count,
            "longitude": longitude,
            "latitude": latitude,
        })


# ── User ─────────────────────────────────────────────────────────────

class AsyncUserAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def profile_self(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/user/profile/self/")

    async def profile_by_id(self, user_id: str | int) -> dict[str, Any]:
        """/aweme/v1/user/ — lookup by numeric user_id. Works in v46+."""
        return await self._t.get("/aweme/v1/user/", params={"user_id": str(user_id)})

    async def resolve_username(self, username: str) -> dict[str, Any] | None:
        """Resolve @username to full profile via search + profile_by_id.
        v46+ dropped unique_id lookup on /aweme/v1/user/."""
        try:
            search_result = await self._t.get("/aweme/v1/general/search/single/", params={
                "keyword": username,
                "count": "5",
                "search_source": "normal_search",
                "query_correct_type": "1",
            })
            for item in search_result.get("data", []):
                if item.get("type") != 4:
                    continue
                for u in item.get("user_list", []):
                    info = u.get("user_info", {})
                    if info.get("unique_id", "").lower() == username.lower():
                        uid = info.get("uid")
                        if uid:
                            result = await self.profile_by_id(uid)
                            if not result.get("_empty"):
                                return result
        except (TikTokError, ServerError):
            pass
        return None

    async def profile_other(self, *, user_id: str = "", sec_user_id: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        return await self._t.get("/aweme/v1/user/profile/other/", params=params)

    async def follower_list(
        self, user_id: str, *, max_time: int = 0, count: int = 20,
        offset: int = 0, sec_user_id: str = "", source_type: int = 1,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "user_id": user_id, "max_time": max_time,
            "count": count, "offset": offset, "source_type": source_type,
        }
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        return await self._t.get("/aweme/v1/user/follower/list/", params=params)

    async def following_list(
        self, user_id: str, *, max_time: int = 0, count: int = 20,
        offset: int = 0, sec_user_id: str = "", source_type: int = 1,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "user_id": user_id, "max_time": max_time,
            "count": count, "offset": offset, "source_type": source_type,
        }
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        return await self._t.get("/aweme/v1/user/following/list/", params=params)

    async def block_list(self, *, count: int = 20, offset: int = 0) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/user/block/list/", params={
            "count": count, "offset": offset,
        })

    async def settings(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/user/settings/")

    async def check_unique_id(self, unique_id: str) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/unique/id/check/", params={
            "unique_id": unique_id,
        })

    async def data_info(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/data/user/info/")

    async def set_settings(self, **settings: Any) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/user/set/settings/", data=settings)


# ── Video ────────────────────────────────────────────────────────────

class AsyncVideoAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def detail(self, aweme_id: str) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/aweme/detail/", params={
            "aweme_id": aweme_id,
        })

    async def multi_detail(self, aweme_ids: list[str]) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/multi/aweme/detail/", data={
            "aweme_ids": json.dumps(aweme_ids),
        })

    async def my_posts(
        self, user_id: str = "", sec_user_id: str = "",
        *, max_cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"max_cursor": max_cursor, "count": count}
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        return await self._t.get("/aweme/v1/aweme/post/", params=params)

    async def favorites(
        self, user_id: str = "", sec_user_id: str = "",
        *, max_cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"max_cursor": max_cursor, "count": count}
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        return await self._t.get("/aweme/v1/aweme/favorite/", params=params)

    async def collect(self, aweme_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/aweme/collect/ — bookmark (1) or unbookmark (0)."""
        return await self._t.post("/aweme/v1/aweme/collect/", params={
            "aweme_id": aweme_id, "action": action,
        }, full_sign=True)

    async def uncollect(self, aweme_id: str) -> dict[str, Any]:
        return await self.collect(aweme_id, action=0)

    async def list_collections(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/aweme/listcollection/", params={
            "cursor": cursor, "count": count,
        })

    async def delete(self, aweme_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/aweme/delete/", data={
            "aweme_id": aweme_id,
        }, full_sign=True)

    async def stats(self, aweme_id: str) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/aweme/stats/", params={
            "aweme_id": aweme_id,
        })

    async def private_list(self, *, max_cursor: int = 0, count: int = 20) -> dict[str, Any]:
        result = await self._t.get("/aweme/v1/private/aweme/", params={
            "max_cursor": max_cursor, "count": count,
        })
        if result.get("aweme_list") is None:
            result["aweme_list"] = []
        return result

    async def liked(
        self, user_id: str = "", sec_user_id: str = "",
        *, max_cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/aweme/favorite/ — alias for favorites (liked videos)."""
        return await self.favorites(user_id, sec_user_id, max_cursor=max_cursor, count=count)

    async def watch_history(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/aweme/history/ — DEPRECATED by TikTok (returns 'Url does not match')."""
        return await self._t.get("/aweme/v1/aweme/history/", params={
            "cursor": cursor, "count": count,
        })

    async def feedback(self, aweme_id: str, feedback_type: int) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/aweme/feedback", data={
            "aweme_id": aweme_id, "feedback_type": feedback_type,
        }, full_sign=True)

    async def related(self, aweme_id: str, *, count: int = 6) -> dict[str, Any]:
        """/aweme/v1/feed/ with type=5 — "related/you may like" videos for
        a given aweme (see video.py:related for the full rationale)."""
        return await self._t.get("/aweme/v1/feed/", params={
            "count": count, "type": 5, "aweme_id": aweme_id,
        })


# ── Upload ───────────────────────────────────────────────────────────

class AsyncUploadAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def creator_info(self) -> dict[str, Any]:
        """Mobile equivalent of the official /v2/post/publish/creator_info/query/.
        See upload.py:creator_info for the full rationale.

        Sync calls this with ``bare=True`` (unsigned, no device params);
        the async transport doesn't implement that mode yet, so this uses
        a normal signed request against the same endpoint."""
        return await self._t.get(UPLOAD_AUTHKEY)

    async def upload_video(
        self,
        path: str,
        *,
        title: str,
        hashtags: Iterable[str] = (),
        music_id: str = "",
        privacy: int = 0,
        disable_comment: bool = False,
        disable_duet: bool = False,
        disable_stitch: bool = False,
        cover_ts_ms: int = 0,
    ) -> dict[str, Any]:
        if not os.path.isfile(path):
            raise InvalidRequest(f"no such file: {path}")

        size = os.path.getsize(path)
        chunk_size, total = _chunking(size)

        init = await self._t.post(UPLOAD_VIDEO_INIT, data={
            "video_size": size, "chunk_size": chunk_size,
            "total_chunk_count": total, "file_name": os.path.basename(path),
        })
        upload_url = _extract(init, _UPLOAD_URL_KEYS)
        upload_id = _extract(init, _UPLOAD_ID_KEYS)
        if not upload_url:
            raise InvalidRequest(f"upload init did not return an upload URL: {init}")

        await self._upload_chunks(upload_url, path, size, chunk_size, total, mime="video/mp4")

        text = _build_text(title, hashtags)
        data: dict[str, Any] = {
            "text": text, "video_id": upload_id, "upload_id": upload_id,
            "privacy_setting": privacy,
            "disable_comment": int(disable_comment),
            "disable_duet": int(disable_duet),
            "disable_stitch": int(disable_stitch),
        }
        if music_id:
            data["music_id"] = music_id
        if cover_ts_ms:
            data["cover_timestamp"] = cover_ts_ms
        return await self._t.post(CREATE_AWEME, data=data)

    async def upload_photo(
        self,
        paths: list[str],
        *,
        title: str,
        hashtags: Iterable[str] = (),
        music_id: str = "",
        privacy: int = 0,
        cover_index: int = 0,
        disable_comment: bool = False,
    ) -> dict[str, Any]:
        if not paths:
            raise InvalidRequest("upload_photo requires at least one path")
        for p in paths:
            if not os.path.isfile(p):
                raise InvalidRequest(f"no such file: {p}")

        image_ids: list[str] = []
        for p in paths:
            size = os.path.getsize(p)
            chunk_size, total = _chunking(size)
            init = await self._t.post(UPLOAD_IMAGE_INIT, data={
                "image_size": size, "chunk_size": chunk_size,
                "total_chunk_count": total, "file_name": os.path.basename(p),
            })
            upload_url = _extract(init, _UPLOAD_URL_KEYS)
            image_id = _extract(init, _UPLOAD_ID_KEYS)
            if not upload_url:
                raise InvalidRequest(f"upload init did not return an upload URL: {init}")
            await self._upload_chunks(upload_url, p, size, chunk_size, total, mime="image/jpeg")
            image_ids.append(image_id or "")

        text = _build_text(title, hashtags)
        data: dict[str, Any] = {
            "text": text, "image_ids": ",".join(image_ids),
            "privacy_setting": privacy, "photo_cover_index": cover_index,
            "disable_comment": int(disable_comment),
        }
        if music_id:
            data["music_id"] = music_id
        return await self._t.post(CREATE_PHOTO, data=data)

    async def _upload_chunks(
        self, upload_url: str, path: str, size: int,
        chunk_size: int, total: int, *, mime: str,
    ) -> None:
        with open(path, "rb") as f:
            for idx in range(total):
                start = idx * chunk_size
                end = size - 1 if idx == total - 1 else start + chunk_size - 1
                f.seek(start)
                blob = f.read(end - start + 1)
                await self._t.request("PUT", upload_url, content=blob, raw=True, headers={
                    "Content-Type": mime,
                    "Content-Length": str(len(blob)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                })


# ── Search ───────────────────────────────────────────────────────────

class AsyncSearchAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def general(
        self, keyword: str, *, offset: int = 0, count: int = 10,
        search_source: str = "normal_search", query_type: int = 0,
        is_filter_search: int = 0,
    ) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/general/search/single/", params={
            "keyword": keyword, "offset": offset, "count": count,
            "search_source": search_source, "query_type": query_type,
            "is_filter_search": is_filter_search,
        })

    async def discover(self, keyword: str, *, offset: int = 0, count: int = 10) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/discover/search/", params={
            "keyword": keyword, "offset": offset, "count": count,
        })

    async def videos(
        self, keyword: str, *, offset: int = 0, count: int = 10,
        sort_type: int = 0, publish_time: int = 0,
    ) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/search/item/", params={
            "keyword": keyword, "offset": offset, "count": count,
            "sort_type": sort_type, "publish_time": publish_time,
        })

    async def suggestions(self, keyword: str, *, count: int = 10) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/search/sug/", params={
            "keyword": keyword, "count": count,
        })

    async def hot_list(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v2/category/list/")

    async def hashtag_search(self, keyword: str, *, offset: int = 0, count: int = 10) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/challenge/search/", params={
            "keyword": keyword, "offset": offset, "count": count,
        })

    async def hashtag_detail(self, challenge_id: str = "", challenge_name: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {}
        if challenge_id:
            params["ch_id"] = challenge_id
        if challenge_name:
            params["challenge_name"] = challenge_name
        return await self._t.get("/aweme/v1/challenge/detail/", params=params)

    async def hashtag_videos(
        self, challenge_id: str, *, cursor: int = 0, count: int = 10,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/challenge/aweme/", params={
            "ch_id": challenge_id, "cursor": cursor,
            "count": count, "sort_type": sort_type,
        })

    async def user_suggestions(self, keyword: str, *, count: int = 10) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/search/user/sug/", params={
            "keyword": keyword, "count": count,
        })

    async def search_history(self) -> dict[str, Any]:
        return await self._t.get(f"{SEARCH_BASE}/aweme/v1/search/history/")


# ── Comment ──────────────────────────────────────────────────────────

class AsyncCommentAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def list(self, aweme_id: str, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v2/comment/list/", params={
            "aweme_id": aweme_id, "cursor": cursor, "count": count,
        })

    async def replies(
        self, aweme_id: str, comment_id: str, *, cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/comment/list/reply/", params={
            "item_id": aweme_id, "comment_id": comment_id,
            "cursor": cursor, "count": count,
        })

    async def publish(self, aweme_id: str, text: str, *, reply_id: str = "") -> dict[str, Any]:
        """/aweme/v1/comment/publish/ — post a comment (or reply).

        Sync uses a curl_cffi write-bypass transport not available on the
        async transport; this hits the same endpoint/params directly."""
        params: dict[str, Any] = {"aweme_id": aweme_id}
        if reply_id:
            params["reply_id"] = reply_id
        return await self._t.post(
            "/aweme/v1/comment/publish/",
            params=params,
            data={"text": text, "aweme_id": aweme_id},
            full_sign=True,
        )

    async def delete(self, aweme_id: str, comment_id: str) -> dict[str, Any]:
        """/aweme/v1/comment/delete/ — the POST body field must be named
        ``cid``, NOT ``comment_id`` (query params still use ``comment_id``);
        see comment.py:delete for the full rationale."""
        return await self._t.post("/aweme/v1/comment/delete/", params={
            "aweme_id": aweme_id, "comment_id": comment_id,
        }, data={"aweme_id": aweme_id, "cid": comment_id}, full_sign=True)

    async def digg(self, aweme_id: str, comment_id: str, *, digg_type: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/comment/digg/", params={
            "aweme_id": aweme_id, "comment_id": comment_id, "digg_type": digg_type,
        }, data={
            "aweme_id": aweme_id, "comment_id": comment_id, "digg_type": digg_type,
        }, full_sign=True)


# ── Social ───────────────────────────────────────────────────────────

class AsyncSocialAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def follow(self, user_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/commit/follow/user/ — action params go in the query
        string (not POST body), matching social.py."""
        return await self._t.post("/aweme/v1/commit/follow/user/", params={
            "user_id": user_id, "type": action,
        }, full_sign=True)

    async def unfollow(self, user_id: str) -> dict[str, Any]:
        return await self.follow(user_id, action=0)

    async def like(self, aweme_id: str, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/commit/item/digg/", params={
            "aweme_id": aweme_id, "type": action,
        }, full_sign=True)

    async def unlike(self, aweme_id: str) -> dict[str, Any]:
        return await self.like(aweme_id, action=0)

    async def dislike(self, aweme_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/commit/dislike/item/", params={
            "aweme_id": aweme_id,
        }, full_sign=True)

    async def block(self, user_id: str, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/user/block/", params={
            "user_id": user_id, "type": action,
        }, full_sign=True)

    async def unblock(self, user_id: str) -> dict[str, Any]:
        return await self.block(user_id, action=0)

    async def remove_follower(self, user_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/remove/follower/", params={
            "user_id": user_id,
        }, full_sign=True)

    async def friend_list(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/social/friend/", params={
            "cursor": cursor, "count": count,
        })

    async def digg_list(self, aweme_id: str, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/digg/list/ — DEPRECATED server-side; see social.py:digg_list."""
        return await self._t.get("/aweme/v1/digg/list/", params={
            "aweme_id": aweme_id, "cursor": cursor, "count": count, "digg_type": 1,
        })

    async def recommend_users(self, *, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/recommend/user/", params={
            "count": count,
        })


# ── Music ────────────────────────────────────────────────────────────

class AsyncMusicAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def detail(self, music_id: str) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/music/detail/", params={
            "music_id": music_id,
        })

    async def videos(
        self, music_id: str, *, cursor: int = 0, count: int = 20,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/music/aweme/", params={
            "music_id": music_id, "cursor": cursor,
            "count": count, "sort_type": sort_type,
        })

    async def search(self, keyword: str, *, offset: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/music/search/", params={
            "keyword": keyword, "offset": offset, "count": count,
        })

    async def collect(self, music_id: str, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/music/collect/", data={
            "music_id": music_id, "type": action,
        }, full_sign=True)

    async def recommended(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/music/choices/ — recommended music (video-creation music
        picker). The old ``/aweme/v1/music/list/`` path is deprecated
        server-side; see music.py:recommended for the full rationale."""
        return await self._t.get("/aweme/v1/music/choices/", params={
            "cursor": cursor, "count": count,
        })

    async def hot(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/hot/music/")

    async def collection(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/music/collection/", params={
            "cursor": cursor, "count": count,
        })

    async def user_collected(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/user/music/collect/", params={
            "cursor": cursor, "count": count,
        })


# ── Notice ───────────────────────────────────────────────────────────

class AsyncNoticeAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def multi(
        self, *, max_time: int = 0, count: int = 20, notice_group: int = 32,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/notice/multi/", params={
            "max_time": max_time, "count": count, "notice_group": notice_group,
        })

    async def count(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/notice/count/")

    async def inbox(
        self, *, cursor: int = 0, count: int = 20, fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/inbox/agg_list/ — DEPRECATED server-side. With
        ``fallback=True`` (default) falls back to ``multi()``, the working
        replacement; see notice.py:inbox for the full rationale."""
        try:
            return await self._t.get("/aweme/v1/inbox/agg_list/", params={
                "cursor": cursor, "count": count,
            })
        except TikTokError:
            if not fallback:
                raise
            result = await self.multi(max_time=cursor, count=count)
            if isinstance(result, dict):
                result["_source"] = "notice_multi_fallback"
            return result

    async def delete(self, notice_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/notice/del/", data={
            "notice_id": notice_id,
        }, full_sign=True)

    async def shield(self, notice_type: int, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/notice/shield/", data={
            "notice_type": notice_type, "type": action,
        }, full_sign=True)


# ── Passport ─────────────────────────────────────────────────────────

class AsyncPassportAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def _login_request(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        resp = await self._t.post(path, data=data, raw=True)
        cookies = dict(resp.cookies)
        body = _parse_aweme_envelope(resp)
        response_data = body.get("data") if isinstance(body, dict) else None
        self._t.device.update_session(response_data, cookies)
        return body

    async def account_info(self) -> dict[str, Any]:
        return await self._t.get("/passport/account/info/v2/", full_sign=True)

    async def token_beat(self) -> dict[str, Any]:
        return await self._t.get("/passport/token/beat/v2/", full_sign=True)

    async def email_login(self, email: str, password: str) -> dict[str, Any]:
        return await self._login_request("/passport/email/login/", {
            "email": email, "password": password, "account_sdk_source": "app",
        })

    async def sms_login(self, mobile: str, code: str) -> dict[str, Any]:
        return await self._login_request("/passport/mobile/sms_login/", {
            "mobile": mobile, "code": code,
        })

    async def send_sms_code(self, mobile: str, *, scene: str = "login") -> dict[str, Any]:
        return await self._t.post("/passport/mobile/send_code/", data={
            "mobile": mobile, "scene": scene,
        }, full_sign=True)

    async def send_email_code(self, email: str, *, scene: str = "login") -> dict[str, Any]:
        return await self._t.post("/passport/email/send_code/", data={
            "email": email, "scene": scene,
        }, full_sign=True)

    async def email_register(self, email: str, password: str, code: str) -> dict[str, Any]:
        return await self._t.post("/passport/email/register/v2/", data={
            "email": email, "password": password, "code": code,
        }, full_sign=True)

    async def logout(self) -> dict[str, Any]:
        return await self._t.post("/passport/user/logout/", full_sign=True)

    async def check_email(self, email: str) -> dict[str, Any]:
        return await self._t.get("/passport/email/check_code/", params={
            "email": email,
        }, full_sign=True)

    async def account_set(self, **fields: Any) -> dict[str, Any]:
        return await self._t.post("/passport/account/set/", data=fields, full_sign=True)

    async def available_ways(self) -> dict[str, Any]:
        return await self._t.get("/passport/auth/available_ways/", full_sign=True)

    async def password_check(self) -> dict[str, Any]:
        return await self._t.get("/passport/password/check/", full_sign=True)

    async def user_settings(self) -> dict[str, Any]:
        return await self._t.get("/passport/user/settings/", full_sign=True)

    async def switch_account(self) -> dict[str, Any]:
        return await self._t.post("/passport/account/switch/v2/", full_sign=True)


# ── Live ─────────────────────────────────────────────────────────────

class AsyncLiveAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def room_enter(self, room_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/room/enter/", data={
            "room_id": room_id,
        }, full_sign=True)

    async def room_leave(self, room_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/room/leave/", data={
            "room_id": room_id,
        }, full_sign=True)

    async def room_info(self, room_id: str) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/live/room/info/", params={
            "room_id": room_id,
        })

    async def room_create(self, title: str, *, live_type: int = 0) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/room/create/", data={
            "title": title, "live_type": live_type,
        }, full_sign=True)

    async def room_finish(self, room_id: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/room/finish/", data={
            "room_id": room_id,
        }, full_sign=True)

    async def room_audience(
        self, room_id: str, *, cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/live/room/audience/", params={
            "room_id": room_id, "cursor": cursor, "count": count,
        })

    async def comment_list(
        self, room_id: str, *, cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/live/comment/list/", params={
            "room_id": room_id, "cursor": cursor, "count": count,
        })

    async def comment_send(self, room_id: str, text: str) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/comment/send/", data={
            "room_id": room_id, "content": text,
        }, full_sign=True)

    async def like(self, room_id: str, *, count: int = 1) -> dict[str, Any]:
        return await self._t.post("/aweme/v1/live/like/", data={
            "room_id": room_id, "count": count,
        }, full_sign=True)

    async def gift_send(
        self, room_id: str, gift_id: str, *, count: int = 1,
        to_user_id: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "room_id": room_id, "gift_id": gift_id, "gift_count": count,
        }
        if to_user_id:
            payload["to_user_id"] = to_user_id
        return await self._t.post("/aweme/v1/live/gift/send/", data=payload, full_sign=True)

    async def recommend(self, *, count: int = 6) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/live/recommend/", params={
            "count": count,
        })

    async def search(
        self, keyword: str, *, offset: int = 0, count: int = 10,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/live/search/", params={
            "keyword": keyword, "offset": offset, "count": count,
        })


# ── DM ───────────────────────────────────────────────────────────────

class AsyncDMAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def conversations(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/v1/conversation/list/", params={
            "cursor": cursor, "count": count,
        }, proto_mode="generic")

    async def conversation_detail(self, conversation_id: str) -> dict[str, Any]:
        return await self._t.get("/v1/conversation/get_core_info/", params={
            "conversation_id": conversation_id,
        }, proto_mode="generic")

    async def create_conversation(self, to_user_id: str) -> dict[str, Any]:
        return await self._t.post("/v2/conversation/create/", data={
            "user_id": to_user_id,
        }, full_sign=True, proto_mode="generic")

    async def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        return await self._t.post("/v1/conversation/delete/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    async def leave_conversation(self, conversation_id: str) -> dict[str, Any]:
        return await self._t.post("/v1/conversation/leave/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    async def block_conversation(self, conversation_id: str, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/v1/conversation/block_conversation/", data={
            "conversation_id": conversation_id, "type": action,
        }, full_sign=True, proto_mode="generic")

    async def mute(self, conversation_id: str, *, action: int = 1) -> dict[str, Any]:
        return await self._t.post("/v1/conversation/set_setting_info/", data={
            "conversation_id": conversation_id, "mute_status": action,
        }, full_sign=True, proto_mode="generic")

    async def mark_read(self, conversation_id: str, *, read_index: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {"conversation_id": conversation_id}
        if read_index:
            payload["read_index"] = read_index
        return await self._t.post("/v3/conversation/mark_read/", data=payload, full_sign=True, proto_mode="generic")

    async def unread_count(self) -> dict[str, Any]:
        return await self._t.get("/v1/client/unread_count/", proto_mode="generic")

    async def messages(
        self, conversation_id: str, *, cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        return await self._t.get("/v1/message/get_by_conversation/", params={
            "conversation_id": conversation_id, "cursor": cursor, "count": count,
        }, proto_mode="generic")

    async def send(
        self, conversation_id: str, text: str, *, to_user_id: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "conversation_id": conversation_id, "content": text, "content_type": 1,
        }
        if to_user_id:
            payload["to_user_id"] = to_user_id
        return await self._t.post("/v1/message/send/", data=payload, full_sign=True, proto_mode="generic")

    async def delete_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        return await self._t.post("/v1/message/delete/", data={
            "conversation_id": conversation_id, "message_id": message_id,
        }, full_sign=True, proto_mode="generic")

    async def recall_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        return await self._t.post("/v1/message/recall/", data={
            "conversation_id": conversation_id, "message_id": message_id,
        }, full_sign=True, proto_mode="generic")

    async def stranger_conversations(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        return await self._t.get("/v1/stranger/get_conversation_list/", params={
            "cursor": cursor, "count": count,
        }, proto_mode="generic")

    async def stranger_messages(
        self, conversation_id: str, *, cursor: int = 0, count: int = 20,
    ) -> dict[str, Any]:
        return await self._t.get("/v1/stranger/get_messages/", params={
            "conversation_id": conversation_id, "cursor": cursor, "count": count,
        }, proto_mode="generic")

    async def delete_stranger_conversation(self, conversation_id: str) -> dict[str, Any]:
        return await self._t.post("/v1/stranger/delete_conversation/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    async def cloud_token(self) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/im/cloud/token/")


# ── Effect / Sticker ────────────────────────────────────────────────

class AsyncEffectAPI:
    def __init__(self, transport: AsyncAndroidTransport):
        self._t = transport

    async def detail(self, *effect_ids: str) -> dict[str, Any]:
        """/aweme/v1/sticker/detail/ — effect info by one or more IDs.

        Sync calls this with ``bare=True`` (unsigned, no device params);
        the async transport doesn't implement that mode yet, so this uses
        a normal signed request against the same endpoint/params."""
        ids = ",".join(effect_ids)
        return await self._t.get("/aweme/v1/sticker/detail/", params={
            "sticker_ids": ids,
        })

    async def videos(
        self, effect_id: str, *, count: int = 20, cursor: int = 0,
    ) -> dict[str, Any]:
        return await self._t.get("/aweme/v1/sticker/aweme/", params={
            "sticker_id": effect_id, "count": count, "cursor": cursor,
        })
