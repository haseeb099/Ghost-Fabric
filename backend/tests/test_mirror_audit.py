from __future__ import annotations

from pathlib import Path

from app.audit.memory import MemoryAuditStore
from app.main import ScenarioState
from app.mirror_audit import append_tabletop_trace
from app.mirror_scenario import load_mirror_scenario


def test_mirror_trace_is_persisted_through_canonical_audit_store() -> None:
    scenario = load_mirror_scenario(
        Path(__file__).parents[1]
        / "app"
        / "fixtures"
        / "mirror-fictional-network-partition.yaml"
    )
    store = MemoryAuditStore()
    state = ScenarioState(audit_store=store)
    initial_sequence = state.sequence

    appended = append_tabletop_trace(
        state,
        scenario=scenario,
        selections={"relay-loss": "bridge", "evidence-gap": "tabletop"},
    )

    assert len(appended) == 7
    events = store.list_events(state.correlation_id)
    trace_events = events[initial_sequence:]
    assert [event["type"] for event in trace_events] == [
        "mirror.decision.presented",
        "mirror.branch.recorded",
        "mirror.outcome.recorded",
        "mirror.decision.presented",
        "mirror.branch.recorded",
        "mirror.outcome.recorded",
        "mirror.replay.completed",
    ]
    assert all(event["payload"]["effect"] == "tabletop-fixture-only" for event in trace_events)
    assert all(event["source"] == "mirror" for event in trace_events)
    assert [event["payload"]["virtual_time_ms"] for event in trace_events] == [
        1000,
        2000,
        3000,
        4000,
        5000,
        6000,
        7000,
    ]
