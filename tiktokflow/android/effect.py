"""Effect/Sticker endpoints: detail, videos by effect.

/aweme/v1/sticker/detail/ — информация об эффекте (param: sticker_ids).
/aweme/v1/sticker/aweme/ — видео с этим эффектом."""
from __future__ import annotations

from typing import Any

from .transport import AndroidTransport


class EffectAPI:
    def __init__(self, transport: AndroidTransport):
        self._t = transport

    def detail(self, *effect_ids: str) -> dict[str, Any]:
        """/aweme/v1/sticker/detail/ — effect info by one or more IDs."""
        ids = ",".join(effect_ids)
        return self._t.get("/aweme/v1/sticker/detail/", params={
            "sticker_ids": ids,
        }, bare=True)

    def videos(
        self,
        effect_id: str,
        *,
        count: int = 20,
        cursor: int = 0,
    ) -> dict[str, Any]:
        """/aweme/v1/sticker/aweme/ — videos using this effect."""
        return self._t.get("/aweme/v1/sticker/aweme/", params={
            "sticker_id": effect_id,
            "count": count,
            "cursor": cursor,
        }, bare=True)
