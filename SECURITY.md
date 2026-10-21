# Security

## Reporting

If you discover a security vulnerability, please report it privately via [Telegram @mxmtkchk](https://t.me/mxmtkchk).

Do **not** open a public issue.

## Architecture

- The signing server holds all cryptographic material. The SDK never contains signing algorithms.
- Your API key authenticates requests to the signing server only — it is never sent to TikTok.
- Your IP connects to TikTok directly. The signing server never sees TikTok's responses or your data.
