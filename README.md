# tiktok-private-api

**Unofficial TikTok mobile API SDK for Python.** Talks to the same private
endpoints the real Android/iOS app uses — feed, profiles, search, comments,
likes, follows, uploads — with full request signing (X-Argus / X-Ladon /
X-Gorgon / X-Khronos). **No TikTok for Developers account, no OAuth, no app
review, no `SELF_ONLY` limit.** You drive a real logged-in session, not the
throttled official API.

> This is a reverse-engineering / automation toolkit. Use it on accounts and
> data you are authorized to access.

---

## Why this instead of the official API

| | Official TikTok API | **tiktok-private-api** |
|---|---|---|
| Developer account / app review | required | **not needed** |
| `client_key` / `client_secret` | required | **not needed** |
| Reading feed, other users, search | ❌ not exposed | ✅ |
| Likes / comments / follows / blocks | ❌ | ✅ |
| Public posting (not just `SELF_ONLY`) | after review only | ✅ |
| Rate limits | tight, per-app | per-account, mobile-grade |

The official Content Posting / Display API only lets you touch *your own*
connected account in a sandbox. This SDK speaks the mobile protocol, so it does
what the app does.

## Features

- **Full mobile signing** — X-Argus, X-Ladon, X-Gorgon, X-Khronos, device
  fingerprint, auto device registration.
- **Android + iOS** — one API surface (`AndroidClient` / `IOSClient`), the iOS
  layer overrides device params + Safari TLS impersonation.
- **160+ endpoints across 14 modules** — feed, user, video, search, comment,
  social (like/follow/block), music, notice, live, dm, effect, upload, passport.
- **Reliable engagement writes** — like, comment, follow, block, collect routed
  through the device's own TTNet/QUIC stack to pass server-side checks (Janus/SC).
- **Session-based auth** — extract a logged-in session from an emulator or
  jailbroken device; no password handling in the SDK.
- **Extras** — async client, multi-account fleet with cooldown/ban tracking,
  web-scraping fallbacks, proxy rotation, MCP server.

## Quick start

Request signing runs on our hosted service — you just need an API key. No
device, no local signing setup to maintain.

```python
from tiktokflow import TikTokAPI

tt = TikTokAPI(api_key="sk_...")        # get a key — see "Get access" below

me   = tt.user.profile_self()
feed = tt.feed.for_you(count=10)
tt.social.like(feed["aweme_list"][0]["aweme_id"])
tt.social.follow(feed["aweme_list"][0]["author"]["uid"])
tt.comment.publish(feed["aweme_list"][0]["aweme_id"], "🔥")
```

```python
# iOS device profile, proxy rotation, rate limiting — one call:
tt = TikTokAPI(api_key="sk_...", platform="ios",
               proxies=["socks5://user:pass@host:port"], rate_limit=2.0)
```

## Endpoint modules

| Module | What it covers |
|--------|----------------|
| `feed` | For You, Following, Friends, Nearby |
| `user` | profiles, followers/following, edit profile (name/bio/username/avatar), privacy settings, block list, account status |
| `video` | detail, my posts, favorites, collections, stats, insights/analytics, delete |
| `search` | universal / video / user search, suggestions, trending, hashtags |
| `comment` | list, replies, publish, delete, digg |
| `social` | follow, like, block, dislike, friend list, digg list, recommend users |
| `music` | detail, videos by track, search, trending, collections |
| `notice` | notifications, unread count, inbox |
| `effect` | sticker/effect detail, videos by effect |
| `live` | search, room info, gifts |
| `dm` | conversations, messages, send, stranger inbox |
| `passport` | all login (email/phone/username+pass, code, QR, OAuth), registration, password reset, token refresh |
| `upload` | video + photo-carousel upload and publish |

## Install

```bash
pip install tiktok-private-api
```

## How it works

Mobile request signing (X-Argus / X-Ladon / X-Gorgon / device fingerprint) is
the hard part that breaks every few app updates. We run it as a managed service:
your client sends the request, our signing server returns valid headers, TikTok
accepts it. You get a stable API and never touch signing internals — they're
kept server-side, not shipped in this package.

## Get access

API keys, pricing, higher-volume plans, and custom work:
**[@mxmtkchk](https://t.me/mxmtkchk)** on Telegram.

## Disclaimer

Not affiliated with or endorsed by TikTok / ByteDance. Provided for research and
automation on authorized accounts. You are responsible for complying with
TikTok's terms and applicable law.
