"""Social interaction endpoints: follow, like, share, block, dislike.

Write endpoints send action params in query string (NOT POST body) and
use write=True to enable curl_cffi transport with edge-IP pinning for
Janus-Mini(fast) / Envoy SC bypass."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport


class SocialAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def follow(self, user_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/commit/follow/user/
        action: 1 = follow, 0 = unfollow."""
        return self._t.post("/aweme/v1/commit/follow/user/", params={
            "user_id": user_id,
            "type": action,
        }, write=True, full_sign=True)

    def unfollow(self, user_id: str) -> dict[str, Any]:
        return self.follow(user_id, action=0)

    def like(self, aweme_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/commit/item/digg/
        action: 1 = like, 0 = unlike."""
        return self._t.post("/aweme/v1/commit/item/digg/", params={
            "aweme_id": aweme_id,
            "type": action,
        }, write=True, full_sign=True)

    def unlike(self, aweme_id: str) -> dict[str, Any]:
        return self.like(aweme_id, action=0)

    def dislike(self, aweme_id: str) -> dict[str, Any]:
        """/aweme/v1/commit/dislike/item/ — not interested."""
        return self._t.post("/aweme/v1/commit/dislike/item/", params={
            "aweme_id": aweme_id,
        }, full_sign=True)

    def block(self, user_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/user/block/
        action: 1 = block, 0 = unblock."""
        return self._t.post("/aweme/v1/user/block/", params={
            "user_id": user_id,
            "type": action,
        }, write=True, full_sign=True)

    def unblock(self, user_id: str) -> dict[str, Any]:
        return self.block(user_id, action=0)

    def remove_follower(self, user_id: str) -> dict[str, Any]:
        """/aweme/v1/remove/follower/"""
        return self._t.post("/aweme/v1/remove/follower/", params={
            "user_id": user_id,
        }, write=True, full_sign=True)

    def friend_list(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/social/friend/ — mutual followers (friends)."""
        return self._t.get("/aweme/v1/social/friend/", params={
            "cursor": cursor,
            "count": count,
        })

    def digg_list(self, aweme_id: str, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/digg/list/ — users who liked a video.

        DEPRECATED server-side. Live probing (2026-08-26) against the
        emulator account found: dropping ``digg_type`` returns status_code=5
        "Invalid parameters" (confirming it IS a recognized/required param),
        but with ``digg_type`` present every variant tried — ``item_id``
        instead of ``aweme_id``, ``max_cursor`` instead of ``cursor``,
        ``digg_type=0``, smaller ``count``, adding ``sec_uid``, bare request
        without common device params — consistently returns status_code=4
        "Server is currently unavailable". The ``/aweme/v2/digg/list/``
        variant returns status_code=1 "Url does not match" (doesn't exist).
        This matches TikTok's public "liked by" list being pulled for
        privacy years ago — the params are right, the feature is gone.
        No working replacement is known; kept as-is for reference."""
        return self._t.get("/aweme/v1/digg/list/", params={
            "aweme_id": aweme_id,
            "cursor": cursor,
            "count": count,
            "digg_type": 1,
        })

    def recommend_users(self, *, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/recommend/user/ — suggested users to follow."""
        return self._t.get("/aweme/v1/recommend/user/", params={
            "count": count,
        })
