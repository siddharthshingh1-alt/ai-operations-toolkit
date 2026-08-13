"""Workflow execution (CLAUDE.md Section 7).

The engine walks a workflow node by node, keeping a shared `context` dict that
each node reads from and writes to, and recording a `NodeRun` for every step so
the whole execution is auditable.

Node behaviour is supplied by *handlers* registered against a `NodeType`. That
keeps the engine free of AI, email, and database concerns — those handlers are
registered by the projects that need them, as those projects get built.

Human-in-the-loop is enforced structurally, not by convention: reaching a
HUMAN_APPROVAL node pauses the run and returns. Nothing downstream of it can
execute until `resume()` is called with an approver.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiops_utils import Stopwatch, ValidationError, get_logger, utcnow
from aiops_workflow.types import (
    ExecutionStatus,
    NodeRun,
    NodeStatus,
    NodeType,
    Workflow,
    WorkflowExecution,
    WorkflowNode,
)

logger = get_logger(__name__)

#: A handler receives the node and the mutable run context, and returns the
#: output to record. Raising is a node failure.
NodeHandler = Callable[[WorkflowNode, dict[str, Any]], dict[str, Any]]

#: Guards against a workflow whose `next_id` links form a cycle.
MAX_STEPS = 100


class WorkflowEngine:
    """Executes workflow definitions.

    engine = WorkflowEngine()
    engine.register(NodeType.AI_CLASSIFICATION, my_classifier_handler)
    execution = engine.run(workflow, context={"email_id": "..."})
    """

    def __init__(self) -> None:
        self._handlers: dict[NodeType, NodeHandler] = {}
        self._register_builtins()

    # ------------------------------------------------------------- registration

    def register(self, node_type: NodeType, handler: NodeHandler) -> None:
        """Register the handler for a node type, replacing any existing one."""
        self._handlers[node_type] = handler

    def registered_types(self) -> list[NodeType]:
        """Node types that can currently execute. Shown in the builder palette."""
        return sorted(self._handlers, key=lambda node_type: node_type.value)

    def _register_builtins(self) -> None:
        """Handlers with no external dependencies, available from the start."""
        self.register(NodeType.TRIGGER, _handle_trigger)
        self.register(NodeType.CONDITION, _handle_condition)
        self.register(NodeType.TRANSFORM, _handle_transform)

    # ---------------------------------------------------------------- execution

    def run(
        self, workflow: Workflow, *, context: dict[str, Any] | None = None
    ) -> WorkflowExecution:
        """Execute `workflow` from its start node."""
        if not workflow.start_node_id:
            raise ValidationError(f"Workflow {workflow.name!r} has no start node.")
        if workflow.node(workflow.start_node_id) is None:
            raise ValidationError(
                f"Workflow {workflow.name!r} start node {workflow.start_node_id!r} does not exist."
            )

        execution = WorkflowExecution(workflow_id=workflow.id, context=dict(context or {}))
        return self._walk(workflow, execution, workflow.start_node_id)

    def resume(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        *,
        approved_by: str,
        approved: bool = True,
    ) -> WorkflowExecution:
        """Continue a run paused at a HUMAN_APPROVAL node."""
        if execution.status is not ExecutionStatus.AWAITING_APPROVAL:
            raise ValidationError("This execution is not awaiting approval.")
        if not approved_by.strip():
            raise ValidationError("An approver must be identified.")

        paused_node_id = execution.awaiting_node_id
        assert paused_node_id is not None  # implied by AWAITING_APPROVAL
        node = workflow.node(paused_node_id)
        if node is None:
            raise ValidationError(f"Approval node {paused_node_id!r} no longer exists.")

        # Record the decision itself as an auditable step.
        execution.node_runs.append(
            NodeRun(
                node_id=node.id,
                node_type=node.type,
                label=node.label,
                status=NodeStatus.SUCCEEDED if approved else NodeStatus.SKIPPED,
                output={"approved": approved, "approved_by": approved_by},
            )
        )
        execution.context["approved"] = approved
        execution.context["approved_by"] = approved_by
        execution.awaiting_node_id = None

        if not approved:
            execution.status = ExecutionStatus.SUCCEEDED
            execution.finished_at = utcnow()
            logger.info(
                "workflow rejected at approval step",
                extra={"execution_id": execution.id, "approved_by": approved_by},
            )
            return execution

        execution.status = ExecutionStatus.RUNNING
        return self._walk(workflow, execution, node.next_id)

    # ------------------------------------------------------------------ internals

    def _walk(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        start_node_id: str | None,
    ) -> WorkflowExecution:
        """Walk the graph from `start_node_id` until it ends, pauses, or fails."""
        node_id = start_node_id
        steps = 0

        while node_id is not None:
            steps += 1
            if steps > MAX_STEPS:
                return self._fail(
                    execution,
                    f"Workflow exceeded {MAX_STEPS} steps — it probably contains a loop.",
                )

            node = workflow.node(node_id)
            if node is None:
                return self._fail(execution, f"Node {node_id!r} does not exist.")

            # Human-in-the-loop: stop here and hand control back to a person.
            if node.type is NodeType.HUMAN_APPROVAL:
                execution.status = ExecutionStatus.AWAITING_APPROVAL
                execution.awaiting_node_id = node.id
                execution.node_runs.append(
                    NodeRun(
                        node_id=node.id,
                        node_type=node.type,
                        label=node.label,
                        status=NodeStatus.AWAITING_APPROVAL,
                    )
                )
                logger.info(
                    "workflow paused for approval",
                    extra={"execution_id": execution.id, "node_id": node.id},
                )
                return execution

            handler = self._handlers.get(node.type)
            if handler is None:
                return self._fail(
                    execution,
                    f"No handler registered for node type {node.type.value!r}.",
                )

            try:
                with Stopwatch() as sw:
                    output = handler(node, execution.context)
            except Exception as exc:  # noqa: BLE001 — recorded as a node failure
                execution.node_runs.append(
                    NodeRun(
                        node_id=node.id,
                        node_type=node.type,
                        label=node.label,
                        status=NodeStatus.FAILED,
                        duration_ms=sw.elapsed_ms,
                        error=str(exc),
                    )
                )
                return self._fail(execution, f"Node {node.label!r} failed: {exc}")

            execution.node_runs.append(
                NodeRun(
                    node_id=node.id,
                    node_type=node.type,
                    label=node.label,
                    status=NodeStatus.SUCCEEDED,
                    duration_ms=sw.elapsed_ms,
                    output=output,
                    ai_model=output.get("_ai_model"),
                    estimated_cost_usd=output.get("_estimated_cost_usd"),
                )
            )
            execution.context.update(output)

            # A CONDITION node picks the branch; every other node goes forward.
            if node.type is NodeType.CONDITION and not output.get("result", False):
                node_id = node.next_id_if_false
            else:
                node_id = node.next_id

        execution.status = ExecutionStatus.SUCCEEDED
        execution.finished_at = utcnow()
        logger.info(
            "workflow completed",
            extra={
                "execution_id": execution.id,
                "steps": len(execution.node_runs),
                "cost_usd": execution.total_cost_usd,
            },
        )
        return execution

    @staticmethod
    def _fail(execution: WorkflowExecution, message: str) -> WorkflowExecution:
        execution.status = ExecutionStatus.FAILED
        execution.error = message
        execution.finished_at = utcnow()
        logger.warning(
            "workflow failed",
            extra={"execution_id": execution.id, "reason": message},
        )
        return execution


# ------------------------------------------------------------- builtin handlers


def _handle_trigger(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
    """Entry point. Records the event name that started the run."""
    return {"triggered_by": node.config.get("event", "manual")}


def _handle_condition(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
    """Compare a context field against a value.

    Config: {"field": "severity", "operator": "eq", "value": "high"}
    Operators: eq, ne, gt, gte, lt, lte, contains, in.
    """
    field = node.config.get("field")
    if not field:
        raise ValidationError("Condition node needs a 'field' in its config.")

    operator = node.config.get("operator", "eq")
    expected = node.config.get("value")
    actual = context.get(field)

    comparisons: dict[str, Callable[[Any, Any], bool]] = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "contains": lambda a, b: b in (a or ""),
        "in": lambda a, b: a in (b or []),
    }
    compare = comparisons.get(operator)
    if compare is None:
        raise ValidationError(
            f"Unknown condition operator {operator!r}. "
            f"Expected one of: {', '.join(sorted(comparisons))}."
        )

    try:
        result = compare(actual, expected)
    except TypeError as exc:
        # e.g. comparing a string to a number — a definition error worth naming.
        raise ValidationError(
            f"Cannot apply {operator!r} to {type(actual).__name__} and "
            f"{type(expected).__name__} for field {field!r}."
        ) from exc

    return {"result": result, "evaluated_field": field, "evaluated_value": actual}


def _handle_transform(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
    """Copy and rename context fields.

    Config: {"mapping": {"target_field": "source_field"}}
    """
    mapping: dict[str, str] = node.config.get("mapping", {})
    if not mapping:
        raise ValidationError("Transform node needs a non-empty 'mapping' config.")
    return {target: context.get(source) for target, source in mapping.items()}
