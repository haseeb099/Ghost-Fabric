"""Deterministic, fixture-only event loop for MIRROR tabletop scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.mirror_scenario import MirrorScenario, MirrorScenarioError


class MirrorEventType(StrEnum):
    DECISION_PRESENTED = "decision.presented"
    BRANCH_RECORDED = "branch.recorded"
    OUTCOME_RECORDED = "outcome.recorded"
    REPLAY_COMPLETED = "replay.completed"


@dataclass(frozen=True)
class MirrorEvent:
    sequence: int
    virtual_time_ms: int
    scenario_id: str
    event_type: MirrorEventType
    decision_point_id: str | None
    branch_id: str | None
    detail: str
    mode: str = "tabletop-fixture"


class MirrorEventLoop:
    """A seed-stable loop that waits for human-supplied declared choices."""

    def __init__(self, scenario: MirrorScenario, *, step_ms: int = 1000) -> None:
        if step_ms <= 0:
            raise MirrorScenarioError("event-loop step must be positive")
        self.scenario = scenario
        self.step_ms = step_ms
        self._cursor = 0
        self._events: list[MirrorEvent] = []

    @property
    def completed(self) -> bool:
        return self._cursor >= len(self.scenario.decision_points)

    @property
    def current_decision_point(self):
        if self.completed:
            return None
        return self.scenario.decision_points[self._cursor]

    @property
    def events(self) -> list[MirrorEvent]:
        return list(self._events)

    def present_next(self) -> MirrorEvent:
        if self.completed:
            raise MirrorScenarioError("tabletop replay is already complete")
        point = self.scenario.decision_points[self._cursor]
        return self._append(
            MirrorEventType.DECISION_PRESENTED,
            point.id,
            None,
            point.condition,
        )

    def select_branch(self, branch_id: str) -> list[MirrorEvent]:
        """Record only a declared human branch selection and its fixture outcome."""
        if self.completed:
            raise MirrorScenarioError("tabletop replay is already complete")
        point = self.scenario.decision_points[self._cursor]
        branch = next((item for item in point.branches if item.id == branch_id), None)
        if branch is None:
            raise MirrorScenarioError(f"unknown selection {branch_id!r} for {point.id}")

        emitted = [
            self._append(MirrorEventType.BRANCH_RECORDED, point.id, branch.id, branch.label),
            self._append(MirrorEventType.OUTCOME_RECORDED, point.id, branch.id, branch.outcome),
        ]
        self._cursor += 1
        if self.completed:
            emitted.append(
                self._append(
                    MirrorEventType.REPLAY_COMPLETED,
                    None,
                    None,
                    "deterministic tabletop fixture replay complete",
                )
            )
        return emitted

    def run(self, selections: dict[str, str]) -> list[MirrorEvent]:
        """Run a complete declared replay; missing human selections are rejected."""
        while not self.completed:
            point = self.scenario.decision_points[self._cursor]
            self.present_next()
            selection = selections.get(point.id)
            if selection is None:
                raise MirrorScenarioError(f"missing selection for {point.id}")
            self.select_branch(selection)
        return self.events

    def _append(
        self,
        event_type: MirrorEventType,
        decision_point_id: str | None,
        branch_id: str | None,
        detail: str,
    ) -> MirrorEvent:
        event = MirrorEvent(
            sequence=len(self._events) + 1,
            virtual_time_ms=(len(self._events) + 1) * self.step_ms,
            scenario_id=self.scenario.id,
            event_type=event_type,
            decision_point_id=decision_point_id,
            branch_id=branch_id,
            detail=detail,
        )
        self._events.append(event)
        return event
