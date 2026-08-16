"""Tests for Project 4 — AI Workflow Builder.

The critical tests here are about the high-risk approval guard, because it is a
new rule that did not exist before this project and the whole claim rests on it
being real rather than described.

`HIGH_RISK_NODES` sat in the engine for the whole life of this repository,
declared as the nodes that "must never run unattended", and consulted by
nothing. Anyone could have built trigger → AI writes an email → send. These
tests assert that they now cannot: not that the builder discourages it, that
the engine refuses it.

Nothing here needs an API key or a network — the AI is a stub.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from aiops_builder import (
    RUNNABLE_TYPES,
    UNAVAILABLE_TYPES,
    all_templates,
    booking_complaint_template,
    expected_ai_requests,
    register_builder_handlers,
)

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_utils import ValidationError
from aiops_workflow import (
    ExecutionStatus,
    NodeType,
    Workflow,
    WorkflowEngine,
    WorkflowNode,
    has_loop,
    unguarded_high_risk_nodes,
    validate_workflow,
)

# --------------------------------------------------------------------- doubles


class _StubAI(AIProvider):
    """Returns whatever the requested schema needs, without a network call."""

    name = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        model = kwargs["output_model"]
        fields = model.model_fields
        values: dict[str, Any] = {}
        for name, field in fields.items():
            annotation = field.annotation
            if annotation is float:
                values[name] = 0.9
            elif annotation is dict or getattr(annotation, "__origin__", None) is dict:
                values[name] = {"example": "value"}
            else:
                values[name] = "Flight delay" if name == "category" else "stub output"
        return AIResult[Any](
            value=model(**values),
            provider="stub",
            model="stub-model",
            duration_ms=2,
            usage=Usage(input_tokens=40, output_tokens=20, estimated_cost_usd=0.0001),
        )

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        raise NotImplementedError

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        raise NotImplementedError

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


def _unsafe_workflow() -> Workflow:
    """Trigger → draft an email → send it. Nobody approves anything."""
    return Workflow(
        id="wf_unsafe",
        name="Unsafe",
        start_node_id="a",
        nodes=[
            WorkflowNode(id="a", type=NodeType.TRIGGER, label="Start", next_id="b"),
            WorkflowNode(
                id="b",
                type=NodeType.AI_GENERATION,
                label="Write to the agency",
                config={"instruction": "Write something"},
                next_id="c",
            ),
            WorkflowNode(id="c", type=NodeType.EMAIL, label="Send it", next_id=None),
        ],
    )


def _safe_workflow() -> Workflow:
    """The same flow with a person in it."""
    workflow = _unsafe_workflow()
    workflow.id = "wf_safe"
    workflow.name = "Safe"
    workflow.nodes[1].next_id = "approve"
    workflow.nodes.insert(
        2,
        WorkflowNode(id="approve", type=NodeType.HUMAN_APPROVAL, label="Approve", next_id="c"),
    )
    return workflow


# ------------------------------------------------- the guard (critical tests)


def test_an_unguarded_high_risk_node_is_identified() -> None:
    unguarded = unguarded_high_risk_nodes(_unsafe_workflow())
    assert [node.id for node in unguarded] == ["c"]


def test_an_approved_high_risk_node_is_not_flagged() -> None:
    assert unguarded_high_risk_nodes(_safe_workflow()) == []


def test_the_engine_refuses_to_run_an_unsafe_workflow() -> None:
    """The rule is enforced by the engine, not by the builder remembering."""
    with pytest.raises(ValidationError) as caught:
        WorkflowEngine().run(_unsafe_workflow())

    # The message must name the offending step, or it is not actionable.
    assert "Send it" in caught.value.user_message
    assert "approval" in caught.value.user_message.lower()


def test_one_unguarded_route_is_enough_to_refuse() -> None:
    """A branch that skips the approval makes the whole workflow unsafe.

    The dangerous shape is a Condition where one side goes through approval and
    the other does not — it looks safe on the canvas and is not.
    """
    workflow = Workflow(
        id="wf_branch",
        name="Branchy",
        start_node_id="t",
        nodes=[
            WorkflowNode(id="t", type=NodeType.TRIGGER, label="Start", next_id="cond"),
            WorkflowNode(
                id="cond",
                type=NodeType.CONDITION,
                label="Urgent?",
                config={"field": "urgent"},
                next_id="approve",  # true  -> approval -> send
                next_id_if_false="send",  # false -> straight to send
            ),
            WorkflowNode(
                id="approve", type=NodeType.HUMAN_APPROVAL, label="Approve", next_id="send"
            ),
            WorkflowNode(id="send", type=NodeType.EMAIL, label="Send it"),
        ],
    )

    assert [node.id for node in unguarded_high_risk_nodes(workflow)] == ["send"]
    with pytest.raises(ValidationError):
        WorkflowEngine().run(workflow)


def test_the_guard_cannot_be_switched_off() -> None:
    """There is deliberately no argument that disables the check."""
    import inspect

    signature = inspect.signature(WorkflowEngine.run)
    names = set(signature.parameters)
    assert not (names & {"enforce", "skip_validation", "unsafe", "force"})


# ------------------------------------------------------ other validation


def test_a_workflow_with_no_start_node_is_blocked() -> None:
    issues = validate_workflow(Workflow(name="Empty"))
    assert any(issue.code == "no_start_node" and issue.blocks_execution for issue in issues)


def test_a_dangling_connection_is_blocked() -> None:
    workflow = Workflow(
        name="Dangling",
        start_node_id="a",
        nodes=[WorkflowNode(id="a", type=NodeType.TRIGGER, label="Start", next_id="gone")],
    )
    issues = validate_workflow(workflow)
    assert any(issue.code == "dangling_next" and issue.blocks_execution for issue in issues)


def test_a_loop_is_detected_before_running() -> None:
    workflow = Workflow(
        name="Loop",
        start_node_id="a",
        nodes=[
            WorkflowNode(id="a", type=NodeType.TRIGGER, label="A", next_id="b"),
            WorkflowNode(
                id="b",
                type=NodeType.TRANSFORM,
                label="B",
                config={"mapping": {"x": "y"}},
                next_id="a",
            ),
        ],
    )
    assert has_loop(workflow)
    assert any(issue.code == "loop" for issue in validate_workflow(workflow))


def test_an_unconfigured_condition_is_reported_but_does_not_block() -> None:
    workflow = Workflow(
        name="Unconfigured",
        start_node_id="a",
        nodes=[
            WorkflowNode(id="a", type=NodeType.TRIGGER, label="A", next_id="b"),
            WorkflowNode(id="b", type=NodeType.CONDITION, label="Check"),
        ],
    )
    issues = [i for i in validate_workflow(workflow) if i.code == "unconfigured"]
    assert issues and not issues[0].blocks_execution


# ------------------------------------------------------------------ running


def test_a_safe_workflow_runs_and_pauses_for_approval() -> None:
    stub = _StubAI()
    engine = register_builder_handlers(WorkflowEngine(), provider_override=stub)

    execution = engine.run(_safe_workflow(), context={"input": "The flight is late."})

    assert execution.status is ExecutionStatus.AWAITING_APPROVAL
    assert stub.calls == 1, "the drafting node should have run"
    # The email node has not executed.
    assert not any(run.node_type is NodeType.EMAIL for run in execution.node_runs)


def test_the_email_node_only_runs_after_approval() -> None:
    stub = _StubAI()
    engine = register_builder_handlers(WorkflowEngine(), provider_override=stub)
    workflow = _safe_workflow()

    execution = engine.run(workflow, context={"input": "The flight is late."})
    execution = engine.resume(workflow, execution, approved_by="Anita Rao")

    assert execution.status is ExecutionStatus.SUCCEEDED
    email_runs = [run for run in execution.node_runs if run.node_type is NodeType.EMAIL]
    assert len(email_runs) == 1
    # Recorded, never transmitted.
    assert email_runs[0].output["transmitted"] == 0
    assert email_runs[0].output["approved_by"] == "Anita Rao"


def test_rejecting_never_reaches_the_email_node() -> None:
    stub = _StubAI()
    engine = register_builder_handlers(WorkflowEngine(), provider_override=stub)
    workflow = _safe_workflow()

    execution = engine.run(workflow, context={"input": "The flight is late."})
    execution = engine.resume(workflow, execution, approved_by="Anita Rao", approved=False)

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert not any(run.node_type is NodeType.EMAIL for run in execution.node_runs)


def test_an_ai_node_with_no_input_fails_before_spending_a_request() -> None:
    stub = _StubAI()
    engine = register_builder_handlers(WorkflowEngine(), provider_override=stub)

    execution = engine.run(_safe_workflow(), context={})

    assert execution.status is ExecutionStatus.FAILED
    assert stub.calls == 0, "no AI request should have been made"
    assert "empty" in (execution.error or "").lower()


def test_a_classifier_with_no_categories_is_refused() -> None:
    engine = register_builder_handlers(WorkflowEngine(), provider_override=_StubAI())
    workflow = Workflow(
        name="Classify",
        start_node_id="a",
        nodes=[
            WorkflowNode(id="a", type=NodeType.TRIGGER, label="Start", next_id="b"),
            WorkflowNode(id="b", type=NodeType.AI_CLASSIFICATION, label="Classify"),
        ],
    )
    execution = engine.run(workflow, context={"input": "something"})
    assert execution.status is ExecutionStatus.FAILED
    assert "categor" in (execution.error or "").lower()


# ----------------------------------------------------------------- templates


def test_the_travel_operations_workflow_loads_unchanged() -> None:
    """The one-engine claim, asserted rather than described.

    This is Project 6's real definition, imported and validated by Project 4's
    tooling. If the two ever stopped speaking the same type, this fails.
    """
    from aiops_travelops import incident_workflow

    template = next(wf for wf, _ in all_templates() if wf.id == "wf_travel_incident")
    live = incident_workflow()

    assert [node.id for node in template.nodes] == [node.id for node in live.nodes]
    assert [node.type for node in template.nodes] == [node.type for node in live.nodes]
    # And it satisfies the guard, which is why the flagship still runs.
    assert unguarded_high_risk_nodes(template) == []


def test_the_shipped_templates_have_no_blocking_problems() -> None:
    for workflow, _ in all_templates():
        blocking = [i for i in validate_workflow(workflow) if i.blocks_execution]
        assert blocking == [], f"{workflow.name}: {[i.message for i in blocking]}"


def test_the_request_estimate_counts_only_ai_nodes() -> None:
    assert expected_ai_requests(booking_complaint_template().nodes) == 2


# ------------------------------------------------------------------ palette


def test_webhook_and_database_are_offered_but_not_runnable() -> None:
    """Shown with a reason rather than silently missing or faked."""
    assert NodeType.WEBHOOK not in RUNNABLE_TYPES
    assert NodeType.DATABASE not in RUNNABLE_TYPES
    assert set(UNAVAILABLE_TYPES) == {NodeType.WEBHOOK, NodeType.DATABASE}
    for reason in UNAVAILABLE_TYPES.values():
        assert "not available" in reason.lower()


def test_this_project_contains_no_engine() -> None:
    """Section 7: the engine is built once; Project 4 is a client of it.

    Asserted against the source rather than against a docstring. A second
    executor would need to walk nodes itself — a loop over `next_id`, a node
    dispatch table, a status machine — so the test looks for those, and for the
    positive fact that execution happens by calling the shared engine.
    """
    import inspect

    import aiops_builder.handlers as handlers
    import aiops_builder.models as models
    import aiops_builder.router as router
    import aiops_builder.service as service
    import aiops_builder.templates as templates

    package = "\n".join(
        inspect.getsource(module) for module in (service, handlers, router, models, templates)
    )

    # Signs of a second engine.
    for marker in ("def _walk", "while node_id", "MAX_STEPS", "ExecutionStatus.RUNNING ="):
        assert marker not in package, f"{marker!r} suggests a second engine in Project 4"

    # And the positive fact: running means asking the shared engine.
    source = inspect.getsource(service)
    assert "WorkflowEngine(" in source
    assert ".run(" in source and ".resume(" in source


def test_a_seeding_failure_does_not_break_the_list() -> None:
    """Convenience must not be able to break the feature it decorates.

    Seeding runs inside the list endpoint so a first visitor does not meet an
    empty page. When the two were coupled, a seeding failure in production
    turned every request for the list — including ones needing nothing seeded —
    into a 500.
    """
    from aiops_builder.service import seed_templates
    from sqlalchemy.exc import OperationalError

    class _BrokenSession:
        rolled_back = False

        def scalar(self, *args: Any, **kwargs: Any) -> Any:
            raise OperationalError("SELECT 1", {}, Exception("connection timeout expired"))

        def rollback(self) -> None:
            self.rolled_back = True

    session = _BrokenSession()
    assert seed_templates(cast("Any", session)) == 0
    assert session.rolled_back, "a failed seed must not leave the transaction dirty"
