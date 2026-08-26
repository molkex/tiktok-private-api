"""Единый набор ошибок SDK. Один слой маппинга — HTTP-транспорт и API-обёртки
поднимают только эти типы, а не голые httpx.HTTPStatusError, чтобы MCP/вызывающий
код ловил предсказуемое дерево исключений."""


class TikTokError(Exception):
    """Базовая ошибка. code — машиночитаемый код из ответа TikTok (log_id для трассировки)."""

    def __init__(self, message: str, *, code: str | None = None, log_id: str | None = None,
                 http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.log_id = log_id
        self.http_status = http_status

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"code={self.code}")
        if self.log_id:
            parts.append(f"log_id={self.log_id}")
        return " ".join(parts)


class AuthError(TikTokError):
    """Токен протух/невалиден/нет нужного scope. Вызывающий должен обновить или переавторизовать."""


class RateLimitError(TikTokError):
    """429 или daily-quota. retry_after — секунды до следующей попытки, если TikTok их отдал."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class InvalidRequest(TikTokError):
    """4xx кроме auth/rate — кривые параметры, отклонённый контент, неверный creator_info."""


class ServerError(TikTokError):
    """5xx на стороне TikTok — имеет смысл ретраить."""
