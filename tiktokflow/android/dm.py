"""Direct message (IM) endpoints.

IMPORTANT — verified against work/all_strings.txt (decompiled libmetasec_ov +
resource strings) and work/eps_aweme.txt / work/eps_api.txt:

The guessed `/aweme/v1/im/...` REST scheme does NOT exist in the APK. The only
confirmed path under /aweme/v1/im/ is `/aweme/v1/im/cloud/token/` (used to
fetch an upload token for IM media attachments — see `cloud_token()` below).

TikTok's actual DM stack is a separate ByteDance IM SDK
(`com.bytedance.im.core` / `com.ss.android.ugc.aweme.im.core`), primarily a
persistent socket/long-poll channel for realtime delivery, with an HTTP
fallback API on bare `/v1/`, `/v2/`, `/v3/` paths (no `/aweme` prefix) served
from im-va.tiktokv.com. A route table found in the strings dump
(act_priority host_replace rules) shows a subset of these same bare paths —
including /v1/conversation/list, /v1/message/send, /v1/message/get_by_conversation,
/v3/conversation/mark_read — get redirected to `api-normal.tiktokv.com`, i.e.
the same host class AndroidTransport already talks to. That's the basis for
routing these calls through the existing AndroidTransport/signing pipeline
below instead of standing up a second client for im-va.tiktokv.com.

Most of this has not been confirmed against live traffic, so treat field
names/response shapes as best-effort from the string tables and adjust once
you can see a real response. Exception: send() and the Request/RequestBody/
Response/ResponseBody envelope it builds ARE confirmed, both by decompiling
com.bytedance.im.core.proto (classes10.dex/classes37.dex, Square Wire
messages -- exact field numbers) and by live-testing against emulator-5554 --
see send()'s docstring. The same envelope almost certainly applies to every
other bare `/v1/`, `/v2/`, `/v3/` POST below (they currently post
form-urlencoded `data=` instead, like send() used to), but only send() has
been fixed to use it. No `mute` RPC was found in the string tables; ConversationModelImpl
mute()/setMute() traces down to `conversation/set_setting_info` (or the batch
variant) in the decompiled client, so `mute()` below targets that endpoint
using a guessed field name — verify before relying on it.

Confirmed bare paths (work/all_strings.txt ~line 121170-121260):
/v1/conversation/list, /v1/conversation/get_core_info, /v1/conversation/delete,
/v1/conversation/leave, /v1/conversation/mark_read, /v3/conversation/mark_read,
/v1/conversation/block_conversation, /v1/conversation/set_setting_info,
/v1/conversation/batch_set_setting_info, /v2/conversation/create,
/v1/message/get_by_conversation, /v1/message/send, /v1/message/delete,
/v1/message/recall, /v1/client/unread_count, /v1/stranger/get_conversation_list,
/v1/stranger/get_messages, /v1/stranger/delete_conversation.
"""
from __future__ import annotations

import random
import time
from typing import Any

from .crypto import ProtoBuf
from .transport import AndroidTransport


def _new_client_message_id() -> str:
    """Generate a snowflake-ish numeric client_message_id (ms timestamp +
    3 random digits), matching the shape real IM SDK clients use. The server
    only uses this for de-dup/idempotency and echoes it back; exact format
    isn't validated, but a plain numeric string is the safe/common choice."""
    return f"{int(time.time() * 1000)}{random.randint(0, 999):03d}"


# cmd used to select the "send message" RPC inside the Request/Response
# envelope (see send() docstring). CONFIRMED live against im-va.tiktokv.com
# via api-normal.tiktokv.com: cmd=1 with a RequestBody.send_message_body
# (field 1) payload gets past envelope/schema validation (a wrong cmd or a
# body in the wrong RequestBody field produces "failed to decode Protobuf
# message: ..." at status_code=500; this configuration instead reaches real
# business logic and returns the same account-level status_code=200001 seen
# on every other DM read endpoint on the test account) -- see send()'s
# docstring for the full trace.
_CMD_SEND_MESSAGE = 1
_REQUESTBODY_FIELD_SEND_MESSAGE = 1
# ResponseBody's mirrored oneof field for the reply is UNCONFIRMED (this
# account never got past the 200001 precondition to observe a real success
# envelope) -- guessed as 1 by analogy with RequestBody, whose field 1 is
# also send_message_body (both were generated from the same ordered list of
# IM RPCs, so the numbering is very likely mirrored 1:1).
_RESPONSEBODY_FIELD_SEND_MESSAGE = 1


def _decode_send_response(result: dict) -> dict[str, Any]:
    """Unwrap com.bytedance.im.core.proto.Response -> ResponseBody ->
    SendMessageResponseBody from the generic field-number-keyed decode (see
    send()'s docstring for how each layer's field numbers were confirmed).

    Response (top level; CONFIRMED live -- these are exactly the fields that
    come back for every DM endpoint on this account, success or error):
        1 cmd  3 status_code(0=success)  4 error_desc  6 body(ResponseBody)
        7 log_id
    ResponseBody.send_message_body: field 1, UNCONFIRMED (see above).
    SendMessageResponseBody (CONFIRMED type/field-numbers via decompile,
    contents UNCONFIRMED live -- see send() docstring):
        1 server_message_id  2 extra_info  3 status  4 client_message_id
        5 check_code  6 check_message  7 filtered_content  8 is_async_send
        9 new_ticket  10 conversation(ConversationInfoV2)

    decode_generic()'s top-level status_code/status_msg guess (fields 1/2 as
    a common BaseResp) happens to be CORRECT for field 1 by coincidence with
    Response.cmd but WRONG in spirit (it's not a status) and misses
    status_code entirely (real one is field 3) -- this ignores it and reads
    _raw directly."""
    env = result.get("_raw", {}) if isinstance(result, dict) else {}

    def g(d: dict, idx: int) -> Any:
        # decode_raw()/_jsonify() always store field values as a list (one
        # entry per occurrence on the wire, to support repeated fields) --
        # unwrap to the first (only, for these singular fields) value.
        if not isinstance(d, dict):
            return None
        vals = d.get(str(idx))
        if not vals:
            return None
        return vals[0] if isinstance(vals, list) else vals

    status_code = g(env, 3)
    body = g(env, 6)
    inner = g(body, _RESPONSEBODY_FIELD_SEND_MESSAGE) if isinstance(body, dict) else None

    out: dict[str, Any] = {
        "status_code": status_code if isinstance(status_code, int) else None,
        "error_desc": g(env, 4),
        "log_id": g(env, 7),
        "status": None,
        "server_message_id": None,
        "client_message_id": None,
        "new_ticket": None,
        "check_code": None,
        "check_message": None,
        "filtered_content": None,
        "is_async_send": None,
        "conversation": None,
        "_raw": env,
    }
    if isinstance(inner, dict):
        st = g(inner, 3)
        out["status"] = st if isinstance(st, int) else None
        out["server_message_id"] = g(inner, 1)
        out["client_message_id"] = g(inner, 4)
        out["new_ticket"] = g(inner, 9)
        out["check_code"] = g(inner, 5)
        out["check_message"] = g(inner, 6)
        out["filtered_content"] = g(inner, 7)
        is_async = g(inner, 8)
        out["is_async_send"] = bool(is_async) if is_async is not None else None
        out["conversation"] = g(inner, 10)
    return out


class DMAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    # -- conversations --------------------------------------------------

    def conversations(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/v1/conversation/list — paginated conversation (chat) list."""
        return self._t.get("/v1/conversation/list/", params={
            "cursor": cursor,
            "count": count,
        }, proto_mode="generic")

    def conversation_detail(self, conversation_id: str) -> dict[str, Any]:
        """/v1/conversation/get_core_info — single conversation detail."""
        return self._t.get("/v1/conversation/get_core_info/", params={
            "conversation_id": conversation_id,
        }, proto_mode="generic")

    def create_conversation(self, to_user_id: str) -> dict[str, Any]:
        """/v2/conversation/create — get-or-create a 1:1 conversation with a user.
        Needed before send() if no conversation_id is known yet."""
        return self._t.post("/v2/conversation/create/", data={
            "user_id": to_user_id,
        }, full_sign=True, proto_mode="generic")

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        """/v1/conversation/delete"""
        return self._t.post("/v1/conversation/delete/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    def leave_conversation(self, conversation_id: str) -> dict[str, Any]:
        """/v1/conversation/leave — leave a group conversation."""
        return self._t.post("/v1/conversation/leave/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    def block_conversation(self, conversation_id: str, *, action: int = 1) -> dict[str, Any]:
        """/v1/conversation/block_conversation — block/report a conversation (spam).
        action: 1 = block, 0 = unblock."""
        return self._t.post("/v1/conversation/block_conversation/", data={
            "conversation_id": conversation_id,
            "type": action,
        }, full_sign=True, proto_mode="generic")

    def mute(self, conversation_id: str, *, action: int = 1) -> dict[str, Any]:
        """/v1/conversation/set_setting_info — mute/unmute a conversation.
        UNVERIFIED: no direct 'mute' RPC found in the string tables; the
        decompiled ConversationModelImpl.mute()/setMute() calls funnel into
        this settings endpoint. field name below ('mute_status') is a guess —
        confirm against real traffic before relying on it.
        action: 1 = mute, 0 = unmute."""
        return self._t.post("/v1/conversation/set_setting_info/", data={
            "conversation_id": conversation_id,
            "mute_status": action,
        }, full_sign=True, proto_mode="generic")

    def mark_read(self, conversation_id: str, *, read_index: str = "") -> dict[str, Any]:
        """/v3/conversation/mark_read — mark a conversation as read (latest
        version referenced in the app's own routing table; /v1/conversation/mark_read
        also exists as an older variant)."""
        payload: dict[str, Any] = {"conversation_id": conversation_id}
        if read_index:
            payload["read_index"] = read_index
        return self._t.post("/v3/conversation/mark_read/", data=payload, full_sign=True, proto_mode="generic")

    def unread_count(self) -> dict[str, Any]:
        """/v1/client/unread_count — total unread DM count across conversations."""
        return self._t.get("/v1/client/unread_count/", proto_mode="generic")

    # -- messages ---------------------------------------------------------

    def messages(
        self,
        conversation_id: str,
        *,
        cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """/v1/message/get_by_conversation — messages in a conversation."""
        return self._t.get("/v1/message/get_by_conversation/", params={
            "conversation_id": conversation_id,
            "cursor": cursor,
            "count": count,
        }, proto_mode="generic")

    def send(
        self,
        conversation_id: str,
        text: str,
        *,
        conversation_type: int = 1,
        conversation_short_id: int = 0,
        message_type: int = 1,
        ticket: str = "",
        client_message_id: str = "",
    ) -> dict[str, Any]:
        """/v1/message/send — send a text message.

        Reverse-engineered from the app's decompiled DEX (classes10.dex has
        com.bytedance.im.core.proto.SendMessageRequestBody/ResponseBody;
        classes37.dex has the RequestBody/ResponseBody envelope oneofs). All
        of these are Square Wire-generated protobuf messages, so field
        numbers come straight from their ADAPTER.encode()/decode()/<init>
        methods -- not guessed. What follows is CONFIRMED against a live
        session (emulator-5554, api-normal.tiktokv.com) except where noted:

        The POST body is NOT a bare SendMessageRequestBody -- posting one
        directly gets rejected with "failed to decode Protobuf message:
        Request.cmd: invalid wire type" (status_code=500), proving the server
        parses the body as a full envelope. The confirmed wire shape:

            Request {                            (com.bytedance.im.core.proto.Request)
              1  cmd = 1                          int32 -- selects the RPC;
                                                   1 got past validation into
                                                   real business logic (a
                                                   wrong body encoding within
                                                   the parsed envelope
                                                   changes status_code, a
                                                   wrong cmd/body-field would
                                                   still 500 with a decode
                                                   error the way the bare
                                                   SendMessageRequestBody
                                                   attempt did)
              8  body -> RequestBody {            (com.bytedance.im.core.proto.RequestBody, a ~90-field oneof-by-convention over every IM RPC)
                   1  send_message_body -> SendMessageRequestBody {
                        1  conversation_id        string
                        2  conversation_type      int32  (1=1:1 chat, 2=group
                                                           -- value itself
                                                           inferred, not a
                                                           literal found in
                                                           the decompile)
                        3  conversation_short_id  int64  (optional)
                        4  content                string (message text)
                        6  message_type           int32  (1=text -- inferred,
                                                           matches this
                                                           method's previous
                                                           content_type=1
                                                           guess)
                        7  ticket                 string (see below)
                        8  client_message_id      string (idempotency key)
                      }
                 }
            }

        ticket: ConversationInfoV2 (what conversations()/conversation_detail()
        decode into _raw -- field 4) carries a per-conversation anti-abuse
        `ticket` a send must echo back in SendMessageRequestBody field 7; the
        response returns a fresh `new_ticket` to use next time. If not passed
        here, it's fetched automatically via conversation_detail(conversation_id).

        The response is unwrapped the mirror-image way by _decode_send_response()
        (see there for exact field numbers and which layer is confirmed vs.
        inferred): Response{status_code, error_desc, body} -> ResponseBody
        {send_message_body} -> SendMessageResponseBody{status, server_message_id,
        new_ticket, ...}. Check the returned "ok" (status_code==0) key, not
        the top-level dict decode_generic() itself produces (its status_code
        guess happens to line up with Response.cmd, not an actual status).

        Blocker as of this writing: every DM endpoint on the test account
        (conversations(), unread_count(), stranger_conversations(), and this
        send()) returns Response.status_code=200001 with error_desc="200001"
        -- consistent across reads and writes, so it's an account/session-level
        IM precondition (e.g. IM subsystem never initialized/logged in for
        this account -- matches the emulator-state memory note about a data
        wipe), not a send()-specific bug. A send() call against an account
        with a working IM session should return status_code=0 and a real
        server_message_id with the envelope above unchanged.

        No dedicated recipient/user_id field exists on SendMessageRequestBody
        -- conversation_id is required. For a brand-new 1:1 conversation,
        call create_conversation(to_user_id) first to obtain one."""
        if not ticket:
            try:
                detail = self.conversation_detail(conversation_id)
                draw = detail.get("_raw", {}) if isinstance(detail, dict) else {}
                ticket = draw.get("4") or ""
                if not conversation_short_id:
                    sid = draw.get("2")
                    if isinstance(sid, int):
                        conversation_short_id = sid
            except Exception:
                pass

        if not client_message_id:
            client_message_id = _new_client_message_id()

        send_fields: dict[int, Any] = {
            1: conversation_id,
            2: conversation_type,
            4: text,
            6: message_type,
            8: client_message_id,
        }
        if conversation_short_id:
            send_fields[3] = conversation_short_id
        if ticket:
            send_fields[7] = ticket

        send_message_body = ProtoBuf(send_fields).to_buf()
        request_body = ProtoBuf({_REQUESTBODY_FIELD_SEND_MESSAGE: send_message_body}).to_buf()
        request = ProtoBuf({1: _CMD_SEND_MESSAGE, 8: request_body}).to_buf()

        result = self._t.post(
            "/v1/message/send/",
            content=request,
            write=True,
            full_sign=True,
            proto_mode="generic",
        )
        decoded = _decode_send_response(result if isinstance(result, dict) else {})
        decoded["ok"] = decoded.get("status_code") == 0
        return decoded

    def delete_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        """/v1/message/delete — delete a message for yourself."""
        return self._t.post("/v1/message/delete/", data={
            "conversation_id": conversation_id,
            "message_id": message_id,
        }, full_sign=True, proto_mode="generic")

    def recall_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        """/v1/message/recall — recall (unsend) a message for everyone."""
        return self._t.post("/v1/message/recall/", data={
            "conversation_id": conversation_id,
            "message_id": message_id,
        }, full_sign=True, proto_mode="generic")

    # -- message requests (stranger inbox) ---------------------------------

    def stranger_conversations(self, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/v1/stranger/get_conversation_list — DM requests from non-followed
        users (the "message requests" folder)."""
        return self._t.get("/v1/stranger/get_conversation_list/", params={
            "cursor": cursor,
            "count": count,
        }, proto_mode="generic")

    def stranger_messages(self, conversation_id: str, *, cursor: int = 0, count: int = 20) -> dict[str, Any]:
        """/v1/stranger/get_messages — messages inside a stranger conversation."""
        return self._t.get("/v1/stranger/get_messages/", params={
            "conversation_id": conversation_id,
            "cursor": cursor,
            "count": count,
        }, proto_mode="generic")

    def delete_stranger_conversation(self, conversation_id: str) -> dict[str, Any]:
        """/v1/stranger/delete_conversation — decline/delete a message request."""
        return self._t.post("/v1/stranger/delete_conversation/", data={
            "conversation_id": conversation_id,
        }, full_sign=True, proto_mode="generic")

    # -- media ---------------------------------------------------------

    def cloud_token(self) -> dict[str, Any]:
        """/aweme/v1/im/cloud/token/ — the one confirmed endpoint actually
        under the /aweme/v1/im/ prefix; issues an upload token for IM media
        attachments (images/files sent in DMs)."""
        return self._t.get("/aweme/v1/im/cloud/token/")
