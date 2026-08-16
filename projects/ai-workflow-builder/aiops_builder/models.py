"""Storage for workflow definitions and their runs (CLAUDE.md Section 12).

The definition is stored as a whole JSON document rather than shredded into
node and edge tables. That is deliberate: `Workflow` is already a validated
Pydantic model owned by the engine, and normalising it here would mean this
project maintaining a second, drifting description of a shape it does not own.
Reading a row and calling `Workflow.model_validate` gives back exactly what the
engine expects, which is the whole point of Project 4 being a client rather
than a reimplementation.

Executions are stored the same way and never modified after a run finishes, so
the log is an audit record rather than a status field.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id


class WorkflowRecord(Base, TimestampMixin):
    """One saved workflow definition."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("wf"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: The engine's `Workflow` model, serialised whole.
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    #: Read-only rows exist to be looked at, not edited — the Travel Operations
    #: flow is stored this way so the builder can prove it renders a real
    #: workflow from another project without offering to break it.
    is_read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    executions: Mapped[list[ExecutionRecord]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="ExecutionRecord.created_at.desc()",
    )

    __table_args__ = (Index("ix_workflows_created_at", "created_at"),)


class ExecutionRecord(Base, TimestampMixin):
    """One run of one workflow."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("exe"))
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )

    #: Denormalised so the list view can be rendered without parsing every run.
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    #: The engine's `WorkflowExecution`, serialised whole. Includes every node
    #: run, its duration, its output and its AI cost.
    execution: Mapped[dict] = mapped_column(JSONB, nullable=False)

    workflow: Mapped[WorkflowRecord] = relationship(back_populates="executions")

    __table_args__ = (Index("ix_workflow_executions_workflow", "workflow_id"),)
