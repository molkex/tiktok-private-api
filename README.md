# tiktok-private-api

## What it is

An open-source Python SDK for the private TikTok mobile API — the same
endpoints the Android and iOS apps use for feed, profiles, video, comments,
likes, follows, uploads, DMs, search, music, live and notifications. The hard
part — request signing (X-Argus / X-Ladon / X-Gorgon / X-Khronos / device
fingerprint) — is **not** done in this package. Instead, the client makes a
small call to a hosted signing service with your API key, gets back the
signature headers for that one request, and then sends the actual TikTok
request from your own machine. **Your HTTP requests to TikTok leave your IP,
not ours.** We never see request bodies or responses.

## Install

```bash
pip install tiktok-private-api
```

> **Known issue:** version `0.4.3` currently on PyPI has an import bug and
> fails to load (`ModuleNotFoundError` on first `import tiktokflow`). A fixed
> `0.4.4` is being prepared — pin to it once released. In the meantime, use
> `0.3.0` (`pip install tiktok-private-api==0.3.0`).

## Quickstart

Sync:

```python
from tiktokflow import TikTokAPI

tt = TikTokAPI(api_key="sk_live_...")

me   = tt.user.profile_self()
feed = tt.feed.for_you(count=10)
first = feed["aweme_list"][0]
tt.social.like(first["aweme_id"])
tt.comment.publish(first["aweme_id"], "nice")
```

Async:

```python
import asyncio
from tiktokflow.android.async_client import AsyncAndroidClient
from tiktokflow.android.remote_signer import RemoteSigner
from tiktokflow.android.device import Device

async def main():
    signer = RemoteSigner("https://sign.example", api_key="sk_live_...")
    async with AsyncAndroidClient(Device(), signer=signer) as tt:
        feed = await tt.feed.for_you(count=10)
        print(len(feed["aweme_list"]))

asyncio.run(main())
```

## How to get a key

1. Open [`@lazymanagerrobot`](https://t.me/lazymanagerrobot) on Telegram.
2. Send `/key`.
3. The bot replies with your personal API key (shown once — save it).

Keys are **free** right now. A paid tier is planned later; it will be a
single flag flip on the server, so your code will not change — only the
rate-limit numbers.

## What we see on our side

The signing service receives: your API key, the TikTok endpoint path, and the
request parameters that have to be included in the signature. For
accounting and abuse protection it keeps, per key:

- which endpoints were called,
- counts and timestamps,
- the HTTP status code TikTok returned.

What it **does not** log:

- request bodies,
- response bodies,
- TikTok user IDs / usernames / aweme IDs / cookies,
- any TikTok content (videos, text, DMs, comments),
- your TikTok session tokens.

This is enforced in the service code: the log writers only accept the fields
above, and request/response bodies never reach them. If you want to audit it,
ping the maintainer on Telegram — the relevant file in the private repo can
be shared.

## Rate limits and tiers

- **No monthly or daily quotas.** You pay nothing while the service is free; usage is not capped by volume.
- **Per-key safety ceiling: 100 req/s, burst 500.** This is a crash-loop guard for the signing service itself, not a product limit — a thousand client accounts at normal activity stay well under it. If a runaway script spikes above the burst, the service answers `429` on the excess; backing off a second clears it.
- **Paid tier (later):** no rate changes planned; the paid flag unlocks support, SLAs, and extended endpoints when they land. Same API, same key format.

The limit is global per key, not per process, so running two workers does
not double it.

## Supported endpoints

Twelve domain modules, exposed as `tt.<module>.<method>`:

- `profile` / `user` — profiles, followers, following, edit profile, privacy, block list
- `video` — detail, my posts, favorites, collections, stats, delete
- `feed` — For You, Following, Friends, Nearby
- `comment` — list, replies, publish, delete, digg
- `dm` — conversations, messages, send, stranger inbox
- `search` — universal / video / user search, suggestions, trending, hashtags
- `social` — follow, like, block, dislike, friend list, digg list, recommend users
- `upload` — video and photo-carousel upload and publish
- `live` — search, room info, gifts
- `music` — detail, videos by track, search, trending, collections
- `notice` — notifications, unread count, inbox
- `passport` — login (email / phone / username+pass / code / QR / OAuth), registration, password reset, token refresh

Exact module list is pinned by `ops/release/public_manifest.txt` in the source
repo — nothing ships to PyPI that is not in that file.

## <a id="donate"></a>Donations

If this SDK saves you time, a tip is appreciated.

| Network | Address |
|---|---|
| Bitcoin (BTC) | `bc1q73j9y68g02skp7tgfx8dy22w32rjrnea0647lg` |
| Ethereum (ETH, ERC-20) | `0xF44233bee0f73152De3ba9Ebe8d5270C25825c7D` |
| Tron (TRX, TRC-20) | `TLmPmbg5n4BzJLCAiRREjJH1mErDQGg9BS` |
| Solana (SOL) | `q24r8XxZ7EVHmCEzKVSPUiAsuy1FFkfrpYmyw8AWx27` |

Please verify the address matches the network before sending.

## Legal and attribution

This is an **unofficial, reverse-engineered** client. It is not affiliated
with, endorsed by, or sponsored by TikTok or ByteDance. "TikTok" and related
marks belong to ByteDance Ltd. Use the SDK only on accounts and data you are
authorised to access, and in compliance with applicable law and TikTok's
terms of service.

Licensed under the MIT License — see [`LICENSE`](LICENSE).

## Links

- Issues: <https://github.com/molkex/tiktok-private-api/issues>
- Security policy: [`SECURITY.md`](SECURITY.md)
- Key dispatcher bot: [`@lazymanagerrobot`](https://t.me/lazymanagerrobot)
