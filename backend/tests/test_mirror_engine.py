from __future__ import annotations

from pathlib import Path

import pytest

from app.mirror_engine import MirrorEventLoop, MirrorEventType
from app.mirror_scenario import MirrorScenarioError, load_mirror_scenario


SCENARIO = load_mirror_scenario(
    Path(__file__).parents[1] / "app" / "fixtures" / "mirror-fictional-network-partition.yaml"
)
SELECTIONS = {"relay-loss": "bridge", "evidence-gap": "tabletop"}


def test_event_loop_waits_for_declared_human_choice() -> None:
    loop = MirrorEventLoop(SCENARIO)
    presented = loop.present_next()
    assert presented.event_type is MirrorEventType.DECISION_PRESENTED
    assert presented.decision_point_id == "relay-loss"

    emitted = loop.select_branch("bridge")
    assert [event.event_type for event in emitted] == [
        MirrorEventType.BRANCH_RECORDED,
        MirrorEventType.OUTCOME_RECORDED,
    ]
    assert not loop.completed


def test_event_loop_replays_identically_one_hundred_times() -> None:
    traces = []
    for _ in range(100):
        loop = MirrorEventLoop(SCENARIO)
        traces.append(
            [
                (
                    event.sequence,
                    event.virtual_time_ms,
                    event.event_type,
                    event.decision_point_id,
                    event.branch_id,
                    event.detail,
                    event.mode,
                )
                for event in loop.run(SELECTIONS)
            ]
        )
    assert all(trace == traces[0] for trace in traces)
    assert [event[1] for event in traces[0]] == [1000, 2000, 3000, 4000, 5000, 6000, 7000]
    assert traces[0][-1][2] is MirrorEventType.REPLAY_COMPLETED


def test_event_loop_rejects_missing_or_unknown_human_choice() -> None:
    with pytest.raises(MirrorScenarioError, match="missing selection"):
        MirrorEventLoop(SCENARIO).run({"relay-loss": "bridge"})

    loop = MirrorEventLoop(SCENARIO)
    loop.present_next()
    with pytest.raises(MirrorScenarioError, match="unknown selection"):
        loop.select_branch("execute")


def test_event_loop_supports_explicit_deterministic_step_size() -> None:
    events = MirrorEventLoop(SCENARIO, step_ms=250).run(SELECTIONS)
    assert [event.virtual_time_ms for event in events] == [
        250,
        500,
        750,
        1000,
        1250,
        1500,
        1750,
    ]
    with pytest.raises(MirrorScenarioError, match="step must be positive"):
        MirrorEventLoop(SCENARIO, step_ms=0)
