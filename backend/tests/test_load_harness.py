"""Unit tests for the GF-52 developer load harness (no absolute latency gates)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_load_harness import (
    BASELINE_LABEL,
    RESULT_LABEL,
    LoadConfig,
    bucket_samples,
    command_id_for,
    ensure_allowed_target,
    is_loopback_url,
    percentile,
    render_svg_chart,
    run_load_harness,
    summarize_phase,
    write_artifacts,
    RequestSample,
)


def test_loopback_detection_and_non_local_rejection() -> None:
    assert is_loopback_url("http://127.0.0.1:8000")
    assert is_loopback_url("http://localhost:8000/api")
    ensure_allowed_target("http://127.0.0.1:8000")
    with pytest.raises(ValueError, match="non-local"):
        ensure_allowed_target("https://example.com")
    ensure_allowed_target("https://example.com", allow_non_local=True)


def test_config_requires_confirm_flag(tmp_path: Path) -> None:
    config = LoadConfig(
        base_url="http://127.0.0.1:8000",
        confirm_local_simulation=False,
        output_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="confirm-local-simulation"):
        config.validate()


def test_command_ids_are_deterministic_and_unique() -> None:
    first = [command_id_for(42, index) for index in range(5)]
    second = [command_id_for(42, index) for index in range(5)]
    assert first == second
    assert len(set(first)) == 5


def test_percentile_and_phase_summary() -> None:
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    samples = [
        RequestSample("read", "GET", "/api/v1/health", 200, 10.0, True, started_at=1.0),
        RequestSample("read", "GET", "/api/v1/health", 500, 20.0, False, started_at=1.1),
        RequestSample("read", "GET", "/api/v1/health", 200, 30.0, True, started_at=1.2),
    ]
    summary = summarize_phase("read", samples)
    assert summary.attempted == 3
    assert summary.errors == 1
    assert summary.error_rate == pytest.approx(1 / 3, rel=1e-3)
    assert summary.p50_ms == 20.0


def test_bucket_and_svg_output() -> None:
    samples = [
        RequestSample("read", "GET", "/api/v1/health", 200, 12.0, True, started_at=10.0),
        RequestSample("read", "GET", "/api/v1/health", 200, 18.0, True, started_at=10.4),
        RequestSample("mutation", "POST", "/api/v1/scenario/advance", 200, 22.0, True, started_at=11.1),
    ]
    buckets = bucket_samples(samples, bucket_seconds=1.0)
    assert len(buckets) >= 2
    svg = render_svg_chart(buckets)
    assert "developer-fixture-only" in svg
    assert "polyline" in svg


def test_run_load_harness_with_fake_requester(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_requester(*, method: str, url: str, headers: dict, json_body, timeout: float):
        calls.append(f"{method} {url}")
        assert "Authorization" in headers
        assert "X-Request-ID" in headers
        if method == "POST":
            assert "X-Command-ID" in headers
        return 200, 5.0, headers["X-Request-ID"], None

    config = LoadConfig(
        base_url="http://127.0.0.1:8000",
        confirm_local_simulation=True,
        output_dir=tmp_path,
        read_requests=4,
        mutation_advances=3,
        concurrency=2,
        seed=7,
        max_rate_per_second=100,
        include_mesh_failover_observation=True,
    )
    result = run_load_harness(config, requester=fake_requester)
    assert result.label == RESULT_LABEL
    assert result.baseline_label == BASELINE_LABEL
    assert "Not production capacity" in result.notice
    assert len(result.phases) == 2
    assert result.failover_observation is not None
    assert any("mesh/failover" in call for call in calls)
    assert any("scenario/reset" in call for call in calls)
    assert sum(1 for call in calls if "scenario/advance" in call) == 3

    paths = write_artifacts(result, tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["label"] == RESULT_LABEL
    assert paths["csv"].exists()
    assert "developer-fixture-only" in paths["svg"].read_text(encoding="utf-8")


def test_rate_cap_guard(tmp_path: Path) -> None:
    config = LoadConfig(
        base_url="http://127.0.0.1:8000",
        confirm_local_simulation=True,
        output_dir=tmp_path,
        max_rate_per_second=500,
    )
    with pytest.raises(ValueError, match="capped at 200"):
        config.validate()
