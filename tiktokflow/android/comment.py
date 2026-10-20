"""Comment endpoints: list, publish, delete, like, replies.

/aweme/v2/comment/list/ — комментарии к видео.
/aweme/v1/comment/list/reply/ — ответы на комментарий.
/aweme/v1/comment/publish/ — написать комментарий.
/aweme/v1/comment/delete/ — удалить комментарий.
/aweme/v1/comment/digg/ — лайк/дизлайк комментария."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport


class CommentAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def list(
        self,
        aweme_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v2/comment/list/ with web API fallback for v46.7.3 version gate."""
        result = self._t.get("/aweme/v2/comment/list/", params={
            "aweme_id": aweme_id,
            "cursor": cursor,
            "count": count,
        }, bare=True)
        if result.get("_empty") and web_fallback:
            from .web_scraper import comments_web
            web = comments_web(aweme_id, cursor=cursor, count=count)
            if web:
                web["_source"] = "web_api"
                return web
        return result

    def replies(
        self,
        aweme_id: str,
        comment_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/aweme/v1/comment/list/reply/ — replies to a comment."""
        return self._t.get("/aweme/v1/comment/list/reply/", params={
            "item_id": aweme_id,
            "comment_id": comment_id,
            "cursor": cursor,
            "count": count,
        })

    def publish(
        self,
        aweme_id: str,
        text: str,
        *,
        reply_id: str = "",
    ) -> dict[str, Any]:
        """/aweme/v1/comment/publish/ — post a comment (or reply).
        Uses curl_cffi write bypass for Envoy SC."""
        params: dict[str, Any] = {"aweme_id": aweme_id}
        if reply_id:
            params["reply_id"] = reply_id
        from urllib.parse import urlencode as _ue
        body = _ue({"text": text, "aweme_id": aweme_id}).encode()
        return self._t.post(
            "/aweme/v1/comment/publish/",
            params=params,
            content=body,
            write=True,
            full_sign=True,
        )

    def delete(self, aweme_id: str, comment_id: str) -> dict[str, Any]:
        """/aweme/v1/comment/delete/ — delete own comment.

        The POST body field must be named ``cid``, NOT ``comment_id`` (query
        params still use ``comment_id``). Sending ``comment_id`` in the body
        makes the server return status_code=4 "Server is currently
        unavailable" for every request, even against a comment the account
        owns; verified live against emulator (@1232140499y) that switching
        the body key to ``cid`` returns status_code=0."""
        from urllib.parse import urlencode as _ue
        body = _ue({"aweme_id": aweme_id, "cid": comment_id}).encode()
        return self._t.post("/aweme/v1/comment/delete/", params={
            "aweme_id": aweme_id,
            "comment_id": comment_id,
        }, content=body, write=True, full_sign=True)

    def digg(self, aweme_id: str, comment_id: str, *, digg_type: int = 1) -> dict[str, Any]:
        """/aweme/v1/comment/digg/ — like (1) or unlike (0) a comment."""
        from urllib.parse import urlencode as _ue
        body = _ue({"aweme_id": aweme_id, "comment_id": comment_id, "digg_type": str(digg_type)}).encode()
        return self._t.post("/aweme/v1/comment/digg/", params={
            "aweme_id": aweme_id,
            "comment_id": comment_id,
            "digg_type": digg_type,
        }, content=body, write=True, full_sign=True)

    def pin(self, aweme_id: str, comment_id: str, *, op: int = 1) -> dict[str, Any]:
        """/tiktok/comment/pin/v1 — creator pins (op=1) or unpins (op=2) a
        top comment on their own video.

        VERIFIED live against the emulator (@1232140499y, v46): path exists
        and reaches real business logic (not the gateway false-positive
        trap — that returns status_code=0/"url doesn't match" with no other
        keys, over GET; this endpoint only accepts POST and returns
        status_code=4). Field names were determined by live probing:
        {aweme_id, comment_id, action} → status_code=4 "Invalid parameters
        code=5" (wrong field names, rejected before reaching business
        logic); {item_id, comment_id, op=1 or op=2} → status_code=4
        "Server is currently unavailable code=4" reproducibly, INCLUDING
        against a garbage item_id, i.e. this is TikTok's generic masked
        "comment not found" response, not a real server outage — the
        request format itself is accepted. {item_id, comment_id, op=0} was
        rejected as "Invalid parameters", confirming op is a 1/2 enum
        (pin/unpin), not a 1/0 toggle like this file's digg().

        Could not be verified end-to-end with a real success response: the
        two videos on this test account both return "This video does not
        exist code=2209" from comment.publish(), so no real comment_id to
        pin was obtainable in this session."""
        from urllib.parse import urlencode as _ue
        body = _ue({"item_id": aweme_id, "comment_id": comment_id, "op": str(op)}).encode()
        return self._t.post("/tiktok/comment/pin/v1", params={
            "item_id": aweme_id,
            "comment_id": comment_id,
            "op": op,
        }, content=body, write=True, full_sign=True)

    def unpin(self, aweme_id: str, comment_id: str) -> dict[str, Any]:
        return self.pin(aweme_id, comment_id, op=2)
