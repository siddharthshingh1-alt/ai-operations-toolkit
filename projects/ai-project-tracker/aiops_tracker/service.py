"""Domain logic for the Project Tracker (CLAUDE.md Section 13).

The split this module maintains: **facts are computed, judgements are asked
for**. `facts.py` produces the numbers; the four AI entry points here take
those numbers and return an opinion about them. No function in this file asks a
model how many tasks are overdue, and none ever should.

Each AI entry point is one request, invoked from its own route, called from its
own button. Nothing here runs on page load — on a free tier of roughly twenty
requests a day, a tracker that assessed every project on every visit would
spend the budget before anyone read anything.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult
from aiops_config import Settings, get_settings
from aiops_tracker import prompts
from aiops_tracker.facts import project_facts, task_views
from aiops_tracker.models import (
    Health,
    Priority,
    ProjectState,
    TaskStatus,
    TrackedProject,
    TrackedTask,
)
from aiops_tracker.schema import (
    CreateProjectRequest,
    CreateTaskRequest,
    HealthAssessment,
    NextActions,
    ProjectDetail,
    ProjectListItem,
    ProjectSummary,
    UpdateProjectRequest,
    UpdateTaskRequest,
    UsageInfo,
    WeeklyReportContent,
)
from aiops_tracker.seed import seed_projects
from aiops_utils import NotFoundError, ValidationError, get_logger

logger = get_logger(__name__)


def today() -> date:
    """The current date in UTC.

    A function rather than a call site so tests can freeze it, and so every
    overdue calculation in one request agrees with the others.
    """
    return datetime.now(UTC).date()


# ------------------------------------------------------------------ reading


def _loaded(statement: Any) -> Any:
    """Eager-load tasks; every read of a project needs them for its facts."""
    return statement.options(selectinload(TrackedProject.tasks))


def list_projects(db: Session) -> list[TrackedProject]:
    return list(
        db.scalars(_loaded(select(TrackedProject).order_by(TrackedProject.created_at.desc())))
    )


def get_project(db: Session, project_id: str) -> TrackedProject:
    project = db.scalar(_loaded(select(TrackedProject).where(TrackedProject.id == project_id)))
    if project is None:
        raise NotFoundError(
            f"No project {project_id!r}.", user_message="That project does not exist."
        )
    return project


def get_task(db: Session, task_id: str) -> TrackedTask:
    task = db.get(TrackedTask, task_id)
    if task is None:
        raise NotFoundError(f"No task {task_id!r}.", user_message="That task does not exist.")
    return task


def seed_if_empty(db: Session) -> int:
    """Install the demo projects if none exist.

    Wrapped the way the Workflow Builder's seed is, and for the reason that
    one taught: a convenience that can break the feature it decorates is not a
    convenience. A failure here leaves the list working and empty.
    """
    try:
        if db.scalar(select(TrackedProject.id).limit(1)) is not None:
            return 0
        created = seed_projects(db)
        db.flush()
        logger.info("seeded tracker projects", extra={"seeded": created})
        return created
    except Exception as exc:  # noqa: BLE001 — seeding may never break the list
        db.rollback()
        logger.warning(
            "could not seed tracker projects; continuing without them",
            extra={"error": str(exc).splitlines()[0][:200]},
        )
        return 0


# ------------------------------------------------------------------- writing


def create_project(db: Session, request: CreateProjectRequest) -> TrackedProject:
    project = TrackedProject(
        name=request.name.strip(),
        description=request.description.strip(),
        owner=request.owner.strip(),
        target_date=request.target_date,
        risks=[r.strip() for r in request.risks if r.strip()],
        state=ProjectState.ACTIVE.value,
    )
    db.add(project)
    db.flush()
    return project


def update_project(
    db: Session, project: TrackedProject, request: UpdateProjectRequest
) -> TrackedProject:
    if request.name is not None:
        project.name = request.name.strip()
    if request.description is not None:
        project.description = request.description.strip()
    if request.owner is not None:
        project.owner = request.owner.strip()
    if request.state is not None:
        project.state = request.state.value
    if request.target_date is not None:
        project.target_date = request.target_date
    if request.risks is not None:
        project.risks = [r.strip() for r in request.risks if r.strip()]
    db.flush()
    return project


def delete_project(db: Session, project: TrackedProject) -> None:
    db.delete(project)
    db.flush()


def _validate_dependency(
    db: Session, project: TrackedProject, task_id: str | None, depends_on_id: str | None
) -> None:
    """Refuse a dependency that is missing, cross-project, or circular.

    The walk here is what stops a cycle being *created*; `facts.blocking_task`
    is what stops one already in the data from hanging a request. Both are
    needed — this check cannot see a cycle formed by two concurrent writes,
    and the reader must survive whatever is on disk.
    """
    if depends_on_id is None:
        return
    if depends_on_id == task_id:
        raise ValidationError(
            "A task cannot depend on itself.",
            user_message="A task cannot depend on itself.",
        )

    parent = db.get(TrackedTask, depends_on_id)
    if parent is None:
        raise NotFoundError(
            f"No task {depends_on_id!r} to depend on.",
            user_message="The task this one should wait for does not exist.",
        )
    if parent.project_id != project.id:
        raise ValidationError(
            "Cross-project dependency rejected.",
            user_message="A task can only depend on another task in the same project.",
        )

    # Walk up from the proposed parent: if we reach this task, the edge closes
    # a loop.
    seen: set[str] = set()
    current: TrackedTask | None = parent
    while current is not None and current.id not in seen:
        if current.id == task_id:
            raise ValidationError(
                "Circular dependency rejected.",
                user_message=(
                    "That would create a circular dependency — the other task is "
                    "already waiting on this one."
                ),
            )
        seen.add(current.id)
        current = db.get(TrackedTask, current.depends_on_id) if current.depends_on_id else None


def create_task(db: Session, project: TrackedProject, request: CreateTaskRequest) -> TrackedTask:
    _validate_dependency(db, project, None, request.depends_on_id)
    task = TrackedTask(
        project_id=project.id,
        title=request.title.strip(),
        owner=request.owner.strip(),
        due_date=request.due_date,
        status=request.status.value,
        priority=request.priority.value,
        # A reason for being blocked is only meaningful on a blocked task.
        blocker_note=(request.blocker_note if request.status == TaskStatus.BLOCKED else None),
        depends_on_id=request.depends_on_id,
        position=len(project.tasks),
    )
    db.add(task)
    db.flush()
    db.refresh(project)
    return task


def update_task(db: Session, task: TrackedTask, request: UpdateTaskRequest) -> TrackedTask:
    project = get_project(db, task.project_id)

    if request.clear_depends_on:
        task.depends_on_id = None
    elif request.depends_on_id is not None:
        _validate_dependency(db, project, task.id, request.depends_on_id)
        task.depends_on_id = request.depends_on_id

    if request.title is not None:
        task.title = request.title.strip()
    if request.owner is not None:
        task.owner = request.owner.strip()
    if request.clear_due_date:
        task.due_date = None
    elif request.due_date is not None:
        task.due_date = request.due_date
    if request.priority is not None:
        task.priority = request.priority.value

    if request.status is not None:
        task.status = request.status.value
        # A blocker reason must not outlive the block it described.
        if request.status != TaskStatus.BLOCKED:
            task.blocker_note = None

    if request.blocker_note is not None and task.status == TaskStatus.BLOCKED.value:
        task.blocker_note = request.blocker_note

    db.flush()
    return task


def delete_task(db: Session, task: TrackedTask) -> None:
    db.delete(task)
    db.flush()


# ------------------------------------------------------------------- viewing


def detail_of(project: TrackedProject, *, on: date | None = None) -> ProjectDetail:
    day = on or today()
    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        owner=project.owner,
        state=project.state,
        target_date=project.target_date,
        risks=list(project.risks or []),
        health=project.health,
        health_reasoning=project.health_reasoning,
        health_factors=list(project.health_factors or []),
        health_confidence=project.health_confidence,
        health_assessed_at=project.health_assessed_at,
        next_actions=list(project.next_actions or []),
        summary=project.summary,
        facts=project_facts(project, today=day),
        tasks=task_views(project, today=day),
        created_at=project.created_at,
    )


def list_item_of(project: TrackedProject, *, on: date | None = None) -> ProjectListItem:
    facts = project_facts(project, today=on or today())
    return ProjectListItem(
        id=project.id,
        name=project.name,
        owner=project.owner,
        state=project.state,
        target_date=project.target_date,
        health=project.health,
        health_reasoning=project.health_reasoning,
        task_count=facts.task_count,
        done_count=facts.done_count,
        overdue_count=facts.overdue_count,
        blocked_count=facts.blocked_count,
        completion_percent=facts.completion_percent,
    )


# ------------------------------------------------------------------------ AI


def _usage_of(result: AIResult[Any]) -> UsageInfo:
    return UsageInfo(
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_demo_cache=getattr(result, "from_demo_cache", False),
    )


def _provider(
    settings: Settings | None, override: AIProvider | None
) -> tuple[AIProvider, Settings]:
    resolved = settings or get_settings()
    return (override or get_provider(resolved)), resolved


def assess_health(
    db: Session,
    project: TrackedProject,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    on: date | None = None,
) -> tuple[TrackedProject, UsageInfo]:
    """Ask the model to judge this project's health, and to justify it.

    One AI request. The facts it reasons over are computed first and passed in;
    `HealthAssessment` requires `reasoning` and `contributing_factors`, so a
    bare label fails validation inside the provider and never reaches here.
    """
    day = on or today()
    provider, resolved = _provider(settings, provider_override)
    facts = project_facts(project, today=day)

    result = provider.generate_structured_output(
        prompts.assessment_prompt(project.name, project.description, facts),
        output_model=HealthAssessment,
        system=prompts.ASSESS_SYSTEM,
    )
    assessment = result.value

    project.health = assessment.health.value
    project.health_reasoning = assessment.reasoning
    project.health_factors = list(assessment.contributing_factors)
    project.health_confidence = assessment.confidence
    project.health_assessed_at = datetime.now(UTC)
    db.flush()

    logger.info(
        "project health assessed",
        extra={
            "project": "ai-project-tracker",
            "project_id": project.id,
            "health": project.health,
            "model": result.model,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )
    _ = resolved
    return project, _usage_of(result)


def suggest_next_actions(
    db: Session,
    project: TrackedProject,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    on: date | None = None,
) -> tuple[TrackedProject, UsageInfo]:
    """Ask for a short ranked list of what to do next. One AI request."""
    day = on or today()
    provider, _ = _provider(settings, provider_override)
    facts = project_facts(project, today=day)

    open_tasks = [
        (t.id, t.title, t.status, t.owner)
        for t in project.tasks
        if t.status != TaskStatus.DONE.value
    ]
    if not open_tasks:
        raise ValidationError(
            "Every task on this project is done.",
            user_message=(
                "Every task here is done, so there is nothing to recommend. Add a task first."
            ),
        )

    result = provider.generate_structured_output(
        prompts.next_actions_prompt(project.name, facts, open_tasks),
        output_model=NextActions,
        system=prompts.NEXT_ACTIONS_SYSTEM,
    )

    known = {t.id for t in project.tasks}
    stored: list[dict] = []
    for action in result.value.actions:
        # Drop an id the model invented rather than storing a link that leads
        # nowhere. The advice survives; only the false reference is removed.
        task_id = action.task_id if action.task_id in known else None
        if action.task_id and task_id is None:
            logger.warning(
                "model referenced an unknown task; dropping the reference",
                extra={"project_id": project.id, "claimed_task_id": action.task_id[:64]},
            )
        stored.append({"action": action.action, "rationale": action.rationale, "task_id": task_id})

    project.next_actions = stored
    db.flush()
    return project, _usage_of(result)


def summarize_health(
    db: Session,
    project: TrackedProject,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    on: date | None = None,
) -> tuple[TrackedProject, UsageInfo]:
    """Ask for a standup-ready paragraph. One AI request."""
    day = on or today()
    provider, _ = _provider(settings, provider_override)
    facts = project_facts(project, today=day)

    result = provider.generate_structured_output(
        prompts.summary_prompt(project.name, facts, project.health),
        output_model=ProjectSummary,
        system=prompts.SUMMARY_SYSTEM,
    )
    project.summary = result.value.summary
    db.flush()
    return project, _usage_of(result)


def weekly_report(
    db: Session,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    on: date | None = None,
) -> tuple[WeeklyReportContent, list[ProjectListItem], UsageInfo]:
    """Generate the weekly status report across every active project.

    One AI request for the whole report rather than one per project: a report
    is a single document with a single argument, and stitching per-project
    paragraphs together produces something that reads like a mail merge.
    """
    day = on or today()
    provider, _ = _provider(settings, provider_override)

    projects = [p for p in list_projects(db) if p.state != ProjectState.DONE.value]
    if not projects:
        raise ValidationError(
            "No active projects to report on.",
            user_message="There are no active projects to report on. Add one first.",
        )

    blocks = [
        prompts.project_block(p.name, p.health, project_facts(p, today=day)) for p in projects
    ]
    result = provider.generate_structured_output(
        prompts.report_prompt(blocks, day.isoformat()),
        output_model=WeeklyReportContent,
        system=prompts.REPORT_SYSTEM,
    )

    logger.info(
        "weekly report generated",
        extra={
            "project": "ai-project-tracker",
            "projects_covered": len(projects),
            "model": result.model,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )
    return (
        result.value,
        [list_item_of(p, on=day) for p in projects],
        _usage_of(result),
    )


__all__ = [
    "Health",
    "Priority",
    "TaskStatus",
    "assess_health",
    "create_project",
    "create_task",
    "delete_project",
    "delete_task",
    "detail_of",
    "get_project",
    "get_task",
    "list_item_of",
    "list_projects",
    "seed_if_empty",
    "suggest_next_actions",
    "summarize_health",
    "today",
    "update_project",
    "update_task",
    "weekly_report",
]
