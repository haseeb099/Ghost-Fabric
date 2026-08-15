from __future__ import annotations

import os
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from copy import deepcopy

import jwt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "AUTH_TOKENS",
        "viewer-token=viewer:DEMO-VIEWER,operator-token=operator:DEMO-OPERATOR",
    )
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("AUTH_API_KEYS", "api-viewer=viewer:API-VIEWER")
    monkeypatch.setenv("AUTH_JWT_SECRET", "fixture-jwt-secret-at-least-32-bytes")
    monkeypatch.setenv("AUDIT_BACKEND", "memory")
    from app.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_viewer_cannot_mutate_when_auth_required(auth_env: None) -> None:
    from app.main import app

    client = TestClient(app)
    denied = client.post(
        "/api/v1/scenario/reset",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/v1/scenario/reset",
        headers={"Authorization": "Bearer operator-token", "X-Command-ID": "auth-reset-1"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["scenario"]["sequence"] >= 1

    snapshot = client.get(
        "/api/v1/scenario",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert snapshot.status_code == 200

    api_key_snapshot = client.get(
        "/api/v1/scenario",
        headers={"X-API-Key": "api-viewer"},
    )
    assert api_key_snapshot.status_code == 200

    encoded = jwt.encode(
        {
            "sub": "JWT-VIEWER",
            "role": "viewer",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "fixture-jwt-secret-at-least-32-bytes",
        algorithm="HS256",
    )
    jwt_snapshot = client.get(
        "/api/v1/scenario",
        headers={"Authorization": f"Bearer {encoded}"},
    )
    assert jwt_snapshot.status_code == 200


def test_api_key_and_jwt_authentication() -> None:
    from app.auth import resolve_principal
    from app.settings import Settings

    settings = Settings(
        auth_mode="required",
        auth_api_keys="api-operator=operator:API-OPERATOR",
        auth_jwt_secret="fixture-jwt-secret-at-least-32-bytes",
    )
    api_principal = resolve_principal(None, settings, "api-operator")
    assert api_principal.subject == "API-OPERATOR"
    assert api_principal.role == "operator"

    encoded = jwt.encode(
        {
            "sub": "JWT-VIEWER",
            "role": "viewer",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )
    jwt_principal = resolve_principal(f"Bearer {encoded}", settings)
    assert jwt_principal.subject == "JWT-VIEWER"
    assert jwt_principal.role == "viewer"


def test_memory_audit_store_survives_state_swap() -> None:
    from app.audit.memory import MemoryAuditStore
    from app.main import ScenarioState

    store = MemoryAuditStore()
    first = ScenarioState(audit_store=store)
    first.set_actor_context(type("P", (), {"subject": "DEMO-OPERATOR", "role": "operator"})())
    first._append_event("prophet", "scenario.advanced", "info", {"delta_seconds": 5})
    correlation_id = first.correlation_id
    exported_before = deepcopy(store.list_events(correlation_id))
    assert len(exported_before) >= 2

    second = ScenarioState(audit_store=store)
    # New state starts a new run; historical events remain queryable by correlation id.
    assert store.list_events(correlation_id) == exported_before
    assert second.correlation_id != correlation_id


def test_phoenix_workflow_and_outbox_restore_from_active_audit_snapshot() -> None:
    from app.audit.memory import MemoryAuditStore
    from app.main import ScenarioState

    store = MemoryAuditStore()
    first = ScenarioState(audit_store=store)
    first.set_actor_context(type("P", (), {"subject": "DEMO-OPERATOR", "role": "operator"})())
    first.record_phoenix_transition(first.phoenix_workflow.request_approval("route-atlas"))
    first.record_phoenix_transition(first.phoenix_workflow.approve("DEMO-OPERATOR", "operator"))
    first.record_phoenix_transition(first.phoenix_workflow.record_simulated_execution())
    first.record_phoenix_transition(first.phoenix_workflow.verify(succeeded=True))

    first.restore_from_active_run()

    assert first.phoenix_workflow.state.value == "restored"
    assert first.phoenix_workflow.approval_actor == "DEMO-OPERATOR"
    assert len(first.phoenix_outbox.snapshot()) == 4


def test_chameleon_bridge_persists_server_hashed_commit_evidence() -> None:
    from app.audit.memory import MemoryAuditStore
    from app.auth import Principal
    from app.chameleon_bridge import ChameleonTopologyCommit, ingest_committed_topology
    from app.main import ScenarioState

    store = MemoryAuditStore()
    state = ScenarioState(audit_store=store)
    evidence = ChameleonTopologyCommit(
        cluster_id="regional-pilot-a",
        raft_term=2,
        raft_index=7,
        correlation_id=state.correlation_id,
        payload_hash="a" * 64,
        audit_event_ref="evt_chameleon_requested_001",
    )
    event = ingest_committed_topology(
        state,
        principal=Principal("DEMO-OPERATOR", "operator", authenticated=True),
        evidence=evidence,
    )

    assert event.type == "chameleon.topology_revision_committed"
    assert event.source == "chameleon-control-plane"
    assert event.payload == evidence.model_dump()
    persisted = store.list_events(state.correlation_id)[-1]
    assert persisted["event_hash"] == event.event_hash
    assert persisted["actor"] == "DEMO-OPERATOR"
    assert persisted["role"] == "operator"


def test_chameleon_bridge_rejects_viewer_and_cross_run_evidence() -> None:
    from app.audit.memory import MemoryAuditStore
    from app.auth import Principal
    from app.chameleon_bridge import (
        ChameleonBridgeError,
        ChameleonTopologyCommit,
        ingest_committed_topology,
    )
    from app.main import ScenarioState

    state = ScenarioState(audit_store=MemoryAuditStore())
    evidence = ChameleonTopologyCommit(
        cluster_id="regional-pilot-a",
        raft_term=2,
        raft_index=7,
        correlation_id=state.correlation_id,
        payload_hash="b" * 64,
        audit_event_ref="evt_chameleon_requested_002",
    )
    with pytest.raises(ChameleonBridgeError, match="operator role"):
        ingest_committed_topology(
            state,
            principal=Principal("DEMO-VIEWER", "viewer", authenticated=True),
            evidence=evidence,
        )

    evidence.correlation_id = "other-run"
    with pytest.raises(ChameleonBridgeError, match="correlation ID"):
        ingest_committed_topology(
            state,
            principal=Principal("DEMO-OPERATOR", "operator", authenticated=True),
            evidence=evidence,
        )


def test_chameleon_commit_contract_forbids_recovery_shaped_data() -> None:
    from pydantic import ValidationError

    from app.chameleon_bridge import ChameleonTopologyCommit

    schema_path = Path(__file__).parents[2] / "contracts" / "chameleon-topology-commit.schema.json"
    contract = json.loads(schema_path.read_text(encoding="utf-8"))
    assert contract["additionalProperties"] is False
    assert "recovery_command" not in contract["properties"]

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ChameleonTopologyCommit(
            cluster_id="regional-pilot-a",
            raft_term=2,
            raft_index=7,
            correlation_id="run-1",
            payload_hash="c" * 64,
            audit_event_ref="evt_chameleon_requested_003",
            recovery_command="approve-route-atlas",
        )


@pytest.mark.skipif(
    os.getenv("GHOST_FABRIC_PG_TEST") != "1",
    reason="Set GHOST_FABRIC_PG_TEST=1 with a reachable DATABASE_URL to run Postgres checks",
)
def test_postgres_audit_restart_safe_export_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://ghost:ghost@localhost:5432/ghost_fabric",
    )
    monkeypatch.setenv("AUDIT_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTH_MODE", "optional")
    monkeypatch.delenv("AUTH_TOKENS", raising=False)
    from app.settings import get_settings

    get_settings.cache_clear()
    from app.audit.postgres import PostgresAuditStore
    from app.main import ScenarioState

    store = PostgresAuditStore(database_url)
    state = ScenarioState(audit_store=store)
    state.set_actor_context(type("P", (), {"subject": "DEMO-OPERATOR", "role": "operator"})())
    state.record_phoenix_transition(state.phoenix_workflow.request_approval("route-atlas"))
    state.record_phoenix_transition(state.phoenix_workflow.approve("DEMO-OPERATOR", "operator"))
    state.record_phoenix_transition(state.phoenix_workflow.record_simulated_execution())
    state.record_phoenix_transition(state.phoenix_workflow.verify(succeeded=True))
    state.remember_command("pg-idem-1", {"ok": True, "scenario": {"sequence": 1}})
    correlation_id = state.correlation_id
    events = store.list_events(correlation_id)
    assert events
    assert store.get_command("pg-idem-1") == {"ok": True, "scenario": {"sequence": 1}}

    restored = ScenarioState(audit_store=store)
    restored.restore_from_active_run()
    assert restored.correlation_id == correlation_id
    assert store.list_events(correlation_id)[0]["event_hash"] == events[0]["event_hash"]
    assert restored.cached_command("pg-idem-1") == {"ok": True, "scenario": {"sequence": 1}}
    assert restored.phoenix_workflow.state.value == "restored"
    assert len(restored.phoenix_outbox.snapshot()) == 4
    get_settings.cache_clear()
