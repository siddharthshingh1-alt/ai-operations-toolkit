"""Static checks on a workflow definition, before anything executes.

The important one is `unguarded_high_risk_nodes`.

`HIGH_RISK_NODES` has existed since the engine was written, declared as the set
of nodes that "must never run unattended" — and enforced by nothing. It was a
comment wearing the clothes of a rule. Anyone could have built

    trigger -> AI writes an email -> send it

with no human anywhere in it, and the engine would have run it.

This module makes the rule real, and `WorkflowEngine.run` refuses a definition
that breaks it. There is deliberately no flag to switch that off: an escape
hatch would put the rule back where it started, one keyword argument away from
meaning nothing.
"""

from __future__ import annotations

from collections import deque

from pydantic import BaseModel

from aiops_workflow.types import HIGH_RISK_NODES, NodeType, Workflow, WorkflowNode


class ValidationIssue(BaseModel):
    """One problem with a definition, in terms a builder UI can render."""

    #: Stable machine-readable code, for the frontend to branch on.
    code: str
    message: str
    #: The node the problem belongs to, when it belongs to one.
    node_id: str | None = None

    @property
    def blocks_execution(self) -> bool:
        """Whether this must be fixed before the workflow may run."""
        return self.code in _BLOCKING


_BLOCKING = frozenset(
    {
        "no_start_node",
        "start_node_missing",
        "dangling_next",
        "unguarded_high_risk",
        "loop",
    }
)


def _walk_order(workflow: Workflow) -> list[WorkflowNode]:
    """Every node reachable from the start, breadth-first."""
    if not workflow.start_node_id:
        return []

    seen: set[str] = set()
    order: list[WorkflowNode] = []
    queue: deque[str] = deque([workflow.start_node_id])

    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = workflow.node(node_id)
        if node is None:
            continue
        order.append(node)
        for nxt in (node.next_id, node.next_id_if_false):
            if nxt:
                queue.append(nxt)
    return order


def unguarded_high_risk_nodes(workflow: Workflow) -> list[WorkflowNode]:
    """High-risk nodes reachable without first passing a human approval.

    A node counts as guarded only if *every* route to it passes through a
    `HUMAN_APPROVAL` node. One unguarded route is enough to make it unsafe —
    the whole point is that it must not be possible to reach the action without
    a person, not that it is usually hard to.
    """
    if not workflow.start_node_id:
        return []

    # (node_id, has_passed_approval). The same node is explored twice at most,
    # once per approval state, which is what lets an unguarded route be found
    # even when a guarded one also exists.
    start = (workflow.start_node_id, False)
    seen: set[tuple[str, bool]] = {start}
    queue: deque[tuple[str, bool]] = deque([start])
    unguarded: dict[str, WorkflowNode] = {}

    while queue:
        node_id, approved = queue.popleft()
        node = workflow.node(node_id)
        if node is None:
            continue

        if node.type in HIGH_RISK_NODES and not approved:
            unguarded[node.id] = node

        now_approved = approved or node.type is NodeType.HUMAN_APPROVAL
        for nxt in (node.next_id, node.next_id_if_false):
            if not nxt:
                continue
            state = (nxt, now_approved)
            if state not in seen:
                seen.add(state)
                queue.append(state)

    # Definition order, so the message a user sees matches the canvas.
    order = {node.id: index for index, node in enumerate(workflow.nodes)}
    return sorted(unguarded.values(), key=lambda node: order.get(node.id, 0))


def has_loop(workflow: Workflow) -> bool:
    """True when following the links can revisit a node.

    The engine already survives a loop — it stops after a step limit — but
    failing at run time with "probably contains a loop" is a worse experience
    than refusing to save one.
    """
    if not workflow.start_node_id:
        return False

    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in done:
            return False
        node = workflow.node(node_id)
        if node is None:
            return False

        visiting.add(node_id)
        for nxt in (node.next_id, node.next_id_if_false):
            if nxt and walk(nxt):
                return True
        visiting.discard(node_id)
        done.add(node_id)
        return False

    return walk(workflow.start_node_id)


def validate_workflow(workflow: Workflow) -> list[ValidationIssue]:
    """Everything wrong with a definition, worst first.

    Returns issues rather than raising, so a builder can show all of them at
    once instead of making someone fix one, save, and discover the next.
    """
    issues: list[ValidationIssue] = []

    if not workflow.start_node_id:
        issues.append(
            ValidationIssue(
                code="no_start_node",
                message="This workflow has no starting step. Add a Trigger node.",
            )
        )
    elif workflow.node(workflow.start_node_id) is None:
        issues.append(
            ValidationIssue(
                code="start_node_missing",
                message="The starting step no longer exists. Pick a new one.",
            )
        )

    known = {node.id for node in workflow.nodes}
    for node in workflow.nodes:
        for label, nxt in (("next", node.next_id), ("false branch", node.next_id_if_false)):
            if nxt and nxt not in known:
                issues.append(
                    ValidationIssue(
                        code="dangling_next",
                        message=(
                            f"{node.label!r} points its {label} at a step that no longer exists."
                        ),
                        node_id=node.id,
                    )
                )

    if has_loop(workflow):
        issues.append(
            ValidationIssue(
                code="loop",
                message=(
                    "The steps form a loop, so the workflow would never finish. "
                    "Remove one of the connections that leads backwards."
                ),
            )
        )

    for node in unguarded_high_risk_nodes(workflow):
        issues.append(
            ValidationIssue(
                code="unguarded_high_risk",
                message=(
                    f"{node.label!r} performs an action that reaches the outside "
                    "world, and it can be reached without a human approving it "
                    "first. Add a Human approval step before it."
                ),
                node_id=node.id,
            )
        )

    # Nodes reachable but never configured produce a confusing run-time error;
    # naming them here is cheaper than debugging later.
    for node in _walk_order(workflow):
        if node.type is NodeType.CONDITION and not node.config.get("field"):
            issues.append(
                ValidationIssue(
                    code="unconfigured",
                    message=f"{node.label!r} needs a field to test.",
                    node_id=node.id,
                )
            )
        if node.type is NodeType.TRANSFORM and not node.config.get("mapping"):
            issues.append(
                ValidationIssue(
                    code="unconfigured",
                    message=f"{node.label!r} needs at least one field mapping.",
                    node_id=node.id,
                )
            )

    issues.sort(key=lambda issue: (not issue.blocks_execution, issue.code))
    return issues


def blocking_issues(workflow: Workflow) -> list[ValidationIssue]:
    """Only the issues that must be fixed before the workflow can run."""
    return [issue for issue in validate_workflow(workflow) if issue.blocks_execution]
