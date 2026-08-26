"""User endpoints: profile, followers, following, block, account management.

/aweme/v1/user/profile/self/ — свой профиль.
/aweme/v1/user/profile/other/ — чужой профиль по user_id/sec_user_id.
/aweme/v1/user/follower/list/ — подписчики.
/aweme/v1/user/following/list/ — подписки.
/aweme/v1/user/block/list/ — заблокированные.
/aweme/v1/user/settings/ — настройки аккаунта.
/aweme/v1/unique/id/check/ — проверка доступности username.
/aweme/v1/commit/user/ — edit profile fields (nickname/signature/unique_id/avatar_uri),
    one field per call: POST field_name=value (form-urlencoded). Confirmed live
    against v46 (see set_nickname/set_signature) — the server replies with a
    real business error ("Slow down, you are editing too fast.", code=3002284)
    when the field is understood, vs. a generic invalid-params error otherwise.
/aweme/v1/user/set/settings/ — POST field=<name>&value=<int>, one setting per
    call. Confirmed exact shape via decompile of
    com.ss.android.ugc.tiktok.pns.utils.network.api.UserSetSettingsApi
    (Retrofit: @Field("field") String, @Field("value") int) and live-tested
    (comment/duet/stitch/download_setting/react all accepted, status_code=0).
/tiktok/account/status/get/v1 — account standing/appeal info. Confirmed live.
/aweme/v1/fancy/qrcode/info/ — profile QR code. Endpoint reachable (status_code=0
    envelope) but the schema_type/object_id combination that returns a real QR
    was not found by black-box probing — see get_qrcode() docstring.
/aweme/v1/twitter/bind/, /aweme/v1/twitter/unbind/ — social account linking.
    Confirmed via decompile of the Retrofit interface (twitter/unbind takes no
    params, twitter/bind takes twitter_id/twitter_name/access_token/secret_token
    — i.e. it commits an already-completed OAuth token, it does not do the OAuth
    dance itself). instagram/* and youtube/* endpoints exist (seen as literal
    strings in the apk) but their exact field names were not decompiled —
    implemented by analogy to twitter and marked UNVERIFIED."""
from __future__ import annotations

from typing import Any

from ..errors import TikTokError, ServerError
from .transport import AndroidTransport

class UserAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def profile_self(self) -> dict[str, Any]:
        """/aweme/v1/user/profile/self/"""
        return self._t.get("/aweme/v1/user/profile/self/")

    def profile_by_id(self, user_id: str | int) -> dict[str, Any]:
        """/aweme/v1/user/ — lookup by numeric user_id. Works in v46+."""
        return self._t.get("/aweme/v1/user/", params={"user_id": str(user_id)})

    def profile_other(
        self,
        *,
        user_id: str = "",
        sec_user_id: str = "",
        username: str = "",
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """Get another user's profile. Tries /aweme/v1/user/ (v46+) first,
        then /aweme/v1/user/profile/other/, web scraping as last resort."""
        if user_id:
            try:
                result = self._t.get("/aweme/v1/user/", params={"user_id": user_id})
                if result.get("user", {}).get("uid"):
                    return result
            except (TikTokError, ServerError):
                pass
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        if params:
            try:
                result = self._t.get("/aweme/v1/user/profile/other/", params=params)
                if not result.get("_empty"):
                    return result
            except (TikTokError, ServerError):
                pass
        if username:
            resolved = self.resolve_username(username)
            if resolved and not resolved.get("_empty"):
                return resolved
        if web_fallback and username:
            from .web_scraper import user_detail_web
            web = user_detail_web(username)
            if web:
                web["_source"] = "web_scraping"
                return web
        return {}

    def resolve_username(self, username: str) -> dict[str, Any] | None:
        """Resolve @username to full profile via search + profile_by_id.
        v46+ dropped unique_id lookup on /aweme/v1/user/."""
        try:
            search_result = self._t.get("/aweme/v1/general/search/single/", params={
                "keyword": username,
                "count": "5",
                "search_source": "normal_search",
                "query_correct_type": "1",
            })
            for item in search_result.get("data", []):
                if item.get("type") != 4:
                    continue
                for u in item.get("user_list", []):
                    info = u.get("user_info", {})
                    if info.get("unique_id", "").lower() == username.lower():
                        uid = info.get("uid")
                        if uid:
                            result = self.profile_by_id(uid)
                            if not result.get("_empty"):
                                return result
        except (TikTokError, ServerError):
            pass
        return None

    def follower_list(
        self,
        user_id: str,
        *,
        max_time: int = 0,
        count: int = 20,
        offset: int = 0,
        sec_user_id: str = "",
        source_type: int = 1,
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/user/follower/list/ — paginated followers."""
        params: dict[str, Any] = {
            "user_id": user_id,
            "max_time": max_time,
            "count": count,
            "offset": offset,
            "source_type": source_type,
        }
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        result = self._t.get("/aweme/v1/user/follower/list/", params=params, bare=True)
        if result.get("_empty") and web_fallback and sec_user_id:
            from .web_scraper import user_followers_web
            web = user_followers_web(sec_user_id, max_cursor=max_time, count=count)
            if web:
                web["_source"] = "web_api"
                return web
        return result

    def following_list(
        self,
        user_id: str,
        *,
        max_time: int = 0,
        count: int = 20,
        offset: int = 0,
        sec_user_id: str = "",
        source_type: int = 1,
        web_fallback: bool = True,
    ) -> dict[str, Any]:
        """/aweme/v1/user/following/list/ — paginated following."""
        params: dict[str, Any] = {
            "user_id": user_id,
            "max_time": max_time,
            "count": count,
            "offset": offset,
            "source_type": source_type,
        }
        if sec_user_id:
            params["sec_user_id"] = sec_user_id
        result = self._t.get("/aweme/v1/user/following/list/", params=params, bare=True)
        if result.get("_empty") and web_fallback and sec_user_id:
            from .web_scraper import user_following_web
            web = user_following_web(sec_user_id, max_cursor=max_time, count=count)
            if web:
                web["_source"] = "web_api"
                return web
        return result

    def block_list(self, *, count: int = 20, offset: int = 0) -> dict[str, Any]:
        """/aweme/v1/user/block/list/"""
        return self._t.get("/aweme/v1/user/block/list/", params={
            "count": count,
            "offset": offset,
        }, bare=True)

    def settings(self) -> dict[str, Any]:
        """/aweme/v1/user/settings/"""
        return self._t.get("/aweme/v1/user/settings/")

    def check_unique_id(self, unique_id: str, *, web_fallback: bool = True) -> dict[str, Any]:
        """/aweme/v1/unique/id/check/ — check if username is available."""
        result = self._t.get("/aweme/v1/unique/id/check/", params={
            "unique_id": unique_id,
        }, bare=True)
        if result.get("_empty") and web_fallback:
            from .web_scraper import user_detail_web
            web = user_detail_web(unique_id)
            is_taken = web is not None and bool(web.get("user", {}).get("uid"))
            return {
                "unique_id": unique_id,
                "is_valid": not is_taken,
                "existing_user": web.get("user") if is_taken else None,
                "status_code": 0,
                "_source": "web_scraping",
            }
        return result

    def data_info(self) -> dict[str, Any]:
        """/aweme/v1/data/user/info/ — DEPRECATED by TikTok (returns 'Url does not match')."""
        return self._t.get("/aweme/v1/data/user/info/")

    def set_settings(self, **settings: Any) -> dict[str, Any]:
        """/aweme/v1/user/set/settings/ — update account settings."""
        return self._t.post("/aweme/v1/user/set/settings/", data=settings)

    # ------------------------------------------------------------------
    # Profile editing — /aweme/v1/commit/user/
    # ------------------------------------------------------------------
    #
    # Confirmed shape via decompile of two sibling Retrofit interfaces that
    # share this endpoint (ProfileLinksOrderUpdateAPI, CommitSchoolInfoAPI):
    # POST, @FormUrlEncoded, exactly one @Field(<field_name>) per call. The
    # app commits nickname/signature/unique_id/avatar_uri the same way (one
    # field per POST) — confirmed live for nickname/signature: the emulator
    # account returned status_code=3002284 "Slow down, you are editing too
    # fast." (a real per-field rate limit, not a routing/param-name error)
    # when re-submitting the *current* nickname and a fresh signature value.

    def _commit_user(self, **field: Any) -> dict[str, Any]:
        """/aweme/v1/commit/user/ — commit a single profile field.
        Pass exactly one keyword, e.g. _commit_user(nickname="foo")."""
        return self._t.post("/aweme/v1/commit/user/", data=field, write=True)

    def set_nickname(self, nickname: str) -> dict[str, Any]:
        """/aweme/v1/commit/user/ field=nickname. CONFIRMED live (v46,
        emulator @1232140499y): re-committing the current nickname returned
        status_code=3002284 "Slow down, you are editing too fast." — the
        server understood and rate-limited the edit rather than rejecting
        the field name. TikTok also rate-limits nickname changes to a few
        per month on the real account, so avoid calling this repeatedly."""
        return self._commit_user(nickname=nickname)

    def set_signature(self, signature: str) -> dict[str, Any]:
        """/aweme/v1/commit/user/ field=signature (bio). CONFIRMED live:
        committing a new value returned status_code=3002284 (same per-field
        edit-rate-limit as set_nickname, confirming the field name)."""
        return self._commit_user(signature=signature)

    def set_unique_id(self, unique_id: str) -> dict[str, Any]:
        """/aweme/v1/commit/user/ field=unique_id (username). UNVERIFIED:
        the field name is the endpoint's own literal string constant (found
        in the same dex as the commit/user/ URL) and matches the public
        convention for this endpoint, but the live no-op test (re-committing
        the current unique_id) returned an empty 200 body rather than a
        parseable business error, so it wasn't possible to positively
        confirm request acceptance the way set_nickname/set_signature were.
        Call check_unique_id() first — TikTok also throttles unique_id
        changes to roughly once every 30 days."""
        return self._commit_user(unique_id=unique_id)

    def set_avatar_uri(self, avatar_uri: str) -> dict[str, Any]:
        """/aweme/v1/commit/user/ field=avatar_uri. UNVERIFIED: not
        live-tested (account was rate-limited by the set_nickname/
        set_signature probes above before this could be tried); avatar_uri
        is a TOS object key already returned by a prior ImageX image
        upload — see upload_avatar()."""
        return self._commit_user(avatar_uri=avatar_uri)

    def upload_avatar(self, path: str) -> dict[str, Any]:
        """Upload a local image and set it as the profile avatar.

        Flow: /aweme/v1/upload/authkey/ -> ImageX ApplyImageUpload -> PUT
        bytes to TOS -> ImageX CommitImageUpload -> set_avatar_uri(). This
        reuses UploadAPI's ImageX plumbing (tiktokflow/android/upload.py),
        which documents that ApplyImageUpload/ApplyUploadInner's SigV4
        signing is NOT confirmed working yet (every attempt gets a generic
        "Invalid Authorization header" from the VOD/ImageX control plane —
        see upload.py's module docstring "REMAINING BLOCKER"). UNVERIFIED /
        currently blocked: this will raise InvalidRequest at the
        ApplyImageUpload step until that signing issue is resolved."""
        from .upload import UploadAPI
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        uploader = UploadAPI(self._t)
        creds = uploader._authkey()
        photo_cfg = creds.get("photo_upload_config") or {}
        auth2 = photo_cfg.get("authorization2") or {}
        if not auth2:
            raise TikTokError(f"upload/authkey response missing photo_upload_config.authorization2: {creds}")
        with open(path, "rb") as f:
            data = f.read()
        apply_result = uploader._vod_call(
            "ApplyImageUpload",
            {
                "SpaceName": auth2.get("space_name", ""),
                "ServiceId": auth2.get("space_name", ""),
                "FileSize": str(len(data)),
            },
            auth2,
        )
        upload_addr = (apply_result.get("Result") or apply_result).get("UploadAddress") or {}
        session_key = upload_addr.get("SessionKey", "")
        store_infos = upload_addr.get("StoreInfos") or []
        upload_hosts = upload_addr.get("UploadHosts") or [photo_cfg.get("fileHostName", "")]
        if not store_infos:
            raise TikTokError(f"ApplyImageUpload did not return StoreInfos: {apply_result}")
        uploader._put_object(data, store_infos, upload_hosts, mime="image/jpeg")
        import json as _json
        commit_result = uploader._vod_call(
            "CommitImageUpload",
            {"SpaceName": auth2.get("space_name", "")},
            auth2,
            method="POST",
            body=_json.dumps({"SessionKey": session_key}).encode(),
        )
        from .upload import _extract_vod_ref
        vid, uri = _extract_vod_ref(commit_result)
        avatar_uri = vid or uri
        if not avatar_uri:
            raise TikTokError(f"CommitImageUpload did not return a Vid/Uri: {commit_result}")
        return self.set_avatar_uri(avatar_uri)

    # ------------------------------------------------------------------
    # Privacy settings — named helpers over /aweme/v1/user/set/settings/
    # ------------------------------------------------------------------
    #
    # Field names confirmed by decompiling UserSetSettingsApi's callers and
    # cross-checked against the live GET /aweme/v1/user/settings/ response
    # (which uses the identical key names). Live-tested with no-op values
    # (re-submitting the account's current setting) on the emulator account:
    # comment/duet/stitch/download_setting/react all returned status_code=0.
    #
    # Enum meaning (0=everyone, 1=friends, 2=off/nobody) is the standard
    # TikTok convention and matches a FOLLOWER(0)/FRIEND(1)/NOBODY(2) enum
    # found in the apk (class C0XPW, classes15.dex) — UNVERIFIED that this
    # specific enum backs these specific fields (couldn't find the enum's
    # call site), but it is consistent with the app's UI and every other
    # public TikTok reverse-engineering reference for these fields.

    def _set_setting_field(self, field: str, value: int) -> dict[str, Any]:
        """/aweme/v1/user/set/settings/ — single field=value POST, matching
        the app's own Retrofit call shape (one field per request)."""
        return self._t.post("/aweme/v1/user/set/settings/", data={"field": field, "value": value}, write=True)

    def set_who_can_comment(self, value: int) -> dict[str, Any]:
        """field=comment. CONFIRMED live (status_code=0). value: 0=everyone,
        1=friends, 2=off (UNVERIFIED enum mapping, see class docstring)."""
        return self._set_setting_field("comment", value)

    def set_who_can_duet(self, value: int) -> dict[str, Any]:
        """field=duet. CONFIRMED live (status_code=0). Same value enum as
        set_who_can_comment (UNVERIFIED exact mapping)."""
        return self._set_setting_field("duet", value)

    def set_who_can_stitch(self, value: int) -> dict[str, Any]:
        """field=stitch. CONFIRMED live (status_code=0). Same value enum as
        set_who_can_comment (UNVERIFIED exact mapping)."""
        return self._set_setting_field("stitch", value)

    def set_who_can_download(self, value: int) -> dict[str, Any]:
        """field=download_setting. CONFIRMED live (status_code=0).
        Commonly 0=on/everyone, 1=off (UNVERIFIED exact mapping)."""
        return self._set_setting_field("download_setting", value)

    def set_who_can_react(self, value: int) -> dict[str, Any]:
        """field=react ("Videos You Like" / react feature visibility).
        CONFIRMED live (status_code=0). UNVERIFIED exact value enum."""
        return self._set_setting_field("react", value)

    def set_private_account(self, private: bool) -> dict[str, Any]:
        """field=private_account, value=1/0. Endpoint reachable but this
        specific field is currently BLOCKED on the test account/app build:
        live call returned status_code=4, "Couldn't change. Update TikTok
        to the latest version and try again" (code=3002394) even for a
        same-value no-op — this looks like a server-side app-version gate
        on account-type-changing settings (the same error appeared for the
        DM/chat setting below, ruling out a field-name typo). UNVERIFIED
        whether the field name itself is exactly right; only that this
        client cannot currently exercise it end-to-end."""
        return self._set_setting_field("private_account", 1 if private else 0)

    def set_dm_privacy(self, value: int) -> dict[str, Any]:
        """field=chat_set — who can send you direct messages. BLOCKED same
        as set_private_account: live call returned status_code=4, code=3002394
        "Update TikTok to the latest version". UNVERIFIED field name/enum
        beyond what's in the current GET /aweme/v1/user/settings/ response
        (chat_set/chat_user_type/chat_settings_panel are the candidate keys;
        chat_set was the one tried)."""
        return self._set_setting_field("chat_set", value)

    def privacy_settings(self) -> dict[str, Any]:
        """Current privacy-relevant values, extracted from
        GET /aweme/v1/user/settings/ (CONFIRMED live) plus the `secret`
        (private account) flag which only appears on profile_self()'s user
        object, not on the settings envelope."""
        settings = self.settings()
        profile = self.profile_self().get("user", {})
        keys = (
            "comment", "duet", "stitch", "react", "download_setting",
            "download_prompt", "chat_set", "chat_user_type",
            "chat_settings_panel", "chat_setting_open_everyone",
            "sug_to_who_share_link",
        )
        result: dict[str, Any] = {k: settings[k] for k in keys if k in settings}
        result["private_account"] = profile.get("secret")
        return result

    # ------------------------------------------------------------------
    # Account status
    # ------------------------------------------------------------------

    def account_status(self) -> dict[str, Any]:
        """/tiktok/account/status/get/v1 — account standing (in good
        standing / warnings / strikes) and appeal status. CONFIRMED live:
        returns account_status_info + account_appeal_info + avatarUrl."""
        return self._t.get("/tiktok/account/status/get/v1", bare=True)

    # ------------------------------------------------------------------
    # QR code
    # ------------------------------------------------------------------

    def get_qrcode(self, object_id: str = "", schema_type: int = 1, meta_params: str = "{}") -> dict[str, Any]:
        """/aweme/v1/fancy/qrcode/info/ — GET a profile QR code.
        UNVERIFIED: the endpoint is real and reachable (confirmed via
        decompile — GET, query params schema_type: int, object_id: str,
        meta_params: str) and returns a well-formed status_code=0 envelope,
        but every (schema_type, object_id) combination tried live
        (schema_type 0/1/2/3/4/5, object_id as raw uid and as the profile's
        https://www.tiktok.com/@<unique_id> share URL) came back with
        status_msg="url doesn't match" instead of QR image data — the
        correct object_id format/schema_type for a *profile* QR (as opposed
        to a video or other shareable object) was not found by black-box
        probing. Defaults left as schema_type=1 / object_id=<own uid> as a
        starting point for further investigation."""
        params: dict[str, Any] = {"schema_type": schema_type, "meta_params": meta_params}
        if object_id:
            params["object_id"] = object_id
        return self._t.get("/aweme/v1/fancy/qrcode/info/", params=params, bare=True)

    # ------------------------------------------------------------------
    # Social account linking
    # ------------------------------------------------------------------

    def unlink_twitter(self) -> dict[str, Any]:
        """/aweme/v1/twitter/unbind/ — GET, no params. CONFIRMED via
        decompile of the Retrofit interface (X.InterfaceC123510dSq)."""
        return self._t.get("/aweme/v1/twitter/unbind/", bare=True)

    def link_twitter(self, twitter_id: str, twitter_name: str, access_token: str, secret_token: str) -> dict[str, Any]:
        """/aweme/v1/twitter/bind/ — GET with twitter_id/twitter_name/
        access_token/secret_token. CONFIRMED param names via decompile of
        the Retrofit interface. This call only COMMITS an already-completed
        Twitter OAuth token to the account — it does not perform the OAuth
        flow itself; twitter_id/access_token/secret_token must come from a
        prior Twitter (X) OAuth1 authorization the caller has already done."""
        return self._t.get("/aweme/v1/twitter/bind/", params={
            "twitter_id": twitter_id,
            "twitter_name": twitter_name,
            "access_token": access_token,
            "secret_token": secret_token,
        }, bare=True)

    def unlink_instagram(self) -> dict[str, Any]:
        """/aweme/v1/instagram/unbind/ — UNVERIFIED: endpoint path confirmed
        only as a literal string in the apk (not decompiled to a Retrofit
        interface); implemented by analogy to unlink_twitter (GET, no
        params)."""
        return self._t.get("/aweme/v1/instagram/unbind/", bare=True)

    def link_instagram(self, instagram_id: str, instagram_name: str, access_token: str) -> dict[str, Any]:
        """/aweme/v1/instagram/bind/ — UNVERIFIED: endpoint path confirmed
        only as a literal string in the apk; field names implemented by
        analogy to link_twitter (Instagram OAuth2 has no secret_token, so
        that field is omitted here — unconfirmed whether the real field is
        called instagram_id/instagram_name or something else)."""
        return self._t.get("/aweme/v1/instagram/bind/", params={
            "instagram_id": instagram_id,
            "instagram_name": instagram_name,
            "access_token": access_token,
        }, bare=True)

    def unlink_youtube(self) -> dict[str, Any]:
        """/aweme/v1/youtube/unbind/ — UNVERIFIED: endpoint path confirmed
        only as a literal string in the apk; implemented by analogy to
        unlink_twitter (GET, no params)."""
        return self._t.get("/aweme/v1/youtube/unbind/", bare=True)

    def link_youtube(self, youtube_id: str, youtube_name: str, access_token: str) -> dict[str, Any]:
        """/aweme/v1/youtube/bind/ — UNVERIFIED: endpoint path confirmed
        only as a literal string in the apk; field names implemented by
        analogy to link_twitter/link_instagram, unconfirmed."""
        return self._t.get("/aweme/v1/youtube/bind/", params={
            "youtube_id": youtube_id,
            "youtube_name": youtube_name,
            "access_token": access_token,
        }, bare=True)

    # ------------------------------------------------------------------
    # Profile category (business/creator) and region
    # ------------------------------------------------------------------
    #
    # NOT FOUND: no endpoint for switching account type (personal/creator/
    # business) or for reading/writing the account's registered region was
    # located. Searched: decompiled Retrofit interfaces and raw dex strings
    # across all 50 classesN.dex for account_type/creator_account/
    # enterprise_user_type/account_region/category-of-account patterns —
    # found only unrelated hits (live-streaming permission levels, content
    # category filters for the kids/nearby feeds, school info). TikTok's
    # business/creator account switch and region are very likely handled
    # through /tiktok/... or /passport/app/region* endpoints requiring a
    # full onboarding-flow trace (out of scope here — passport.py is owned
    # by another agent per this task's constraints). Not implemented.
