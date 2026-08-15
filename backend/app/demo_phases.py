"""Deterministic cinematic demo phase projection for the resilience console."""

from __future__ import annotations

from typing import Any, Literal

DemoPhaseId = Literal[
    "baseline",
    "evidence_rising",
    "relay_interrupted",
    "tabletop_choice",
    "recovery_review",
    "workflow_restored",
    "complete",
]

PHASE_ORDER: list[DemoPhaseId] = [
    "baseline",
    "evidence_rising",
    "relay_interrupted",
    "tabletop_choice",
    "recovery_review",
    "workflow_restored",
    "complete",
]

PHASE_COPY: dict[DemoPhaseId, dict[str, str]] = {
    "baseline": {
        "title": "Calm baseline",
        "cue": "Twelve fictional civil resilience nodes are online. Continuity is intact.",
        "operator_hint": "Advance the synthetic evidence feed to begin the exercise.",
    },
    "evidence_rising": {
        "title": "Evidence develops",
        "cue": "Labeled synthetic signals are rising. PROPHET remains review-only.",
        "operator_hint": "Continue advancing until the warning threshold, then inject relay loss.",
    },
    "relay_interrupted": {
        "title": "Relay interruption",
        "cue": "NORTHSTAR is offline. CHAMELEON recomputed routes and handed coordination to ATLAS-2.",
        "operator_hint": "Compare MIRROR tabletop branches and select one declared response.",
    },
    "tabletop_choice": {
        "title": "Human tabletop choice",
        "cue": "A fixture-only decision point is waiting. No automated branch selection is allowed.",
        "operator_hint": "Select one declared branch, then review ranked recovery options.",
    },
    "recovery_review": {
        "title": "Recovery review",
        "cue": "PHOENIX ranked reversible workflow routes. Explicit operator approval is required.",
        "operator_hint": "Approve one simulated route, then verify restoration or rollback.",
    },
    "workflow_restored": {
        "title": "Workflow restored",
        "cue": "Simulated recovery verified. The append-only audit trail is ready for export.",
        "operator_hint": "Replay a checkpoint or export the hash-chained audit evidence.",
    },
    "complete": {
        "title": "Exercise complete",
        "cue": "All four layers were exercised with human approval and fixture-only outcomes.",
        "operator_hint": "Reset the scenario to rehearse again.",
    },
}


def project_demo_phase(
    *,
    alert_state: str,
    coordinator_offline: bool,
    selected_branch: str | None,
    phoenix_state: str,
    awaiting_tabletop: bool,
) -> dict[str, Any]:
    """Derive the cinematic phase from durable scenario state only."""
    if phoenix_state == "failed":
        phase: DemoPhaseId = "complete"
    elif phoenix_state == "restored":
        phase = "workflow_restored"
    elif phoenix_state in {"approval", "execution", "verify", "rollback"}:
        phase = "recovery_review"
    elif selected_branch and coordinator_offline:
        phase = "recovery_review"
    elif coordinator_offline and awaiting_tabletop:
        phase = "tabletop_choice"
    elif coordinator_offline:
        phase = "relay_interrupted"
    elif alert_state in {"watch", "warning"}:
        phase = "evidence_rising"
    else:
        phase = "baseline"

    copy = PHASE_COPY[phase]
    index = PHASE_ORDER.index(phase)
    return {
        "id": phase,
        "index": index + 1,
        "total": len(PHASE_ORDER),
        "title": copy["title"],
        "cue": copy["cue"],
        "operator_hint": copy["operator_hint"],
        "label": "fictional-exercise-phase",
        "notice": "Guided simulation pacing only; phases do not authorize external action.",
    }
