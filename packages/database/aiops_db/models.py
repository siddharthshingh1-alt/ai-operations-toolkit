"""Shared ORM models.

Only cross-cutting tables live here. Project-specific tables belong to their
own project package, added when that project is built.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aiops_db.base import Base, TimestampMixin, utcnow
from aiops_utils import new_id


class ActivityLog(Base, TimestampMixin):
    """Audit trail for every meaningful action (CLAUDE.md Sections 5, 22, 3d).

    Records who did what, when, with which model, how long it took, whether a
    human approved it, and what it cost.

    Deliberately stores no prompt or response bodies — Section 22 says not to
    log sensitive content unnecessarily. `summary` is a short, human-written
    description of the action, not the payload.
    """

    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("act"))

    # ----- who and what --------------------------------------------------
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    project: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ----- outcome -------------------------------------------------------
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="success")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    # ----- AI metadata (null for non-AI actions) --------------------------
    ai_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Null when the model has no known price — never a guessed figure.
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    from_demo_cache: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ----- human-in-the-loop (CLAUDE.md Section 5) ------------------------
    human_approved: Mapped[bool | None] = mapped_column(nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        # The dashboard's most common query: this project's recent activity.
        Index("ix_activity_log_project_occurred", "project", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<ActivityLog {self.id} {self.project}/{self.action} {self.status}>"
