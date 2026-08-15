"""Bounded Prometheus RED metrics for the Ghost Fabric API pilot.

Metrics are process telemetry only. They never replace the canonical audit
trail and must not claim measured SLO attainment.
"""

from __future__ import annotations

import re
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

SERVICE_NAME = "ghost-fabric-api"
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_ID_RE = re.compile(r"(?<=/)[0-9a-fA-F]{8,}(?=/|$)")
_NUMERIC_RE = re.compile(r"(?<=/)\d+(?=/|$)")

REGISTRY = CollectorRegistry()

REQUESTS_TOTAL = Counter(
    "ghost_fabric_http_requests_total",
    "Total HTTP requests handled by the API",
    labelnames=("service", "method", "route", "status_class"),
    registry=REGISTRY,
)
REQUEST_ERRORS_TOTAL = Counter(
    "ghost_fabric_http_request_errors_total",
    "HTTP responses with status >= 500",
    labelnames=("service", "method", "route", "status_class"),
    registry=REGISTRY,
)
REQUESTS_IN_FLIGHT = Gauge(
    "ghost_fabric_http_requests_in_flight",
    "In-flight HTTP requests",
    labelnames=("service",),
    registry=REGISTRY,
)
REQUEST_DURATION_SECONDS = Histogram(
    "ghost_fabric_http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=("service", "method", "route", "status_class"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)
AUDIT_STORE_HEALTH = Gauge(
    "ghost_fabric_audit_store_healthy",
    "1 when the active audit store reports healthy, else 0",
    labelnames=("service", "backend"),
    registry=REGISTRY,
)
SCENARIO_EVENT_COUNT = Gauge(
    "ghost_fabric_scenario_event_count",
    "Current in-memory scenario event count for the active run",
    labelnames=("service",),
    registry=REGISTRY,
)
CONNECTED_CLIENTS = Gauge(
    "ghost_fabric_connected_clients",
    "Active WebSocket console connections",
    labelnames=("service",),
    registry=REGISTRY,
)


def status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def normalize_route(path: str) -> str:
    """Collapse path params into low-cardinality templates."""
    if not path:
        return "unknown"
    normalized = _UUID_RE.sub("{id}", path)
    normalized = _HEX_ID_RE.sub("{id}", normalized)
    normalized = _NUMERIC_RE.sub("{id}", normalized)
    if len(normalized) > 120:
        return "overflow"
    return normalized


def observe_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    route = normalize_route(path)
    klass = status_class(status_code)
    labels = {
        "service": SERVICE_NAME,
        "method": method.upper(),
        "route": route,
        "status_class": klass,
    }
    REQUESTS_TOTAL.labels(**labels).inc()
    REQUEST_DURATION_SECONDS.labels(**labels).observe(max(duration_seconds, 0.0))
    if status_code >= 500:
        REQUEST_ERRORS_TOTAL.labels(**labels).inc()


def mark_request_started() -> None:
    REQUESTS_IN_FLIGHT.labels(service=SERVICE_NAME).inc()


def mark_request_finished() -> None:
    REQUESTS_IN_FLIGHT.labels(service=SERVICE_NAME).dec()


def refresh_runtime_gauges(
    *,
    audit_healthy: bool,
    audit_backend: str,
    event_count: int,
    connected_clients: int,
) -> None:
    AUDIT_STORE_HEALTH.labels(service=SERVICE_NAME, backend=audit_backend or "unknown").set(
        1 if audit_healthy else 0
    )
    SCENARIO_EVENT_COUNT.labels(service=SERVICE_NAME).set(event_count)
    CONNECTED_CLIENTS.labels(service=SERVICE_NAME).set(connected_clients)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def metrics_snapshot() -> dict[str, Any]:
    """Test helper returning current counter/gauge samples."""
    samples: dict[str, float] = {}
    for metric in (
        REQUESTS_TOTAL,
        REQUEST_ERRORS_TOTAL,
        REQUESTS_IN_FLIGHT,
        REQUEST_DURATION_SECONDS,
        AUDIT_STORE_HEALTH,
        SCENARIO_EVENT_COUNT,
        CONNECTED_CLIENTS,
    ):
        for sample in metric.collect()[0].samples:
            key = f"{sample.name}|{','.join(f'{k}={v}' for k, v in sorted(sample.labels.items()))}"
            samples[key] = sample.value
    return samples
