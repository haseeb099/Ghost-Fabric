"""Timed demo rehearsal runner for GF-22 evidence.

Paces operator actions to docs/DEMO_RUNBOOK.md beat windows and asserts
API evidence at each checkpoint. Records three wall-clock takes.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "app" / "fixtures" / "broken-signal-v1.json"
OUT = ROOT / "app" / "fixtures" / "demo-rehearsal-results.json"


@dataclass
class BeatResult:
    name: str
    scheduled_start_s: float
    elapsed_s: float
    ok: bool
    detail: str


@dataclass
class RehearsalResult:
    take: int
    started_at: str
    elapsed_s: float
    fixture_sha256: str
    pass_under_120: bool
    beats: list[BeatResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def wait_until(deadline: float) -> None:
    remaining = deadline - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)


def main() -> None:
    fixture_sha = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    takes: list[RehearsalResult] = []

    with httpx.Client(base_url=API, timeout=10.0) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        assert health.json()["mode"] == "deterministic-fixture"

        for take in range(1, 4):
            client.post("/api/scenario/reset").raise_for_status()
            snap = client.get("/api/scenario").json()
            assert snap["scenario"]["sequence"] == 1
            assert snap["network"]["availability"] == 100
            assert snap["network"]["coordinator"] == "northstar"
            assert snap["events"][0]["sequence"] == 1

            t0 = time.perf_counter()
            started = time.strftime("%Y-%m-%dT%H:%M:%S")
            result = RehearsalResult(
                take=take,
                started_at=started,
                elapsed_s=0.0,
                fixture_sha256=fixture_sha,
                pass_under_120=False,
            )

            wait_until(t0 + 15)
            result.beats.append(
                BeatResult(
                    "baseline_safety",
                    0,
                    round(time.perf_counter() - t0, 2),
                    snap["scenario"]["classification"] == "FICTIONAL TRAINING SIMULATION",
                    f"classification={snap['scenario']['classification']}",
                )
            )

            wait_until(t0 + 32)
            metrics = snap["network"]["metrics"] or {}
            ok = bool(metrics) or len(snap["network"]["nodes"]) == 12
            result.beats.append(
                BeatResult(
                    "chameleon_graph",
                    15,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"nodes={len(snap['network']['nodes'])} metrics_keys={list(metrics)[:6]}",
                )
            )

            client.post("/api/scenario/speed", json={"multiplier": 4}).raise_for_status()
            client.post("/api/scenario/advance", json={"seconds": 45}).raise_for_status()
            wait_until(t0 + 48)
            snap = client.get("/api/scenario").json()
            evidence = snap["prophet"]["evidence"]
            ok = (
                evidence["thresholds"]["watch"] == 55
                and evidence["thresholds"]["warning"] == 80
                and isinstance(snap["prophet"]["confidence"], int)
            )
            result.beats.append(
                BeatResult(
                    "prophet_confidence",
                    32,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"confidence={snap['prophet']['confidence']} thresholds={evidence['thresholds']}",
                )
            )

            wait_until(t0 + 60)
            telemetry = client.get("/api/prophet/telemetry").json()
            samples = telemetry["samples"]
            has_fp = any(s.get("label") == "false_positive" for s in samples)
            has_partial = any(s.get("quality") == "partial" for s in samples)
            guard = evidence.get("false_positive_guardrail", "")
            ok = has_fp and has_partial and bool(guard)
            result.beats.append(
                BeatResult(
                    "false_positive_guardrail",
                    48,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"fp={has_fp} partial={has_partial} guardrail={bool(guard)}",
                )
            )

            client.post("/api/network/fail/northstar").raise_for_status()
            wait_until(t0 + 78)
            snap = client.get("/api/scenario").json()
            coordinator = snap["network"]["coordinator"]
            ok = coordinator is not None and coordinator != "northstar"
            result.beats.append(
                BeatResult(
                    "node_loss_handoff",
                    60,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"coordinator={coordinator}",
                )
            )

            wait_until(t0 + 96)
            options = snap["phoenix"]["options"]
            ok = len(options) > 0 and "availability" in snap["phoenix"]["planner"]["ranking"]
            result.beats.append(
                BeatResult(
                    "phoenix_ranking",
                    78,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"options={len(options)} recommended={options[0]['id'] if options else None}",
                )
            )

            option_id = options[0]["id"] if options else "route-atlas"
            client.post(
                "/api/recovery/approve",
                json={"option_id": option_id, "actor": "DEMO-COMMANDER"},
            ).raise_for_status()
            wait_until(t0 + 110)
            snap = client.get("/api/scenario").json()
            approved = any(e.get("type") == "recovery.approved" for e in snap["events"])
            restored = snap["phoenix"]["workflow_status"] == "restored"
            result.beats.append(
                BeatResult(
                    "human_approval",
                    96,
                    round(time.perf_counter() - t0, 2),
                    approved and restored,
                    f"approved={approved} status={snap['phoenix']['workflow_status']}",
                )
            )

            export = client.get("/api/audit/export")
            export.raise_for_status()
            body = export.json()
            fixture_meta = body.get("fixture") or {}
            ok = "export_hash" in body and (
                fixture_meta.get("id") == "broken-signal-v1" or body.get("fixture_id") == "broken-signal-v1"
            )
            wait_until(t0 + 120)
            result.beats.append(
                BeatResult(
                    "audit_export",
                    110,
                    round(time.perf_counter() - t0, 2),
                    ok,
                    f"export_hash={str(body.get('export_hash', ''))[:16]} events={len(body.get('events', []))}",
                )
            )

            result.elapsed_s = round(time.perf_counter() - t0, 2)
            result.pass_under_120 = result.elapsed_s <= 120.5 and all(b.ok for b in result.beats)
            if not all(b.ok for b in result.beats):
                failed = [b.name for b in result.beats if not b.ok]
                result.notes.append(f"Failed beats: {', '.join(failed)}")
            takes.append(result)
            print(json.dumps(asdict(result), indent=2))

    payload = {
        "schema_version": 1,
        "purpose": "gf-22-timed-demo-rehearsals",
        "method": "agent-paced-api-dry-run following DEMO_RUNBOOK beat windows",
        "fixture_sha256": fixture_sha,
        "takes": [asdict(t) for t in takes],
        "all_passed": all(t.pass_under_120 for t in takes),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("WROTE", OUT)
    print("ALL_PASSED", payload["all_passed"])


if __name__ == "__main__":
    main()
