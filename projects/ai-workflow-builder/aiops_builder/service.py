"""Domain logic for the Workflow Builder.

There is no execution logic in this module, and there must never be. Running a
workflow means handing the engine's own `Workflow` object to the engine's own
`run()`; resuming means calling its `resume()`. This project stores
definitions, renders them, and asks. CLAUDE.md Section 7 is explicit that the
engine is built once, and Project 4 is a client of it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_ai.base import AIProvider
from aiops_builder.handlers import expected_ai_requests, register_builder_handlers
from aiops_builder.models import ExecutionRecord, WorkflowRecord
from aiops_builder.templates import all_templates
from aiops_config import Settings, get_settings
from aiops_utils import NotFoundError, ValidationError, get_logger
from aiops_workflow import (
    ExecutionStatus,
    ValidationIssue,
    Workflow,
    WorkflowEngine,
    WorkflowExecution,
    validate_workflow,
)

logger = get_logger(__name__)


# ------------------------------------------------------------------ reading


def definition_of(record: WorkflowRecord) -> Workflow:
    """The stored document, back as the engine's own type."""
    return Workflow.model_validate(record.definition)


def list_workflows(db: Session) -> list[WorkflowRecord]:
    return list(db.scalars(select(WorkflowRecord).order_by(WorkflowRecord.created_at)))


def get_workflow(db: Session, workflow_id: str) -> WorkflowRecord:
    record = db.get(WorkflowRecord, workflow_id)
    if record is None:
        raise NotFoundError(
            f"No workflow {workflow_id!r}.", user_message="That workflow does not exist."
        )
    return record


def seed_templates(db: Session) -> int:
    """Install the starting workflows if none exist.

    A failure here must not take the list endpoint down with it. Seeding is a
    convenience — it stops the first visitor meeting an empty page — and the
    list of workflows is the actual feature. When the two were coupled, a
    seeding failure in production turned every request for the list into a 500,
    including requests that needed nothing seeded. Convenience that can break
    the thing it decorates is not convenience.
    """
    try:
        if db.scalar(select(WorkflowRecord.id).limit(1)) is not None:
            return 0

        created = 0
        for workflow, read_only in all_templates():
            db.add(
                WorkflowRecord(
                    id=workflow.id,
                    name=workflow.name,
                    description=workflow.description,
                    definition=workflow.model_dump(mode="json"),
                    is_read_only=read_only,
                )
            )
            created += 1
        db.flush()
        # Not `extra={"created": ...}`: `created` is a reserved LogRecord
        # attribute, and logging raises KeyError rather than overwrite it. That
        # turned a successful seed into a 500 on the very request that
        # performed it — the failure this function's own docstring is about.
        logger.info("seeded workflow templates", extra={"seeded": created})
        return created
    except Exception as exc:  # noqa: BLE001 — see the docstring: seeding may never break the list
        db.rollback()
        logger.warning(
            "could not seed workflow templates; continuing without them",
            extra={"error": str(exc).splitlines()[0][:200]},
        )
        return 0


# ------------------------------------------------------------------ writing


def create_workflow(db: Session, workflow: Workflow) -> WorkflowRecord:
    """Store a new definition, keyed by the id the document already carries.

    The `id=` is load-bearing. Without it the row's primary key came from the
    column default and the document kept its own — two independent
    `new_id("wf")` calls — so a freshly created workflow had a row id that
    disagreed with `definition.id`. Both are spelled `wf_...`, so nothing
    looked wrong anywhere; the editor saved to the document's id, no row had
    it, and the save came back "That workflow does not exist" while the empty
    workflow sat in the list.

    `save_workflow` already states the invariant this restores: the id in the
    document follows the row. `seed_templates` already honoured it. Creation
    was the one place that did not.
    """
    record = WorkflowRecord(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        definition=workflow.model_dump(mode="json"),
        is_read_only=False,
    )
    db.add(record)
    db.flush()
    return record


def save_workflow(db: Session, record: WorkflowRecord, workflow: Workflow) -> WorkflowRecord:
    """Replace a definition.

    Saving an invalid definition is allowed on purpose — a half-built workflow
    is a normal state to leave the canvas in, and refusing to save it would
    lose work. Running one is not allowed; that check happens at run time,
    where it matters.
    """
    if record.is_read_only:
        raise ValidationError(
            f"Workflow {record.id} is read-only.",
            user_message=(
                "This workflow is read-only. It is the definition another "
                "project runs for real — duplicate it to make changes."
            ),
        )

    # The id in the document always follows the row, so a copied definition
    # cannot overwrite the workflow it was copied from.
    workflow = workflow.model_copy(update={"id": record.id})
    record.name = workflow.name
    record.description = workflow.description
    record.definition = workflow.model_dump(mode="json")
    db.flush()
    return record


def duplicate_workflow(db: Session, record: WorkflowRecord) -> WorkflowRecord:
    """Copy a workflow, including a read-only one, as an editable draft."""
    workflow = definition_of(record)
    copy = Workflow(
        name=f"{workflow.name} (copy)",
        description=workflow.description,
        nodes=workflow.nodes,
        start_node_id=workflow.start_node_id,
    )
    return create_workflow(db, copy)


def delete_workflow(db: Session, record: WorkflowRecord) -> None:
    if record.is_read_only:
        raise ValidationError(
            f"Workflow {record.id} is read-only.",
            user_message="This workflow is read-only and cannot be deleted.",
        )
    db.delete(record)
    db.flush()


# ------------------------------------------------------------------ checking


def issues_for(record: WorkflowRecord) -> list[ValidationIssue]:
    """Problems with a stored definition.

    The `unconfigured` checks assume the engine's *default* Condition and
    Transform handlers, which read their settings from node config. A project
    that registers its own handler for those types does not need that config —
    Project 6's "Find affected bookings" transform is one — so those advisory
    issues are dropped for read-only workflows, which are exactly the ones
    owned by another project. The blocking checks still apply to everything.
    """
    issues = validate_workflow(definition_of(record))
    if record.is_read_only:
        return [issue for issue in issues if issue.code != "unconfigured"]
    return issues


def ai_request_estimate(record: WorkflowRecord) -> int:
    return expected_ai_requests(definition_of(record).nodes)


# ------------------------------------------------------------------ running


def _engine(
    settings: Settings | None = None, provider_override: AIProvider | None = None
) -> WorkflowEngine:
    return register_builder_handlers(
        WorkflowEngine(), settings=settings or get_settings(), provider_override=provider_override
    )


def _store(db: Session, record: WorkflowRecord, execution: WorkflowExecution) -> ExecutionRecord:
    stored = ExecutionRecord(
        workflow_id=record.id,
        status=execution.status.value,
        execution=execution.model_dump(mode="json"),
    )
    db.add(stored)
    db.flush()
    return stored


def run_workflow(
    db: Session,
    record: WorkflowRecord,
    *,
    context: dict[str, Any] | None = None,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
) -> ExecutionRecord:
    """Execute a saved workflow.

    Blocking problems are reported before anything runs, so a workflow that
    cannot finish does not spend AI requests discovering that. The engine
    performs the high-risk approval check itself as well — this one exists to
    give a builder every problem at once rather than one per attempt.
    """
    workflow = definition_of(record)

    blocking = [issue for issue in validate_workflow(workflow) if issue.blocks_execution]
    if blocking:
        raise ValidationError(
            "; ".join(issue.message for issue in blocking),
            user_message=blocking[0].message
            + (f" ({len(blocking) - 1} other problem(s) to fix.)" if len(blocking) > 1 else ""),
        )

    execution = _engine(settings, provider_override).run(workflow, context=dict(context or {}))
    stored = _store(db, record, execution)
    logger.info(
        "workflow run",
        extra={
            "project": "ai-workflow-builder",
            "workflow_id": record.id,
            "execution_id": execution.id,
            "status": execution.status.value,
            "estimated_cost_usd": execution.total_cost_usd,
        },
    )
    return stored


def resume_execution(
    db: Session,
    stored: ExecutionRecord,
    *,
    approved_by: str,
    approved: bool,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
) -> ExecutionRecord:
    """Continue a run paused at a human-approval step."""
    execution = WorkflowExecution.model_validate(stored.execution)
    if execution.status is not ExecutionStatus.AWAITING_APPROVAL:
        raise ValidationError(
            f"Execution {stored.id} is not awaiting approval.",
            user_message="That run is not waiting for a decision.",
        )

    workflow = definition_of(stored.workflow)
    execution = _engine(settings, provider_override).resume(
        workflow, execution, approved_by=approved_by, approved=approved
    )

    stored.status = execution.status.value
    stored.execution = execution.model_dump(mode="json")
    db.flush()
    logger.info(
        "workflow execution resumed",
        extra={
            "project": "ai-workflow-builder",
            "execution_id": stored.id,
            "approved": approved,
            "approved_by": approved_by,
        },
    )
    return stored


def list_executions(
    db: Session, record: WorkflowRecord, *, limit: int = 20
) -> list[ExecutionRecord]:
    return list(
        db.scalars(
            select(ExecutionRecord)
            .where(ExecutionRecord.workflow_id == record.id)
            .order_by(ExecutionRecord.created_at.desc())
            .limit(limit)
        )
    )


def get_execution(db: Session, execution_id: str) -> ExecutionRecord:
    stored = db.get(ExecutionRecord, execution_id)
    if stored is None:
        raise NotFoundError(
            f"No execution {execution_id!r}.", user_message="That run does not exist."
        )
    return stored
