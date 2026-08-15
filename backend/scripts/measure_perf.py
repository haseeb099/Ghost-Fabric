"""Measure event-to-UI and scenario-reset latency for Ghost Fabric."""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1))))
    return ordered[index]


def measure() -> dict[str, float | int]:
    client = TestClient(app)
    client.post("/api/scenario/reset")

    event_latencies_ms: list[float] = []
    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()
        for _ in range(40):
            started = time.perf_counter()
            response = client.post("/api/scenario/advance", json={"seconds": 5})
            assert response.status_code == 200
            message = websocket.receive_json()
            elapsed_ms = (time.perf_counter() - started) * 1000
            assert message["kind"] == "event"
            event_latencies_ms.append(elapsed_ms)

    reset_latencies_ms: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.post("/api/scenario/reset")
        assert response.status_code == 200
        reset_latencies_ms.append((time.perf_counter() - started) * 1000)

    return {
        "samples_event_to_ui": len(event_latencies_ms),
        "event_to_ui_p50_ms": round(statistics.median(event_latencies_ms), 3),
        "event_to_ui_p95_ms": round(percentile(event_latencies_ms, 95), 3),
        "event_to_ui_max_ms": round(max(event_latencies_ms), 3),
        "samples_reset": len(reset_latencies_ms),
        "reset_p50_ms": round(statistics.median(reset_latencies_ms), 3),
        "reset_p95_ms": round(percentile(reset_latencies_ms, 95), 3),
        "reset_max_ms": round(max(reset_latencies_ms), 3),
    }


if __name__ == "__main__":
    results = measure()
    output = Path(__file__).resolve().parents[1] / "app" / "fixtures" / "perf-review-latest.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
