"""Prometheus RED metrics tests for GF-50."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.metrics import normalize_route, observe_request, render_metrics, status_class


def test_normalize_route_bounds_cardinality() -> None:
    assert normalize_route("/api/v1/scenario/replay/12") == "/api/v1/scenario/replay/{id}"
    assert normalize_route("/api/v1/network/fail/northstar") == "/api/v1/network/fail/northstar"
    assert (
        normalize_route("/api/v1/items/550e8400-e29b-41d4-a716-446655440000")
        == "/api/v1/items/{id}"
    )
    assert status_class(200) == "2xx"
    assert status_class(503) == "5xx"


def test_observe_request_records_errors_and_duration() -> None:
    observe_request(method="GET", path="/api/v1/health", status_code=200, duration_seconds=0.01)
    observe_request(method="GET", path="/api/v1/health", status_code=503, duration_seconds=0.02)
    payload, content_type = render_metrics()
    text = payload.decode("utf-8")
    assert "text/plain" in content_type
    assert "ghost_fabric_http_requests_total" in text
    assert 'route="/api/v1/health"' in text
    assert "ghost_fabric_http_request_errors_total" in text
    assert "ghost_fabric_http_request_duration_seconds_bucket" in text


def test_live_metrics_endpoint_exposes_prometheus_text() -> None:
    from app.main import app

    client = TestClient(app)
    before = client.get("/api/v1/health")
    assert before.status_code == 200
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "ghost_fabric_http_requests_total" in response.text
    assert "ghost_fabric_audit_store_healthy" in response.text
    assert "ghost_fabric_scenario_event_count" in response.text
    aliased = client.get("/api/v1/metrics")
    assert aliased.status_code == 200
    assert "ghost_fabric_http_requests_total" in aliased.text


def test_metrics_do_not_alter_audit_event_chain() -> None:
    from app.main import app, state

    client = TestClient(app)
    client.post("/api/scenario/reset")
    head_before = state.events[-1].event_hash if state.events else None
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    head_after = state.events[-1].event_hash if state.events else None
    assert head_after == head_before
