"""Deterministic, simulation-only PHOENIX recovery workflow state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class WorkflowState(StrEnum):
    ALERT = "alert"
    APPROVAL = "approval"
    EXECUTION = "execution"
    VERIFY = "verify"
    RESTORED = "restored"
    ROLLBACK = "rollback"
    FAILED = "failed"


class WorkflowTransitionError(ValueError):
    """A transition was requested outside the allowed simulation workflow."""


@dataclass(frozen=True)
class WorkflowTransition:
    sequence: int
    from_state: WorkflowState
    to_state: WorkflowState
    actor: str
    reason: str


@dataclass
class PhoenixWorkflow:
    """A bounded recovery simulation; it cannot execute external actions."""

    workflow_id: str
    correlation_id: str
    state: WorkflowState = WorkflowState.ALERT
    selected_option_id: str | None = None
    approval_actor: str | None = None
    transitions: list[WorkflowTransition] = field(default_factory=list)

    def request_approval(self, option_id: str, actor: str = "system") -> WorkflowTransition:
        if self.state is not WorkflowState.ALERT:
            raise WorkflowTransitionError("approval can only be requested from alert")
        if not option_id:
            raise WorkflowTransitionError("a recovery option is required")
        self.selected_option_id = option_id
        return self._transition(WorkflowState.APPROVAL, actor, "recovery option requires explicit approval")

    def approve(self, actor: str, role: Literal["viewer", "operator"]) -> WorkflowTransition:
        if self.state is not WorkflowState.APPROVAL:
            raise WorkflowTransitionError("approval is not currently pending")
        if role != "operator":
            raise WorkflowTransitionError("operator role required for simulated recovery approval")
        if not actor:
            raise WorkflowTransitionError("approval actor is required")
        self.approval_actor = actor
        return self._transition(WorkflowState.EXECUTION, actor, "explicit simulated recovery approval")

    def record_simulated_execution(self, actor: str = "system") -> WorkflowTransition:
        if self.state is not WorkflowState.EXECUTION:
            raise WorkflowTransitionError("simulated execution requires prior approval")
        return self._transition(WorkflowState.VERIFY, actor, "reversible simulation step recorded")

    def verify(self, succeeded: bool, actor: str = "system") -> WorkflowTransition:
        if self.state is not WorkflowState.VERIFY:
            raise WorkflowTransitionError("verification requires simulated execution")
        if succeeded:
            return self._transition(WorkflowState.RESTORED, actor, "simulation verification passed")
        return self._transition(WorkflowState.ROLLBACK, actor, "simulation verification failed; rollback required")

    def complete_rollback(self, actor: str = "system") -> WorkflowTransition:
        if self.state is not WorkflowState.ROLLBACK:
            raise WorkflowTransitionError("rollback is not pending")
        return self._transition(WorkflowState.FAILED, actor, "simulation rollback completed")

    def request_rollback(self, actor: str) -> WorkflowTransition:
        if self.state is not WorkflowState.RESTORED:
            raise WorkflowTransitionError("rollback requires a restored simulated workflow")
        return self._transition(WorkflowState.ROLLBACK, actor, "operator requested reversible simulation rollback")

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "state": self.state.value,
            "selected_option_id": self.selected_option_id,
            "approval_actor": self.approval_actor,
            "transitions": [
                {
                    "sequence": transition.sequence,
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "actor": transition.actor,
                    "reason": transition.reason,
                }
                for transition in self.transitions
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "PhoenixWorkflow":
        workflow = cls(
            workflow_id=str(value["workflow_id"]),
            correlation_id=str(value["correlation_id"]),
            state=WorkflowState(str(value["state"])),
            selected_option_id=value.get("selected_option_id") or None,
            approval_actor=value.get("approval_actor") or None,
        )
        workflow.transitions = [
            WorkflowTransition(
                sequence=int(item["sequence"]),
                from_state=WorkflowState(str(item["from_state"])),
                to_state=WorkflowState(str(item["to_state"])),
                actor=str(item["actor"]),
                reason=str(item["reason"]),
            )
            for item in value.get("transitions", [])  # type: ignore[union-attr]
        ]
        return workflow

    def _transition(self, to_state: WorkflowState, actor: str, reason: str) -> WorkflowTransition:
        transition = WorkflowTransition(
            sequence=len(self.transitions) + 1,
            from_state=self.state,
            to_state=to_state,
            actor=actor,
            reason=reason,
        )
        self.state = to_state
        self.transitions.append(transition)
        return transition
