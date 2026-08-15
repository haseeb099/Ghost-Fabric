from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


@pytest.fixture()
def security_auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "AUTH_TOKENS",
        "viewer-token=viewer:DEMO-VIEWER,operator-token=operator:DEMO-OPERATOR",
    )
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("AUTH_API_KEYS", "api-viewer=viewer:API-VIEWER,api-operator=operator:API-OPERATOR")
    monkeypatch.setenv("AUTH_JWT_SECRET", "fixture-jwt-secret-at-least-32-bytes")
    monkeypatch.setenv("AUDIT_BACKEND", "memory")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from app.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_production_rejects_optional_auth_and_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="optional",
            auth_tokens="operator-token=operator:DEMO-OPERATOR",
            default_role="viewer",
        )

    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="required",
            auth_tokens="operator-token=operator:DEMO-OPERATOR",
            default_role="operator",
        )

    with pytest.raises(ValidationError):
        Settings(
            environment="development",
            auth_jwt_secret="too-short",
        )

    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_mode="required",
            default_role="viewer",
        )

    ok = Settings(
        environment="production",
        auth_mode="required",
        auth_tokens="operator-token=operator:DEMO-OPERATOR",
        default_role="viewer",
        auth_jwt_secret="fixture-jwt-secret-at-least-32-bytes",
    )
    assert ok.auth_mode == "required"
    get_settings.cache_clear()


def test_reject_dual_credential_channels(security_auth_env: None) -> None:
    from app.auth import resolve_principal
    from app.settings import get_settings
    from fastapi import HTTPException

    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        resolve_principal("Bearer operator-token", settings, "api-operator")
    assert exc.value.status_code == 401
    assert "not both" in str(exc.value.detail)


def test_action_policy_denies_viewer_for_operator_actions() -> None:
    from app.rbac import action_allowed

    assert action_allowed("query", "viewer")
    assert action_allowed("export_audit", "viewer")
    assert not action_allowed("mutate_scenario", "viewer")
    assert not action_allowed("approve_recovery", "viewer")
    assert not action_allowed("rollback_recovery", "viewer")
    assert not action_allowed("mesh_failover", "viewer")
    assert action_allowed("approve_recovery", "operator")


def test_auth_decisions_recorded_without_credentials(security_auth_env: None) -> None:
    from app.main import app, state

    client = TestClient(app)
    denied = client.post(
        "/api/v1/scenario/reset",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert denied.status_code == 403

    deny_events = [event for event in state.events if event.type == "auth.decision"]
    assert deny_events
    latest_deny = deny_events[-1].payload
    assert latest_deny["decision"] == "deny"
    assert latest_deny["action"] == "mutate_scenario"
    assert latest_deny["subject"] == "DEMO-VIEWER"
    serialized = str(latest_deny)
    assert "viewer-token" not in serialized
    assert "operator-token" not in serialized
    assert "api-viewer" not in serialized

    allowed = client.post(
        "/api/v1/phoenix/approve",
        headers={"Authorization": "Bearer operator-token", "X-Command-ID": "sec-approve-1"},
        json={"option_id": "missing-option"},
    )
    # Auth allow is recorded even when the business object is missing.
    assert allowed.status_code == 404
    allow_events = [
        event
        for event in state.events
        if event.type == "auth.decision" and event.payload.get("decision") == "allow"
    ]
    assert any(event.payload.get("action") == "approve_recovery" for event in allow_events)
    for event in allow_events:
        blob = str(event.payload)
        assert "operator-token" not in blob
        assert "Bearer" not in blob


def test_mesh_failover_action_requires_operator(security_auth_env: None) -> None:
    from app.main import app

    client = TestClient(app)
    denied = client.post(
        "/api/v1/mesh/failover",
        headers={"Authorization": "Bearer viewer-token"},
        json={"node_id": "ridge"},
    )
    assert denied.status_code == 403
    assert "mesh_failover" in denied.json()["detail"]

    # Ensure dual headers are rejected at the API boundary too.
    ambiguous = client.get(
        "/api/v1/scenario",
        headers={"Authorization": "Bearer viewer-token", "X-API-Key": "api-viewer"},
    )
    assert ambiguous.status_code == 401


def test_jwt_requires_claims_and_min_secret(security_auth_env: None) -> None:
    from app.auth import resolve_principal
    from app.settings import Settings
    from fastapi import HTTPException

    settings = Settings(
        auth_mode="required",
        auth_jwt_secret="fixture-jwt-secret-at-least-32-bytes",
    )
    missing_role = jwt.encode(
        {
            "sub": "JWT-USER",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        resolve_principal(f"Bearer {missing_role}", settings)

    valid = jwt.encode(
        {
            "sub": "JWT-OPERATOR",
            "role": "operator",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    principal = resolve_principal(f"Bearer {valid}", settings)
    assert principal.subject == "JWT-OPERATOR"
    assert principal.role == "operator"
    assert principal.authenticated is True
