import asyncio

from fastapi.testclient import TestClient

from app.ai_adapter import ProviderNeutralAdapter
from app.main import app


client = TestClient(app)


def test_health_reports_fixture_mode() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic-fixture"


def test_mesh_topology_is_versioned_read_only_fixture_state() -> None:
    client.post("/api/scenario/reset")
    response = client.get("/api/v1/mesh/topology")

    assert response.status_code == 200
    topology = response.json()
    assert topology["schema_version"] == 1
    assert topology["nodes"]
    assert topology["coordinator"] is not None
    assert topology["notice"].startswith("Fixture-backed")
    assert "execution" in topology["notice"]


def test_prophet_read_models_expose_labeled_review_only_evidence() -> None:
    client.post("/api/scenario/reset")

    scores = client.get("/api/v1/prophet/scores")
    explanation = client.get("/api/v1/prophet/explain")

    assert scores.status_code == 200
    assert scores.json()["mode"] == "fixture"
    assert scores.json()["signals"]
    assert "does not authorize action" in scores.json()["notice"]
    assert explanation.status_code == 200
    assert explanation.json()["mode"] == "fixture"
    assert explanation.json()["explanation"]["mode"] == "fixture"
    assert "cannot determine ground truth" in explanation.json()["notice"]


def test_phoenix_workflow_read_model_does_not_approve_or_execute() -> None:
    client.post("/api/scenario/reset")
    response = client.get("/api/v1/phoenix/workflows")

    assert response.status_code == 200
    workflow = response.json()
    assert workflow["schema_version"] == 1
    assert workflow["workflow_status"] == "degraded"
    assert workflow["approved_option"] is None
    assert workflow["options"]
    assert workflow["approval_policy"] == {"operator": 1}
    assert workflow["pre_approved"]["auto_execute"] is False
    assert workflow["pre_approved"]["templates"]
    assert all(item["requires_operator_confirm"] for item in workflow["pre_approved"]["templates"])
    assert "explicit operator approval remains required" in workflow["notice"]


def test_versioned_mesh_failover_and_phoenix_approval_routes() -> None:
    client.post("/api/v1/scenario/reset")
    failover = client.post(
        "/api/v1/mesh/failover",
        json={"node_id": "northstar"},
        headers={"X-Command-ID": "mesh-failover-alias-1"},
    )
    assert failover.status_code == 200
    assert failover.json()["network"]["coordinator"] == "atlas"

    approved = client.post(
        "/api/v1/phoenix/approve",
        json={"option_id": "route-atlas"},
        headers={"X-Command-ID": "phoenix-approve-alias-1"},
    )
    assert approved.status_code == 200
    assert approved.json()["phoenix"]["approved_option"] == "route-atlas"
    assert approved.json()["phoenix"]["workflow"]["state"] == "execution"

    executed = client.post(
        "/api/v1/phoenix/execute",
        headers={"X-Command-ID": "phoenix-execute-alias-1"},
    )
    assert executed.status_code == 200
    assert executed.json()["phoenix"]["workflow"]["state"] == "verify"

    verified = client.post(
        "/api/v1/phoenix/verify",
        json={"succeeded": True},
        headers={"X-Command-ID": "phoenix-verify-alias-1"},
    )
    assert verified.status_code == 200
    workflow = verified.json()["phoenix"]["workflow"]
    assert workflow["state"] == "restored"
    assert [transition["to_state"] for transition in workflow["transitions"]] == [
        "approval",
        "execution",
        "verify",
        "restored",
    ]
    assert verified.json()["phoenix"]["notification_outbox"]

    rolled_back = client.post(
        "/api/v1/phoenix/rollback",
        json={"reason": "operator rehearsal rollback"},
        headers={"X-Command-ID": "phoenix-rollback-alias-1"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["phoenix"]["workflow"]["state"] == "failed"
    assert rolled_back.json()["phoenix"]["approved_option"] is None


def test_failed_phoenix_verification_enters_rollback() -> None:
    client.post("/api/v1/scenario/reset")
    client.post("/api/v1/mesh/failover", json={"node_id": "northstar"})
    client.post("/api/v1/phoenix/approve", json={"option_id": "route-atlas"})
    client.post("/api/v1/phoenix/execute")
    failed = client.post("/api/v1/phoenix/verify", json={"succeeded": False, "reason": "verification fixture failed"})
    assert failed.status_code == 200
    assert failed.json()["phoenix"]["workflow"]["state"] == "failed"
    assert failed.json()["phoenix"]["approved_option"] is None
    assert any(event["type"] == "phoenix.rollback_completed" for event in failed.json()["events"])


def test_mirror_catalog_and_human_branch_selection_are_fixture_only() -> None:
    client.post("/api/scenario/reset")
    catalog = client.get("/api/v1/mirror/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["active_scenario_id"] == "mirror-fictional-network-partition-v1"
    assert len(catalog.json()["scenarios"]) >= 8

    detail = client.get("/api/v1/mirror/scenarios/mirror-fictional-network-partition-v1")
    assert detail.status_code == 200
    assert detail.json()["scenario"]["classification"] == "synthetic-training"

    baseline = client.get("/api/scenario").json()
    assert baseline["mirror"]["awaiting_choice"] is True
    assert baseline["mirror"]["decision_point_id"] == "relay-loss"
    assert {branch["id"] for branch in baseline["mirror"]["branches"]} == {"hold", "bridge", "partition"}
    assert baseline["scenario"]["demo_phase"]["id"] == "baseline"

    branch = client.post(
        "/api/tabletop/select",
        json={"branch_id": "bridge", "decision_point_id": "relay-loss"},
    )
    assert branch.status_code == 200
    assert branch.json()["mirror"]["selected_branch"] == "bridge"
    assert any(event["type"] == "mirror.branch.recorded" for event in branch.json()["events"])
    assert all(
        event["payload"].get("effect") == "tabletop-fixture-only"
        for event in branch.json()["events"]
        if event["type"].startswith("mirror.")
    )


def test_api_errors_are_structured() -> None:
    response = client.post("/api/v1/mesh/failover", json={})
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "detail": "Request validation failed",
    }


def test_coordinator_handoff_and_recovery_are_audited() -> None:
    client.post("/api/scenario/reset")

    failed = client.post("/api/network/fail/northstar")
    assert failed.status_code == 200
    failed_snapshot = failed.json()
    assert failed_snapshot["network"]["coordinator"] == "atlas"
    assert any(event["type"] == "coordinator.handoff" for event in failed_snapshot["events"])
    assert failed_snapshot["events"][-1]["type"] == "recovery.options_recomputed"
    assert failed_snapshot["phoenix"]["planner"]["available_options"] == 4
    assert failed_snapshot["phoenix"]["options"][0]["id"] == "route-atlas"

    approved = client.post(
        "/api/recovery/approve",
        json={"option_id": "route-atlas", "actor": "TEST-COMMANDER"},
    )
    assert approved.status_code == 200
    assert approved.json()["phoenix"]["workflow"]["state"] == "execution"
    client.post("/api/recovery/execute")
    restored = client.post("/api/recovery/verify", json={"succeeded": True}).json()
    assert restored["phoenix"]["workflow_status"] == "restored"
    assert restored["phoenix"]["approved_option"] == "route-atlas"


def test_forecast_is_deterministic_after_reset() -> None:
    client.post("/api/scenario/reset")
    first = client.post("/api/scenario/advance", json={"seconds": 20}).json()
    first_confidence = first["prophet"]["confidence"]

    client.post("/api/scenario/reset")
    second = client.post("/api/scenario/advance", json={"seconds": 20}).json()

    assert second["prophet"]["confidence"] == first_confidence
    assert second["prophet"]["signals"] == first["prophet"]["signals"]


def test_replay_checkpoint_preserves_historical_state() -> None:
    reset = client.post("/api/scenario/reset").json()
    reset_sequence = reset["scenario"]["sequence"]
    client.post("/api/scenario/advance", json={"seconds": 15})
    current = client.get("/api/scenario").json()

    replay = client.get(f"/api/scenario/replay/{reset_sequence}")
    assert replay.status_code == 200
    assert replay.json()["scenario"]["sequence"] == reset_sequence
    assert replay.json()["prophet"]["confidence"] == 36
    assert current["prophet"]["confidence"] > replay.json()["prophet"]["confidence"]


def test_websocket_resume_returns_only_missed_events() -> None:
    client.post("/api/scenario/reset")
    with client.websocket_connect("/ws/events") as websocket:
        initial = websocket.receive_json()
    first_sequence = initial["snapshot"]["scenario"]["sequence"]

    client.post("/api/scenario/advance", json={"seconds": 10})
    with client.websocket_connect(
        f"/ws/events?correlation_id={initial['snapshot']['scenario']['correlation_id']}&after_sequence={first_sequence}"
    ) as websocket:
        resumed = websocket.receive_json()

    assert resumed["kind"] == "resume"
    assert resumed["from_sequence"] == first_sequence
    assert len(resumed["events"]) == 1
    assert resumed["events"][0]["sequence"] == first_sequence + 1


def test_speed_and_branch_changes_are_deterministic_and_audited() -> None:
    client.post("/api/scenario/reset")
    speed = client.post("/api/scenario/speed", json={"multiplier": 4})
    assert speed.status_code == 200
    assert speed.json()["scenario"]["speed"] == 4

    advanced = client.post("/api/scenario/advance", json={"seconds": 5}).json()
    assert advanced["scenario"]["time_ms"] == 20_000
    assert advanced["events"][-1]["payload"]["speed"] == 4

    branch = client.post(
        "/api/tabletop/select",
        json={"branch_id": "bridge", "actor": "TEST-COMMANDER"},
    )
    assert branch.status_code == 200
    assert branch.json()["mirror"]["selected_branch"] == "bridge"
    assert any(event["type"] == "mirror.outcome.recorded" for event in branch.json()["events"])
    assert branch.json()["events"][-1]["payload"]["effect"] == "tabletop-fixture-only"


def test_retried_mutation_is_idempotent() -> None:
    client.post("/api/scenario/reset")
    headers = {"X-Command-ID": "test-idempotency-advance-001"}

    first = client.post("/api/scenario/advance", json={"seconds": 5}, headers=headers)
    second = client.post("/api/scenario/advance", json={"seconds": 5}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    current = client.get("/api/scenario").json()
    assert current["scenario"]["time_ms"] == 5_000
    assert current["scenario"]["sequence"] == first.json()["scenario"]["sequence"]


def test_mesh_routes_recompute_and_detect_partitions() -> None:
    reset = client.post("/api/scenario/reset").json()
    assert reset["network"]["metrics"]["connected_components"] == 1
    assert reset["network"]["metrics"]["active_links"] == 21

    handoff = client.post("/api/network/fail/northstar").json()
    assert handoff["network"]["coordinator"] == "atlas"
    assert handoff["network"]["metrics"]["connected_components"] == 1
    assert handoff["network"]["metrics"]["coordinator_reachable_nodes"] == 11
    assert any(event["type"] == "mesh.routes_recomputed" for event in handoff["events"])
    assert handoff["events"][-1]["type"] == "recovery.options_recomputed"

    client.post("/api/scenario/reset")
    client.post("/api/network/fail/harbor")
    client.post("/api/network/fail/kestrel")
    partitioned = client.post("/api/network/fail/mosaic").json()
    assert partitioned["network"]["metrics"]["connected_components"] == 2
    assert partitioned["network"]["metrics"]["coordinator_reachable_nodes"] == 8
    assert any(event["type"] == "mesh.routes_recomputed" and event["severity"] == "warning" for event in partitioned["events"])


def test_phoenix_ranker_orders_safe_options_and_handles_no_valid_path() -> None:
    baseline = client.post("/api/scenario/reset").json()["phoenix"]
    options = baseline["options"]
    assert len(options) == 4
    assert baseline["planner"]["ranking"] == [
        "availability",
        "reliability",
        "latency",
        "reversibility",
    ]
    assert options[0]["id"] == "route-atlas"
    assert options[0]["availability"] == 100
    assert options[0]["status"] == "recommended"
    assert options[0]["reversibility"] == "high"
    assert all("non-lethal" not in option["rationale"].lower() for option in options)

    unavailable = client.post("/api/network/fail/ridge").json()["phoenix"]
    assert unavailable["options"] == []
    assert unavailable["planner"]["available_options"] == 0
    assert unavailable["workflow_status"] == "degraded"
    assert unavailable["planner"]["notice"].startswith("Non-lethal")


def test_append_only_audit_export_preserves_replayable_event_chain() -> None:
    client.post("/api/scenario/reset")
    client.post("/api/scenario/speed", json={"multiplier": 2})
    client.post("/api/scenario/advance", json={"seconds": 15})
    exported = client.get("/api/audit/export")
    assert exported.status_code == 200
    audit = exported.json()

    assert audit["schema_version"] == 1
    assert audit["export_type"] == "ghost-fabric-append-only-audit"
    assert audit["fixture"] == {
        "id": "broken-signal-v1",
        "version": "1.0.0",
        "seed": 4107,
    }
    assert audit["event_count"] == len(audit["records"]) == 3
    assert audit["event_chain_head"] == audit["records"][-1]["event_hash"]
    assert len(audit["export_hash"]) == 64

    for expected_sequence, record in enumerate(audit["records"], start=1):
        assert record["sequence"] == expected_sequence
        assert len(record["event_hash"]) == 64
        replay = client.get(f"/api/scenario/replay/{record['sequence']}")
        assert replay.status_code == 200
        assert replay.json()["scenario"]["event_chain_head"] == record["event_hash"]

    same_export = client.get("/api/audit/export").json()
    assert same_export["export_hash"] == audit["export_hash"]


def test_health_metrics_and_correlation_trace_are_structured() -> None:
    client.post("/api/scenario/reset")
    client.post("/api/scenario/advance", json={"seconds": 5})
    health = client.get("/api/health").json()
    trace = client.get("/api/observability").json()

    assert health["status"] == "healthy"
    assert set(health["components"].values()) <= {"healthy", "degraded"}
    assert health["metrics"]["event_count"] == 2
    assert trace["correlation_id"] == health["correlation_id"]
    assert len(trace["trace"]) == 2
    for index, log in enumerate(trace["trace"], start=1):
        assert log["sequence"] == index
        assert log["correlation_id"] == trace["correlation_id"]
        assert {"timestamp", "level", "service", "event_type", "event_hash"} <= set(log)


def test_ai_adapter_uses_fixture_for_offline_malformed_timeout_and_prohibited_output() -> None:
    context = {"confidence": 36, "contributors": ["Spectrum", "Logistics", "Network"]}

    class Malformed:
        async def analyze(self, _: dict) -> dict:
            return {"summary": "too short"}

    class Prohibited:
        async def analyze(self, _: dict) -> dict:
            return {
                "summary": "Synthetic evidence needs review.",
                "contributors": ["Spectrum"],
                "uncertainty": "The fixture remains bounded and non-authoritative.",
                "recommendation": "Select a target for a strike.",
                "mode": "provider",
            }

    class Timeout:
        async def analyze(self, _: dict) -> dict:
            await asyncio.sleep(0.02)
            return {}

    for provider, timeout in ((None, 0.01), (Malformed(), 0.01), (Prohibited(), 0.01), (Timeout(), 0.001)):
        output = asyncio.run(
            ProviderNeutralAdapter(provider, timeout_seconds=timeout, retries=1).analyze(context)
        )
        assert output.mode == "fixture"
        assert output.contributors == context["contributors"]

    response = client.get("/api/analysis/summary")
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"


def test_performance_measurement_records_event_and_reset_latency() -> None:
    from scripts.measure_perf import measure

    results = measure()
    assert results["samples_event_to_ui"] == 40
    assert results["samples_reset"] == 20
    assert results["event_to_ui_p95_ms"] < 500
    assert results["reset_p95_ms"] < 500


def test_asset_registry_is_versioned_fictional_and_connected() -> None:
    response = client.get("/api/scenario/definition")
    assert response.status_code == 200
    definition = response.json()
    nodes = definition["nodes"]
    node_ids = {node["id"] for node in nodes}

    assert definition["fixture_version"] == "1.0.0"
    assert definition["seed"] == 4107
    assert len(definition["branch_points"]) == 2
    assert 12 <= len(nodes) <= 20
    assert len(node_ids) == len(nodes)
    assert sum(node["is_coordinator"] for node in nodes) == 1
    assert definition["map"]["overlay_coordinates"] == "fictional-generalized-training-only"
    assert "no real asset locations" in definition["map"]["provenance"].lower()

    for node in nodes:
        assert node["capabilities"]
        assert node["zone"]
        assert node["display"]["symbol"]
        assert 46 <= node["latitude"] <= 52
        assert 24 <= node["longitude"] <= 37
        assert set(node["links"]) <= node_ids
        for target_id in node["links"]:
            target = next(item for item in nodes if item["id"] == target_id)
            assert node["id"] in target["links"]

    fixture_text = str(definition).lower()
    for prohibited_term in ("weapon", "targeting", "missile", "rafale", "f-16"):
        assert prohibited_term not in fixture_text


def _run_golden_path() -> dict:
    client.post("/api/scenario/reset")
    client.post("/api/scenario/speed", json={"multiplier": 2})
    client.post("/api/scenario/advance", json={"seconds": 45})
    client.post("/api/tabletop/select", json={"branch_id": "bridge", "decision_point_id": "relay-loss"})
    client.post("/api/network/fail/northstar")
    client.post("/api/recovery/approve", json={"option_id": "route-atlas"})
    client.post("/api/recovery/execute")
    return client.post("/api/recovery/verify", json={"succeeded": True}).json()


def test_golden_path_replays_with_identical_event_hashes() -> None:
    definition = client.get("/api/scenario/definition").json()
    expected = definition["expected_end_state"]

    first = _run_golden_path()
    first_hashes = [event["event_hash"] for event in first["events"]]
    second = _run_golden_path()
    second_hashes = [event["event_hash"] for event in second["events"]]

    assert second_hashes == first_hashes
    assert len(second_hashes) == expected["event_count"]
    assert all(len(event_hash) == 64 for event_hash in second_hashes)
    assert second["scenario"]["time_ms"] == expected["scenario_time_ms"]
    assert second["scenario"]["speed"] == expected["speed"]
    assert second["prophet"]["state"] == expected["alert_state"]
    assert second["prophet"]["confidence"] == expected["threat_confidence"]
    assert second["mirror"]["selected_branch"] == expected["selected_branch"]
    assert second["network"]["coordinator"] == expected["coordinator"]
    assert second["network"]["availability"] == expected["network_availability"]
    assert second["phoenix"]["approved_option"] == expected["approved_recovery"]
    assert second["phoenix"]["workflow"]["state"] == expected["phoenix_state"]
    assert second["scenario"]["demo_phase"]["id"] == "workflow_restored"
    assert second["scenario"]["event_chain_head"] == second_hashes[-1]


def test_prophet_fixture_covers_noise_missing_data_onset_and_false_positive() -> None:
    first = client.get("/api/prophet/telemetry")
    second = client.get("/api/prophet/telemetry")
    assert first.status_code == 200
    assert second.json() == first.json()

    telemetry = first.json()
    samples = telemetry["samples"]
    labels = {sample["label"] for sample in samples}
    assert telemetry["scenario_id"] == "broken-signal-v1"
    assert telemetry["seed"] == 4107
    assert {"normal", "missing_data", "false_positive", "pattern_onset", "pre_event", "synthetic_event"} <= labels
    assert [sample["minute"] for sample in samples] == sorted(
        (sample["minute"] for sample in samples)
    )

    missing = next(sample for sample in samples if sample["label"] == "missing_data")
    assert missing["quality"] == "partial"
    assert any(missing[signal] is None for signal in ("spectrum", "logistics", "network"))

    false_positive = next(
        sample for sample in samples if sample["label"] == "false_positive"
    )
    baselines = {
        signal["id"]: signal["baseline_range"] for signal in telemetry["signals"]
    }
    excursions = [
        signal
        for signal in ("spectrum", "logistics", "network")
        if not baselines[signal][0] <= false_positive[signal] <= baselines[signal][1]
    ]
    assert excursions == ["spectrum"]
    assert false_positive["event_observed"] is False

    onset = next(sample for sample in samples if sample["label"] == "pattern_onset")
    assert onset["minute"] == telemetry["label_policy"]["pattern_onset_minute"] == -47
    assert sum(sample["event_observed"] for sample in samples) == 1

    summary = client.get("/api/scenario").json()["prophet"]["telemetry"]
    assert summary["sample_count"] == len(samples)
    assert summary["missing_data_samples"] == 1
    assert summary["false_positive_samples"] == 1
    assert summary["observed_events"] == 1


def test_prophet_snapshot_exposes_auditable_fixture_playback_rows() -> None:
    baseline = client.post("/api/scenario/reset").json()["prophet"]
    assert baseline["telemetry"]["simulation_minute"] == -90
    assert baseline["telemetry"]["current_sample"]["label"] == "normal"
    assert baseline["evidence"]["data_quality"] == "complete"
    assert baseline["telemetry"]["source"] == "deterministic-synthetic-generator"

    partial = client.post("/api/scenario/advance", json={"seconds": 40}).json()["prophet"]
    assert partial["telemetry"]["simulation_minute"] == -50
    assert partial["telemetry"]["current_sample"]["label"] == "missing_data"
    assert partial["telemetry"]["current_sample"]["logistics"] is None
    assert partial["evidence"]["data_quality"] == "partial"

    event = client.post("/api/scenario/advance", json={"seconds": 50}).json()["prophet"]
    assert event["telemetry"]["simulation_minute"] == 0
    assert event["telemetry"]["current_sample"]["event_observed"] is True


def test_prophet_scoring_calibration_thresholds_and_evidence_are_deterministic() -> None:
    client.post("/api/scenario/reset")
    baseline = client.get("/api/scenario").json()["prophet"]
    assert baseline["confidence"] == 36
    assert baseline["state"] == "nominal"
    assert baseline["evidence"]["confidence_interval"] == [22, 50]
    assert baseline["evidence"]["thresholds"] == {"watch": 55, "warning": 80}
    assert baseline["evidence"]["confirming_signal_count"] == 1
    assert "single-signal excursion" in baseline["evidence"]["false_positive_guardrail"]
    assert baseline["evidence"]["top_contributors"][0]["id"] == "spectrum"

    client.post("/api/scenario/speed", json={"multiplier": 2})
    warning = client.post("/api/scenario/advance", json={"seconds": 45}).json()["prophet"]
    assert warning["confidence"] == 81
    assert warning["state"] == "warning"
    assert warning["warning_window_minutes"] == 47
    assert warning["evidence"]["confidence_interval"] == [75, 87]
    assert warning["evidence"]["confirming_signal_count"] == 3
    assert warning["evidence"]["top_contributors"] == [
        {"id": "logistics", "label": "Utility service queue", "contribution": 39},
        {"id": "network", "label": "Emergency mesh traffic", "contribution": 39},
        {"id": "spectrum", "label": "Civil radio congestion", "contribution": 39},
    ]
