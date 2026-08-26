"""Live streaming endpoints: rooms, chat, gifts, recommendations.

Verified against v46 on the logged-in emulator (TTNet bridge). Every
/aweme/v1/live/room/*, /aweme/v1/live/comment/*, /aweme/v1/live/like/,
/aweme/v1/live/gift/send/ and /aweme/v1/live/recommend/ call now returns
HTTP 502 — identical to a deliberately bogus path probed as a baseline
(/aweme/v1/live/totally/bogus/path/), meaning the gateway no longer routes
these at all in v46 (dead, not a soft "url doesn't match" JSON trap, but
the same conclusion: no route). None of these appear as literal strings in
the v46 APK's dex either (grepped every classes*.dex), consistent with the
mobile client no longer using the /aweme/v1/live/* namespace for the live
feature — TikTok's live product has moved to the separate `webcast`
surface, which is out of scope for this pass (no webcast client wired into
this SDK yet).

Only /aweme/v1/live/search/ is confirmed alive: real, differentiated
results (room_id, author, room_cover change per keyword/run) with
status_code=0.

/aweme/v1/live/room/enter/ — DEAD (HTTP 502).
/aweme/v1/live/room/leave/ — DEAD (HTTP 502).
/aweme/v1/live/room/info/ — DEAD (HTTP 502).
/aweme/v1/live/room/create/ — DEAD (HTTP 502).
/aweme/v1/live/room/finish/ — DEAD (HTTP 502).
/aweme/v1/live/room/audience/ — DEAD (HTTP 502).
/aweme/v1/live/comment/list/ — DEAD (HTTP 502).
/aweme/v1/live/comment/send/ — DEAD (HTTP 502).
/aweme/v1/live/like/ — DEAD (HTTP 502).
/aweme/v1/live/gift/send/ — DEAD (HTTP 502).
/aweme/v1/live/recommend/ — DEAD (HTTP 502).
/aweme/v1/live/search/ — CONFIRMED WORKING (status_code=0, real rooms)."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport

class LiveAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    # ── room management ──────────────────────────────────────────

    def room_enter(self, room_id: str) -> dict[str, Any]:
        """/aweme/v1/live/room/enter/ — DEAD in v46: confirmed HTTP 502 on the
        emulator (same as a bogus-path baseline), no route. Kept for API
        shape / future reactivation only."""
        return self._t.post("/aweme/v1/live/room/enter/", data={
            "room_id": room_id,
        }, full_sign=True)

    def room_leave(self, room_id: str) -> dict[str, Any]:
        """/aweme/v1/live/room/leave/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.post("/aweme/v1/live/room/leave/", data={
            "room_id": room_id,
        }, full_sign=True)

    def room_info(self, room_id: str) -> dict[str, Any]:
        """/aweme/v1/live/room/info/ — DEAD in v46: confirmed HTTP 502, even
        against a real room_id pulled from a live search() result."""
        return self._t.get("/aweme/v1/live/room/info/", params={
            "room_id": room_id,
        })

    def room_create(self, title: str, *, live_type: int = 0) -> dict[str, Any]:
        """/aweme/v1/live/room/create/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.post("/aweme/v1/live/room/create/", data={
            "title": title,
            "live_type": live_type,
        }, full_sign=True)

    def room_finish(self, room_id: str) -> dict[str, Any]:
        """/aweme/v1/live/room/finish/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.post("/aweme/v1/live/room/finish/", data={
            "room_id": room_id,
        }, full_sign=True)

    def room_audience(
        self,
        room_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/live/room/audience/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.get("/aweme/v1/live/room/audience/", params={
            "room_id": room_id,
            "cursor": cursor,
            "count": count,
        })

    # ── live chat ─────────────────────────────────────────────────

    def comment_list(
        self,
        room_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/live/comment/list/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.get("/aweme/v1/live/comment/list/", params={
            "room_id": room_id,
            "cursor": cursor,
            "count": count,
        })

    def comment_send(self, room_id: str, text: str) -> dict[str, Any]:
        """/aweme/v1/live/comment/send/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.post("/aweme/v1/live/comment/send/", data={
            "room_id": room_id,
            "content": text,
        }, full_sign=True)

    # ── interactions ──────────────────────────────────────────────

    def like(self, room_id: str, *, count: int = 1) -> dict[str, Any]:
        """/aweme/v1/live/like/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.post("/aweme/v1/live/like/", data={
            "room_id": room_id,
            "count": count,
        }, full_sign=True)

    def gift_send(
        self,
        room_id: str,
        gift_id: str,
        *,
        count: int = 1,
        to_user_id: str = "",
    ) -> dict[str, Any]:
        """/aweme/v1/live/gift/send/ — DEAD in v46: confirmed HTTP 502. Not
        found as a literal path in the v46 APK dex either; the live-gifting
        flow has moved off /aweme/v1/live/* (likely to a webcast-domain
        endpoint not covered by this client)."""
        payload: dict[str, Any] = {
            "room_id": room_id,
            "gift_id": gift_id,
            "gift_count": count,
        }
        if to_user_id:
            payload["to_user_id"] = to_user_id
        return self._t.post("/aweme/v1/live/gift/send/", data=payload, full_sign=True)

    # ── discovery ─────────────────────────────────────────────────

    def recommend(self, *, count: int = 6) -> dict[str, Any]:
        """/aweme/v1/live/recommend/ — DEAD in v46: confirmed HTTP 502."""
        return self._t.get("/aweme/v1/live/recommend/", params={
            "count": count,
        })

    def search(
        self,
        keyword: str,
        *,
        offset: int = 0,
        count: int = 10,
    ) -> dict[str, Any]:
        """/aweme/v1/live/search/ — CONFIRMED WORKING in v46: status_code=0
        with real, differentiated results per keyword (verified: room_id /
        author / room_cover change across calls; type=1 items carry a live
        'lives' room with a real room_id, type=2 items are matched user
        accounts with no active room)."""
        return self._t.get("/aweme/v1/live/search/", params={
            "keyword": keyword,
            "offset": offset,
            "count": count,
        })
