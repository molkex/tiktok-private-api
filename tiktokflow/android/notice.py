"""Notification endpoints.

/aweme/v1/notice/multi/ — all notifications aggregated.
/aweme/v1/notice/count/ — unread notification count.
/aweme/v1/inbox/agg_list/ — inbox aggregate list."""
from __future__ import annotations

from typing import Any

from ..errors import TikTokError
from .transport import AndroidTransport


class NoticeAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def multi(
        self,
        *,
        max_time: int = 0,
        count: int = 20,
        notice_group: int = 32,
    ) -> dict[str, Any]:
        """/aweme/v1/notice/multi/ — paginated notification list."""
        return self._t.get("/aweme/v1/notice/multi/", params={
            "max_time": max_time,
            "count": count,
            "notice_group": notice_group,
        })

    def count(self) -> dict[str, Any]:
        """/aweme/v1/notice/count/ — unread count."""
        return self._t.get("/aweme/v1/notice/count/")

    def inbox(
        self,
        *,
        cursor: int = 0,
        count: int = 20,
        fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/inbox/agg_list/ — aggregated inbox.

        DEPRECATED server-side. Live probing (2026-08-26) found this path
        returns status_code=4 "Server is currently unavailable" for every
        variant tried (no params, ``type``, ``min_time``, ``max_cursor``,
        ``box_type``) even though ``notice/multi`` and ``notice/count`` work
        fine on the same account — same code=4 fingerprint as the other
        endpoints found deprecated in this pass. No sibling inbox path
        exists (checked ``/aweme/v1/tako/inbox/state/`` too — unrelated).
        With ``fallback=True`` (default) this transparently falls back to
        ``multi()``, which is the working replacement TikTok's own app now
        uses for aggregated notifications."""
        try:
            return self._t.get("/aweme/v1/inbox/agg_list/", params={
                "cursor": cursor,
                "count": count,
            })
        except TikTokError:
            if not fallback:
                raise
            result = self.multi(max_time=cursor, count=count)
            if isinstance(result, dict):
                result["_source"] = "notice_multi_fallback"
            return result

    def delete(self, notice_id: str) -> dict[str, Any]:
        """/aweme/v1/notice/del/"""
        return self._t.post("/aweme/v1/notice/del/", data={
            "notice_id": notice_id,
        }, full_sign=True)

    def shield(self, notice_type: int, *, action: int = 1) -> dict[str, Any]:
        """/aweme/v1/notice/shield/ — mute a notification type."""
        return self._t.post("/aweme/v1/notice/shield/", data={
            "notice_type": notice_type,
            "type": action,
        }, full_sign=True)
