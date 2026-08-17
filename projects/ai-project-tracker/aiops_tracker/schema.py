"""Request, response and AI output shapes for the Project Tracker.

This module is where Section 13's "AI must explain *why* it assigned the
status" stops being a hope and becomes a type. `HealthAssessment.reasoning`
and `.contributing_factors` are required fields with no defaults, so a model
that returns `{"health": "red"}` has produced an **invalid** response: it fails
Pydantic validation before any of it reaches the database, and the caller gets
a provider error rather than a bare label rendered as if it meant something.

That is the whole difference between asking a model to explain itself and
requiring it to. A prompt that asks politely is honoured most of the time; a
required field is honoured every time or the response does not exist.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from aiops_tracker.models import Health, Priority, ProjectState, TaskStatus

# ------------------------------------------------------------------ AI output


class HealthAssessment(BaseModel):
    """The model's judgement of one project's health.

    Every field is an opinion about facts it was handed. The overdue count, the
    blocked count and the deadline arithmetic were computed before the model
    was called (Section 11's rule, applied here): the model interprets them and
    is not permitted to recompute them.
    """

    health: Health = Field(
        description="GREEN if on track, YELLOW if at risk, RED if it will miss without intervention."
    )
    reasoning: str = Field(
        min_length=1,
        description=(
            "Two to four sentences explaining this status, referring to the "
            "specific overdue, blocked and deadline figures supplied. A decision "
            "summary, not chain of thought."
        ),
    )
    contributing_factors: list[str] = Field(
        min_length=1,
        description=(
            "The concrete facts that drove the status — one short phrase each, "
            "for example '3 tasks overdue' or 'integration task blocked 9 days'."
        ),
    )
    confidence: str = Field(
        default="medium",
        description="How confident this assessment is: low, medium or high.",
    )


class SuggestedAction(BaseModel):
    """One recommended next step, tied to something real."""

    action: str = Field(min_length=1, description="What to do, phrased as an instruction.")
    rationale: str = Field(
        min_length=1, description="Why this is the most useful thing to do next."
    )
    task_id: str | None = Field(
        default=None,
        description="The id of the task this concerns, exactly as supplied. Null if it concerns the project as a whole.",
    )


class NextActions(BaseModel):
    """A short ranked list. Deliberately short — a list of twenty is a backlog."""

    actions: list[SuggestedAction] = Field(
        min_length=1, description="Between one and five actions, most urgent first."
    )


class ProjectSummary(BaseModel):
    """A paragraph a team lead could paste into a standup without editing."""

    summary: str = Field(
        min_length=1,
        description=(
            "Three to five sentences: where the project stands, what is at risk, "
            "and what happens next. Plain language, no bullet points, no preamble."
        ),
    )


class WeeklyReportContent(BaseModel):
    """The generated weekly status report (Section 13)."""

    executive_summary: str = Field(
        min_length=1, description="Three or four sentences for someone who reads nothing else."
    )
    highlights: list[str] = Field(
        default_factory=list, description="What genuinely moved this week."
    )
    concerns: list[str] = Field(
        default_factory=list, description="What is overdue, blocked, or slipping."
    )
    risks: list[str] = Field(
        default_factory=list, description="What might go wrong, drawn from the recorded risks."
    )
    recommended_actions: list[str] = Field(
        default_factory=list, description="What the team should do next week."
    )


# ------------------------------------------------------------------- requests


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=4000)
    owner: str = Field(default="", max_length=200)
    target_date: date | None = None
    risks: list[str] = Field(default_factory=list, max_length=20)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, max_length=200)
    state: ProjectState | None = None
    target_date: date | None = None
    risks: list[str] | None = Field(default=None, max_length=20)


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    owner: str = Field(default="", max_length=200)
    due_date: date | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    blocker_note: str | None = Field(default=None, max_length=2000)
    depends_on_id: str | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    owner: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    blocker_note: str | None = Field(default=None, max_length=2000)
    depends_on_id: str | None = None
    #: Explicit clears, because `None` in the fields above means "leave alone".
    clear_due_date: bool = False
    clear_depends_on: bool = False


# ------------------------------------------------------------------ responses


class TaskView(BaseModel):
    """One task, with the computed facts about it attached.

    `is_overdue` and `blocked_by` are calculated in code on every read. They
    are never stored and never generated, so they cannot drift from the data
    or be invented by a model.
    """

    id: str
    title: str
    owner: str
    due_date: date | None
    status: str
    priority: str
    blocker_note: str | None
    depends_on_id: str | None
    depends_on_title: str | None
    #: Past its due date and not done. Computed, not stored.
    is_overdue: bool
    #: Days past due; negative means days remaining. None when there is no date.
    days_overdue: int | None
    #: Title of the unfinished task this one waits on, if any.
    blocked_by: str | None


class ProjectFacts(BaseModel):
    """Everything measurable about a project. No AI involved in any of it.

    This is the object handed to the model when it assesses health, which is
    why it is a named type rather than an inline dict: the exact set of facts
    the judgement rests on is a thing worth being able to see, test, and show
    a reviewer next to the answer.
    """

    task_count: int
    done_count: int
    in_progress_count: int
    todo_count: int
    blocked_count: int
    overdue_count: int
    overdue_task_titles: list[str] = Field(default_factory=list)
    blocked_task_titles: list[str] = Field(default_factory=list)
    #: Tasks that cannot start because something unfinished precedes them.
    dependency_blocked_titles: list[str] = Field(default_factory=list)
    unassigned_count: int = 0
    completion_percent: float = 0.0
    days_to_target: int | None = None
    target_date: date | None = None
    risk_count: int = 0
    risks: list[str] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    """One project in the list view."""

    id: str
    name: str
    owner: str
    state: str
    target_date: date | None
    health: str | None
    health_reasoning: str | None
    task_count: int
    done_count: int
    overdue_count: int
    blocked_count: int
    completion_percent: float


class ProjectDetail(BaseModel):
    """Everything one project page needs."""

    id: str
    name: str
    description: str
    owner: str
    state: str
    target_date: date | None
    risks: list[str]
    health: str | None
    health_reasoning: str | None
    health_factors: list[str]
    health_confidence: str | None
    health_assessed_at: datetime | None
    next_actions: list[dict]
    summary: str | None
    facts: ProjectFacts
    tasks: list[TaskView]
    created_at: datetime


class UsageInfo(BaseModel):
    """Cost metadata for an AI step (Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class AssessResponse(BaseModel):
    project: ProjectDetail
    usage: UsageInfo


class WeeklyReportResponse(BaseModel):
    """The generated report, plus the facts it was generated from."""

    generated_at: datetime
    project_count: int
    content: WeeklyReportContent
    #: Per-project figures, so a reader can check the prose against the numbers.
    project_facts: list[ProjectListItem]
    usage: UsageInfo


class ProjectListResponse(BaseModel):
    projects: list[ProjectListItem]
    seeded: int = 0
    #: What one assessment would cost, so a button can say so before it is pressed.
    ai_requests_per_assessment: int = 1
