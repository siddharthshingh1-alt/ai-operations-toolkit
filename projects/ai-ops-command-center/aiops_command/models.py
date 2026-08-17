"""Storage for the Ops Command Center (CLAUDE.md Section 17).

**One table, holding only this project's own output.**

That is the constraint Section 17 imposes — "this is an aggregator, not a new
source of truth, and must not duplicate logic that already exists". Nothing
about tasks, workflows, incidents or metrics is copied here. Those live in the
projects that own them and are re-read on every request.

What is stored is the narrative a model wrote, and the per-source signal counts
it was written from. The counts are not a cache of the sources: they exist so
the page can say "three signals have changed since this brief was generated"
instead of presenting yesterday's paragraph as this morning's situation. A
stored summary that cannot tell you it is stale is worse than no stored summary
at all.
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id


class OpsBrief(Base, TimestampMixin):
    """One generated daily brief."""

    __tablename__ = "ops_briefs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("brief"))

    #: The model's morning-brief paragraph.
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    #: Recommended actions, each already checked against a real signal id.
    actions: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    #: Per-source signal counts at the moment of generation, e.g.
    #: {"tracker": 4, "workflows": 1, "travel_ops": 2, "dashboard": 3}.
    #: Compared against a fresh gather to detect staleness.
    signal_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    #: Which sources answered when this was written, so a brief generated while
    #: a source was down does not silently look complete.
    unavailable_sources: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (Index("ix_ops_briefs_created_at", "created_at"),)
