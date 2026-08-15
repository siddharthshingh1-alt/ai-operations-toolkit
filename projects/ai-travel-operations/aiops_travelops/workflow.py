"""The delay-incident workflow, expressed as a workflow definition.

This is the flow CLAUDE.md Section 14 names:

    Flight delay detected -> find affected bookings -> classify severity
    -> create operations task -> draft communication -> human approval

It is built on the shared engine from Section 7 rather than as bespoke
procedural code, and that choice is doing real work rather than being tidy:

**The pause is structural.** `WorkflowEngine` stops at a `HUMAN_APPROVAL` node
and returns. There is no argument that skips it and no code path that walks
past it — the only way to reach the node after it is `engine.resume()`, which
demands an approver. The send node therefore *cannot* execute unapproved, and
that is a property of the graph rather than a rule someone remembered to
follow. It is also the second of two independent guards: the email adapter's
`send_reply` requires `approved_by` as well, so an unapproved send cannot even
be expressed.

**The run is the audit trail.** Every node records what it produced, how long
it took and what it cost, including the approval decision itself. Section 5
asks who initiated an action, when, with what input and whether a human
approved — one stored `WorkflowExecution` answers all of it.
"""

from __future__ import annotations

from typing import Any

from aiops_workflow import NodeType, Workflow, WorkflowNode

# Node ids are fixed rather than generated so a stored execution stays readable
# after a restart, and so tests can refer to a step by name.
TRIGGER_ID = "n_trigger"
LOOKUP_ID = "n_lookup"
ASSESS_ID = "n_assess"
DRAFT_ID = "n_draft"
APPROVAL_ID = "n_approval"
RECORD_ID = "n_record"


def incident_workflow() -> Workflow:
    """The definition. Handlers are registered separately, in `service.py`."""
    return Workflow(
        id="wf_travel_incident",
        name="Travel incident response",
        description=(
            "From an incident report to an approved agent communication. "
            "Pauses for a human before anything is said to a partner."
        ),
        start_node_id=TRIGGER_ID,
        nodes=[
            WorkflowNode(
                id=TRIGGER_ID,
                type=NodeType.TRIGGER,
                label="Incident reported",
                next_id=LOOKUP_ID,
            ),
            WorkflowNode(
                id=LOOKUP_ID,
                type=NodeType.TRANSFORM,
                label="Find affected bookings",
                # Deterministic on purpose. Which bookings are affected is a
                # matter of record, and asking a model to decide it would put a
                # guess where a lookup belongs.
                next_id=ASSESS_ID,
            ),
            WorkflowNode(
                id=ASSESS_ID,
                type=NodeType.AI_CLASSIFICATION,
                label="Assess severity",
                config={"outputs": ["severity", "reasoning_summary", "recommended_action"]},
                next_id=DRAFT_ID,
            ),
            WorkflowNode(
                id=DRAFT_ID,
                type=NodeType.AI_GENERATION,
                label="Draft agent communications",
                next_id=APPROVAL_ID,
            ),
            WorkflowNode(
                id=APPROVAL_ID,
                type=NodeType.HUMAN_APPROVAL,
                label="Operations approval",
                # Everything after this node is unreachable until a person
                # approves. That is the whole point of the node's existence.
                next_id=RECORD_ID,
            ),
            WorkflowNode(
                id=RECORD_ID,
                type=NodeType.EMAIL,
                label="Record approved communication",
                next_id=None,
            ),
        ],
    )


def approval_is_reachable_only_after(workflow: Workflow, node_id: str) -> bool:
    """True when `node_id` sits downstream of the approval node.

    Exists so a test can assert the graph's shape rather than trusting a
    comment: if someone rewires the send node to bypass approval, the test that
    calls this fails.
    """
    approval = workflow.node(APPROVAL_ID)
    if approval is None:
        return False

    reachable_before: set[str] = set()
    current = workflow.start_node_id
    while current is not None and current != APPROVAL_ID:
        node = workflow.node(current)
        if node is None:
            break
        reachable_before.add(node.id)
        current = node.next_id

    return node_id not in reachable_before


def trigger_context(**values: Any) -> dict[str, Any]:
    """Starting context for a run. Kept in one place so tests and the service agree."""
    return dict(values)
