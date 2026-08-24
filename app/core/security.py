"""Optional API-key authentication and local rate limiting."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic

from fastapi import Request, status

from app.core.config import Settings
from app.core.errors import RegLensError


@dataclass
class _RateWindow:
    started_at: float
    count: int = 0


class InMemoryRateLimiter:
    """Minute-window limiter suitable for local demos and single-process deploys."""

    def __init__(self, *, limit_per_minute: int) -> None:
        if limit_per_minute <= 0:
            raise ValueError("limit_per_minute must be greater than zero")
        self.limit_per_minute = limit_per_minute
        self._windows: dict[str, _RateWindow] = {}
        self._lock = RLock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = monotonic()
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.started_at >= 60:
                self._windows[key] = _RateWindow(started_at=now, count=1)
                return True, 60
            if window.count >= self.limit_per_minute:
                retry_after = max(1, int(round(60 - (now - window.started_at))))
                return False, retry_after
            window.count += 1
            retry_after = max(1, int(round(60 - (now - window.started_at))))
            return True, retry_after


def access_error_for_request(request: Request, settings: Settings) -> RegLensError | None:
    if _is_exempt(request, settings):
        return None
    if settings.api_key is None:
        return None

    provided = request.headers.get(settings.api_key_header)
    if provided is None:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            provided = authorization[7:]
    if provided != settings.api_key:
        return RegLensError(
            "valid RegLens API key is required",
            code="unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details={"header": settings.api_key_header},
        )
    return None


def rate_limit_error_for_request(
    request: Request,
    settings: Settings,
    limiter: InMemoryRateLimiter | None,
) -> tuple[RegLensError | None, int | None]:
    if limiter is None or _is_exempt(request, settings):
        return None, None
    key = _rate_limit_key(request, settings)
    allowed, retry_after = limiter.allow(key)
    if allowed:
        return None, None
    return (
        RegLensError(
            "rate limit exceeded",
            code="rate_limited",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"limit_per_minute": settings.rate_limit_per_minute},
        ),
        retry_after,
    )


def _is_exempt(request: Request, settings: Settings) -> bool:
    if request.method == "OPTIONS":
        return True
    return request.url.path in settings.auth_exempt_paths


def _rate_limit_key(request: Request, settings: Settings) -> str:
    api_key = request.headers.get(settings.api_key_header)
    if api_key:
        return f"api-key:{api_key}"
    client = request.client.host if request.client is not None else "unknown-client"
    return f"client:{client}"
