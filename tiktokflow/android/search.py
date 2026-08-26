"""Search endpoints: general, users, hashtags, music, suggestions.

Frida capture shows search endpoints go to search.tiktokv.com (not api19).
Working endpoints (v46.4.3, no login):
  - /aweme/v1/general/search/single/ — structure OK, results require activation
  - /aweme/v1/search/sug/            — autocomplete suggestions (WORKS)
  - /aweme/v1/search/user/sug/       — user suggestions (WORKS)
  - /aweme/v1/challenge/search/      — hashtag search structure

Soft-blocked (need MetaSec/login):
  - /aweme/v1/search/item/     — video search
  - /aweme/v1/music/search/    — music search
  - /aweme/v1/challenge/detail/
  - /aweme/v1/challenge/aweme/
"""
from __future__ import annotations

from typing import Any

from .device import SEARCH_BASE
from .transport import AndroidTransport


class SearchAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def general(
        self,
        keyword: str,
        *,
        offset: int = 0,
        count: int = 10,
        search_source: str = "normal_search",
        query_type: int = 0,
        is_filter_search: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v1/general/search/single/ — universal search."""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/general/search/single/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
            "search_source": search_source,
            "query_type": query_type,
            "is_filter_search": is_filter_search,
        })

    def discover(self, keyword: str, *, offset: int = 0, count: int = 10) -> dict[str, Any]:
        """/aweme/v1/discover/search/ — requires search host."""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/discover/search/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
        })

    def videos(
        self,
        keyword: str,
        *,
        offset: int = 0,
        count: int = 10,
        sort_type: int = 0,
        publish_time: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v1/search/item/ — search videos only."""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/search/item/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
            "sort_type": sort_type,
            "publish_time": publish_time,
        })

    def suggestions(self, keyword: str, *, count: int = 10) -> dict[str, Any]:
        """/aweme/v1/search/sug/ — autocomplete suggestions."""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/search/sug/", params={
            "keyword": keyword,
            "count": count,
        })

    def hot_list(self) -> dict[str, Any]:
        """/aweme/v2/category/list/ — trending/category feed (replaces deprecated hot/search/list)."""
        return self._t.get("/aweme/v2/category/list/")

    def hashtag_search(self, keyword: str, *, offset: int = 0, count: int = 10) -> dict[str, Any]:
        """/aweme/v1/challenge/search/"""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/challenge/search/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
        })

    def hashtag_detail(self, challenge_id: str = "", challenge_name: str = "") -> dict[str, Any]:
        """/aweme/v1/challenge/detail/"""
        params: dict[str, Any] = {}
        if challenge_id:
            params["ch_id"] = challenge_id
        if challenge_name:
            params["challenge_name"] = challenge_name
        return self._t.get("/aweme/v1/challenge/detail/", params=params)

    def hashtag_videos(
        self,
        challenge_id: str,
        *,
        cursor: int = 0,
        count: int = 10,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v1/challenge/aweme/ — videos under a hashtag."""
        return self._t.get("/aweme/v1/challenge/aweme/", params={
            "ch_id": challenge_id,
            "cursor": cursor,
            "count": count,
            "sort_type": sort_type,
        })

    def user_suggestions(self, keyword: str, *, count: int = 10) -> dict[str, Any]:
        """/aweme/v1/search/user/sug/"""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/search/user/sug/", params={
            "keyword": keyword,
            "count": count,
        })

    def search_history(self) -> dict[str, Any]:
        """/aweme/v1/search/history/ — requires search host."""
        return self._t.get(f"{SEARCH_BASE}/aweme/v1/search/history/")
