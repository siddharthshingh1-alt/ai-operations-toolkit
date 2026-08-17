"""HTTP routes for the Project Tracker.

Mounted by `apps/api` under `/api/tracker`.

The four AI routes are all POSTs and all separate. That is deliberate: each one
is a request a person chose to spend, and grouping them behind a single
"analyse" endpoint would hide the cost of three requests behind one button.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from aiops_config import Settings, get_settings
from aiops_db import get_db
from aiops_docproc import Document, DocumentSection, ExportFormat, get_exporter
from aiops_tracker import service
from aiops_tracker.schema import (
    AssessResponse,
    CreateProjectRequest,
    CreateTaskRequest,
    ProjectDetail,
    ProjectListResponse,
    UpdateProjectRequest,
    UpdateTaskRequest,
    WeeklyReportContent,
    WeeklyReportResponse,
)

router = APIRouter(prefix="/api/tracker", tags=["project-tracker"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


# -------------------------------------------------------------- projects: CRUD


@router.get("/projects", response_model=ProjectListResponse, summary="Tracked projects")
def list_projects(db: DbDep) -> ProjectListResponse:
    seeded = service.seed_if_empty(db)
    projects = service.list_projects(db)
    return ProjectListResponse(
        projects=[service.list_item_of(p) for p in projects],
        seeded=seeded,
    )


@router.post("/projects", response_model=ProjectDetail, summary="Create a project")
def create_project(request: CreateProjectRequest, db: DbDep) -> ProjectDetail:
    return service.detail_of(service.create_project(db, request))


@router.get("/projects/{project_id}", response_model=ProjectDetail, summary="One project")
def get_project(project_id: str, db: DbDep) -> ProjectDetail:
    return service.detail_of(service.get_project(db, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectDetail, summary="Update a project")
def update_project(project_id: str, request: UpdateProjectRequest, db: DbDep) -> ProjectDetail:
    project = service.get_project(db, project_id)
    return service.detail_of(service.update_project(db, project, request))


@router.delete("/projects/{project_id}", summary="Delete a project")
def delete_project(project_id: str, db: DbDep) -> dict[str, str]:
    service.delete_project(db, service.get_project(db, project_id))
    return {"status": "deleted"}


# ----------------------------------------------------------------- tasks: CRUD


@router.post("/projects/{project_id}/tasks", response_model=ProjectDetail, summary="Add a task")
def create_task(project_id: str, request: CreateTaskRequest, db: DbDep) -> ProjectDetail:
    project = service.get_project(db, project_id)
    service.create_task(db, project, request)
    return service.detail_of(service.get_project(db, project_id))


@router.patch("/tasks/{task_id}", response_model=ProjectDetail, summary="Update a task")
def update_task(task_id: str, request: UpdateTaskRequest, db: DbDep) -> ProjectDetail:
    task = service.get_task(db, task_id)
    service.update_task(db, task, request)
    return service.detail_of(service.get_project(db, task.project_id))


@router.delete("/tasks/{task_id}", response_model=ProjectDetail, summary="Delete a task")
def delete_task(task_id: str, db: DbDep) -> ProjectDetail:
    task = service.get_task(db, task_id)
    project_id = task.project_id
    service.delete_task(db, task)
    return service.detail_of(service.get_project(db, project_id))


# --------------------------------------------------------------------- the AI
#
# One route per capability, one AI request each. Every one is triggered by a
# button; none of them run on a page load.


@router.post(
    "/projects/{project_id}/assess",
    response_model=AssessResponse,
    summary="Assess health (1 AI request)",
)
def assess(project_id: str, db: DbDep, settings: SettingsDep) -> AssessResponse:
    """Judge GREEN / YELLOW / RED, with the reasoning that produced it.

    The reasoning is not optional. `HealthAssessment` requires it, so a model
    that answers with a bare label fails validation and this route returns a
    provider error rather than a status nobody can check.
    """
    project = service.get_project(db, project_id)
    project, usage = service.assess_health(db, project, settings=settings)
    return AssessResponse(project=service.detail_of(project), usage=usage)


@router.post(
    "/projects/{project_id}/next-actions",
    response_model=AssessResponse,
    summary="Suggest next actions (1 AI request)",
)
def next_actions(project_id: str, db: DbDep, settings: SettingsDep) -> AssessResponse:
    project = service.get_project(db, project_id)
    project, usage = service.suggest_next_actions(db, project, settings=settings)
    return AssessResponse(project=service.detail_of(project), usage=usage)


@router.post(
    "/projects/{project_id}/summarize",
    response_model=AssessResponse,
    summary="Summarise project health (1 AI request)",
)
def summarize(project_id: str, db: DbDep, settings: SettingsDep) -> AssessResponse:
    project = service.get_project(db, project_id)
    project, usage = service.summarize_health(db, project, settings=settings)
    return AssessResponse(project=service.detail_of(project), usage=usage)


@router.post(
    "/report/weekly",
    response_model=WeeklyReportResponse,
    summary="Generate the weekly status report (1 AI request)",
)
def weekly(db: DbDep, settings: SettingsDep) -> WeeklyReportResponse:
    content, facts, usage = service.weekly_report(db, settings=settings)
    return WeeklyReportResponse(
        generated_at=datetime.now(UTC),
        project_count=len(facts),
        content=content,
        project_facts=facts,
        usage=usage,
    )


# --------------------------------------------------------------------- export


@router.post("/report/weekly/export", summary="Download a generated weekly report")
def export_report(
    content: WeeklyReportContent,
    fmt: Annotated[Literal["markdown", "html", "pdf"], Query(alias="format")] = "pdf",
) -> Response:
    """Render an already-generated report through the shared exporter.

    A POST taking the report as its body, rather than a GET that regenerates
    it: exporting must never spend an AI request, and it must produce exactly
    the document on the screen rather than a second, differently-worded one.
    """
    exporter = get_exporter(ExportFormat(fmt))
    document = Document(
        title="Weekly operations status report",
        subtitle=f"Generated {datetime.now(UTC).date().isoformat()}",
        metadata={"Source": "AI Operations Toolkit — Project Tracker", "Data": "Synthetic"},
        sections=[
            DocumentSection(heading="Executive summary", body=content.executive_summary),
            DocumentSection(heading="Highlights", bullets=content.highlights),
            DocumentSection(heading="Concerns", bullets=content.concerns),
            DocumentSection(heading="Risks", bullets=content.risks),
            DocumentSection(heading="Recommended actions", bullets=content.recommended_actions),
        ],
        footer=("Generated by an AI model from computed project figures. All data is synthetic."),
    )
    body = exporter.render(document)
    filename = f"weekly-status-report.{exporter.extension}"
    return Response(
        content=body,
        media_type=exporter.media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
