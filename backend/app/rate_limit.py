"""Process-local per-credential API rate limiting for the pilot REST surface."""

from __future__ import annotations

from hashlib import sha256
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class FixedWindowRateLimiter:
    """One-second fixed windows; production multi-instance use needs a shared store."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("rate limit must be positive")
        self.limit = limit
        self._windows: dict[str, tuple[int, int]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current_window = int(monotonic() if now is None else now)
        with self._lock:
            window, count = self._windows.get(key, (current_window, 0))
            if window != current_window:
                window, count = current_window, 0
            if count >= self.limit:
                self._windows[key] = (window, count)
                return False, 0
            count += 1
            self._windows[key] = (window, count)
            return True, self.limit - count


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit requests per credential without retaining or logging credentials."""

    def __init__(self, app: object, *, limit: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.limiter = FixedWindowRateLimiter(limit)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        key = _credential_key(request)
        allowed, remaining = self.limiter.allow(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limit_exceeded",
                    "detail": "Per-customer request limit exceeded",
                },
                headers={
                    "Retry-After": "1",
                    "X-RateLimit-Limit": str(self.limiter.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def _credential_key(request: Request) -> str:
    credential = request.headers.get("x-api-key") or request.headers.get("authorization")
    if credential:
        return "credential:" + sha256(credential.encode("utf-8")).hexdigest()
    client = request.client.host if request.client else "anonymous"
    return f"anonymous:{client}"
