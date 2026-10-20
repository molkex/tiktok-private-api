# tiktok-private-api

A Python SDK for the private TikTok mobile API — the same endpoints the
Android and iOS apps use. Pure HTTP from your machine; request signing
(X-Argus / X-Ladon / X-Gorgon / X-Khronos / device fingerprint) runs on a
hosted service you call with an API key. Requests to TikTok leave your IP,
not ours.

```bash
pip install tiktok-private-api
```

```python
from tiktokflow import TikTokAPI

tt = TikTokAPI(api_key="sk_live_...")
feed = tt.feed.for_you(count=10)
for v in feed["aweme_list"]:
    print(v["author"]["unique_id"], v["statistics"]["digg_count"], v["desc"][:60])
```

That's it — no phone, no emulator, no login. The client mints a fresh
device on first use.

## Get a key

Open [`@tiktok_private_api_bot`](https://t.me/tiktok_private_api_bot) on
Telegram, send `/key`, save the key it replies with (shown once).

Keys are **free**, no daily or monthly quotas, same limit for everyone:
**1000 req/s with burst 5000 per key**. Anything beyond `/key /rotate
/revoke /stats` — ping [`@mxmtkchk`](https://t.me/mxmtkchk) directly.

## What works without login

Public reads work on a freshly minted device, no TikTok account needed:

| Module          | Methods                                                                                     |
|-----------------|---------------------------------------------------------------------------------------------|
| `tt.feed`       | `for_you`                                                                                   |
| `tt.user`       | `profile_other`, `info`, `resolve_username`, `follower_list`, `following_list`              |
| `tt.video`      | `detail`, `multi_detail`, `stats`                                                           |
| `tt.comment`    | `list`, `replies`                                                                           |
| `tt.search`     | `general`, `users`, `videos`, `suggestions`, `hot_list`, `hashtag_search`, `hashtag_detail`, `hashtag_videos`, `music` |
| `tt.music`      | `detail`, `videos`, `search`, `recommended`, `hot`                                          |
| `tt.live`       | `recommend`, `room_info`, `search`                                                          |
| `tt.social`     | `digg_list`, `recommend_users`                                                              |

```python
tt = TikTokAPI(api_key="sk_live_...")

# Pull a user profile + their recent posts via resolve_username
me = tt.user.info(username="tiktok")
print(me["user"]["follower_count"])

# Grab video details
detail = tt.video.detail("7295...8832")

# Trending hashtags
hot = tt.search.hot_list()

# Live rooms
rooms = tt.live.recommend(count=10)
```

## What needs a logged-in account

Owned content, writes, DMs, uploads, notifications:

| Module       | Needs login                                                                              |
|--------------|------------------------------------------------------------------------------------------|
| `tt.user`    | `profile_self`, `settings`, `set_nickname`, `set_signature`, `set_unique_id`, `upload_avatar`, `privacy_settings`, `set_*` |
| `tt.feed`    | `following`, `friends`, `nearby`                                                         |
| `tt.video`   | `my_posts`, `favorites`, `collect`, `uncollect`, `list_collections`, `delete`, `pin`, `unpin`, `liked`, `watch_history`, `private_list` |
| `tt.comment` | `publish`, `delete`, `digg`                                                              |
| `tt.social`  | `follow`, `unfollow`, `like`, `unlike`, `block`, `unblock`, `friend_list`, `repost`, `unrepost`, `remove_follower` |
| `tt.dm`      | `conversations`, `messages`, `send`, `send_image`, `send_video`, `mark_read`, `unread_count`, `stranger_*` |
| `tt.upload`  | `creator_info`, `upload_video`, `upload_photo`                                           |
| `tt.notice`  | `multi`, `count`, `inbox`, `delete`, `shield`                                            |
| `tt.live`    | `room_create`, `room_enter`, `room_leave`, `comment_send`, `gift_send`, `like`, `room_audience` |
| `tt.music`   | `collect`, `collection`, `user_collected`                                                |

Login options via `tt.passport`:

```python
tt = TikTokAPI(api_key="sk_live_...")

# Email + password
tt.passport.email_login("user@example.com", "password")

# SMS: request code, then login
tt.passport.send_sms_code("+15551234567", scene="login")
tt.passport.sms_login("+15551234567", "123456")

# Username + password
tt.passport.username_login("tiktokuser", "password")

# After login, cookies live on tt.device — save for reuse
tt.device.save_session_env("~/.secrets.env")

# Later:
from tiktokflow.android.device import Device
d = Device()
d.load_session_env("~/.secrets.env")
tt = TikTokAPI(api_key="sk_live_...", device=d)
```

TikTok sometimes shows a captcha during SMS send; `send_sms_code` and
`username_login` accept a `captcha=` arg. For automated solving, set
`RUCAPTCHA_API_KEY` and the client will use the 2captcha/rucaptcha
Coordinates method.

## The write caveat (read this before shipping anything)

Follow, like, comment publish, favorite — pure-HTTP writes return **200 OK**
but **TikTok often does not persist them**. The server records the attempt,
checks it against on-device behavioural signals it expects to see from a
real app session (sensor events, app-lifecycle traces, re-entrancy), and
when they are missing it silently drops the write. The response looks
successful.

What this means in practice:

- **Reads are reliable** — zero-device feeds, profiles, searches, video
  metadata, comment lists.
- **Removals are reliable** — `unfollow`, `unlike`, `delete`, `uncollect`,
  `remove_follower` work from pure HTTP.
- **Writes are flaky** — `follow`, `like`, `comment.publish`, `collect`
  may or may not stick. Treat them as fire-and-forget until you verify.

If sticky writes matter for your use case (growth tools, engagement
automation, posting at scale), you need an on-device executor to replay
the write with real signals. Ping [`@mxmtkchk`](https://t.me/mxmtkchk)
— that integration is available separately.

## Android vs iOS

Same API surface, different device identity and transport. Switch with
one argument:

```python
tt = TikTokAPI(api_key="sk_live_...", platform="ios")
feed = tt.feed.for_you(count=10)   # same call, iOS endpoints under the hood
```

Android is the primary target and gets new endpoints first; iOS mirrors
the module layout and reuses the method names.

## Rate limits & reliability

- **1000 req/s with burst 5000 per key.** This is a service safety ceiling,
  not a product cap — a thousand concurrent client accounts at normal
  activity stay well under it.
- **429 is auto-retried** with exponential backoff; the client surfaces
  the exception only after retries are exhausted.
- **The limit is global per key**, not per process — running two workers
  doesn't double it.
- **No daily or monthly quotas.** You pay nothing; usage is not capped by
  volume.

Big farm (tens of thousands of accounts)? Per-key limits can be raised
on request — ping [`@mxmtkchk`](https://t.me/mxmtkchk).

## Advanced

### Custom signing server

Default is `https://sign.54-38-243-162.nip.io`. Override:

```python
tt = TikTokAPI(api_key="sk_live_...", signing_server="https://sign.your-domain.tld")
```

Or via env var:

```bash
export TIKTOKFLOW_SIGNING_SERVER=https://sign.your-domain.tld
```

### Proxies

```python
# Single SOCKS5/HTTP proxy
tt = TikTokAPI(api_key="sk_live_...", proxy="socks5://user:pass@host:1080")

# Pool with round-robin rotation
tt = TikTokAPI(
    api_key="sk_live_...",
    proxies=["http://p1:8080", "http://p2:8080"],
    proxy_rotate="round_robin",   # or "random"
)
```

### Device persistence

A registered device is a reusable identity. Save it, load it, treat it as
one TikTok account's phone.

```python
from tiktokflow.android.device import Device
from tiktokflow.android.register import register_device
from tiktokflow.android.remote_signer import RemoteSigner

signer = RemoteSigner("https://sign.54-38-243-162.nip.io", "sk_live_...")
device = register_device(signer=signer)
device.save("device.json")

# Later
device = Device.load("device.json")
tt = TikTokAPI(api_key="sk_live_...", device=device)
```

Session cookies (after login) ride on the Device too and go into
`~/.secrets.env` via `device.save_session_env()` / `device.load_session_env()`.

### Multi-account

For managing many accounts programmatically, the SDK ships an SQLite-backed
registry:

```python
from tiktokflow.android.account_store import AccountStore

store = AccountStore()                       # ~/.tiktokflow/accounts.db, chmod 600
store.add("alice", device=device)
account = store.get("alice")
tt = TikTokAPI(api_key="sk_live_...", device=account.device)
```

### Async

```python
import asyncio
from tiktokflow.android.async_client import AsyncAndroidClient
from tiktokflow.android.remote_signer import RemoteSigner
from tiktokflow.android.device import Device

async def main():
    signer = RemoteSigner("https://sign.54-38-243-162.nip.io", "sk_live_...")
    async with AsyncAndroidClient(Device(), signer=signer) as tt:
        feed = await tt.feed.for_you(count=10)
        print(len(feed["aweme_list"]))

asyncio.run(main())
```

### Rate limit cap

Throttle locally in addition to the service ceiling:

```python
tt = TikTokAPI(api_key="sk_live_...", rate_limit=20.0)   # 20 req/s client-side
```

## Supported endpoints

Twelve domain modules on both Android and iOS, exposed as
`tt.<module>.<method>`:

- `feed` — For You, Following, Friends, Nearby
- `user` — profiles, followers, following, settings, edit profile, privacy, block list
- `video` — detail, multi-detail, stats, my posts, favorites, collections, pin, delete, watch history, liked, insights
- `comment` — list, replies, publish, delete, digg
- `search` — universal / video / user search, suggestions, hot list, hashtag search + detail + videos, music
- `social` — follow, unfollow, like, unlike, block, dislike, repost, friend list, digg list, recommend users, remove follower
- `music` — detail, videos by track, search, hot, recommended, collect, collections
- `live` — recommend, search, room info, enter/leave, comments, gifts, like, create/finish
- `dm` — conversations, messages, send text/image/video, mark read, unread count, mute, stranger inbox, recall
- `upload` — video upload, photo-carousel upload, creator info
- `notice` — notifications multi, inbox, count, delete, shield
- `passport` — email / SMS / username+password / QR / OAuth login, registration, password reset, SMS code, TOTP, token refresh

## <a id="donate"></a>Donations

If this SDK saves you time, a tip is appreciated.

| Network                | Address                                        |
|------------------------|------------------------------------------------|
| Bitcoin (BTC)          | `bc1q73j9y68g02skp7tgfx8dy22w32rjrnea0647lg`   |
| Ethereum (ETH, ERC-20) | `0xF44233bee0f73152De3ba9Ebe8d5270C25825c7D`   |
| Tron (TRX, TRC-20)     | `TLmPmbg5n4BzJLCAiRREjJH1mErDQGg9BS`           |
| Solana (SOL)           | `q24r8XxZ7EVHmCEzKVSPUiAsuy1FFkfrpYmyw8AWx27`  |

Please verify the address matches the network before sending.

## Legal

This is an **unofficial, reverse-engineered** client. It is not affiliated
with, endorsed by, or sponsored by TikTok or ByteDance. "TikTok" and
related marks belong to ByteDance Ltd. Use the SDK only on accounts and
data you are authorised to access, and in compliance with applicable law
and TikTok's terms of service.

Licensed under the MIT License — see [`LICENSE`](LICENSE).

## Links

- Issues — <https://github.com/molkex/tiktok-private-api/issues>
- Security policy — [`SECURITY.md`](SECURITY.md)
- Key dispatcher — [`@tiktok_private_api_bot`](https://t.me/tiktok_private_api_bot)
- Maintainer — [`@mxmtkchk`](https://t.me/mxmtkchk)
