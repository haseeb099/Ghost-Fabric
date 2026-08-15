"""Tests for request-scoped structured logging (GF-49)."""

from __future__ import annotations

import json
import logging
from io import StringIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.structured_logging import (
    JsonLogFormatter,
    RequestLoggingMiddleware,
    configure_structured_logging,
    hashed_identity,
)


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_json_log_formatter_emits_required_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="ghost_fabric",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="http_request",
        args=(),
        exc_info=None,
    )
    record.service = "ghost-fabric-api"
    record.request_id = "req_test"
    record.correlation_id = "run_test"
    record.method = "GET"
    record.path = "/api/v1/health"
    record.status_code = 200
    record.duration_ms = 1.5
    record.action = "GET /api/v1/health"
    record.user_hash = "abcd1234"

    payload = json.loads(formatter.format(record))
    assert payload["level"] == "info"
    assert payload["service"] == "ghost-fabric-api"
    assert payload["request_id"] == "req_test"
    assert payload["correlation_id"] == "run_test"
    assert payload["action"] == "GET /api/v1/health"
    assert payload["user_hash"] == "abcd1234"


def test_hashed_identity_never_returns_raw_credential() -> None:
    class _Req:
        headers = {"authorization": "Bearer secret-token"}

    digest = hashed_identity(_Req())  # type: ignore[arg-type]
    assert digest is not None
    assert "secret-token" not in digest
    assert len(digest) == 16


def test_request_logging_middleware_echoes_ids_and_logs() -> None:
    logger = logging.getLogger("ghost_fabric.test_middleware")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    capture = _CaptureHandler()
    logger.addHandler(capture)

    app = FastAPI()
    app.add_middleware(
        RequestLoggingMiddleware,
        logger=logger,
        get_correlation_id=lambda: "run_fixture",
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "req_fixed_001", "Authorization": "Bearer secret-token"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_fixed_001"
    assert response.headers["X-Correlation-ID"] == "run_fixture"
    assert capture.records
    record = capture.records[-1]
    assert record.getMessage() == "http_request"
    assert record.request_id == "req_fixed_001"
    assert record.correlation_id == "run_fixture"
    assert record.user_hash
    assert "secret-token" not in str(record.user_hash)


def test_configure_structured_logging_writes_json_line() -> None:
    stream = StringIO()
    logger = configure_structured_logging(level="INFO", json_logs=True)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.info(
        "service_boot",
        extra={"service": "ghost-fabric-api", "action": "configure", "correlation_id": "run_boot"},
    )
    payload = json.loads(stream.getvalue().strip())
    assert payload["message"] == "service_boot"
    assert payload["service"] == "ghost-fabric-api"
    assert payload["correlation_id"] == "run_boot"


def test_live_api_emits_request_and_correlation_headers() -> None:
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req_live_001"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_live_001"
    assert response.headers["X-Correlation-ID"].startswith("run_")
