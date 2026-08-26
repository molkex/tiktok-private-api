"""Passport (auth) endpoints: login, register, device register, email/sms.

/passport/auth/login/ — login with third-party (Google/Facebook/Apple).
/passport/email/login/ — login with email+password.
/passport/mobile/sms_login/ — login with SMS code.
/passport/mobile/send_code/ — send SMS verification code.
/passport/email/send_code/ — send email verification code.
/passport/account/info/v2/ — account info.
/passport/user/logout/ — logout.
/passport/token/beat/v2/ — token heartbeat/refresh.

NB: Device register goes through log.snssdk.com, not the main API host.

Additional endpoints below (mobile/username/QR/OAuth login, registration,
password reset/change) were extracted from the APK
(com.zhiliaoapp.musically.apk, classes25.dex — the passport SDK module) via
jadx decompilation. Each method's docstring says whether the exact request
shape was found in decompiled source ("Verified: <ClassName>") or only the
endpoint path was confirmed present in the APK's string table, in which case
params are inferred by symmetry with a verified sibling endpoint and the
docstring is marked "# UNVERIFIED".

/passport/user/login/ — unified login: email OR mobile OR username + password
    (confirmed via X.C0rHR.LJIIJJI(), which all three login flows share).
Username availability for the public @handle is checked via
user.check_unique_id() in user.py (not duplicated here); this module's
set_login_name() sets the passport *login* username, a different field.
A client can also be built directly from raw cookies via
Device.import_cookies() (see device.py) instead of going through any login
call here — useful when cookies were captured out-of-band."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport, _parse_aweme_envelope


class PassportAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def _login_request(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Send a login request, capture session cookies, update device.
        Uses skip_app_id to bypass Janus gateway on login endpoints."""
        resp = self._t.post(path, data=data, raw=True, skip_app_id=True)
        cookies = dict(resp.cookies)
        body = _parse_aweme_envelope(resp)
        response_data = body.get("data") if isinstance(body, dict) else None
        self._t.device.update_session(response_data, cookies)
        return body

    def account_info(self) -> dict[str, Any]:
        """/passport/account/info/v2/"""
        return self._t.get("/passport/account/info/v2/", full_sign=True)

    def token_beat(self) -> dict[str, Any]:
        """/passport/token/beat/v2/ — token keepalive."""
        return self._t.get("/passport/token/beat/v2/", full_sign=True)

    def email_login(self, email: str, password: str) -> dict[str, Any]:
        """/passport/email/login/ — captures session cookies."""
        return self._login_request("/passport/email/login/", {
            "email": email,
            "password": password,
            "account_sdk_source": "app",
        })

    def sms_login(self, mobile: str, code: str) -> dict[str, Any]:
        """/passport/mobile/sms_login/ — captures session cookies."""
        return self._login_request("/passport/mobile/sms_login/", {
            "mobile": mobile,
            "code": code,
        })

    def send_sms_code(self, mobile: str, *, scene: str = "login") -> dict[str, Any]:
        """/passport/mobile/send_code/"""
        return self._t.post("/passport/mobile/send_code/", data={
            "mobile": mobile,
            "scene": scene,
        }, full_sign=True)

    def send_email_code(self, email: str, *, scene: str = "login") -> dict[str, Any]:
        """/passport/email/send_code/"""
        return self._t.post("/passport/email/send_code/", data={
            "email": email,
            "scene": scene,
        }, full_sign=True)

    def email_register(self, email: str, password: str, code: str,
                       *, recaptcha_token: str = "") -> dict[str, Any]:
        """/passport/email/register/v2/ — captures session cookies.

        Real client also sends mix_mode=1/fixed_mix_mode=1 (encrypted-field
        envelope flag); include them so the server accepts the request."""
        data = {
            "email": email,
            "password": password,
            "code": code,
            "mix_mode": "1",
            "fixed_mix_mode": "1",
            "type": "34",
        }
        if recaptcha_token:
            data["recaptcha_token"] = recaptcha_token
        return self._login_request("/passport/email/register/v2/", data)

    def logout(self) -> dict[str, Any]:
        """/passport/user/logout/"""
        return self._t.post("/passport/user/logout/", full_sign=True)

    def check_email(self, email: str) -> dict[str, Any]:
        """/passport/email/check_code/ — verify email code."""
        return self._t.get("/passport/email/check_code/", params={
            "email": email,
        }, full_sign=True)

    def account_set(self, **fields: Any) -> dict[str, Any]:
        """/passport/account/set/ — update account fields."""
        return self._t.post("/passport/account/set/", data=fields, full_sign=True)

    def available_ways(self) -> dict[str, Any]:
        """/passport/auth/available_ways/ — available login methods."""
        return self._t.get("/passport/auth/available_ways/", full_sign=True)

    def password_check(self) -> dict[str, Any]:
        """/passport/password/check/ — check if password is set."""
        return self._t.get("/passport/password/check/", full_sign=True)

    def user_settings(self) -> dict[str, Any]:
        """/passport/user/setting/ — account security settings."""
        return self._t.get("/passport/user/setting/", full_sign=True)

    def switch_account(self) -> dict[str, Any]:
        """/passport/account/switch/v2/"""
        return self._t.post("/passport/account/switch/v2/", full_sign=True)

    # ------------------------------------------------------------------
    # LOGIN — mobile / username / passwordless-email / OAuth / QR-code
    # ------------------------------------------------------------------

    def user_login(
        self,
        *,
        email: str | None = None,
        mobile: str | None = None,
        username: str | None = None,
        account: str | None = None,
        password: str,
        token: str | None = None,
        captcha: str | None = None,
        scene: int | None = None,
    ) -> dict[str, Any]:
        """/passport/user/login/ — unified login endpoint. Pass exactly one
        of email/mobile/username/account plus a password; captures session
        cookies.

        Verified: X.C0rHR.LJIIJJI() in the APK (classes25.dex) — the same
        static builder backs email-login, mobile-login, and username-login
        internally (params: email|mobile|username|account, password,
        mix_mode=1, optional token/captcha/scene). username is lowercased
        before sending, matching the client."""
        data: dict[str, Any] = {"password": password, "mix_mode": "1"}
        if email:
            data["email"] = email
        if mobile:
            data["mobile"] = mobile
        if username:
            data["username"] = username.lower()
        if account:
            data["account"] = account
        if token:
            data["token"] = token
        if captcha:
            data["captcha"] = captcha
        if scene:
            data["scene"] = str(scene)
        return self._login_request("/passport/user/login/", data)

    def mobile_login(
        self, mobile: str, password: str, *, captcha: str | None = None,
        scene: int | None = None,
    ) -> dict[str, Any]:
        """Login by phone/mobile + password. See user_login() —
        /passport/user/login/. Verified via X.C0rHR.LJIIJJI() (same builder
        as email/username login, mobile branch)."""
        return self.user_login(mobile=mobile, password=password, captcha=captcha, scene=scene)

    def username_login(
        self, username: str, password: str, *, captcha: str | None = None,
    ) -> dict[str, Any]:
        """Login by username + password. See user_login() —
        /passport/user/login/. Verified via X.C0rHR.LJIIJJI() (same builder
        as email/mobile login, username branch)."""
        return self.user_login(username=username, password=password, captcha=captcha)

    def email_code_login(self, email: str, code: str, *, type_: int = 13) -> dict[str, Any]:
        """/passport/app/email/code_login/ — passwordless login: email +
        verification code (send the code first via
        send_email_code(email, scene="login")). Captures session cookies.

        Verified: X.C09200rFg.LIZ() in the APK — params: email, code, type,
        mix_mode=1. `type_` mirrors the client's
        AccountLoginSignupUnificationExperiment flag: 13 = legacy flow,
        16 = the newer unified login/signup flow; both were seen as literal
        constants in the decompiled source."""
        return self._login_request("/passport/app/email/code_login/", {
            "email": email,
            "code": code,
            "type": str(type_),
            "mix_mode": "1",
        })

    def _oauth_params(
        self,
        platform: str,
        access_token: str | None,
        code: str | None,
        expires_in: int | None,
        platform_app_id: str | None,
        extra: dict[str, str] | None,
    ) -> dict[str, str]:
        """Build the shared OAuth param set. Verified: X.C09980rIg.LIZIZ()
        in the APK — param order/names: platform, access_token, expires_in,
        code, platform_app_id, then any extra provider-specific fields."""
        data: dict[str, str] = {"platform": platform}
        if access_token:
            data["access_token"] = access_token
        if expires_in:
            data["expires_in"] = str(expires_in)
        if code:
            data["code"] = code
        if platform_app_id:
            data["platform_app_id"] = platform_app_id
        if extra:
            data.update(extra)
        return data

    def oauth_login(
        self,
        platform: str,
        *,
        access_token: str | None = None,
        code: str | None = None,
        expires_in: int | None = None,
        platform_app_id: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """/passport/auth/login/ — third-party OAuth login (Google, Facebook,
        Apple, Twitter, ...); creates a TikTok account if none is bound to
        the provider identity yet. Captures session cookies.

        Verified: X.C12890rTl.LJFF()/LIZLLL() + X.C09980rIg.LIZIZ() in the
        APK — params: platform, access_token, code, expires_in,
        platform_app_id. The caller supplies the provider's own
        access_token/code (obtained from that provider's SDK/OAuth flow
        outside this SDK); this method only performs TikTok's half of the
        exchange."""
        data = self._oauth_params(platform, access_token, code, expires_in, platform_app_id, extra)
        return self._login_request("/passport/auth/login/", data)

    def oauth_login_only(
        self,
        platform: str,
        *,
        access_token: str | None = None,
        code: str | None = None,
        expires_in: int | None = None,
        platform_app_id: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """/passport/auth/login_only/ — third-party OAuth login WITHOUT
        auto-creating a new account (fails if no TikTok account is already
        bound to the provider identity). Same params as oauth_login().

        Verified: X.C12890rTl.LIZJ()/LJ() in the APK."""
        data = self._oauth_params(platform, access_token, code, expires_in, platform_app_id, extra)
        return self._login_request("/passport/auth/login_only/", data)

    def qr_get_qrcode(self, *, service: str | None = None) -> dict[str, Any]:
        """/passport/mobile/get_qrcode/ — request a login QR code/token.
        Poll the result with qr_check_qrconnect(token) using the `token`
        field from this response; render/display the accompanying
        qrcode/url field for the user to scan with an already-logged-in
        device.

        Verified: X.QRCodeLoginViewModelV2.MU2()/TU2() in the APK — params:
        scene="0", use_native ("1" only under a client-side experiment, "0"
        otherwise), optional service/token. `service` identifies the
        polling channel; safe to omit for a single-app flow."""
        data = {"scene": "0", "use_native": "0"}
        if service:
            data["service"] = service
        return self._t.post("/passport/mobile/get_qrcode/", data=data, full_sign=True)

    def qr_check_qrconnect(self, token: str, *, service: str | None = None) -> dict[str, Any]:
        """/passport/mobile/check_qrconnect/ — poll QR login status. Call
        repeatedly with the token from qr_get_qrcode() until the status
        turns "confirmed"; captures session cookies once that happens.

        Verified: X.QRCodeLoginViewModelV2.QU2()/TU2() in the APK — params:
        token, scene="0", use_native, optional service."""
        data = {"token": token, "scene": "0", "use_native": "0"}
        if service:
            data["service"] = service
        return self._login_request("/passport/mobile/check_qrconnect/", data)

    def qr_confirm(self, token: str, csrf_token: str, *, approve: bool = True) -> dict[str, Any]:
        """/passport/mobile/confirm_qrcode/ — approve or refuse a pending QR
        login request. Runs on the device that SCANNED the code (i.e. this
        Device must already carry an authenticated session) — it does not
        log in the current device.

        Verified: X.QRCodeLoginVerifyViewModel.MU2() in the APK — params:
        token, decision ("0"=approve, "1"=refuse), csrf_token (obtained by
        scanning the QR code's URL, which is out of scope for this SDK)."""
        return self._t.post("/passport/mobile/confirm_qrcode/", data={
            "token": token,
            "decision": "0" if approve else "1",
            "csrf_token": csrf_token,
        }, full_sign=True)

    def refresh_session(self) -> dict[str, Any]:
        """Renew/keep-alive the current session. TikTok's Android client has
        no separate 'refresh token' endpoint — /passport/token/beat/v2/
        (token_beat()) both keeps the session alive and rotates short-lived
        tokens server-side, so this is just a descriptively-named alias.
        Call it periodically instead of re-authenticating."""
        return self.token_beat()

    # ------------------------------------------------------------------
    # REGISTRATION — phone / username; setting the login username
    # ------------------------------------------------------------------

    def mobile_register(self, mobile: str, code: str, *, password: str | None = None) -> dict[str, Any]:
        """/passport/mobile/register/ — register by phone + SMS code
        (+ optional password). Send the code first via
        send_sms_code(mobile, scene="register"). Captures session cookies.

        # UNVERIFIED: the endpoint path is confirmed present in the APK's
        passport path table (X.C10740rLe, classes25.dex), but the specific
        request-builder class wasn't located in the decompiled module.
        Params are inferred by symmetry with the confirmed
        /passport/email/register/v2/ builder (X.C0rGX.LIZJ())."""
        data: dict[str, Any] = {"mobile": mobile, "code": code, "mix_mode": "1", "fixed_mix_mode": "1"}
        if password:
            data["password"] = password
        return self._login_request("/passport/mobile/register/", data)

    def username_register(self, username: str, password: str) -> dict[str, Any]:
        """/passport/username/register/ — register a new account with just a
        username + password (no email/phone required). Captures session
        cookies.

        Verified: X.C0rGX.LIZLLL() in the APK — params: username, password,
        mix_mode=1."""
        return self._login_request("/passport/username/register/", {
            "username": username,
            "password": password,
            "mix_mode": "1",
        })

    def set_login_name(self, username: str) -> dict[str, Any]:
        """/passport/login_name/update/ — set/change the account's passport
        *login* username. This is distinct from the public @handle
        (unique_id): see user.check_unique_id() in user.py to check @handle
        availability, and /aweme/v1/user/set/ (also in user.py) to change
        the public @handle itself.

        # UNVERIFIED: path confirmed present in the APK's passport path
        table and in StoreRegionInterceptor's endpoint allow-list
        (classes25.dex), but the request-builder class wasn't located; the
        param name "login_name" is a best guess based on the path segment."""
        return self._t.post("/passport/login_name/update/", data={
            "login_name": username,
            "mix_mode": "1",
        }, full_sign=True)

    # ------------------------------------------------------------------
    # ACCOUNT / PASSWORD — code verification tickets, reset, change, set
    # ------------------------------------------------------------------

    def verify_email_code(self, code: str, *, type_: int) -> dict[str, Any]:
        """/passport/email/verify/ — verify an email code sent to the
        session's own email address and receive a `ticket` for a follow-up
        action (e.g. reset_password_by_email_ticket()).

        Verified: X.C0rGX.LJII() in the APK — params: type, code,
        mix_mode=1. `type_` selects which flow the code was sent for; exact
        integer values weren't enumerated in the APK strings — reuse
        whatever value the corresponding send_email_code() call used."""
        return self._t.post("/passport/email/verify/", data={
            "type": str(type_),
            "code": code,
            "mix_mode": "1",
        }, full_sign=True)

    def validate_mobile_code(
        self, code: str, type_: int, *, need_ticket: bool = True,
        scene: int | None = None, shark_ticket: str | None = None,
    ) -> dict[str, Any]:
        """/passport/mobile/validate_code/v1/ — validate an SMS code and
        receive a `ticket` for a follow-up action (e.g.
        reset_password_by_ticket(), change_mobile()).

        Verified: X.C0rGY.LJI() in the APK — params: code, type,
        need_ticket=1, mix_mode=1, fixed_mix_mode=1, optional
        scene/shark_ticket."""
        data: dict[str, Any] = {
            "code": code,
            "type": str(type_),
            "need_ticket": "1" if need_ticket else "0",
            "mix_mode": "1",
            "fixed_mix_mode": "1",
        }
        if scene:
            data["scene"] = str(scene)
        if shark_ticket:
            data["shark_ticket"] = shark_ticket
        return self._t.post("/passport/mobile/validate_code/v1/", data=data, full_sign=True)

    def check_mobile_code(self, mobile: str, code: str, *, type_: int) -> dict[str, Any]:
        """/passport/mobile/check_code/ — verify an SMS code (the mobile
        counterpart of check_email()).

        Verified: X.C0rGY.LJII() in the APK — params: mobile, code, type,
        mix_mode=1, fixed_mix_mode=1."""
        return self._t.post("/passport/mobile/check_code/", data={
            "mobile": mobile,
            "code": code,
            "type": str(type_),
            "mix_mode": "1",
            "fixed_mix_mode": "1",
        }, full_sign=True)

    def reset_password_by_email_ticket(self, password: str, ticket: str) -> dict[str, Any]:
        """/passport/password/reset_by_email_ticket/ — reset the password
        using a `ticket` from verify_email_code(); captures the new session
        cookies.

        Verified: X.C0rGX.LIZIZ() in the APK — params: password, ticket,
        mix_mode=1."""
        return self._login_request("/passport/password/reset_by_email_ticket/", {
            "password": password,
            "ticket": ticket,
            "mix_mode": "1",
        })

    def reset_password_by_ticket(self, password: str, ticket: str) -> dict[str, Any]:
        """/passport/password/reset_by_ticket/ — reset the password using a
        `ticket` from validate_mobile_code(); captures the new session
        cookies.

        Verified: X.C0rGY.LJIIJJI() in the APK — params: password, ticket,
        mix_mode=1."""
        return self._login_request("/passport/password/reset_by_ticket/", {
            "password": password,
            "ticket": ticket,
            "mix_mode": "1",
        })

    def change_password(self, current_password: str, new_password: str) -> dict[str, Any]:
        """/passport/password/update/ — change password while logged in
        (requires the current password).

        Verified: X.C0rGY.LJFF() in the APK — params: current_password,
        password, mix_mode=1."""
        return self._t.post("/passport/password/update/", data={
            "current_password": current_password,
            "password": new_password,
            "mix_mode": "1",
        }, full_sign=True)

    def change_password_v2(
        self, new_password: str, *, rule_strategies: str | None = None,
        passport_ticket: str | None = None,
    ) -> dict[str, Any]:
        """/passport/password/change/v2/ — newer change-password endpoint;
        pass rule_strategies from the server's password-rules response, or a
        passport_ticket from a prior verification step, in place of
        re-sending the current password.

        Verified: com.ss.android.ugc.aweme.account.api.ChangePasswordV2Api
        in the APK — params: password, mix_mode=1, rules_version="v2"
        (default) or rule_strategies, optional passport_ticket."""
        data: dict[str, Any] = {"password": new_password, "mix_mode": "1"}
        if rule_strategies:
            data["rule_strategies"] = rule_strategies
        else:
            data["rules_version"] = "v2"
        if passport_ticket:
            data["passport_ticket"] = passport_ticket
        return self._t.post("/passport/password/change/v2/", data=data, full_sign=True)

    def set_password(self, password: str) -> dict[str, Any]:
        """/passport/password/set/ — set a password for an account created
        without one (e.g. pure SMS/QR-code accounts).

        Verified: X.C0rGY.LJIILJJIL() in the APK — params: password,
        mix_mode=1."""
        return self._t.post("/passport/password/set/", data={
            "password": password,
            "mix_mode": "1",
        }, full_sign=True)

    def verify_password(self, password: str) -> dict[str, Any]:
        """/passport/password/check/ — verify a password against the
        current session's account. Distinct from password_check() above,
        which is a parameterless GET that only reports whether a password
        is set at all.

        Verified: X.C0rGY.LIZLLL() in the APK — params: password,
        mix_mode=1."""
        return self._t.post("/passport/password/check/", data={
            "password": password,
            "mix_mode": "1",
        }, full_sign=True)

    def change_mobile(
        self, mobile: str, code: str, *, captcha: str | None = None,
        ticket: str | None = None,
    ) -> dict[str, Any]:
        """/passport/mobile/change/v1/ — change the account's bound phone
        number. Send the code first via send_sms_code(new_mobile, ...).

        Verified: X.C0rGY.LJIILIIL() in the APK — params: mobile, code,
        mix_mode=1, optional captcha, optional ticket (from
        validate_mobile_code())."""
        data: dict[str, Any] = {"mobile": mobile, "code": code, "mix_mode": "1"}
        if captcha:
            data["captcha"] = captcha
        if ticket:
            data["ticket"] = ticket
        return self._t.post("/passport/mobile/change/v1/", data=data, full_sign=True)
