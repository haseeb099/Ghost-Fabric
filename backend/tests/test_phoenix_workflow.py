from __future__ import annotations

import pytest

from app.phoenix_workflow import PhoenixWorkflow, WorkflowState, WorkflowTransitionError


def test_simulated_recovery_requires_explicit_operator_approval() -> None:
    workflow = PhoenixWorkflow(workflow_id="wf-1", correlation_id="run-1")
    requested = workflow.request_approval("route-atlas")
    assert requested.to_state is WorkflowState.APPROVAL

    with pytest.raises(WorkflowTransitionError, match="operator role"):
        workflow.approve("DEMO-VIEWER", "viewer")
    assert workflow.state is WorkflowState.APPROVAL

    approved = workflow.approve("DEMO-OPERATOR", "operator")
    assert approved.to_state is WorkflowState.EXECUTION
    assert workflow.approval_actor == "DEMO-OPERATOR"


def test_successful_simulated_recovery_follows_execution_and_verify() -> None:
    workflow = PhoenixWorkflow(workflow_id="wf-2", correlation_id="run-2")
    workflow.request_approval("route-harbor")
    workflow.approve("DEMO-OPERATOR", "operator")
    workflow.record_simulated_execution()
    verified = workflow.verify(succeeded=True)

    assert verified.to_state is WorkflowState.RESTORED
    assert [item.to_state for item in workflow.transitions] == [
        WorkflowState.APPROVAL,
        WorkflowState.EXECUTION,
        WorkflowState.VERIFY,
        WorkflowState.RESTORED,
    ]


def test_failed_verification_requires_rollback_before_failure() -> None:
    workflow = PhoenixWorkflow(workflow_id="wf-3", correlation_id="run-3")
    workflow.request_approval("route-local")
    workflow.approve("DEMO-OPERATOR", "operator")
    workflow.record_simulated_execution()
    workflow.verify(succeeded=False)
    assert workflow.state is WorkflowState.ROLLBACK

    complete = workflow.complete_rollback()
    assert complete.to_state is WorkflowState.FAILED


def test_invalid_transition_never_skips_human_approval() -> None:
    workflow = PhoenixWorkflow(workflow_id="wf-4", correlation_id="run-4")
    with pytest.raises(WorkflowTransitionError, match="prior approval"):
        workflow.record_simulated_execution()
    with pytest.raises(WorkflowTransitionError, match="verification requires"):
        workflow.verify(succeeded=True)
