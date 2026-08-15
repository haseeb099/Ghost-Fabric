"""Unit tests for cinematic demo phase projection."""

from app.demo_phases import project_demo_phase


def test_demo_phases_follow_resilience_sequence() -> None:
    baseline = project_demo_phase(
        alert_state="nominal",
        coordinator_offline=False,
        selected_branch=None,
        phoenix_state="alert",
        awaiting_tabletop=True,
    )
    assert baseline["id"] == "baseline"

    rising = project_demo_phase(
        alert_state="warning",
        coordinator_offline=False,
        selected_branch=None,
        phoenix_state="alert",
        awaiting_tabletop=True,
    )
    assert rising["id"] == "evidence_rising"

    tabletop = project_demo_phase(
        alert_state="warning",
        coordinator_offline=True,
        selected_branch=None,
        phoenix_state="alert",
        awaiting_tabletop=True,
    )
    assert tabletop["id"] == "tabletop_choice"

    recovery = project_demo_phase(
        alert_state="warning",
        coordinator_offline=True,
        selected_branch="bridge",
        phoenix_state="approval",
        awaiting_tabletop=False,
    )
    assert recovery["id"] == "recovery_review"

    restored = project_demo_phase(
        alert_state="warning",
        coordinator_offline=True,
        selected_branch="bridge",
        phoenix_state="restored",
        awaiting_tabletop=False,
    )
    assert restored["id"] == "workflow_restored"
    assert "authorize external action" in restored["notice"]
