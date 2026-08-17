"""Database tables for the project tracker (CLAUDE.md Section 13).

Two tables: `tracked_projects` and `tracked_tasks`. Section 13 asks the tracker
to hold projects, tasks, owners, deadlines, dependencies, risks and blockers,
and all seven live here rather than in a model's head:

  * owner and deadline are columns on a task
  * a dependency is `depends_on_id`, a task pointing at another task
  * a blocker is `blocker_note` — free text, but only meaningful while the
    task's status is BLOCKED
  * risks belong to the project, because a risk is rarely about one task

The health assessment is stored alongside the project, and stored *with* its
reasoning. `health` and `health_reasoning` are written together by one code
path and there is no route that sets one without the other, so a label without
a justification is not a state this table can reach (Section 5).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id


class Health(StrEnum):
    """A project's health, assigned by the model and never without a reason."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ProjectState(StrEnum):
    """Where the project is in its life, set by a person rather than the model."""

    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"


class TaskStatus(StrEnum):
    """The tracker in Section 10's action-item schema, reused deliberately."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TrackedProject(Base, TimestampMixin):
    """One project being tracked."""

    __tablename__ = "tracked_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("prj"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ProjectState.ACTIVE.value
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Known risks, as plain strings. A risk is something that might happen;
    #: a blocker is something that already has. They are kept apart because a
    #: tracker that conflates them cannot tell you which projects need
    #: attention today and which need watching.
    risks: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # ---- the assessment: written by the model, always as a pair -------------
    health: Mapped[str | None] = mapped_column(String(16), nullable=True)
    health_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_factors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    health_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    health_assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: The model's suggested next actions, stored so the page survives a reload
    #: without spending another request.
    next_actions: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    #: The prose summary a lead can paste into a standup.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    tasks: Mapped[list[TrackedTask]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TrackedTask.created_at",
    )

    __table_args__ = (
        Index("ix_tracked_projects_state", "state"),
        Index("ix_tracked_projects_created_at", "created_at"),
    )


class TrackedTask(Base, TimestampMixin):
    """One task inside a project."""

    __tablename__ = "tracked_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tsk"))
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tracked_projects.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TaskStatus.TODO.value)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default=Priority.MEDIUM.value)

    #: Why this task is blocked. Only meaningful while `status` is BLOCKED —
    #: the service clears it when a task moves off that status, so a stale
    #: reason cannot outlive the block it described.
    blocker_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The task that must finish first. `SET NULL` rather than `CASCADE`:
    #: deleting a prerequisite should not silently delete the work that was
    #: waiting on it — that work still exists, it is simply no longer blocked.
    depends_on_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tracked_tasks.id", ondelete="SET NULL"), nullable=True
    )

    #: Ordering hint for the UI; not exposed as a feature.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped[TrackedProject] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tracked_tasks_project", "project_id"),
        Index("ix_tracked_tasks_status", "status"),
        Index("ix_tracked_tasks_due_date", "due_date"),
    )
