"""Workflow definitions and execution records (CLAUDE.md Section 7).

A workflow is: Trigger -> Step -> AI/Logic -> Condition -> Action -> Output.

This module owns the shape. `engine.py` owns the execution. Project 4 (the
visual builder) is a *client* of this engine — it edits these definitions and
renders these execution logs; it does not implement a second engine.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from aiops_utils import new_id, utcnow


class NodeType(StrEnum):
    """The reusable node palette from CLAUDE.md Section 7."""

    TRIGGER = "trigger"
    AI_CLASSIFICATION = "ai_classification"
    AI_EXTRACTION = "ai_extraction"
    AI_SUMMARIZATION = "ai_summarization"
    CONDITION = "condition"
    TRANSFORM = "transform"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DATABASE = "database"
    NOTIFICATION = "notification"
    HUMAN_APPROVAL = "human_approval"


#: Nodes that must never run unattended (CLAUDE.md Section 5, human-in-the-loop).
HIGH_RISK_NODES = frozenset({NodeType.EMAIL, NodeType.WEBHOOK, NodeType.DATABASE})


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"


class WorkflowNode(BaseModel):
    """One step in a workflow."""

    id: str = Field(default_factory=lambda: new_id("node"))
    type: NodeType
    label: str
    #: Node-specific settings, e.g. {"categories": [...]} for a classifier.
    config: dict[str, Any] = Field(default_factory=dict)
    #: Node to run next on success. None ends the workflow.
    next_id: str | None = None
    #: CONDITION nodes only: where to go when the condition is false.
    next_id_if_false: str | None = None


class Workflow(BaseModel):
    """A stored workflow definition."""

    id: str = Field(default_factory=lambda: new_id("wf"))
    name: str
    description: str = ""
    nodes: list[WorkflowNode] = Field(default_factory=list)
    start_node_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)

    def node(self, node_id: str) -> WorkflowNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)


class NodeRun(BaseModel):
    """The record of one node executing. This is the auditable unit."""

    node_id: str
    node_type: NodeType
    label: str
    status: NodeStatus
    started_at: datetime = Field(default_factory=utcnow)
    duration_ms: int = 0
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    #: Populated for AI nodes so cost rolls up per execution (Section 3d).
    ai_model: str | None = None
    estimated_cost_usd: float | None = None


class WorkflowExecution(BaseModel):
    """One run of a workflow, start to finish (or to a pause for approval)."""

    id: str = Field(default_factory=lambda: new_id("run"))
    workflow_id: str
    status: ExecutionStatus = ExecutionStatus.RUNNING
    context: dict[str, Any] = Field(default_factory=dict)
    node_runs: list[NodeRun] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    #: Set when the run paused on a HUMAN_APPROVAL node.
    awaiting_node_id: str | None = None
    error: str | None = None

    @property
    def total_cost_usd(self) -> float:
        """Total estimated AI spend for this run. Unpriced calls count as zero."""
        return round(sum(run.estimated_cost_usd or 0.0 for run in self.node_runs), 6)
