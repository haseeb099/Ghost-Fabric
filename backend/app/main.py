from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.ai_adapter import ProviderNeutralAdapter
from app.audit import build_audit_store
from app.auth import Principal, require_action, require_operator, require_viewer
from app.chameleon_bridge import ChameleonTopologyCommit
from app.citizen_grid import CitizenGrid
from app.demo_phases import project_demo_phase
from app.metrics import refresh_runtime_gauges, render_metrics
from app.mirror_audit import append_mirror_events
from app.mirror_engine import MirrorEventLoop
from app.mirror_scenario import MirrorScenario, MirrorScenarioError, load_mirror_catalog
from app.phoenix_notifications import PhoenixNotificationOutbox
from app.phoenix_preapproved import preapproved_projection
from app.phoenix_workflow import PhoenixWorkflow, WorkflowState, WorkflowTransition, WorkflowTransitionError
from app.rate_limit import RateLimitMiddleware
from app.settings import get_settings
from app.structured_logging import RequestLoggingMiddleware, configure_structured_logging

class NodeDisplay(BaseModel):
    symbol: Literal["circle", "square", "triangle", "diamond", "hex"]
    accent: Literal["mint", "cyan", "blue", "amber"]
    priority: int = Field(ge=1, le=3)


class Node(BaseModel):
    id: str
    callsign: str
    role: str
    capabilities: list[str]
    zone: str
    display: NodeDisplay
    x: float
    y: float
    latitude: float
    longitude: float
    status: Literal["online", "degraded", "offline"] = "online"
    is_coordinator: bool = False
    latency_ms: int
    links: list[str]


class Signal(BaseModel):
    id: str
    label: str
    value: float
    unit: str
    trend: Literal["stable", "rising", "falling"]
    contribution: int


class RecoveryOption(BaseModel):
    id: str
    name: str
    route: list[str]
    availability: int
    reliability: int
    latency_seconds: int
    reversibility: Literal["high", "medium", "low"]
    rationale: str
    status: Literal["available", "recommended", "approved"] = "available"


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    correlation_id: str
    sequence: int
    scenario_time_ms: int
    wall_time: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str
    type: str
    severity: Literal["info", "warning", "critical", "success"]
    schema_version: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)
    event_hash: str


class MeshTopologyResponse(BaseModel):
    """Read-only deterministic mesh state; not an operational route command."""

    schema_version: int = 1
    correlation_id: str
    scenario_time_ms: int
    coordinator: str | None
    availability: int
    nodes: list[Node]
    metrics: dict[str, Any]
    notice: str = "Fixture-backed topology view only; no route execution authority."


class ProphetScoreResponse(BaseModel):
    """Read-only deterministic score from labeled synthetic fixture data."""

    schema_version: int = 1
    correlation_id: str
    scenario_time_ms: int
    confidence: int = Field(ge=0, le=100)
    state: Literal["nominal", "watch", "warning"]
    signals: list[Signal]
    mode: Literal["fixture"] = "fixture"
    notice: str = "Review-only synthetic score; it does not authorize action."


class ProphetExplanationResponse(BaseModel):
    """Schema-validated, non-authoritative explanation of a fixture score."""

    schema_version: int = 1
    correlation_id: str
    confidence: int = Field(ge=0, le=100)
    explanation: dict[str, Any]
    mode: Literal["fixture", "provider"] = "fixture"
    notice: str = "Explanation is review-only and cannot determine ground truth."


class PhoenixWorkflowResponse(BaseModel):
    """Read-only simulation workflow view; approval stays on its guarded route."""

    schema_version: int = 1
    correlation_id: str
    scenario_time_ms: int
    workflow_status: Literal["degraded", "restored", "failed", "in_progress"]
    approved_option: str | None
    options: list[RecoveryOption]
    workflow: dict[str, Any]
    notification_outbox: list[dict[str, Any]]
    approval_policy: dict[str, int]
    pre_approved: dict[str, Any]
    planner: dict[str, Any]
    notice: str = "Simulation workflow view only; explicit operator approval remains required."


class GoldenScenario(BaseModel):
    schema_version: int
    fixture_version: str
    id: str
    name: str
    classification: str
    seed: int
    map: dict[str, Any]
    branch_points: list[dict[str, Any]]
    canonical_actions: list[dict[str, Any]]
    expected_end_state: dict[str, Any]
    nodes: list[Node]


class TelemetrySignalDefinition(BaseModel):
    id: str
    label: str
    unit: str
    baseline_range: tuple[float, float]


class TelemetrySample(BaseModel):
    minute: int
    spectrum: float | None
    logistics: float | None
    network: float | None
    quality: Literal["complete", "partial"]
    label: Literal[
        "normal",
        "false_positive",
        "missing_data",
        "pattern_onset",
        "pre_event",
        "synthetic_event",
    ]
    event_observed: bool


class ProphetTelemetryFixture(BaseModel):
    schema_version: int
    fixture_version: str
    id: str
    scenario_id: str
    seed: int
    source: str
    description: str
    signals: list[TelemetrySignalDefinition]
    label_policy: dict[str, Any]
    samples: list[TelemetrySample]


class AdvanceCommand(BaseModel):
    seconds: int = Field(default=5, ge=1, le=60)


class ApprovalCommand(BaseModel):
    option_id: str
    actor: str | None = Field(default=None, min_length=2, max_length=60)


class VerifyCommand(BaseModel):
    succeeded: bool = True
    reason: str = Field(default="operator recorded simulation verification", min_length=4, max_length=240)


class RollbackCommand(BaseModel):
    reason: str = Field(default="operator requested simulated rollback", min_length=4, max_length=240)


class CitizenAttritionCommand(BaseModel):
    percent: int = Field(default=30, ge=1, le=90)


class MeshFailoverCommand(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)


class SpeedCommand(BaseModel):
    multiplier: Literal[1, 2, 4]


class BranchCommand(BaseModel):
    branch_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    decision_point_id: str | None = Field(default=None, min_length=1, max_length=64)
    actor: str | None = Field(default=None, min_length=2, max_length=60)
    scenario_id: str | None = Field(default=None, min_length=1, max_length=80)


class ErrorBody(BaseModel):
    code: str
    detail: str


class HealthResponse(BaseModel):
    status: str
    mode: str
    scenario: str
    connected_clients: int
    components: dict[str, str]
    metrics: dict[str, int]
    correlation_id: str
    time: str
    persistence: dict[str, Any]
    auth_mode: str
    api_version: str


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "broken-signal-v1.json"
GOLDEN_SCENARIO = GoldenScenario.model_validate_json(FIXTURE_PATH.read_text(encoding="utf-8"))
TELEMETRY_PATH = Path(__file__).parent / "fixtures" / "prophet-telemetry-v1.json"
PROPHET_TELEMETRY = ProphetTelemetryFixture.model_validate_json(
    TELEMETRY_PATH.read_text(encoding="utf-8")
)
FIXTURES_DIR = Path(__file__).parent / "fixtures"
MIRROR_CATALOG = load_mirror_catalog(FIXTURES_DIR)
ACTIVE_MIRROR_SCENARIO_ID = "mirror-fictional-network-partition-v1"
ACTIVE_MIRROR_SCENARIO = next(
    scenario for scenario in MIRROR_CATALOG if scenario.id == ACTIVE_MIRROR_SCENARIO_ID
)
analysis_adapter = ProviderNeutralAdapter()


def phoenix_workflow_status(workflow: PhoenixWorkflow) -> str:
    if workflow.state is WorkflowState.RESTORED:
        return "restored"
    if workflow.state is WorkflowState.FAILED:
        return "failed"
    if workflow.state is WorkflowState.ALERT:
        return "degraded"
    return "in_progress"


def mirror_snapshot_projection(
    scenario: MirrorScenario,
    loop: MirrorEventLoop,
    selected_branch: str | None,
) -> dict[str, Any]:
    """Project the active catalog decision point for console comparison."""
    if loop.completed:
        point = scenario.decision_points[-1]
        awaiting_choice = False
    else:
        point = loop.current_decision_point or scenario.decision_points[0]
        awaiting_choice = True
    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "classification": scenario.classification,
        "seed": scenario.seed,
        "decision_point_id": point.id,
        "condition": point.condition,
        "awaiting_choice": awaiting_choice,
        "completed": loop.completed,
        "branches": [
            {
                "id": branch.id,
                "label": branch.label,
                "outcome": branch.outcome,
                "assumption": branch.outcome,
            }
            for branch in point.branches
        ],
        "selected_branch": selected_branch,
        "trace_events": [
            {
                "sequence": event.sequence,
                "virtual_time_ms": event.virtual_time_ms,
                "event_type": event.event_type.value,
                "decision_point_id": event.decision_point_id,
                "branch_id": event.branch_id,
                "detail": event.detail,
                "mode": event.mode,
            }
            for event in loop.events
        ],
        "notice": scenario.notice,
    }


def prophet_telemetry_summary(scenario_time_ms: int = 0) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    for sample in PROPHET_TELEMETRY.samples:
        label_counts[sample.label] = label_counts.get(sample.label, 0) + 1
    # The 90-minute fixture is compressed into the first 90 scenario seconds.
    # Exposing the selected row makes the demonstration auditable and avoids
    # presenting generated values as if they were live observations.
    simulation_minute = min(0, -90 + scenario_time_ms // 1000)
    current_sample = min(
        PROPHET_TELEMETRY.samples,
        key=lambda sample: (abs(sample.minute - simulation_minute), sample.minute),
    )
    return {
        "fixture_id": PROPHET_TELEMETRY.id,
        "fixture_version": PROPHET_TELEMETRY.fixture_version,
        "source": PROPHET_TELEMETRY.source,
        "sample_count": len(PROPHET_TELEMETRY.samples),
        "pattern_onset_minute": PROPHET_TELEMETRY.label_policy["pattern_onset_minute"],
        "missing_data_samples": label_counts.get("missing_data", 0),
        "false_positive_samples": label_counts.get("false_positive", 0),
        "observed_events": sum(sample.event_observed for sample in PROPHET_TELEMETRY.samples),
        "label_counts": label_counts,
        "simulation_minute": simulation_minute,
        "current_sample": current_sample.model_dump(),
        "playback_note": "90 fixture minutes compressed into 90 scenario seconds; nearest labeled row shown.",
    }


def calibrated_prophet_confidence(signals: list[Signal]) -> int:
    """Map weighted synthetic evidence onto the frozen demonstration calibration."""
    baseline_evidence = 29
    baseline_confidence = 36
    full_evidence = 117
    warning_confidence = 81
    evidence = sum(signal.contribution for signal in signals)
    return max(
        0,
        min(
            94,
            round(
                baseline_confidence
                + (evidence - baseline_evidence)
                * (warning_confidence - baseline_confidence)
                / (full_evidence - baseline_evidence)
            ),
        ),
    )


def prophet_evidence(
    signals: list[Signal],
    confidence: int,
    data_quality: Literal["complete", "partial"] = "complete",
) -> dict[str, Any]:
    ordered = sorted(signals, key=lambda signal: (-signal.contribution, signal.id))
    confirming = [signal for signal in signals if signal.contribution >= 12]
    uncertainty = max(6, 18 - min(12, len(confirming) * 4))
    state = "warning" if confidence >= 80 else "watch" if confidence >= 55 else "nominal"
    return {
        "thresholds": {"watch": 55, "warning": 80},
        "confidence_interval": [
            max(0, confidence - uncertainty),
            min(100, confidence + uncertainty),
        ],
        "uncertainty_points": uncertainty,
        "confirming_signal_count": len(confirming),
        "top_contributors": [
            {
                "id": signal.id,
                "label": signal.label,
                "contribution": signal.contribution,
            }
            for signal in ordered[:3]
        ],
        "state": state,
        "data_quality": data_quality,
        "missing_data_policy": PROPHET_TELEMETRY.label_policy["missing_data_policy"],
        "false_positive_guardrail": (
            "Reviewed fixture case: a single-signal excursion remains below the "
            "multi-signal confirmation requirement and does not produce an alert."
        ),
        "calibration": {
            "fixture_id": PROPHET_TELEMETRY.id,
            "fixture_version": PROPHET_TELEMETRY.fixture_version,
            "method": "Frozen linear calibration over weighted labeled synthetic evidence",
        },
    }


def audit_export(correlation_id: str | None = None) -> dict[str, Any]:
    run_id = correlation_id or state.correlation_id
    stored = state.audit_store.list_events(run_id)
    records = stored if stored else [event.model_dump() for event in state.events if event.correlation_id == run_id]
    export = {
        "schema_version": 1,
        "export_type": "ghost-fabric-append-only-audit",
        "fixture": {
            "id": GOLDEN_SCENARIO.id,
            "version": GOLDEN_SCENARIO.fixture_version,
            "seed": GOLDEN_SCENARIO.seed,
        },
        "correlation_id": run_id,
        "event_count": len(records),
        "event_chain_head": records[-1]["event_hash"] if records else None,
        "records": records,
        "persistence": state.audit_store.backend,
    }
    hash_material = {
        key: value for key, value in export.items() if key not in {"persistence"}
    }
    canonical = json.dumps(hash_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**export, "export_hash": sha256(canonical).hexdigest()}


class ScenarioState:
    """Deterministic in-memory state for the fictional training scenario."""

    def __init__(self, audit_store: Any | None = None) -> None:
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()
        self.command_results: dict[str, dict[str, Any]] = {}
        self.structured_logs: list[dict[str, Any]] = []
        self.audit_store = audit_store or build_audit_store(get_settings())
        self.actor: str | None = None
        self.role: str | None = None
        self.reset()

    def set_actor_context(self, principal: Principal | None) -> None:
        if principal is None:
            self.actor = None
            self.role = None
            return
        self.actor = principal.subject
        self.role = principal.role

    def record_auth_decision(
        self,
        *,
        decision: Literal["allow", "deny"],
        action: str,
        reason: str,
        subject: str | None = None,
        role: str | None = None,
        authenticated: bool = False,
    ) -> EventEnvelope:
        """Append an auth.decision event without credential material."""
        return self._append_event(
            source="auth",
            event_type="auth.decision",
            severity="warning" if decision == "deny" else "info",
            payload={
                "decision": decision,
                "action": action,
                "reason": reason,
                "subject": subject or "anonymous",
                "role": role or "none",
                "authenticated": authenticated,
                "effect": "audit-only",
            },
        )

    def reset(self) -> None:
        self.correlation_id = f"run_{uuid4().hex[:10]}"
        self.sequence = 0
        self.scenario_time_ms = 0
        self.threat_confidence = 36
        self.speed = 1
        self.alert_state: Literal["nominal", "watch", "warning"] = "nominal"
        self.approved_recovery: str | None = None
        self.phoenix_workflow = PhoenixWorkflow(
            workflow_id=f"wf_{GOLDEN_SCENARIO.id}",
            correlation_id=self.correlation_id,
        )
        self.phoenix_outbox = PhoenixNotificationOutbox()
        self.selected_branch: str | None = None
        self.mirror_scenario = ACTIVE_MIRROR_SCENARIO
        self.mirror_loop = MirrorEventLoop(self.mirror_scenario)
        self.mirror_loop.present_next()
        self.mirror_audit_cursor = 0
        self.citizen_grid = CitizenGrid()
        self.nodes = deepcopy(GOLDEN_SCENARIO.nodes)
        self.signals = [
            Signal(id="spectrum", label="Civil radio congestion", value=38, unit="%", trend="stable", contribution=12),
            Signal(id="logistics", label="Utility service queue", value=44, unit="idx", trend="stable", contribution=9),
            Signal(id="network", label="Emergency mesh traffic", value=31, unit="idx", trend="stable", contribution=8),
        ]
        self.threat_confidence = calibrated_prophet_confidence(self.signals)
        self.recovery_options = self.rebuild_recovery_options()
        self.route_metrics = self.recompute_routes()
        self.events: list[EventEnvelope] = []
        self.history: dict[int, dict[str, Any]] = {}
        self.structured_logs = []
        bootstrap_snapshot = {
            "scenario": {
                "id": GOLDEN_SCENARIO.id,
                "fixture_version": GOLDEN_SCENARIO.fixture_version,
                "seed": GOLDEN_SCENARIO.seed,
                "correlation_id": self.correlation_id,
            }
        }
        self.audit_store.start_run(
            correlation_id=self.correlation_id,
            fixture_id=GOLDEN_SCENARIO.id,
            fixture_version=GOLDEN_SCENARIO.fixture_version,
            seed=GOLDEN_SCENARIO.seed,
            snapshot=bootstrap_snapshot,
        )
        self._append_event(
            "scenario-engine",
            "scenario.reset",
            "info",
            {
                "fixture": GOLDEN_SCENARIO.id,
                "fixture_version": GOLDEN_SCENARIO.fixture_version,
                "seed": GOLDEN_SCENARIO.seed,
            },
        )

    def rebuild_recovery_options(self) -> list[RecoveryOption]:
        """Rank reversible, non-lethal communications recovery workflows."""
        nodes = {node.id: node for node in self.nodes}
        candidates = [
            {
                "id": "route-atlas",
                "name": "Promote ATLAS-2 relay",
                "route": ["ridge", "echo", "atlas", "vantage"],
                "base_reliability": 94,
                "latency_seconds": 38,
                "reversibility": "high",
                "rationale": "Uses the recovery coordinator and existing signal-fusion relay.",
            },
            {
                "id": "route-harbor",
                "name": "Bridge through HARBOR",
                "route": ["ridge", "echo", "vantage", "harbor"],
                "base_reliability": 87,
                "latency_seconds": 52,
                "reversibility": "high",
                "rationale": "Preserves the civil-response message relay with a slower bridge.",
            },
            {
                "id": "route-basalt",
                "name": "Activate BASALT cache relay",
                "route": ["ridge", "basalt", "lumen", "atlas"],
                "base_reliability": 84,
                "latency_seconds": 44,
                "reversibility": "high",
                "rationale": "Uses cached synthetic telemetry when the primary coordination path is unavailable.",
            },
            {
                "id": "route-local",
                "name": "Operate local partitions",
                "route": ["ridge", "echo"],
                "base_reliability": 78,
                "latency_seconds": 14,
                "reversibility": "medium",
                "rationale": "Maintains local review workflows while full mesh recovery is unavailable.",
            },
        ]
        options: list[RecoveryOption] = []
        for candidate in candidates:
            route_nodes = [nodes[node_id] for node_id in candidate["route"]]
            online_nodes = [node for node in route_nodes if node.status != "offline"]
            availability = round(100 * len(online_nodes) / len(route_nodes))
            if availability < 100:
                continue
            latency_penalty = sum(node.latency_ms for node in route_nodes) // 20
            reliability = max(0, candidate["base_reliability"] - latency_penalty)
            options.append(
                RecoveryOption(
                    id=candidate["id"],
                    name=candidate["name"],
                    route=[node.callsign for node in route_nodes],
                    availability=availability,
                    reliability=reliability,
                    latency_seconds=candidate["latency_seconds"],
                    reversibility=candidate["reversibility"],
                    rationale=candidate["rationale"],
                )
            )
        options.sort(
            key=lambda option: (
                -option.availability,
                -option.reliability,
                option.latency_seconds,
                option.id,
            )
        )
        if options:
            options[0].status = "recommended"
        return options

    def _append_event(
        self,
        source: str,
        event_type: str,
        severity: Literal["info", "warning", "critical", "success"],
        payload: dict[str, Any],
    ) -> EventEnvelope:
        self.sequence += 1
        deterministic_payload = {
            key: value for key, value in payload.items() if key not in {"calculation_ms"}
        }
        hash_material = {
            "previous_hash": self.events[-1].event_hash if self.events else "GENESIS",
            "sequence": self.sequence,
            "scenario_time_ms": self.scenario_time_ms,
            "source": source,
            "type": event_type,
            "severity": severity,
            "schema_version": 1,
            "payload": deterministic_payload,
        }
        event_hash = sha256(
            json.dumps(hash_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        event = EventEnvelope(
            correlation_id=self.correlation_id,
            sequence=self.sequence,
            scenario_time_ms=self.scenario_time_ms,
            source=source,
            type=event_type,
            severity=severity,
            payload=payload,
            event_hash=event_hash,
        )
        self.events.append(event)
        self.structured_logs.append(
            {
                "timestamp": event.wall_time,
                "level": severity,
                "service": source,
                "event_type": event_type,
                "correlation_id": self.correlation_id,
                "sequence": event.sequence,
                "event_hash": event.event_hash,
            }
        )
        snapshot = deepcopy(self.snapshot())
        self.history[event.sequence] = snapshot
        previous_hash = hash_material["previous_hash"]
        self.audit_store.append_event(
            correlation_id=self.correlation_id,
            sequence=event.sequence,
            event=event.model_dump(),
            previous_hash=str(previous_hash),
            actor=self.actor,
            role=self.role,
            snapshot=snapshot,
        )
        return event

    def record_chameleon_topology_commit(
        self, evidence: ChameleonTopologyCommit
    ) -> EventEnvelope:
        """Persist non-executable CHAMELEON commit evidence canonically.

        This is intentionally a local bridge method, not an external API route.
        A reviewed future process boundary must authenticate and validate its
        message before calling it through ``ingest_committed_topology``.
        """
        return self._append_event(
            source="chameleon-control-plane",
            event_type="chameleon.topology_revision_committed",
            severity="success",
            payload=evidence.model_dump(),
        )

    def replay_snapshot(self, sequence: int) -> dict[str, Any]:
        """Return an immutable checkpoint for an event in the active scenario run."""
        checkpoint = self.history.get(sequence)
        if checkpoint is None:
            raise KeyError(sequence)
        return deepcopy(checkpoint)

    def events_after(self, sequence: int) -> list[dict[str, Any]]:
        return [event.model_dump() for event in self.events if event.sequence > sequence]

    def cached_command(self, command_id: str | None) -> dict[str, Any] | None:
        if not command_id:
            return None
        result = self.command_results.get(command_id)
        if result:
            return deepcopy(result)
        stored = self.audit_store.get_command(command_id)
        if stored:
            self.command_results[command_id] = deepcopy(stored)
            return deepcopy(stored)
        return None

    def remember_command(self, command_id: str | None, result: dict[str, Any]) -> None:
        if not command_id:
            return
        if len(self.command_results) >= 256:
            self.command_results.pop(next(iter(self.command_results)))
        self.command_results[command_id] = deepcopy(result)
        self.audit_store.save_command(
            command_id=command_id,
            correlation_id=self.correlation_id,
            result=result,
        )

    def restore_from_active_run(self) -> bool:
        """Reload the latest active durable run into memory when available."""
        active = self.audit_store.get_active_run()
        if not active or not active.get("snapshot") or not active.get("events"):
            return False
        snapshot = active["snapshot"]
        self.correlation_id = active["correlation_id"]
        self.events = [EventEnvelope.model_validate(event) for event in active["events"]]
        self.sequence = self.events[-1].sequence if self.events else 0
        self.scenario_time_ms = snapshot["scenario"]["time_ms"]
        self.speed = snapshot["scenario"]["speed"]
        self.threat_confidence = snapshot["prophet"]["confidence"]
        self.alert_state = snapshot["prophet"]["state"]
        self.approved_recovery = snapshot["phoenix"]["approved_option"]
        workflow_snapshot = snapshot["phoenix"].get("workflow")
        if workflow_snapshot:
            self.phoenix_workflow = PhoenixWorkflow.from_dict(workflow_snapshot)
        else:
            self.phoenix_workflow = PhoenixWorkflow(
                workflow_id=f"wf_{GOLDEN_SCENARIO.id}",
                correlation_id=self.correlation_id,
            )
        self.phoenix_outbox = PhoenixNotificationOutbox()
        self.phoenix_outbox.restore(snapshot["phoenix"].get("notification_outbox", []))
        self.selected_branch = snapshot["mirror"].get("selected_branch")
        mirror_meta = snapshot["mirror"]
        scenario_id = mirror_meta.get("scenario_id", ACTIVE_MIRROR_SCENARIO_ID)
        self.mirror_scenario = next(
            (item for item in MIRROR_CATALOG if item.id == scenario_id),
            ACTIVE_MIRROR_SCENARIO,
        )
        self.mirror_loop = MirrorEventLoop(self.mirror_scenario)
        selections: dict[str, str] = {}
        for item in mirror_meta.get("trace_events", []):
            if item.get("event_type") == "branch.recorded" and item.get("decision_point_id") and item.get("branch_id"):
                selections[str(item["decision_point_id"])] = str(item["branch_id"])
        if selections:
            try:
                self.mirror_loop.run(selections)
            except MirrorScenarioError:
                self.mirror_loop = MirrorEventLoop(self.mirror_scenario)
                self.mirror_loop.present_next()
        elif not self.mirror_loop.completed:
            self.mirror_loop.present_next()
        self.mirror_audit_cursor = len(self.mirror_loop.events)
        citizen_snapshot = snapshot.get("citizen_state")
        self.citizen_grid = (
            CitizenGrid.from_dict(citizen_snapshot) if citizen_snapshot else CitizenGrid()
        )
        self.nodes = [Node.model_validate(node) for node in snapshot["network"]["nodes"]]
        self.signals = [Signal.model_validate(signal) for signal in snapshot["prophet"]["signals"]]
        self.recovery_options = [
            RecoveryOption.model_validate(option) for option in snapshot["phoenix"]["options"]
        ]
        self.route_metrics = deepcopy(snapshot["network"]["metrics"])
        self.history = {event.sequence: deepcopy(snapshot) for event in self.events}
        # Rebuild checkpoints from stored events by keeping the final snapshot for the head.
        if self.events:
            self.history[self.events[-1].sequence] = deepcopy(snapshot)
        self.structured_logs = [
            {
                "timestamp": event.wall_time,
                "level": event.severity,
                "service": event.source,
                "event_type": event.type,
                "correlation_id": event.correlation_id,
                "sequence": event.sequence,
                "event_hash": event.event_hash,
            }
            for event in self.events
        ]
        return True

    def recompute_routes(self) -> dict[str, Any]:
        """Compute connected components and shortest paths over available links."""
        started = perf_counter()
        available = {node.id: node for node in self.nodes if node.status != "offline"}
        adjacency = {node_id: set() for node_id in available}
        active_links: set[tuple[str, str]] = set()
        unavailable_links: set[tuple[str, str]] = set()

        for node in self.nodes:
            for target_id in node.links:
                edge = tuple(sorted((node.id, target_id)))
                target = next((item for item in self.nodes if item.id == target_id), None)
                if not target:
                    continue
                if node.id in available and target_id in available:
                    active_links.add(edge)
                    adjacency[node.id].add(target_id)
                    adjacency[target_id].add(node.id)
                else:
                    unavailable_links.add(edge)

        components: list[list[str]] = []
        unseen = set(adjacency)
        while unseen:
            root = min(unseen)
            queue = [root]
            component: list[str] = []
            unseen.remove(root)
            while queue:
                current = queue.pop(0)
                component.append(current)
                for neighbor in sorted(adjacency[current]):
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        queue.append(neighbor)
            components.append(sorted(component))

        coordinator = next((node.id for node in self.nodes if node.is_coordinator and node.id in available), None)
        routes: dict[str, list[str]] = {}
        if coordinator:
            for start_id in sorted(available):
                if start_id == coordinator:
                    routes[start_id] = [start_id]
                    continue
                queue: list[list[str]] = [[start_id]]
                visited = {start_id}
                while queue:
                    path = queue.pop(0)
                    current = path[-1]
                    if current == coordinator:
                        routes[start_id] = path
                        break
                    for neighbor in sorted(adjacency[current]):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append([*path, neighbor])

        reachable = len(routes)
        return {
            "connected_components": len(components),
            "components": components,
            "active_links": len(active_links),
            "unavailable_links": [list(edge) for edge in sorted(unavailable_links)],
            "coordinator_reachable_nodes": reachable,
            "alternate_routes": sum(1 for path in routes.values() if len(path) > 2),
            "routes": routes,
            "calculation_ms": round((perf_counter() - started) * 1000, 3),
        }

    def flush_mirror_audit(self) -> list[EventEnvelope]:
        """Persist newly emitted fixture-only MIRROR loop events canonically."""
        pending = self.mirror_loop.events[self.mirror_audit_cursor :]
        self.mirror_audit_cursor = len(self.mirror_loop.events)
        return append_mirror_events(self, pending)  # type: ignore[arg-type]

    def record_phoenix_transition(self, transition: WorkflowTransition) -> EventEnvelope:
        """Persist every simulation workflow transition and its notification intent."""
        event_type = f"phoenix.workflow.{transition.to_state.value}"
        self.phoenix_outbox.queue(
            correlation_id=self.correlation_id,
            workflow_id=self.phoenix_workflow.workflow_id,
            event_type=event_type,
            actor=transition.actor,
        )
        event = self._append_event(
            "phoenix",
            event_type,
            "success" if transition.to_state is WorkflowState.RESTORED else "info",
            {
                "workflow_id": self.phoenix_workflow.workflow_id,
                "transition_sequence": transition.sequence,
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "actor": transition.actor,
                "reason": transition.reason,
                "effect": "simulation-only",
            },
        )
        return event

    def snapshot(self) -> dict[str, Any]:
        coordinator = next((node for node in self.nodes if node.is_coordinator), None)
        telemetry = prophet_telemetry_summary(self.scenario_time_ms)
        mirror = mirror_snapshot_projection(
            self.mirror_scenario,
            self.mirror_loop,
            self.selected_branch,
        )
        northstar = next((node for node in self.nodes if node.id == "northstar"), None)
        demo = project_demo_phase(
            alert_state=self.alert_state,
            coordinator_offline=bool(northstar and northstar.status == "offline"),
            selected_branch=self.selected_branch,
            phoenix_state=self.phoenix_workflow.state.value,
            awaiting_tabletop=bool(mirror["awaiting_choice"]),
        )
        return {
            "scenario": {
                "id": GOLDEN_SCENARIO.id,
                "name": GOLDEN_SCENARIO.name,
                "classification": GOLDEN_SCENARIO.classification,
                "fixture_version": GOLDEN_SCENARIO.fixture_version,
                "seed": GOLDEN_SCENARIO.seed,
                "correlation_id": self.correlation_id,
                "time_ms": self.scenario_time_ms,
                "sequence": self.sequence,
                "speed": self.speed,
                "event_chain_head": self.events[-1].event_hash if self.events else None,
                "demo_phase": demo,
            },
            "network": {
                "nodes": [node.model_dump() for node in self.nodes],
                "coordinator": coordinator.id if coordinator else None,
                "availability": round(100 * sum(node.status != "offline" for node in self.nodes) / len(self.nodes)),
                "metrics": deepcopy(self.route_metrics),
            },
            "prophet": {
                "confidence": self.threat_confidence,
                "state": self.alert_state,
                "signals": [signal.model_dump() for signal in self.signals],
                "warning_window_minutes": 47 if self.alert_state == "warning" else None,
                "method": "Deterministic scoring over labeled synthetic fixture",
                "telemetry": telemetry,
                "evidence": prophet_evidence(
                    self.signals,
                    self.threat_confidence,
                    telemetry["current_sample"]["quality"],
                ),
                "countdown": {
                    "label": "synthetic-virtual-time",
                    "pattern_onset_minute": PROPHET_TELEMETRY.label_policy["pattern_onset_minute"],
                    "simulation_minute": telemetry["simulation_minute"],
                    "minutes_to_synthetic_event": max(0, -telemetry["simulation_minute"])
                    if telemetry["simulation_minute"] < 0
                    else 0,
                    "notice": "Virtual-time fixture countdown only; not an operational launch clock.",
                },
            },
            "mirror": mirror,
            "citizen": self.citizen_grid.projection(),
            "citizen_state": self.citizen_grid.to_dict(),
            "phoenix": {
                "workflow_status": phoenix_workflow_status(self.phoenix_workflow),
                "approved_option": self.approved_recovery,
                "options": [option.model_dump() for option in self.recovery_options],
                "workflow": self.phoenix_workflow.to_dict(),
                "notification_outbox": self.phoenix_outbox.snapshot(),
                "approval_policy": {"operator": 1},
                "pre_approved": preapproved_projection(),
                "planner": {
                    "available_options": len(self.recovery_options),
                    "ranking": [
                        "availability",
                        "reliability",
                        "latency",
                        "reversibility",
                    ],
                    "notice": "Non-lethal simulated workflow recovery only; human approval required.",
                },
            },
            "events": [event.model_dump() for event in self.events[-12:]],
        }


settings = get_settings()
state = ScenarioState(audit_store=build_audit_store(settings))
if settings.restore_active_run and settings.audit_backend == "postgres":
    state.restore_from_active_run()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Synthetic, human-controlled resilience demonstration with durable audit foundation.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, limit=settings.rate_limit_per_second)
configure_structured_logging(level=settings.log_level, json_logs=settings.log_json)
app.add_middleware(
    RequestLoggingMiddleware,
    get_correlation_id=lambda: state.correlation_id,
)
api_v1 = APIRouter(prefix=settings.api_prefix)


@app.exception_handler(HTTPException)
async def structured_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    codes = {
        401: "authentication_required",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        429: "rate_limit_exceeded",
    }
    # Authentication failures may occur before require_action; record them once.
    if exc.status_code == 401 and not getattr(request.state, "auth_decision_recorded", False):
        try:
            state.record_auth_decision(
                decision="deny",
                action="authenticate",
                reason=str(exc.detail),
                subject="anonymous",
                role="none",
                authenticated=False,
            )
            request.state.auth_decision_recorded = True
        except Exception:
            pass
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": codes.get(exc.status_code, "request_failed"),
            "detail": str(exc.detail),
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def structured_validation_error(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "detail": "Request validation failed",
        },
    )


async def broadcast(event: EventEnvelope) -> None:
    disconnected: list[WebSocket] = []
    for client in state.clients:
        try:
            await client.send_json({"kind": "event", "event": event.model_dump(), "snapshot": state.snapshot()})
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        state.clients.discard(client)


async def health() -> dict[str, Any]:
    persistence = state.audit_store.health()
    refresh_runtime_gauges(
        audit_healthy=persistence.get("status") == "healthy",
        audit_backend=str(persistence.get("backend", state.audit_store.backend)),
        event_count=len(state.events),
        connected_clients=len(state.clients),
    )
    return {
        "status": "healthy" if persistence.get("status") == "healthy" else "degraded",
        "mode": "deterministic-fixture",
        "scenario": "broken-signal-v1",
        "connected_clients": len(state.clients),
        "components": {
            "scenario_engine": "healthy",
            "event_stream": "healthy",
            "fixture_store": "healthy",
            "recovery_planner": "healthy" if state.recovery_options else "degraded",
            "audit_store": persistence.get("status", "unknown"),
        },
        "metrics": {
            "event_count": len(state.events),
            "checkpoint_count": len(state.history),
            "structured_log_count": len(state.structured_logs),
        },
        "correlation_id": state.correlation_id,
        "time": datetime.now(UTC).isoformat(),
        "persistence": persistence,
        "auth_mode": settings.auth_mode,
        "api_version": settings.app_version,
    }


async def prometheus_metrics() -> Response:
    """Public Prometheus exposition; process telemetry only, not an audit export."""
    persistence = state.audit_store.health()
    refresh_runtime_gauges(
        audit_healthy=persistence.get("status") == "healthy",
        audit_backend=str(persistence.get("backend", state.audit_store.backend)),
        event_count=len(state.events),
        connected_clients=len(state.clients),
    )
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


async def get_scenario(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    return state.snapshot()


async def get_scenario_definition(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    return GOLDEN_SCENARIO.model_dump()


async def get_prophet_telemetry(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    return PROPHET_TELEMETRY.model_dump()


async def get_prophet_scores(
    _principal: Principal = Depends(require_viewer),
) -> ProphetScoreResponse:
    return ProphetScoreResponse(
        correlation_id=state.correlation_id,
        scenario_time_ms=state.scenario_time_ms,
        confidence=state.threat_confidence,
        state=state.alert_state,
        signals=state.signals,
    )


async def get_prophet_explanation(
    _principal: Principal = Depends(require_viewer),
) -> ProphetExplanationResponse:
    explanation = await analysis_summary(_principal)
    return ProphetExplanationResponse(
        correlation_id=state.correlation_id,
        confidence=state.threat_confidence,
        explanation=explanation,
        mode=explanation["mode"],
    )


async def get_phoenix_workflows(
    _principal: Principal = Depends(require_viewer),
) -> PhoenixWorkflowResponse:
    snapshot = state.snapshot()
    phoenix = snapshot["phoenix"]
    scenario = snapshot["scenario"]
    return PhoenixWorkflowResponse(
        correlation_id=scenario["correlation_id"],
        scenario_time_ms=scenario["time_ms"],
        workflow_status=phoenix["workflow_status"],
        approved_option=phoenix["approved_option"],
        options=[RecoveryOption.model_validate(option) for option in phoenix["options"]],
        workflow=phoenix["workflow"],
        notification_outbox=phoenix["notification_outbox"],
        approval_policy=phoenix["approval_policy"],
        pre_approved=phoenix["pre_approved"],
        planner=phoenix["planner"],
    )


async def get_mesh_topology(
    _principal: Principal = Depends(require_viewer),
) -> MeshTopologyResponse:
    snapshot = state.snapshot()
    network = snapshot["network"]
    scenario = snapshot["scenario"]
    return MeshTopologyResponse(
        correlation_id=scenario["correlation_id"],
        scenario_time_ms=scenario["time_ms"],
        coordinator=network["coordinator"],
        availability=network["availability"],
        nodes=[Node.model_validate(node) for node in network["nodes"]],
        metrics=network["metrics"],
    )


async def export_audit(_principal: Principal = Depends(require_action("export_audit"))) -> dict[str, Any]:
    return audit_export()


async def observability(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    return {
        "correlation_id": state.correlation_id,
        "metrics": {
            "event_count": len(state.events),
            "checkpoint_count": len(state.history),
            "connected_clients": len(state.clients),
        },
        "trace": deepcopy(state.structured_logs[-50:]),
        "persistence": state.audit_store.health(),
    }


async def analysis_summary(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    """Return a schema-validated, non-authoritative explanation only."""
    output = await analysis_adapter.analyze(
        {
            "confidence": state.threat_confidence,
            "contributors": [
                item.label
                for item in sorted(
                    state.signals, key=lambda signal: (-signal.contribution, signal.id)
                )
            ],
        }
    )
    return output.model_dump()


async def replay_scenario(
    sequence: int,
    _principal: Principal = Depends(require_viewer),
) -> dict[str, Any]:
    try:
        return state.replay_snapshot(sequence)
    except KeyError:
        raise HTTPException(status_code=404, detail="No checkpoint exists for that event sequence") from None


async def reset_scenario(
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        state.reset()
        event = state.events[-1]
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def advance_scenario(
    command: AdvanceCommand,
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        elapsed_seconds = command.seconds * state.speed
        state.scenario_time_ms += elapsed_seconds * 1000
        prior_state = state.alert_state
        for index, signal in enumerate(state.signals):
            signal.value = min(98, signal.value + elapsed_seconds * (index + 1) * 0.7)
            signal.trend = "rising"
            signal.contribution = min(
                39,
                signal.contribution + (index + 2) * max(1, elapsed_seconds // 5),
            )
        state.threat_confidence = calibrated_prophet_confidence(state.signals)
        state.alert_state = "warning" if state.threat_confidence >= 80 else "watch" if state.threat_confidence >= 55 else "nominal"
        event_type = "forecast.threshold_crossed" if state.alert_state != prior_state else "scenario.advanced"
        severity: Literal["info", "warning", "critical", "success"] = "warning" if state.alert_state == "warning" else "info"
        event = state._append_event(
            "prophet",
            event_type,
            severity,
            {
                "confidence": state.threat_confidence,
                "state": state.alert_state,
                "delta_seconds": elapsed_seconds,
                "speed": state.speed,
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def set_scenario_speed(
    command: SpeedCommand,
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        previous = state.speed
        state.speed = command.multiplier
        event = state._append_event(
            "scenario-engine",
            "scenario.speed_changed",
            "info",
            {"from": previous, "to": state.speed},
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def select_tabletop_branch(
    command: BranchCommand,
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        if command.scenario_id and command.scenario_id != state.mirror_scenario.id:
            raise HTTPException(status_code=409, detail="Active MIRROR scenario does not match request")
        if state.mirror_loop.completed:
            raise HTTPException(status_code=409, detail="Tabletop fixture replay is already complete")
        point = state.mirror_loop.current_decision_point
        if point is None:
            raise HTTPException(status_code=409, detail="No active tabletop decision point")
        if command.decision_point_id and command.decision_point_id != point.id:
            raise HTTPException(status_code=409, detail="Decision point does not match the active fixture cursor")
        if command.branch_id not in {branch.id for branch in point.branches}:
            raise HTTPException(status_code=404, detail="Unknown tabletop branch for the active decision point")
        presented = any(
            event.decision_point_id == point.id and event.event_type.value == "decision.presented"
            for event in state.mirror_loop.events
        )
        try:
            if not presented:
                state.mirror_loop.present_next()
            state.mirror_loop.select_branch(command.branch_id)
            if not state.mirror_loop.completed and state.mirror_loop.current_decision_point is not None:
                next_presented = any(
                    event.decision_point_id == state.mirror_loop.current_decision_point.id
                    and event.event_type.value == "decision.presented"
                    for event in state.mirror_loop.events
                )
                if not next_presented:
                    state.mirror_loop.present_next()
        except MirrorScenarioError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        state.selected_branch = command.branch_id
        events = state.flush_mirror_audit()
        event = events[-1]
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def get_mirror_catalog(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "active_scenario_id": ACTIVE_MIRROR_SCENARIO_ID,
        "notice": "Approved fixture-only tabletop catalog; no executable actions.",
        "scenarios": [
            {
                "id": scenario.id,
                "name": scenario.name,
                "classification": scenario.classification,
                "seed": scenario.seed,
                "decision_point_count": len(scenario.decision_points),
                "notice": scenario.notice,
            }
            for scenario in MIRROR_CATALOG
        ],
    }


async def get_mirror_scenario(
    scenario_id: str,
    _principal: Principal = Depends(require_viewer),
) -> dict[str, Any]:
    scenario = next((item for item in MIRROR_CATALOG if item.id == scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=404, detail="MIRROR scenario not found")
    return {
        "schema_version": 1,
        "scenario": scenario.model_dump(),
        "notice": "Fixture projection only; human branch selection required for replay.",
    }


async def fail_node(
    node_id: str,
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        node = next((item for item in state.nodes if item.id == node_id), None)
        if node is None:
            raise HTTPException(status_code=404, detail="Simulation node not found")
        if node.status == "offline":
            result = state.snapshot()
            state.remember_command(x_command_id, result)
            return result
        was_coordinator = node.is_coordinator
        node.status = "offline"
        node.is_coordinator = False
        state.scenario_time_ms += 4_000
        state.route_metrics = state.recompute_routes()
        event = state._append_event(
            "chameleon",
            "node.failed",
            "critical",
            {"node_id": node.id, "callsign": node.callsign, "was_coordinator": was_coordinator},
        )
        if was_coordinator:
            replacement = next((item for item in state.nodes if item.id == "atlas" and item.status == "online"), None)
            if replacement:
                replacement.is_coordinator = True
                replacement.status = "degraded"
                state.route_metrics = state.recompute_routes()
                state._append_event(
                    "chameleon",
                    "coordinator.handoff",
                    "success",
                    {"from": node.callsign, "to": replacement.callsign, "route_latency_ms": 63},
                )
        state.route_metrics = state.recompute_routes()
        route_severity: Literal["info", "warning", "critical", "success"] = (
            "warning" if state.route_metrics["connected_components"] > 1 else "success"
        )
        event = state._append_event(
            "chameleon",
            "mesh.routes_recomputed",
            route_severity,
            {
                "connected_components": state.route_metrics["connected_components"],
                "active_links": state.route_metrics["active_links"],
                "alternate_routes": state.route_metrics["alternate_routes"],
                "coordinator_reachable_nodes": state.route_metrics["coordinator_reachable_nodes"],
                "calculation_ms": state.route_metrics["calculation_ms"],
            },
        )
        state.recovery_options = state.rebuild_recovery_options()
        event = state._append_event(
            "phoenix",
            "recovery.options_recomputed",
            "success" if state.recovery_options else "warning",
            {
                "available_options": len(state.recovery_options),
                "recommended_option": state.recovery_options[0].id
                if state.recovery_options
                else None,
                "effect": "review-only; explicit human approval required",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def approve_recovery(
    command: ApprovalCommand,
    principal: Principal = Depends(require_action("approve_recovery")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        option = next((item for item in state.recovery_options if item.id == command.option_id), None)
        if option is None:
            raise HTTPException(status_code=404, detail="Recovery option not found")
        try:
            if state.phoenix_workflow.state is WorkflowState.ALERT:
                state.record_phoenix_transition(
                    state.phoenix_workflow.request_approval(option.id, actor="system")
                )
            for item in state.recovery_options:
                item.status = "available"
            option.status = "approved"
            state.approved_recovery = option.id
            event = state.record_phoenix_transition(
                state.phoenix_workflow.approve(principal.subject, principal.role)
            )
        except WorkflowTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def execute_recovery(
    principal: Principal = Depends(require_action("approve_recovery")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        option = next(
            (item for item in state.recovery_options if item.id == state.approved_recovery),
            None,
        )
        try:
            if option is not None:
                state.scenario_time_ms += option.latency_seconds * 1000
            event = state.record_phoenix_transition(
                state.phoenix_workflow.record_simulated_execution(actor=principal.subject)
            )
        except WorkflowTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def verify_recovery(
    command: VerifyCommand,
    principal: Principal = Depends(require_action("approve_recovery")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        try:
            event = state.record_phoenix_transition(
                state.phoenix_workflow.verify(succeeded=command.succeeded, actor=principal.subject)
            )
            if not command.succeeded:
                event = state.record_phoenix_transition(
                    state.phoenix_workflow.complete_rollback(actor=principal.subject)
                )
                state.approved_recovery = None
                for option in state.recovery_options:
                    option.status = "available"
                state._append_event(
                    "phoenix",
                    "phoenix.rollback_completed",
                    "warning",
                    {
                        "reason": command.reason,
                        "workflow_id": state.phoenix_workflow.workflow_id,
                        "effect": "simulation-only",
                    },
                )
        except WorkflowTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def rollback_recovery(
    command: RollbackCommand,
    principal: Principal = Depends(require_action("rollback_recovery")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        try:
            if state.phoenix_workflow.state is WorkflowState.RESTORED:
                state.record_phoenix_transition(
                    state.phoenix_workflow.request_rollback(principal.subject)
                )
            elif state.phoenix_workflow.state is not WorkflowState.ROLLBACK:
                raise HTTPException(
                    status_code=409,
                    detail="No restored or rollback-pending simulated workflow is available",
                )
            event = state.record_phoenix_transition(
                state.phoenix_workflow.complete_rollback(principal.subject)
            )
        except WorkflowTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        state.approved_recovery = None
        for option in state.recovery_options:
            option.status = "available"
        state._append_event(
            "phoenix",
            "phoenix.rollback_completed",
            "success",
            {
                "reason": command.reason,
                "workflow_id": state.phoenix_workflow.workflow_id,
                "effect": "simulation-only",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def get_citizen_grid(_principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    """Read-only aggregate sensor projection; no device or location data."""
    return state.citizen_grid.projection()


async def register_citizen_detection(
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        outcome = state.citizen_grid.register_detection()
        if outcome["district"] is None:
            raise HTTPException(status_code=409, detail="All synthetic districts already corroborate")
        state.scenario_time_ms += 2_000
        severity: Literal["info", "warning", "critical", "success"] = (
            "warning" if outcome["state"] == "confirmed" else "info"
        )
        event = state._append_event(
            "citizen-grid",
            "citizen.detection_corroborated",
            severity,
            {
                "district": outcome["district"],
                "confirming_districts": outcome["confirming_districts"],
                "confidence": outcome["confidence"],
                "state": outcome["state"],
                "effect": "review-only; human advisory approval required",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def apply_citizen_attrition(
    command: CitizenAttritionCommand,
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        outcome = state.citizen_grid.apply_attrition(command.percent)
        event = state._append_event(
            "citizen-grid",
            "citizen.sensor_attrition",
            "warning",
            {
                "requested_percent": command.percent,
                "removed_sensors": outcome["removed_sensors"],
                "sensors_online": outcome["sensors_online"],
                "confidence": outcome["confidence"],
                "state": outcome["state"],
                "effect": "simulation-only",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def jam_citizen_channel(
    principal: Principal = Depends(require_operator),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        outcome = state.citizen_grid.jam_active_channel()
        if outcome["jammed_channel"] is None:
            raise HTTPException(status_code=409, detail="No available advisory channel remains")
        event = state._append_event(
            "citizen-grid",
            "citizen.channel_degraded",
            "warning" if outcome["fallback_channel"] else "critical",
            {
                "jammed_channel": outcome["jammed_channel"],
                "fallback_channel": outcome["fallback_channel"],
                "effect": "simulation-only",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def dispatch_citizen_warning(
    principal: Principal = Depends(require_action("approve_recovery")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    """Record an operator-approved simulated advisory; nothing is transmitted."""
    async with state.lock:
        cached = state.cached_command(x_command_id)
        if cached:
            return cached
        state.set_actor_context(principal)
        grid = state.citizen_grid
        if grid.grid_state != "confirmed":
            raise HTTPException(
                status_code=409,
                detail="Corroboration guardrail not met; more independent districts are required",
            )
        channel = grid.active_channel
        if channel is None:
            raise HTTPException(status_code=409, detail="No available advisory channel remains")
        outcome = grid.dispatch_warning(channel.id)
        event = state._append_event(
            "citizen-grid",
            "citizen.advisory_approved",
            "success",
            {
                **outcome,
                "actor": principal.subject,
                "role": principal.role,
                "reason": "operator approved a simulated civilian advisory",
            },
        )
        result = state.snapshot()
        state.remember_command(x_command_id, result)
    await broadcast(event)
    return result


async def request_mesh_failover(
    command: MeshFailoverCommand,
    principal: Principal = Depends(require_action("mesh_failover")),
    x_command_id: Annotated[str | None, Header(alias="X-Command-ID")] = None,
) -> dict[str, Any]:
    """Versioned alias for the existing deterministic node-loss simulation."""
    return await fail_node(command.node_id, principal, x_command_id)


def register_routes(router: APIRouter) -> None:
    router.add_api_route("/health", health, methods=["GET"], response_model=HealthResponse)
    router.add_api_route("/metrics", prometheus_metrics, methods=["GET"])
    router.add_api_route("/scenario", get_scenario, methods=["GET"])
    router.add_api_route("/scenario/definition", get_scenario_definition, methods=["GET"])
    router.add_api_route("/mesh/topology", get_mesh_topology, methods=["GET"], response_model=MeshTopologyResponse)
    router.add_api_route("/prophet/telemetry", get_prophet_telemetry, methods=["GET"])
    router.add_api_route("/prophet/scores", get_prophet_scores, methods=["GET"], response_model=ProphetScoreResponse)
    router.add_api_route("/prophet/explain", get_prophet_explanation, methods=["GET"], response_model=ProphetExplanationResponse)
    router.add_api_route("/phoenix/workflows", get_phoenix_workflows, methods=["GET"], response_model=PhoenixWorkflowResponse)
    router.add_api_route("/citizen/grid", get_citizen_grid, methods=["GET"])
    router.add_api_route("/mirror/catalog", get_mirror_catalog, methods=["GET"])
    router.add_api_route("/mirror/scenarios/{scenario_id}", get_mirror_scenario, methods=["GET"])
    router.add_api_route("/audit/export", export_audit, methods=["GET"])
    router.add_api_route("/observability", observability, methods=["GET"])
    router.add_api_route("/analysis/summary", analysis_summary, methods=["GET"])
    router.add_api_route("/scenario/replay/{sequence}", replay_scenario, methods=["GET"])
    router.add_api_route("/scenario/reset", reset_scenario, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/scenario/advance", advance_scenario, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/scenario/speed", set_scenario_speed, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/tabletop/select", select_tabletop_branch, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/citizen/detect", register_citizen_detection, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/citizen/attrition", apply_citizen_attrition, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/citizen/jam", jam_citizen_channel, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/citizen/warn", dispatch_citizen_warning, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/mesh/failover", request_mesh_failover, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/network/fail/{node_id}", fail_node, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/phoenix/approve", approve_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/phoenix/execute", execute_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/phoenix/verify", verify_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/phoenix/rollback", rollback_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/recovery/approve", approve_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/recovery/execute", execute_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})
    router.add_api_route("/recovery/verify", verify_recovery, methods=["POST"], responses={403: {"model": ErrorBody}})


register_routes(api_v1)
api_legacy = APIRouter(prefix="/api")
register_routes(api_legacy)
app.include_router(api_v1)
app.include_router(api_legacy)
app.add_api_route("/metrics", prometheus_metrics, methods=["GET"])


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "api": settings.api_prefix,
        "docs": "/docs",
        "legacy_alias": "/api/*",
        "metrics": "/metrics",
    }


@app.websocket("/ws/events")
@app.websocket("/api/v1/ws/events")
async def event_stream(
    websocket: WebSocket,
    correlation_id: str | None = None,
    after_sequence: int = 0,
) -> None:
    await websocket.accept()
    state.clients.add(websocket)
    if correlation_id == state.correlation_id and after_sequence >= 0:
        await websocket.send_json(
            {
                "kind": "resume",
                "from_sequence": after_sequence,
                "events": state.events_after(after_sequence),
                "snapshot": state.snapshot(),
            }
        )
    else:
        await websocket.send_json({"kind": "snapshot", "snapshot": state.snapshot()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.clients.discard(websocket)
