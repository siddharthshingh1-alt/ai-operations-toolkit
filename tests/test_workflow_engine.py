"""Workflow engine tests.

The one that matters most is `test_approval_blocks_downstream_nodes`: human
approval must be structurally enforced, not merely conventional.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiops_utils import ValidationError
from aiops_workflow import (
    ExecutionStatus,
    NodeStatus,
    NodeType,
    Workflow,
    WorkflowEngine,
    WorkflowNode,
)


def _linear_workflow() -> Workflow:
    """Trigger -> condition -> approval -> email, the Section 7 shape."""
    email = WorkflowNode(id="n4", type=NodeType.EMAIL, label="Send to agent")
    approval = WorkflowNode(
        id="n3", type=NodeType.HUMAN_APPROVAL, label="Ops approval", next_id="n4"
    )
    condition = WorkflowNode(
        id="n2",
        type=NodeType.CONDITION,
        label="High severity?",
        config={"field": "severity", "operator": "eq", "value": "high"},
        next_id="n3",
        next_id_if_false=None,
    )
    trigger = WorkflowNode(
        id="n1",
        type=NodeType.TRIGGER,
        label="Delay detected",
        config={"event": "BOOKING_DELAY_DETECTED"},
        next_id="n2",
    )
    return Workflow(
        name="Booking delay",
        nodes=[trigger, condition, approval, email],
        start_node_id="n1",
    )


def test_run_pauses_at_human_approval() -> None:
    engine = WorkflowEngine()
    execution = engine.run(_linear_workflow(), context={"severity": "high"})

    assert execution.status is ExecutionStatus.AWAITING_APPROVAL
    assert execution.awaiting_node_id == "n3"


def test_approval_blocks_downstream_nodes() -> None:
    """No node past an approval gate may run before a human decides.

    The EMAIL node has no registered handler, so if the engine ever ran past
    the gate on its own this test would fail with a handler error.
    """
    engine = WorkflowEngine()
    execution = engine.run(_linear_workflow(), context={"severity": "high"})

    executed = {run.node_id for run in execution.node_runs}
    assert "n4" not in executed


def test_resume_after_approval_reaches_the_next_node() -> None:
    engine = WorkflowEngine()
    workflow = _linear_workflow()
    execution = engine.run(workflow, context={"severity": "high"})

    # Register a handler so the gated node can now run.
    sent: list[str] = []

    def send_email(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        sent.append(node.id)
        return {"sent": True}

    engine.register(NodeType.EMAIL, send_email)
    execution = engine.resume(workflow, execution, approved_by="ops.anita@example.test")

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert sent == ["n4"]
    assert execution.context["approved_by"] == "ops.anita@example.test"


def test_rejection_stops_the_run_without_executing_the_action() -> None:
    engine = WorkflowEngine()
    workflow = _linear_workflow()
    execution = engine.run(workflow, context={"severity": "high"})

    sent: list[str] = []

    def send_email(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        sent.append(node.id)
        return {"sent": True}

    engine.register(NodeType.EMAIL, send_email)

    execution = engine.resume(
        workflow, execution, approved_by="ops.anita@example.test", approved=False
    )
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert sent == []


def test_resume_requires_an_approver() -> None:
    engine = WorkflowEngine()
    workflow = _linear_workflow()
    execution = engine.run(workflow, context={"severity": "high"})

    with pytest.raises(ValidationError, match="approver"):
        engine.resume(workflow, execution, approved_by="   ")


def test_false_condition_takes_the_other_branch() -> None:
    engine = WorkflowEngine()
    execution = engine.run(_linear_workflow(), context={"severity": "low"})

    # next_id_if_false is None, so the run ends cleanly rather than approving.
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.awaiting_node_id is None


def test_loop_is_detected_rather_than_hanging() -> None:
    """A cycle must fail fast, not spin forever."""
    node = WorkflowNode(id="a", type=NodeType.TRIGGER, label="Loop", next_id="a")
    workflow = Workflow(name="Cyclic", nodes=[node], start_node_id="a")

    execution = WorkflowEngine().run(workflow)
    assert execution.status is ExecutionStatus.FAILED
    assert "loop" in (execution.error or "").lower()


def test_unregistered_node_type_fails_clearly() -> None:
    node = WorkflowNode(id="a", type=NodeType.WEBHOOK, label="Call out")
    workflow = Workflow(name="Webhook", nodes=[node], start_node_id="a")

    execution = WorkflowEngine().run(workflow)
    assert execution.status is ExecutionStatus.FAILED
    assert "no handler registered" in (execution.error or "").lower()


def test_handler_failure_is_recorded_not_swallowed() -> None:
    engine = WorkflowEngine()

    def explode(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("supplier API is down")

    engine.register(NodeType.WEBHOOK, explode)
    node = WorkflowNode(id="a", type=NodeType.WEBHOOK, label="Notify supplier")
    workflow = Workflow(name="Notify", nodes=[node], start_node_id="a")

    execution = engine.run(workflow)
    assert execution.status is ExecutionStatus.FAILED
    assert execution.node_runs[0].status is NodeStatus.FAILED
    assert "supplier API is down" in (execution.node_runs[0].error or "")


def test_missing_start_node_is_rejected() -> None:
    workflow = Workflow(name="Empty", nodes=[], start_node_id=None)
    with pytest.raises(ValidationError, match="no start node"):
        WorkflowEngine().run(workflow)


def test_transform_maps_context_fields() -> None:
    engine = WorkflowEngine()
    node = WorkflowNode(
        id="a",
        type=NodeType.TRANSFORM,
        label="Rename",
        config={"mapping": {"agent": "agent_name"}},
    )
    workflow = Workflow(name="T", nodes=[node], start_node_id="a")

    execution = engine.run(workflow, context={"agent_name": "Skyline Holidays"})
    assert execution.context["agent"] == "Skyline Holidays"


def test_cost_rolls_up_across_nodes() -> None:
    engine = WorkflowEngine()

    def costly(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        return {"_ai_model": "claude-opus-5", "_estimated_cost_usd": 0.0025}

    engine.register(NodeType.AI_CLASSIFICATION, costly)
    first = WorkflowNode(id="a", type=NodeType.AI_CLASSIFICATION, label="Classify", next_id="b")
    second = WorkflowNode(id="b", type=NodeType.AI_CLASSIFICATION, label="Classify again")
    workflow = Workflow(name="Cost", nodes=[first, second], start_node_id="a")

    execution = engine.run(workflow)
    assert execution.total_cost_usd == 0.005
