from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.citizen_grid import PROHIBITED_TERMS, CitizenGrid
from app.main import app


client = TestClient(app)


def test_grid_starts_listening_with_full_synthetic_population() -> None:
    grid = CitizenGrid()
    assert grid.sensors_total == 5000
    assert grid.sensors_online == 5000
    assert grid.grid_state == "listening"
    assert grid.confidence == 0
    assert grid.projection()["ready_for_warning"] is False


def test_single_district_cannot_reach_advisory_readiness() -> None:
    grid = CitizenGrid()
    grid.register_detection()
    assert grid.grid_state == "listening"
    assert grid.projection()["ready_for_warning"] is False

    grid.register_detection()
    assert grid.grid_state == "corroborating"
    assert grid.projection()["ready_for_warning"] is False


def test_corroboration_requires_districts_and_confidence() -> None:
    grid = CitizenGrid()
    for _ in range(7):
        grid.register_detection()
    projection = grid.projection()
    assert projection["confirming_districts"] >= 3
    assert projection["confidence"] >= 55
    assert projection["state"] == "confirmed"
    assert projection["ready_for_warning"] is True


def test_grid_survives_thirty_percent_sensor_attrition() -> None:
    grid = CitizenGrid()
    for _ in range(7):
        grid.register_detection()
    grid.apply_attrition(30)
    projection = grid.projection()
    assert projection["grid_survival_percent"] == 70
    assert projection["state"] == "confirmed"
    assert projection["ready_for_warning"] is True


def test_channel_ladder_falls_back_then_exhausts() -> None:
    grid = CitizenGrid()
    assert grid.jam_active_channel() == {"jammed_channel": "sms", "fallback_channel": "radio"}
    assert grid.jam_active_channel() == {"jammed_channel": "radio", "fallback_channel": "mesh"}
    assert grid.jam_active_channel() == {"jammed_channel": "mesh", "fallback_channel": None}
    assert grid.active_channel is None
    assert grid.projection()["ready_for_warning"] is False


def test_projection_data_fields_never_carry_targeting_language() -> None:
    """Disclaimer prose may negate these terms; data fields must never contain them."""
    grid = CitizenGrid()
    for _ in range(12):
        grid.register_detection()
    grid.dispatch_warning("sms")
    projection = grid.projection()
    disclaimers = {"notice", "guardrail", "privacy"}
    data_fields = {key: value for key, value in projection.items() if key not in disclaimers}
    rendered = str(data_fields).lower()
    for term in PROHIBITED_TERMS:
        assert term not in rendered
    assert "no targeting" in projection["notice"].lower()


def test_district_names_reject_prohibited_content() -> None:
    with pytest.raises(ValueError, match="prohibited citizen-grid term"):
        CitizenGrid(
            districts=[
                type(CitizenGrid().districts[0])(
                    id="d1", name="Launcher Row", sensors_total=10, sensors_online=10
                )
            ]
        )


def test_advisory_requires_corroboration_then_records_audit_evidence() -> None:
    client.post("/api/scenario/reset")

    blocked = client.post("/api/citizen/warn")
    assert blocked.status_code == 409

    for _ in range(7):
        assert client.post("/api/citizen/detect").status_code == 200

    approved = client.post("/api/citizen/warn")
    assert approved.status_code == 200
    citizen = approved.json()["citizen"]
    assert citizen["warning_dispatched"] is True
    assert citizen["dispatch_channel"] == "sms"
    assert citizen["state"] == "confirmed"

    events = approved.json()["events"]
    advisory = next(event for event in events if event["type"] == "citizen.advisory_approved")
    assert advisory["payload"]["effect"] == "simulation-only"
    assert advisory["payload"]["synthetic_lead_seconds"] == 240
    assert "trajectory" not in str(advisory["payload"]).lower()


def test_jammed_channel_forces_fallback_through_api() -> None:
    client.post("/api/scenario/reset")
    for _ in range(7):
        client.post("/api/citizen/detect")

    jammed = client.post("/api/citizen/jam")
    assert jammed.status_code == 200
    channels = {item["id"]: item for item in jammed.json()["citizen"]["channels"]}
    assert channels["sms"]["status"] == "jammed"
    assert channels["radio"]["active"] is True

    approved = client.post("/api/citizen/warn")
    assert approved.json()["citizen"]["dispatch_channel"] == "radio"


def test_grid_read_route_is_available_to_viewers() -> None:
    client.post("/api/scenario/reset")
    response = client.get("/api/citizen/grid")
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "citizen-sensor-simulation"
    assert payload["min_confirming_districts"] == 3
    assert "no device identity" in payload["privacy"]
