# Project status & roadmap

This SDK is early. Reads work well, logins work, writes are a problem.
This page is the honest truth about every endpoint and about what we need help with.

Last updated: 2026-10-20.

## Legend

| | |
|---|---|
| ✅ | works, used in production |
| 🟡 | works but has a known caveat |
| 🔴 | known dead end — call succeeds but the action does not persist, or TikTok refuses from pure HTTP |
| — | not implemented or not applicable |

Access levels:

- **ZD** zero-device — just an API key, SDK mints a device for you
- **LI** logged-in — you authenticated through the SDK (email / sms / oauth / qr)
- **OWN** account-owned — logged in, acting on your own account or your own content

## Capability matrix

| Module | ZD (read) | LI (read + write) | OWN (your account / content) |
|---|---|---|---|
| **feed** | ✅ `for_you` | ✅ `following`, `friends` | — |
| **user** | ✅ `profile_other`, `by_id`, `resolve_username`, `info`, `followers`, `following` | ✅ `block`, `unblock` | ✅ `profile_self`, `settings`, edits (`nickname`, `signature`, `avatar`, `privacy`, `dm_privacy`, `link_social`) — server throttles rapid edits |
| **video** | ✅ `detail`, `multi_detail`, `stats`, `related` | 🔴 `collect` (returns ok, does not persist) | ✅ `my_posts`, `favorites`, `liked`, `watch_history`, `collections`, `insights`, `delete`, `pin`, `unpin` |
| **search** | ✅ `suggestions`, `hot_list`, `users` | 🟡 `general`, `videos`, `music`, `hashtags` (often empty without login) | ✅ `search_history` |
| **music** | ✅ `detail`, `videos`, `search`, `hot`, `recommended` | — | ✅ `collect`, `collection`, `user_collected` |
| **comment** | ✅ `list`, `replies` | 🔴 `publish`, `digg` (returns ok, does not persist) | ✅ `delete`, `pin`, `unpin` |
| **social** | ✅ `digg_list` | 🔴 `follow`, `like`, `repost`, `dislike`<br>✅ `unfollow`, `unlike`, `unrepost`, `block`, `remove_follower` (removals persist) | ✅ `friend_list`, `recommend_users` |
| **live** | ✅ `recommend`, `search`, `room_info`, `comment_list` | 🟡 `room_enter`, `comment_send`, `like`, `gift_send` (verified on an emulator session, not fully re-verified on pure HTTP) | ✅ `room_create`, `room_finish` (your own stream) |
| **dm** | — | ✅ `send` · 🟡 `send_media`, `mute`, `delete_*`, `recall`, `stranger_*` (not re-verified) | ✅ `conversations`, `messages`, `unread_count`, `mark_read` |
| **upload** | — | — | ✅ `creator_info`, `upload_video`, `upload_photo` (creator account required) |
| **notice** | — | — | ✅ `multi`, `count`, `inbox`, `delete`, `shield` |
| **passport** | — | ✅ `email_login`, `sms_login`, `user_login`, `mobile_login`, `oauth_login`, `qr_*` (sessions)<br>🟡 `email_register`, `send_email_code(scene="register")` (experimental auto-captcha, requires `TIKTOKFLOW_RUCAPTCHA_KEY`; still blocked by device-trust wall on many fresh IPs)<br>🔴 `register_mobile`, `register_username` (captcha + device-trust wall, pure HTTP success rate is very low) | ✅ `change_password`, `TOTP`, `logout`, `refresh_session`, `switch_account` |

## Known dead ends on pure HTTP

### Writes that do not persist

`social.follow`, `social.like`, `social.repost`, `comment.publish`, `comment.digg`, `video.collect` return `status_code: 0` and look successful, but TikTok silently drops them when they do not come from an on-device execution context.

What **does** persist: `unfollow`, `unlike`, `unrepost`, `block`, `remove_follower`, `delete`, every edit of your own content, every read.

If you need writes to stick today, you have two options:

- run your own on-device executor (Android emulator / headless device) alongside the SDK and route writes through it
- wait for the sticky-writes service — it is on the roadmap, see below

### Registration

`passport.email_register` and `passport.send_email_code(scene="register")` now auto-handle the slide-captcha when `TIKTOKFLOW_RUCAPTCHA_KEY` is set (bdturing fetch → 2captcha solve → verify → retry with ticket, up to 2 attempts, exponential backoff). This moves them from 🔴 to 🟡 experimental: the captcha step succeeds routinely, but TikTok's second-level `decision_conf` / `twice_verify` and device-trust wall still reject a significant share of fresh-IP attempts. See the SDK README section "Account generation flow" for the honest end-to-end example and limitations.

`passport.register_mobile` and `passport.register_username` are still 🔴 — their captcha path is wired but device-trust rejections dominate. If you need accounts reliably, prefer logging into existing ones or running registration on a real device.

### Captcha on login

`send_email_code` / `send_sms_code` for fresh accounts on new IPs often ask for a slide-captcha. The SDK accepts an optional `captcha=` argument you can fill in from your own solver, and there is an opt-in 2captcha / RuCaptcha hook via `TIKTOKFLOW_RUCAPTCHA_KEY` (your paid key).

## Platforms

| | Android | iOS |
|---|---|---|
| device fingerprint | ✅ full, own `register_device` and `activation` | ✅ own device + transport |
| transport | ✅ | ✅ |
| 12 API modules | ✅ same for both | ✅ same for both |
| select | `TikTokAPI(platform="android")` (default) | `TikTokAPI(platform="ios")` |

## Reliability

- rate: 1000 req/s burst 5000 per key, no monthly cap
- httpx retries 429s with backoff, honors `Retry-After`
- optional per-process `rate_limit=` or `RateLimiter` (default 2 r/s, burst 5) when you want to be nice to TikTok
- the sign-service is operated by a single person right now — downtime happens, usually under a minute

## Roadmap

Roughly in order. No committed dates.

1. **Sticky writes** — hosted on-device executor that routes follow / like / comment through a real Android device. The SDK will keep the same API; `tt.social.follow(user_id)` will persist. Opt-in via a flag or a separate client.
2. **Registration flow** — bundled captcha + residential-proxy adapter so pure HTTP registration becomes viable. Still at best "medium" success rate; use a real device for high-volume account creation.
3. **DM parity** — re-verify every DM method against live traffic, mark unverified ones honestly.
4. **iOS parity for register / activation** — currently iOS reuses the Android device layer where it can; closing the gap.
5. **Per-key usage dashboard** — see your own calls, top endpoints, device fingerprints. Admin side already collects it, user side exposed through the bot's `/stats`.
6. **Rust signing module (server-side)** — faster, harder to extract. Opt-in on the service, no client change.
7. **Public release-guard tooling** — the fail-closed guard that keeps private code out of the public SDK is open-sourceable as a standalone tool.

## How to help

Pull requests welcome. Issues even more so.

**Highest leverage right now:**

- **Sticky-writes executor** — if you have an Android device farm or a redroid setup and want to help bridge writes, say hi.
- **Captcha solver integrations** — beyond 2captcha / RuCaptcha, support for other solver services or local models.
- **Endpoint re-verification** — pick a 🟡 cell, confirm against live traffic, open an issue or a PR with the status change.
- **iOS gaps** — anything that works on Android and should work on iOS but does not.
- **Documentation** — real-world examples (`examples/`), common gotchas, migration notes.
- **Tests** — the SDK ships with a test suite; adding scenarios for your use case helps everyone.

**Lower-touch:**

- open an issue when something you expected to work doesn't
- send PRs with typo and docs fixes
- share your use case on [Discussions](https://github.com/molkex/tiktok-private-api/discussions) — it helps prioritize

## Non-goals

- an all-in-one TikTok automation suite — the SDK gives you the endpoints; the orchestration layer is yours
- cracking TikTok's captcha for free — captcha-solving will stay opt-in and relies on external paid services
- hiding what we do on the signing side — the signing service is a hosted convenience, you can run your own against the same API

## Contact

- bot (keys, support): [@tiktok_private_api_bot](https://t.me/tiktok_private_api_bot)
- maintainer: [@mxmtkchk](https://t.me/mxmtkchk)
- issues: https://github.com/molkex/tiktok-private-api/issues
- security: see [`SECURITY.md`](SECURITY.md)
