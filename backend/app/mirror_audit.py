"""Canonical audit mapping for deterministic MIRROR fixture traces."""

from __future__ import annotations

from typing import Protocol

from app.mirror_engine import MirrorEvent, MirrorEventLoop
from app.mirror_scenario import MirrorScenario


class MirrorAuditWriter(Protocol):
    def _append_event(
        self,
        source: str,
        event_type: str,
        severity: str,
        payload: dict[str, object],
    ) -> object: ...


def mirror_event_payload(trace_event: MirrorEvent) -> dict[str, object]:
    """Map a fixture-only loop event into the canonical audit payload shape."""
    return {
        "scenario_id": trace_event.scenario_id,
        "trace_sequence": trace_event.sequence,
        "virtual_time_ms": trace_event.virtual_time_ms,
        "decision_point_id": trace_event.decision_point_id,
        "branch_id": trace_event.branch_id,
        "detail": trace_event.detail,
        "mode": trace_event.mode,
        "effect": "tabletop-fixture-only",
    }


def append_mirror_events(
    state: MirrorAuditWriter,
    events: list[MirrorEvent],
) -> list[object]:
    """Append already-emitted MIRROR loop events to the canonical audit stream."""
    appended: list[object] = []
    for trace_event in events:
        appended.append(
            state._append_event(
                source="mirror",
                event_type=f"mirror.{trace_event.event_type.value}",
                severity="info",
                payload=mirror_event_payload(trace_event),
            )
        )
    return appended


def append_tabletop_trace(
    state: MirrorAuditWriter,
    *,
    scenario: MirrorScenario,
    selections: dict[str, str],
) -> list[object]:
    """Append declared MIRROR trace events to the existing canonical audit flow.

    The event loop is fixture-only: this creates decision records, not commands
    or external side effects.
    """
    loop = MirrorEventLoop(scenario)
    return append_mirror_events(state, loop.run(selections))
