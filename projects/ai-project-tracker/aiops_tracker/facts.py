"""Everything measurable about a project, computed without a model.

Section 13 lists "identify overdue tasks" and "identify blockers" among the AI
features. They are done here instead, in code, and the model is handed the
answers. That is a deliberate reading of the section rather than a shortcut,
for three reasons:

  * A date comparison is exact. A model asked to count overdue tasks will
    usually be right, and "usually" is the wrong property for the number a
    status report is built on.
  * It is free and instant. Spending a request from a twenty-a-day budget on
    arithmetic leaves less for the judgement, which is the part only a model
    can do.
  * It is the pattern the rest of this repository already follows — the
    Dashboard infers column types in code and asks the model only to
    interpret, and Travel Operations looks up affected bookings with no AI so
    the model cannot invent a booking reference.

What the model does with these facts — decide whether they add up to GREEN,
YELLOW or RED, and say why — is left entirely to it.
"""

from __future__ import annotations

from datetime import date

from aiops_tracker.models import TaskStatus, TrackedProject, TrackedTask
from aiops_tracker.schema import ProjectFacts, TaskView

#: How deep to walk a dependency chain before giving up.
#:
#: A cycle (A waits on B, B waits on A) would otherwise loop forever. The data
#: model permits one because `depends_on_id` is a plain foreign key and any
#: check at write time can be defeated by two writes in the wrong order. So the
#: walk is bounded and the bound is small: a chain longer than this is not a
#: dependency, it is a mistake, and either way the walk must terminate.
MAX_DEPENDENCY_DEPTH = 50


def is_overdue(task: TrackedTask, *, today: date) -> bool:
    """Past its due date and not finished.

    Due *today* is not overdue — the day is not over. This is the boundary
    that matters, and it is the one people get wrong.
    """
    if task.due_date is None:
        return False
    if task.status == TaskStatus.DONE.value:
        return False
    return task.due_date < today


def days_overdue(task: TrackedTask, *, today: date) -> int | None:
    """Days past due. Negative means days still remaining."""
    if task.due_date is None:
        return None
    return (today - task.due_date).days


def blocking_task(task: TrackedTask, by_id: dict[str, TrackedTask]) -> TrackedTask | None:
    """The nearest unfinished task this one is waiting on, if any.

    Walks the dependency chain rather than looking one step back, because a
    task whose prerequisite is itself waiting on something unfinished is just
    as stuck. The walk is bounded by `MAX_DEPENDENCY_DEPTH` and remembers where
    it has been, so a cycle terminates instead of hanging the request.
    """
    seen: set[str] = {task.id}
    current = task
    for _ in range(MAX_DEPENDENCY_DEPTH):
        parent_id = current.depends_on_id
        if parent_id is None or parent_id in seen:
            return None
        parent = by_id.get(parent_id)
        if parent is None:
            return None
        if parent.status != TaskStatus.DONE.value:
            return parent
        seen.add(parent.id)
        current = parent
    return None


def task_views(project: TrackedProject, *, today: date) -> list[TaskView]:
    """Every task with its computed state attached."""
    by_id = {task.id: task for task in project.tasks}
    views: list[TaskView] = []

    for task in sorted(project.tasks, key=lambda t: (t.position, t.created_at)):
        parent = by_id.get(task.depends_on_id) if task.depends_on_id else None
        blocker = blocking_task(task, by_id)
        views.append(
            TaskView(
                id=task.id,
                title=task.title,
                owner=task.owner,
                due_date=task.due_date,
                status=task.status,
                priority=task.priority,
                blocker_note=task.blocker_note,
                depends_on_id=task.depends_on_id,
                depends_on_title=parent.title if parent else None,
                is_overdue=is_overdue(task, today=today),
                days_overdue=days_overdue(task, today=today),
                blocked_by=blocker.title if blocker else None,
            )
        )
    return views


def project_facts(project: TrackedProject, *, today: date) -> ProjectFacts:
    """Compute every measurable fact about a project.

    This is the complete set of inputs the health assessment is allowed to
    reason from. Nothing here is generated, so a reader can check any sentence
    the model writes against a number on the same page.
    """
    views = task_views(project, today=today)

    done = [v for v in views if v.status == TaskStatus.DONE.value]
    overdue = [v for v in views if v.is_overdue]
    blocked = [v for v in views if v.status == TaskStatus.BLOCKED.value]
    dependency_blocked = [
        v for v in views if v.blocked_by is not None and v.status != TaskStatus.DONE.value
    ]

    total = len(views)
    completion = round(100.0 * len(done) / total, 1) if total else 0.0

    return ProjectFacts(
        task_count=total,
        done_count=len(done),
        in_progress_count=sum(1 for v in views if v.status == TaskStatus.IN_PROGRESS.value),
        todo_count=sum(1 for v in views if v.status == TaskStatus.TODO.value),
        blocked_count=len(blocked),
        overdue_count=len(overdue),
        overdue_task_titles=[v.title for v in overdue],
        blocked_task_titles=[v.title for v in blocked],
        dependency_blocked_titles=[v.title for v in dependency_blocked],
        unassigned_count=sum(1 for v in views if not v.owner.strip()),
        completion_percent=completion,
        days_to_target=(project.target_date - today).days if project.target_date else None,
        target_date=project.target_date,
        risk_count=len(project.risks or []),
        risks=list(project.risks or []),
    )
