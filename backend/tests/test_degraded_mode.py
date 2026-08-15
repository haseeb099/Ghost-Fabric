"""Contract checks for degraded-mode fallback behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analysis_endpoint_is_fixture_backed_without_live_provider() -> None:
    client.post("/api/scenario/reset")
    response = client.get("/api/analysis/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    assert "human approval" in body["recommendation"].lower()
    for term in ("target", "weapon", "strike", "kill"):
        assert term not in body["summary"].lower()
        assert term not in body["recommendation"].lower()


def test_backup_evidence_checksum_script_covers_core_fixtures() -> None:
    from scripts.checksum_backup_evidence import EVIDENCE, main, sha256

    assert all(path.exists() for path in EVIDENCE)
    main()
    checksum_path = EVIDENCE[0].parent / "backup-evidence-checksums.json"
    assert checksum_path.exists()
    payload = checksum_path.read_text(encoding="utf-8")
    assert "broken-signal-v1.json" in payload
    assert "DEMO_RUNBOOK.md" in payload
    assert sha256(EVIDENCE[0]) in payload
