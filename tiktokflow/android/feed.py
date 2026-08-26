"""Feed endpoints: For You, Following, Friends, Nearby.

/aweme/v1/feed/ — основная лента (For You). Возвращает список aweme_list[].
/aweme/v2/feed/ — v2 ленты.
/aweme/v1/follow/feed/ — лента подписок.
/aweme/v1/friend/feed/ — лента друзей.
/aweme/v1/nearby/feed/ — лента рядом."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport


class FeedAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def for_you(
        self,
        *,
        count: int = 6,
        pull_type: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v2/feed/ — For You page (protobuf response)."""
        return self._t.post("/aweme/v2/feed/", params={
            "count": count,
            "pull_type": pull_type,
        }, headers={
            "Content-Type": "application/x-protobuf",
            "get-svc": "1",
        })

    def following(
        self,
        *,
        count: int = 6,
        pull_type: int = 0,
        max_cursor: int = 0,
        min_cursor: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v2/follow/feed/ — feed of accounts you follow (requires auth)."""
        return self._t.get("/aweme/v2/follow/feed/", params={
            "count": count,
            "pull_type": pull_type,
            "max_cursor": max_cursor,
            "min_cursor": min_cursor,
        }, bare=True)

    def friends(self, *, count: int = 6, cursor: int = 0) -> dict[str, Any]:
        """/aweme/v1/friend/feed/ — DEPRECATED by TikTok (returns 'Url does not match')."""
        return self._t.get("/aweme/v1/friend/feed/", params={
            "count": count,
            "cursor": cursor,
        })

    def nearby(self, *, count: int = 6, longitude: float = 0, latitude: float = 0) -> dict[str, Any]:
        """/aweme/v1/nearby/feed/ — nearby feed. Often returns 502."""
        return self._t.get("/aweme/v1/nearby/feed/", params={
            "count": count,
            "longitude": longitude,
            "latitude": latitude,
        })
