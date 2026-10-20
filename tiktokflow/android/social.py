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

    def follow(
        self,
        user_id: str,
        *,
        action: int = 1,
        sec_user_id: str = "",
        channel_id: int = 3,
        from_page: int = 19,
        from_pre: int = 50,
        raw: bool = False,
    ) -> dict[str, Any]:
        """/aweme/v1/commit/follow/user/
        action: 1 = follow, 0 = unfollow."""
        if str(user_id) == "6971822573634978822":
            raise ValueError("Inviolable constraint: cannot modify relationship with @cnn (uid 6971822573634978822)")
        import time
        from urllib.parse import urlencode

        action_time = int(time.time() * 1000)
        form_data = {
            "action_time": str(action_time),
            "channel_id": str(channel_id),
            "from": str(from_page),
            "from_pre": str(from_pre),
            "is_network_available": "true",
            "previous_page": "",
            "type": str(action),
            "user_id": str(user_id),
        }
        if sec_user_id:
            form_data["sec_user_id"] = sec_user_id

        body = urlencode(form_data).encode("utf-8")
        return self._t.post(
            "/aweme/v1/commit/follow/user/",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            write=True,
            full_sign=True,
            raw=raw,
        )

    def unfollow(self, user_id: str, *, sec_user_id: str = "", raw: bool = False) -> dict[str, Any]:
        if str(user_id) == "6971822573634978822":
            raise ValueError("Inviolable constraint: cannot modify relationship with @cnn (uid 6971822573634978822)")
        return self.follow(user_id, action=0, sec_user_id=sec_user_id, raw=raw)

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

    # ── repost ──────────────────────────────────────────────────────
    # TikTok's server/client code calls this feature "upvote" internally
    # (RepostXxx UI classes wrap an IUpvoteService / UpvotePublishVM that
    # posts to /tiktok/v1/upvote/...). Confirmed via static string
    # extraction from the v46 APK (work/all_strings.txt) — the literal
    # path constants "/tiktok/v1/upvote/publish/" and "tiktok/v1/upvote/delete"
    # both exist verbatim, alongside a "repost_type" form field used
    # elsewhere in the same feature's model classes
    # (feed/model/upvote/CarrierType, upvote/model/UpvoteDeleteResponse).
    # Not yet live-verified against a real response payload — see
    # AndroidClient.social.repost()/unrepost() call sites in the
    # verification report for status.

    def repost(self, aweme_id: str, *, repost_type: int = 1) -> dict[str, Any]:
        """/tiktok/v1/upvote/publish/ — repost (a.k.a. "upvote") a video to
        your own profile/feed.

        VERIFIED live against the emulator (@1232140499y, v46): the field
        name is ``item_id``, not ``aweme_id`` — sending ``aweme_id`` gets
        rejected pre-business-logic with status_code=4 "Invalid
        parameters"; ``item_id`` reaches real handling. ``repost_type``
        also matters: 0 or 2 return a stable status_code=4
        "status_code=2721 code=2721"; repost_type=1 returned one genuine
        status_code=0 success (real payload, not the gateway trap) against
        a fresh feed video — confirming 1 is the right value — but repeat
        calls (including against other fresh videos, and retrying the same
        video after unrepost() cleanly removed it) mostly reproduce 2721
        again. Net: the request shape ({item_id, repost_type=1}) is
        confirmed correct; 2721 looks like an anti-abuse/rate throttle
        or an account/video eligibility gate rather than a parameter
        error, since it also fires on brand-new targets right after a
        clean delete. Treat this as VERIFIED-but-flaky rather than
        reliably reproducible on demand."""
        return self._t.post("/tiktok/v1/upvote/publish/", params={
            "item_id": aweme_id,
            "repost_type": repost_type,
        }, write=True, full_sign=True)

    def unrepost(self, aweme_id: str) -> dict[str, Any]:
        """/tiktok/v1/upvote/delete/ — remove a previously created repost.

        VERIFIED live: {item_id: aweme_id} returns status_code=0 with a
        real payload (``delete_result: {delete_video_status, sync_delete_video}``)
        reliably and repeatably, including when called against a video
        that was never successfully reposted (idempotent/safe — matches
        the collect()/like() family's unconditional-success behavior
        elsewhere in this codebase)."""
        return self._t.post("/tiktok/v1/upvote/delete/", params={
            "item_id": aweme_id,
        }, write=True, full_sign=True)
