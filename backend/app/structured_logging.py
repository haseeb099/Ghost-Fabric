"""Request-scoped JSON logging that never replaces the canonical audit trail."""

from __future__ import annotations

import logging
import sys
from hashlib import sha256
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.metrics import mark_request_finished, mark_request_started, observe_request

REQUEST_ID_HEADER = "X-Request-ID"
SCENARIO_CORRELATION_HEADER = "X-Correlation-ID"


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log record for stdout sinks."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "service": getattr(record, "service", "ghost-fabric-api"),
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "correlation_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "action",
            "user_hash",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return _json_dumps(payload)


def configure_structured_logging(*, level: str = "INFO", json_logs: bool = True) -> logging.Logger:
    """Configure the process logger once for request and service events."""
    logger = logging.getLogger("ghost_fabric")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger


def hashed_identity(request: Request) -> str | None:
    """Return a non-reversible identity handle; never the raw credential."""
    credential = request.headers.get("x-api-key") or request.headers.get("authorization")
    if not credential:
        return None
    return sha256(credential.encode("utf-8")).hexdigest()[:16]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Echo request IDs and emit structured access logs without capturing secrets."""

    def __init__(
        self,
        app: object,
        *,
        logger: logging.Logger | None = None,
        get_correlation_id: Any | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.logger = logger or logging.getLogger("ghost_fabric")
        self.get_correlation_id = get_correlation_id or (lambda: None)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex[:12]}"
        correlation_id = self.get_correlation_id()
        request.state.request_id = request_id
        started = perf_counter()
        mark_request_started()
        try:
            response = await call_next(request)
        except Exception:
            duration_seconds = perf_counter() - started
            observe_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_seconds=duration_seconds,
            )
            raise
        finally:
            mark_request_finished()
        duration_seconds = perf_counter() - started
        duration_ms = round(duration_seconds * 1000, 3)
        observe_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration_seconds,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        if correlation_id:
            response.headers[SCENARIO_CORRELATION_HEADER] = str(correlation_id)
        self.logger.info(
            "http_request",
            extra={
                "service": "ghost-fabric-api",
                "request_id": request_id,
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "action": f"{request.method} {request.url.path}",
                "user_hash": hashed_identity(request),
            },
        )
        return response


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
