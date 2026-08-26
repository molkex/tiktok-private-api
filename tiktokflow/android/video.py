"""Video endpoints: detail, create, delete, stats, collections.

/aweme/v1/aweme/detail/ — полная информация о видео.
/aweme/v1/multi/aweme/detail/ — batch detail нескольких видео.
/aweme/v1/aweme/post/ — свои посты.
/aweme/v1/aweme/favorite/ — свои лайкнутые.
/aweme/v1/aweme/collect/ — добавить в закладки.
/aweme/v1/aweme/delete/ — удалить видео.
/aweme/v1/aweme/stats/ — статистика видео.
/aweme/v1/private/aweme/ — приватные видео.
/aweme/v1/aweme/listcollection/ — все коллекции.
/aweme/v1/feed/ (type=5) — related/you-may-like videos for an aweme.
/aweme/v1/data/insighs/ — creator video analytics/insights (retention curve,
    like distribution, follower/live history). TikTok's own typo in the path
    ("insighs") and in one JSON field ("distrubution") — verified against
    v46, not our bug."""
from __future__ import annotations

import json
from typing import Any

from ..errors import TikTokError
from .transport import AndroidTransport

class VideoAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def detail(self, aweme_id: str, *, web_fallback: bool = True) -> dict[str, Any]:
        """/aweme/v1/aweme/detail/ with web scraping fallback."""
        result: dict[str, Any] | None = None
        try:
            result = self._t.get("/aweme/v1/aweme/detail/", params={
                "aweme_id": aweme_id,
            })
        except TikTokError:
            pass
        if result and result.get("aweme_detail"):
            return result
        if web_fallback:
            from .web_scraper import video_detail_web
            web = video_detail_web(aweme_id)
            if web:
                return web
        return result or {}

    def multi_detail(self, aweme_ids: list[str], *, web_fallback: bool = True) -> dict[str, Any]:
        """/aweme/v1/multi/aweme/detail/ — batch fetch multiple videos."""
        result = self._t.post("/aweme/v1/multi/aweme/detail/", data={
            "aweme_ids": json.dumps(aweme_ids),
        }, bare=True)
        if result.get("_empty") and web_fallback:
            from .web_scraper import multi_detail_web
            web = multi_detail_web(aweme_ids)
            if web:
                return web
        return result

    def my_posts(
        self,
        user_id: str = "",
        sec_user_id: str = "",
        *,
        max_cursor: int = 0,
        count: int = 20,
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/aweme/post/ — user's posted videos."""
        params: dict[str, Any] = {
            "max_cursor": max_cursor,
            "count": count,
        }
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        result = self._t.get("/aweme/v1/aweme/post/", params=params, bare=True)
        if result.get("_empty") and web_fallback and sec_user_id:
            from .web_scraper import user_posts_web
            web = user_posts_web(sec_user_id, cursor=max_cursor, count=count)
            if web:
                web["_source"] = "web_api"
                return web
        return result

    def favorites(
        self,
        user_id: str = "",
        sec_user_id: str = "",
        *,
        max_cursor: int = 0,
        count: int = 20,
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/aweme/favorite/ — liked videos."""
        params: dict[str, Any] = {
            "max_cursor": max_cursor,
            "count": count,
        }
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        result = self._t.get("/aweme/v1/aweme/favorite/", params=params, bare=True)
        if result.get("_empty") and web_fallback and sec_user_id:
            from .web_scraper import user_favorites_web
            web = user_favorites_web(sec_user_id, cursor=max_cursor, count=count)
            if web:
                web["_source"] = "web_api"
                return web
        return result

    def collect(self, aweme_id: str, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/aweme/collect/ — bookmark (1) or unbookmark (0).
        CDN path-level blocked: returns empty body regardless of bypass."""
        return self._t.post("/aweme/v1/aweme/collect/", params={
            "aweme_id": aweme_id,
            "action": action,
        }, full_sign=True)

    def uncollect(self, aweme_id: str) -> dict[str, Any]:
        return self.collect(aweme_id, action=0)

    def list_collections(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/aweme/listcollection/ — bookmarked videos."""
        return self._t.get("/aweme/v1/aweme/listcollection/", params={
            "cursor": cursor,
            "count": count,
        }, bare=True)

    def delete(self, aweme_id: str) -> dict[str, Any]:
        """/aweme/v1/aweme/delete/"""
        return self._t.post("/aweme/v1/aweme/delete/", data={
            "aweme_id": aweme_id,
        }, full_sign=True)

    def stats(self, aweme_id: str, *, web_fallback: bool = True) -> dict[str, Any]:
        """/aweme/v1/aweme/stats/ with video_detail fallback for stats extraction."""
        result = self._t.get("/aweme/v1/aweme/stats/", params={
            "aweme_id": aweme_id,
        }, bare=True)
        if result.get("_empty") and web_fallback:
            detail = self.detail(aweme_id)
            aweme = detail.get("aweme_detail", {})
            s = aweme.get("statistics")
            if s:
                return {"aweme_id": aweme_id, "statistics": s, "status_code": 0, "_source": "video_detail"}
        return result

    def private_list(self, *, max_cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/private/aweme/ — own private videos."""
        result = self._t.get("/aweme/v1/private/aweme/", params={
            "max_cursor": max_cursor,
            "count": count,
        })
        if result.get("aweme_list") is None:
            result["aweme_list"] = []
        return result

    def liked(
        self,
        user_id: str = "",
        sec_user_id: str = "",
        *,
        max_cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/aweme/favorite/ — alias for favorites (liked videos)."""
        return self.favorites(user_id, sec_user_id, max_cursor=max_cursor, count=count)

    def watch_history(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/aweme/v1/aweme/history/ — DEPRECATED by TikTok (returns 'Url does not match')."""
        return self._t.get("/aweme/v1/aweme/history/", params={
            "cursor": cursor,
            "count": count,
        })

    def feedback(self, aweme_id: str, feedback_type: int) -> dict[str, Any]:
        """/aweme/v1/aweme/feedback — report or feedback on a video."""
        return self._t.post("/aweme/v1/aweme/feedback", data={
            "aweme_id": aweme_id,
            "feedback_type": feedback_type,
        }, full_sign=True)

    # ── analytics / insights ─────────────────────────────────────

    # Confirmed working insigh_type values (v46, verified on emulator via
    # TTNet bridge). Requesting an unrecognized type is silently ignored
    # (no error, just no matching key in the response) rather than failing,
    # so this list is a floor, not a hard whitelist.
    INSIGHT_TYPE_RETENTION_7D = "video_retention_rate_history_7d"
    INSIGHT_TYPE_LIKE_DISTRIBUTION_7D = "video_like_distrubution_7d"  # sic — TikTok's typo, not ours

    def insights(
        self,
        aweme_id: str,
        *,
        insight_types: str | list[str] = (
            "video_retention_rate_history_7d",
            "video_like_distrubution_7d",
        ),
    ) -> dict[str, Any]:
        """/aweme/v1/data/insighs/ — creator video analytics (audience
        retention curve, like distribution, plus follower/live counters
        when present). POST, form-encoded ``type_requests`` = JSON list of
        ``{"aweme_id": ..., "insigh_type": ...}`` objects (note both typos —
        "insighs" in the path and "insigh_type" in the field name — these
        are verbatim from TikTok's own Retrofit interface
        (InterfaceC09980iYk / IAnalyticsDetailService in the v46 APK), not
        transcription errors here).

        Verified live on the emulator (v46): returns status_code=0 with the
        real InsightTypeResponse schema (comment_history, like_history,
        pv_history, share_history, follower_num_history,
        follower_active_history_days/hours, user_live_*_history,
        video_retention_rate_history_7d, video_like_distrubution_7d, ...) —
        this is NOT the gateway false-positive trap (which returns only
        {log_pb, status_code, status_msg} with no other keys).

        IMPORTANT: values only populate for videos the authenticated user
        owns. On someone else's aweme_id every requested metric comes back
        as ``{"status": 2, "value": None}`` (not eligible) — still a real,
        differentiated response, just empty because you don't have access.

        Multiple insight_types can be requested in one call; the response
        merges all recognized keys together. Two confirmed-working types
        are used by default (INSIGHT_TYPE_RETENTION_7D /
        INSIGHT_TYPE_LIKE_DISTRIBUTION_7D). "video_retention_rate_realtime"
        and "video_like_distribution_realtime" were probed and accepted
        without error but never returned a populated key on this account —
        UNVERIFIED, may need a currently-live video or different eligibility.
        """
        if isinstance(insight_types, str):
            insight_types = [insight_types]
        type_requests = json.dumps([
            {"aweme_id": aweme_id, "insigh_type": t} for t in insight_types
        ])
        return self._t.post("/aweme/v1/data/insighs/", data={
            "type_requests": type_requests,
        }, full_sign=True)

    def insights_v2(self, aweme_id: str, *, insight_type: str = "video_retention_rate_history_7d") -> dict[str, Any]:
        """/aweme/v2/data/insight — UNVERIFIED newer sibling of insights().
        GET with query param ``type_requests`` (same JSON shape). The route
        is real (confirmed via v46 InterfaceC09980iYk decompile) and
        distinguishes itself from the gateway trap by returning
        status_code=5 "Invalid parameters" instead of the trap's
        status_code=0 "url doesn't match" — but the exact parameter
        contract it wants beyond type_requests was not found before this
        returned code=5, so it never produced real data in testing. Prefer
        insights() (v1), which is confirmed working."""
        type_requests = json.dumps([{"aweme_id": aweme_id, "insigh_type": insight_type}])
        return self._t.get("/aweme/v2/data/insight", params={
            "type_requests": type_requests,
        })

    def related(self, aweme_id: str, *, count: int = 6) -> dict[str, Any]:
        """/aweme/v1/feed/ with type=5 — "related/you may like" videos for
        a given aweme. The dedicated /aweme/v1/aweme/related/ endpoint is
        DEPRECATED in v46 (returns 'Url does not match'), but the generic
        feed endpoint still serves related content when called with
        type=5 (video-relate feed) + aweme_id. Verified: the returned
        aweme_list changes based on aweme_id (first item is the seed
        video itself, followed by genuinely related videos)."""
        return self._t.get("/aweme/v1/feed/", params={
            "count": count,
            "type": 5,
            "aweme_id": aweme_id,
        })
