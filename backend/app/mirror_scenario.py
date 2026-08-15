"""Fixture-only MIRROR tabletop scenario DSL and deterministic replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


PROHIBITED_TERMS = (
    "target",
    "weapon",
    "missile",
    "personality",
    "psychological",
    "influence operation",
)


class MirrorScenarioError(ValueError):
    """Scenario content violates the fixture-only tabletop boundary."""


class MirrorBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=1, max_length=120)
    outcome: str = Field(min_length=1, max_length=500)


class MirrorDecisionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    condition: str = Field(min_length=1, max_length=500)
    branches: list[MirrorBranch] = Field(min_length=2, max_length=4)


class MirrorScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=160)
    classification: str = Field(pattern=r"^synthetic-training$")
    seed: int = Field(ge=0)
    notice: str = Field(min_length=1, max_length=500)
    decision_points: list[MirrorDecisionPoint] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_tabletop_safety(self) -> "MirrorScenario":
        values = _collect_text(
            {
                "name": self.name,
                "decision_points": [point.model_dump() for point in self.decision_points],
            }
        )
        combined = " ".join(values).lower()
        for term in PROHIBITED_TERMS:
            if term in combined:
                raise MirrorScenarioError(f"prohibited tabletop term: {term}")
        if len({point.id for point in self.decision_points}) != len(self.decision_points):
            raise MirrorScenarioError("decision point IDs must be unique")
        for point in self.decision_points:
            if len({branch.id for branch in point.branches}) != len(point.branches):
                raise MirrorScenarioError(f"branch IDs must be unique within {point.id}")
        return self


def load_mirror_scenario(path: Path) -> MirrorScenario:
    """Load a validated fixture; YAML never supplies executable actions."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MirrorScenarioError("scenario root must be a mapping")
    return MirrorScenario.model_validate(raw)


def load_mirror_catalog(directory: Path) -> list[MirrorScenario]:
    """Load the complete, stably ordered set of approved MIRROR fixtures."""
    scenarios = [
        load_mirror_scenario(path)
        for path in sorted(directory.glob("mirror-*.yaml"))
    ]
    if len({scenario.id for scenario in scenarios}) != len(scenarios):
        raise MirrorScenarioError("scenario IDs must be unique across the catalog")
    return scenarios


def replay_tabletop(
    scenario: MirrorScenario, selections: dict[str, str]
) -> list[dict[str, str]]:
    """Replay declared choices deterministically with no external side effects."""
    trace: list[dict[str, str]] = []
    for point in scenario.decision_points:
        choice = selections.get(point.id)
        if choice is None:
            raise MirrorScenarioError(f"missing selection for {point.id}")
        branch = next((candidate for candidate in point.branches if candidate.id == choice), None)
        if branch is None:
            raise MirrorScenarioError(f"unknown selection {choice!r} for {point.id}")
        trace.append(
            {
                "decision_point_id": point.id,
                "branch_id": branch.id,
                "outcome": branch.outcome,
                "mode": "tabletop-fixture",
            }
        )
    return trace


def _collect_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _collect_text(item)]
    if isinstance(value, list):
        return [text for item in value for text in _collect_text(item)]
    return []
