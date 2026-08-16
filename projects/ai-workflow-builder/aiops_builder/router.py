"""HTTP routes for the Workflow Builder.

Mounted by `apps/api` under `/api/workflows`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aiops_builder import service
from aiops_builder.handlers import RUNNABLE_TYPES, UNAVAILABLE_TYPES
from aiops_builder.models import ExecutionRecord, WorkflowRecord
from aiops_config import Settings, get_settings
from aiops_db import get_db
from aiops_workflow import ValidationIssue, Workflow

router = APIRouter(prefix="/api/workflows", tags=["workflow-builder"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


# ------------------------------------------------------------------ shapes


class PaletteEntry(BaseModel):
    """One node type a builder may place, and whether it can run."""

    type: str
    label: str
    available: bool
    reason: str | None = None
    high_risk: bool = False


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str
    node_count: int
    is_read_only: bool
    blocking_issue_count: int
    ai_request_estimate: int


class ExecutionSummary(BaseModel):
    id: str
    status: str
    created_at: str
    node_count: int
    total_cost_usd: float


class WorkflowDetail(BaseModel):
    id: str
    name: str
    description: str
    is_read_only: bool
    definition: Workflow
    issues: list[ValidationIssue]
    ai_request_estimate: int
    executions: list[ExecutionSummary]


class SaveWorkflowRequest(BaseModel):
    definition: Workflow


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)


class RunRequest(BaseModel):
    """Starting context for a run.

    Free-form because a workflow's nodes decide what they read. The builder UI
    offers a single `input` field, which is what the shipped templates expect.
    """

    context: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=2, max_length=200)


class ExecutionDetail(BaseModel):
    id: str
    workflow_id: str
    status: str
    execution: dict


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowSummary]
    palette: list[PaletteEntry]
    seeded: int = 0


# ------------------------------------------------------------------ helpers


_LABELS = {
    "trigger": "Trigger",
    "condition": "Condition",
    "transform": "Transform",
    "ai_classification": "AI classification",
    "ai_extraction": "AI extraction",
    "ai_summarization": "AI summarisation",
    "ai_generation": "AI drafting",
    "human_approval": "Human approval",
    "notification": "Notification",
    "email": "Email",
    "webhook": "Webhook",
    "database": "Database",
}


def _palette() -> list[PaletteEntry]:
    from aiops_workflow import HIGH_RISK_NODES

    entries = [
        PaletteEntry(
            type=node_type.value,
            label=_LABELS.get(node_type.value, node_type.value),
            available=True,
            high_risk=node_type in HIGH_RISK_NODES,
        )
        for node_type in RUNNABLE_TYPES
    ]
    entries.extend(
        PaletteEntry(
            type=node_type.value,
            label=_LABELS.get(node_type.value, node_type.value),
            available=False,
            reason=reason,
            high_risk=True,
        )
        for node_type, reason in UNAVAILABLE_TYPES.items()
    )
    return entries


def _summary(record: WorkflowRecord) -> WorkflowSummary:
    definition = service.definition_of(record)
    issues = service.issues_for(record)
    return WorkflowSummary(
        id=record.id,
        name=record.name,
        description=record.description,
        node_count=len(definition.nodes),
        is_read_only=record.is_read_only,
        blocking_issue_count=sum(1 for issue in issues if issue.blocks_execution),
        ai_request_estimate=service.ai_request_estimate(record),
    )


def _execution_summary(stored: ExecutionRecord) -> ExecutionSummary:
    runs = stored.execution.get("node_runs", [])
    return ExecutionSummary(
        id=stored.id,
        status=stored.status,
        created_at=stored.created_at.isoformat(),
        node_count=len(runs),
        total_cost_usd=round(sum(float(run.get("estimated_cost_usd") or 0) for run in runs), 6),
    )


def _detail(db: Session, record: WorkflowRecord) -> WorkflowDetail:
    return WorkflowDetail(
        id=record.id,
        name=record.name,
        description=record.description,
        is_read_only=record.is_read_only,
        definition=service.definition_of(record),
        issues=service.issues_for(record),
        ai_request_estimate=service.ai_request_estimate(record),
        executions=[_execution_summary(e) for e in service.list_executions(db, record)],
    )


# ------------------------------------------------------------------- routes


@router.get("", response_model=WorkflowListResponse, summary="Saved workflows")
def list_workflows(db: DbDep) -> WorkflowListResponse:
    seeded = service.seed_templates(db)
    records = service.list_workflows(db)
    return WorkflowListResponse(
        workflows=[_summary(record) for record in records],
        palette=_palette(),
        seeded=seeded,
    )


@router.post("", response_model=WorkflowDetail, summary="Create a workflow")
def create_workflow(request: CreateWorkflowRequest, db: DbDep) -> WorkflowDetail:
    workflow = Workflow(name=request.name, description=request.description)
    record = service.create_workflow(db, workflow)
    return _detail(db, record)


@router.get("/{workflow_id}", response_model=WorkflowDetail, summary="One workflow")
def get_workflow(workflow_id: str, db: DbDep) -> WorkflowDetail:
    return _detail(db, service.get_workflow(db, workflow_id))


@router.put("/{workflow_id}", response_model=WorkflowDetail, summary="Save a workflow")
def save_workflow(workflow_id: str, request: SaveWorkflowRequest, db: DbDep) -> WorkflowDetail:
    """Store a definition, valid or not.

    An unfinished workflow is a normal state to leave the canvas in; refusing
    to save it would lose work. Whether it may *run* is decided at run time.
    """
    record = service.get_workflow(db, workflow_id)
    service.save_workflow(db, record, request.definition)
    return _detail(db, record)


@router.post("/{workflow_id}/duplicate", response_model=WorkflowDetail, summary="Duplicate")
def duplicate_workflow(workflow_id: str, db: DbDep) -> WorkflowDetail:
    record = service.get_workflow(db, workflow_id)
    return _detail(db, service.duplicate_workflow(db, record))


@router.delete("/{workflow_id}", summary="Delete a workflow")
def delete_workflow(workflow_id: str, db: DbDep) -> dict[str, str]:
    service.delete_workflow(db, service.get_workflow(db, workflow_id))
    return {"status": "deleted"}


@router.post("/{workflow_id}/run", response_model=ExecutionDetail, summary="Run a workflow")
def run_workflow(
    workflow_id: str, request: RunRequest, db: DbDep, settings: SettingsDep
) -> ExecutionDetail:
    """Execute a workflow with the shared engine.

    Refused if a high-risk step can be reached without a human approving it
    first — the engine enforces that, and this route surfaces the reason.
    """
    record = service.get_workflow(db, workflow_id)
    stored = service.run_workflow(db, record, context=request.context, settings=settings)
    return ExecutionDetail(
        id=stored.id,
        workflow_id=stored.workflow_id,
        status=stored.status,
        execution=stored.execution,
    )


@router.post(
    "/executions/{execution_id}/decision",
    response_model=ExecutionDetail,
    summary="Approve or reject a paused run",
)
def decide(
    execution_id: str, request: ApprovalRequest, db: DbDep, settings: SettingsDep
) -> ExecutionDetail:
    stored = service.get_execution(db, execution_id)
    stored = service.resume_execution(
        db,
        stored,
        approved_by=request.approved_by,
        approved=request.approved,
        settings=settings,
    )
    return ExecutionDetail(
        id=stored.id,
        workflow_id=stored.workflow_id,
        status=stored.status,
        execution=stored.execution,
    )
