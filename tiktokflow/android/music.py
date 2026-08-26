"""Music endpoints: detail, search, videos by music, collections.

/aweme/v1/music/detail/ — информация о треке.
/aweme/v1/music/aweme/ — видео с этим треком.
/aweme/v1/music/search/ — поиск музыки.
/aweme/v1/music/collect/ — добавить/убрать трек в избранное.
/aweme/v1/music/list/ — рекомендованные треки.
/aweme/v1/hot/music/ — трендовые треки."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport

class MusicAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def detail(self, music_id: str, *, web_fallback: bool = True) -> dict[str, Any]:
        """/aweme/v1/music/detail/ with fallback via music.videos extraction."""
        result = self._t.get("/aweme/v1/music/detail/", params={
            "music_id": music_id,
        }, bare=True)
        if result.get("_empty") and web_fallback:
            from .web_scraper import music_detail_web
            web = music_detail_web(music_id)
            if web:
                return {"music_info": web, "_source": "web_scraping"}
            vids = self.videos(music_id, count=1)
            aweme_list = vids.get("aweme_list", [])
            if aweme_list:
                music = aweme_list[0].get("music", {})
                if music:
                    return {"music_info": music, "status_code": 0, "_source": "music_videos"}
        return result

    def videos(
        self,
        music_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v1/music/aweme/ — videos using this music."""
        return self._t.get("/aweme/v1/music/aweme/", params={
            "music_id": music_id,
            "cursor": cursor,
            "count": count,
            "sort_type": sort_type,
        })

    def search(
        self,
        keyword: str,
        *,
        offset: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/music/search/"""
        return self._t.get("/aweme/v1/music/search/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
        })

    def collect(self, music_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/music/collect/ — DEPRECATED (returns 'url doesn't match').
        1=save, 0=remove."""
        return self._t.post("/aweme/v1/music/collect/", data={
            "music_id": music_id,
            "type": action,
        }, full_sign=True)

    def recommended(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/music/choices/ — recommended music list (video-creation music picker).

        ``/aweme/v1/music/list/`` (the old path) is DEPRECATED server-side:
        live probing (2026-08-26) found it returns status_code=4 "Server is
        currently unavailable" for every param combination tried (no params,
        ``music_list_type``, ``scene``, ``type``), while sibling paths like
        ``/aweme/v1/commerce/music/list/`` give the same code=4 and
        ``/aweme/v1/original/music/list/`` gives a different error
        (status_code=5, so it exists but wants other params — it's for a
        creator's original-sound catalog, not general recommendations).
        ``/aweme/v1/music/choices/`` was confirmed working with status_code=0
        and a populated ``music_list`` using the same cursor/count params —
        it's the music panel used when creating a video.
        ``/aweme/v1/music/beats/songs/`` also works with the same shape and
        is a viable alternative if ``choices`` is later restricted."""
        return self._t.get("/aweme/v1/music/choices/", params={
            "cursor": cursor,
            "count": count,
        })

    def hot(self) -> dict[str, Any]:
        """/aweme/v1/hot/music/ — trending music (ycru host)."""
        return self._t.get("/aweme/v1/hot/music/")

    def collection(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/music/collection/ — saved music."""
        return self._t.get("/aweme/v1/music/collection/", params={
            "cursor": cursor,
            "count": count,
        })

    def user_collected(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/user/music/collect/ — user's saved music."""
        return self._t.get("/aweme/v1/user/music/collect/", params={
            "cursor": cursor,
            "count": count,
        })
