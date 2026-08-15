from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.mirror_scenario import (
    MirrorScenario,
    MirrorScenarioError,
    load_mirror_catalog,
    load_mirror_scenario,
    replay_tabletop,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "app"
    / "fixtures"
    / "mirror-fictional-network-partition.yaml"
)
FIXTURE_DIRECTORY = FIXTURE_PATH.parent


def test_fixture_scenario_loads_with_synthetic_tabletop_boundary() -> None:
    scenario = load_mirror_scenario(FIXTURE_PATH)
    assert scenario.classification == "synthetic-training"
    assert len(scenario.decision_points) == 2
    assert "tabletop" in scenario.notice.lower()


def test_catalog_contains_eight_safe_documented_scenarios() -> None:
    catalog = load_mirror_catalog(FIXTURE_DIRECTORY)
    assert len(catalog) == 8
    assert len({scenario.id for scenario in catalog}) == 8
    assert all(scenario.classification == "synthetic-training" for scenario in catalog)
    assert all(1 <= len(scenario.decision_points) <= 12 for scenario in catalog)
    assert all(
        2 <= len(point.branches) <= 4
        for scenario in catalog
        for point in scenario.decision_points
    )


def test_every_catalog_scenario_replays_deterministically() -> None:
    for scenario in load_mirror_catalog(FIXTURE_DIRECTORY):
        selections = {
            point.id: point.branches[0].id
            for point in scenario.decision_points
        }
        first = replay_tabletop(scenario, selections)
        second = replay_tabletop(scenario, selections)
        assert second == first
        assert all(item["mode"] == "tabletop-fixture" for item in first)


def test_tabletop_replay_is_deterministic_and_non_executable() -> None:
    scenario = load_mirror_scenario(FIXTURE_PATH)
    selections = {"relay-loss": "bridge", "evidence-gap": "tabletop"}

    first = replay_tabletop(scenario, selections)
    second = replay_tabletop(scenario, selections)

    assert first == second
    assert all(item["mode"] == "tabletop-fixture" for item in first)
    assert all("command" not in item for item in first)


def test_replay_rejects_missing_or_unknown_branch_selection() -> None:
    scenario = load_mirror_scenario(FIXTURE_PATH)
    with pytest.raises(MirrorScenarioError, match="missing selection"):
        replay_tabletop(scenario, {"relay-loss": "bridge"})
    with pytest.raises(MirrorScenarioError, match="unknown selection"):
        replay_tabletop(
            scenario,
            {"relay-loss": "unknown", "evidence-gap": "wait"},
        )


def test_scenario_rejects_prohibited_targeting_content() -> None:
    with pytest.raises(ValidationError, match="prohibited tabletop term"):
        MirrorScenario.model_validate(
            {
                "schema_version": 1,
                "id": "unsafe-fixture",
                "name": "Unsafe",
                "classification": "synthetic-training",
                "seed": 1,
                "notice": "Synthetic tabletop fixture",
                "decision_points": [
                    {
                        "id": "point-a",
                        "condition": "Choose a target.",
                        "branches": [
                            {"id": "hold", "label": "Hold", "outcome": "Review."},
                            {"id": "wait", "label": "Wait", "outcome": "Wait."},
                        ],
                    }
                ],
            }
        )


def test_scenario_forbids_undeclared_action_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MirrorScenario.model_validate(
            {
                "schema_version": 1,
                "id": "extra-field-fixture",
                "name": "Safe",
                "classification": "synthetic-training",
                "seed": 1,
                "notice": "Synthetic tabletop fixture",
                "decision_points": [
                    {
                        "id": "point-a",
                        "condition": "Review fixture evidence.",
                        "branches": [
                            {"id": "hold", "label": "Hold", "outcome": "Review."},
                            {"id": "wait", "label": "Wait", "outcome": "Wait."},
                        ],
                    }
                ],
                "action": "execute",
            }
        )
