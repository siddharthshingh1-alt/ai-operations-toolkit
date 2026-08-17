"""Collect operational signals from the projects that already produce them.

This module is the whole argument of Project 9 (CLAUDE.md Section 17), so it is
worth being precise about what it does and does not do.

**It does not compute anything about tasks, workflows, incidents or metrics.**
Every collector below calls the owning project's own read functions and reports
what they return. Where a source already phrases a fact, that phrasing is
reused verbatim rather than restated — `Trend.describe()` and
`Anomaly.describe()` from the analytics service are printed exactly as they
come, so the wording of an observation keeps a single home. Change how an
anomaly reads over there and it changes here, because there is no second copy.

**Each collector is wrapped independently.** A source that raises produces a
`SourceStatus` marked unavailable, carrying the reason, and the other three
still produce their signals. An aggregator that goes blank because one of four
inputs failed is worse than useless: it hides the three that were working.

The dependency direction is one-way. This package imports from Projects 3, 4, 5
and 6; none of them import from it, and none of them know it exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_utils import get_logger

logger = get_logger(__name__)


#: Where each source's signals link back to. Section 17 requires every item to
#: point at the project that owns it — this aggregator is a view, and a view
#: that cannot be traced to its source is just another number to distrust.
SOURCE_LINKS: dict[str, str] = {
    "tracker": "/tasks",
    "workflows": "/workflows",
    "travel_ops": "/travel-ops",
    "dashboard": "/",
}

SOURCE_LABELS: dict[str, str] = {
    "tracker": "Project Tracker",
    "workflows": "Workflow Builder",
    "travel_ops": "Travel Operations",
    "dashboard": "Operations Dashboard",
}


@dataclass
class Signal:
    """One thing worth someone's attention, as its owning project reported it."""

    id: str
    source: str
    severity: str  # "critical" | "warning" | "info"
    title: str
    detail: str
    #: Deep link to the item itself, or to the source project's page.
    link: str
    #: Computed ordering weight. Not a model's opinion — see `rank`.
    score: int = 0


@dataclass
class SourceStatus:
    """Whether one source answered, and what it said if it did not."""

    source: str
    available: bool
    detail: str = ""
    signal_count: int = 0


@dataclass
class SignalSet:
    """Everything collected in one pass, plus the health of each source."""

    signals: list[Signal] = field(default_factory=list)
    sources: list[SourceStatus] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def available_sources(self) -> int:
        return sum(1 for s in self.sources if s.available)

    def counts(self) -> dict[str, int]:
        """The per-source signal counts, for staleness comparison."""
        return {s.source: s.signal_count for s in self.sources}


# --------------------------------------------------------------------- scoring
#
# Ranking is computed, not asked for. A model deciding which of two problems
# matters more would be a judgement nobody could check and would cost a request
# every time the page loaded. The weights are crude on purpose: they only have
# to put the urgent things near the top.

_SEVERITY_WEIGHT = {"critical": 100, "warning": 40, "info": 10}


def _score(severity: str, bump: int = 0) -> int:
    return _SEVERITY_WEIGHT.get(severity, 10) + bump


def rank(signals: list[Signal]) -> list[Signal]:
    """Most urgent first. Deterministic, so the same data ranks the same way."""
    return sorted(signals, key=lambda s: (-s.score, s.source, s.title))


# ------------------------------------------------------------------ collectors


def collect_tracker(db: Session, *, today: date | None = None) -> tuple[list[Signal], str]:
    """Overdue and blocked work, and any project the AI has judged unhealthy.

    Calls the tracker's own `list_projects` and `list_item_of`. The overdue and
    blocked counts are the ones it computed; this does not re-derive them.
    """
    from aiops_tracker import service as tracker

    signals: list[Signal] = []
    projects = tracker.list_projects(db)

    for project in projects:
        item = tracker.list_item_of(project, on=today)
        if item.state == "done":
            continue

        if item.overdue_count:
            severity = "critical" if item.overdue_count >= 3 else "warning"
            signals.append(
                Signal(
                    id=f"tracker:{item.id}:overdue",
                    source="tracker",
                    severity=severity,
                    title=f"{item.overdue_count} overdue task(s) on {item.name}",
                    detail=(
                        f"{item.done_count} of {item.task_count} tasks done "
                        f"({item.completion_percent}% complete)."
                    ),
                    link="/tasks",
                    score=_score(severity, item.overdue_count),
                )
            )

        if item.blocked_count:
            signals.append(
                Signal(
                    id=f"tracker:{item.id}:blocked",
                    source="tracker",
                    severity="warning",
                    title=f"{item.blocked_count} blocked task(s) on {item.name}",
                    detail="Blocked work does not move until someone clears the blocker.",
                    link="/tasks",
                    score=_score("warning", item.blocked_count),
                )
            )

        # The health label is the tracker's AI judgement, already made and
        # already justified. Repeating it here costs nothing and asks nothing.
        if item.health == "red":
            signals.append(
                Signal(
                    id=f"tracker:{item.id}:health",
                    source="tracker",
                    severity="critical",
                    title=f"{item.name} is RED",
                    detail=item.health_reasoning or "Assessed RED by the Project Tracker.",
                    link="/tasks",
                    score=_score("critical", 5),
                )
            )

    return signals, f"{len(projects)} project(s) read."


def collect_workflows(db: Session) -> tuple[list[Signal], str]:
    """Runs paused for a human, and workflows that cannot run at all.

    Calls the builder's own `list_workflows` and `issues_for`, and reads
    execution rows by the status the engine set on them.
    """
    from aiops_builder import service as builder
    from aiops_builder.models import ExecutionRecord

    signals: list[Signal] = []
    workflows = builder.list_workflows(db)
    by_id = {w.id: w for w in workflows}

    waiting = list(
        db.scalars(
            select(ExecutionRecord)
            .where(ExecutionRecord.status == "awaiting_approval")
            .order_by(ExecutionRecord.created_at.desc())
            .limit(25)
        )
    )
    for execution in waiting:
        workflow = by_id.get(execution.workflow_id)
        name = workflow.name if workflow else execution.workflow_id
        signals.append(
            Signal(
                id=f"workflows:{execution.id}:approval",
                source="workflows",
                severity="critical",
                title=f"A run of “{name}” is waiting for approval",
                detail=(
                    "The engine stopped at a human-approval step. Nothing past it "
                    "has run, and nothing will until someone decides."
                ),
                link=f"/workflows/{execution.workflow_id}",
                score=_score("critical", 10),
            )
        )

    for workflow in workflows:
        blocking = [issue for issue in builder.issues_for(workflow) if issue.blocks_execution]
        if blocking:
            signals.append(
                Signal(
                    id=f"workflows:{workflow.id}:blocked",
                    source="workflows",
                    severity="warning",
                    title=f"“{workflow.name}” cannot run",
                    detail=blocking[0].message,
                    link=f"/workflows/{workflow.id}",
                    score=_score("warning", len(blocking)),
                )
            )

    return signals, f"{len(workflows)} workflow(s), {len(waiting)} run(s) awaiting approval."


def collect_travel_ops(db: Session) -> tuple[list[Signal], str]:
    """Incidents that are open, unassessed, or holding drafts for approval.

    Calls Travel Operations' own `list_incidents` and `to_summary`; the
    affected-booking counts are the ones its deterministic lookup produced.
    """
    from aiops_travelops import service as travelops

    signals: list[Signal] = []
    incidents = travelops.list_incidents(db)

    for incident in incidents:
        summary = travelops.to_summary(incident)
        if summary.status == "resolved":
            continue

        if summary.awaiting_approval_count:
            signals.append(
                Signal(
                    id=f"travel_ops:{summary.id}:approval",
                    source="travel_ops",
                    severity="critical",
                    title=f"{summary.awaiting_approval_count} draft(s) awaiting approval",
                    detail=f"{summary.title} — nothing reaches an agency until someone approves.",
                    link=f"/travel-ops/{summary.id}",
                    score=_score("critical", summary.awaiting_approval_count),
                )
            )

        if summary.severity in {"high", "critical"}:
            signals.append(
                Signal(
                    id=f"travel_ops:{summary.id}:severity",
                    source="travel_ops",
                    severity="critical",
                    title=f"{summary.severity.upper()} incident: {summary.title}",
                    detail=(
                        f"{summary.affected_count} booking(s) affected, "
                        f"₹{summary.affected_value_inr:,.0f} at risk."
                    ),
                    link=f"/travel-ops/{summary.id}",
                    score=_score("critical", summary.affected_count),
                )
            )
        elif summary.severity is None and summary.affected_count:
            signals.append(
                Signal(
                    id=f"travel_ops:{summary.id}:unassessed",
                    source="travel_ops",
                    severity="warning",
                    title=f"Unassessed incident: {summary.title}",
                    detail=(
                        f"{summary.affected_count} booking(s) affected and nobody has "
                        "judged how bad it is yet."
                    ),
                    link=f"/travel-ops/{summary.id}",
                    score=_score("warning", summary.affected_count),
                )
            )

    return signals, f"{len(incidents)} incident(s) read."


#: The bundled dataset the brief reads.
#:
#: The Operations Dashboard analyses an uploaded file and persists nothing, so
#: there is no "current KPI state" to aggregate. Reading a bundled dataset is
#: the honest option; giving Project 3 a persistence layer purely so Project 9
#: could read it would be the duplication Section 17 forbids. The UI says which
#: dataset this is, so nobody mistakes it for live production data.
DASHBOARD_DATASET = "operations_metrics"


def collect_dashboard(*, dataset: str = DASHBOARD_DATASET) -> tuple[list[Signal], str]:
    """Anomalies and trend movements, in the analytics service's own words.

    `Trend.describe()` and `Anomaly.describe()` are printed verbatim. This is
    the clearest case of the rule: the sentence describing an anomaly is
    written once, in the service that detects it.
    """
    from aiops_dashboard.analysis import analyse
    from aiops_dashboard.samples import load_sample

    analysis = analyse(load_sample(dataset), dataset=dataset)
    signals: list[Signal] = []

    for anomaly in analysis.anomalies[:5]:
        severity = "warning" if abs(anomaly.z_score) >= 3 else "info"
        signals.append(
            Signal(
                id=f"dashboard:{anomaly.column}:{anomaly.index_label}",
                source="dashboard",
                severity=severity,
                title=f"Anomaly in {anomaly.column}",
                detail=anomaly.describe(),
                link="/",
                score=_score(severity, int(abs(anomaly.z_score))),
            )
        )

    for trend in analysis.trends:
        # Only movements worth a mention. A metric that drifted 2% is noise in
        # a morning brief.
        if abs(trend.change_pct) < 15 or trend.direction == "flat":
            continue
        severity = "warning" if abs(trend.change_pct) >= 30 else "info"
        signals.append(
            Signal(
                id=f"dashboard:{trend.column}:trend",
                source="dashboard",
                severity=severity,
                title=f"{trend.column} is {trend.direction}",
                detail=trend.describe(),
                link="/",
                score=_score(severity, int(abs(trend.change_pct) // 10)),
            )
        )

    return signals, f"{analysis.row_count} rows of {dataset} analysed."


# ------------------------------------------------------------------ the gather

#: (source key, callable). Each entry is invoked inside its own guard.
_COLLECTORS: list[tuple[str, str]] = [
    ("tracker", "collect_tracker"),
    ("workflows", "collect_workflows"),
    ("travel_ops", "collect_travel_ops"),
    ("dashboard", "collect_dashboard"),
]


def gather(db: Session, *, today: date | None = None) -> SignalSet:
    """Collect from every source, surviving any of them failing.

    Every collector runs inside its own try/except. A source that raises is
    reported as unavailable *with the reason*, and the brief is still produced
    from the rest. The reason matters: "unavailable" alone tells an operator
    nothing they can act on.
    """
    result = SignalSet()

    for source, _name in _COLLECTORS:
        try:
            if source == "tracker":
                signals, detail = collect_tracker(db, today=today)
            elif source == "workflows":
                signals, detail = collect_workflows(db)
            elif source == "travel_ops":
                signals, detail = collect_travel_ops(db)
            else:
                signals, detail = collect_dashboard()
        except Exception as exc:  # noqa: BLE001 — one source may never take the brief down
            reason = str(exc).splitlines()[0][:200] if str(exc) else exc.__class__.__name__
            logger.warning(
                "signal source unavailable; continuing without it",
                extra={"signal_source": source, "error": reason},
            )
            result.sources.append(
                SourceStatus(source=source, available=False, detail=reason, signal_count=0)
            )
            continue

        result.signals.extend(signals)
        result.sources.append(
            SourceStatus(source=source, available=True, detail=detail, signal_count=len(signals))
        )

    result.signals = rank(result.signals)
    return result


def changed_since(previous: dict[str, Any] | None, current: dict[str, int]) -> int:
    """How many per-source counts differ from a stored snapshot.

    Used to tell a reader that the brief on screen was written about a
    different situation from the one in front of them. Comparing counts rather
    than signal ids is deliberate: the point is "something moved", not a diff.
    """
    if not previous:
        return 0
    keys = set(previous) | set(current)
    return sum(1 for key in keys if int(previous.get(key, 0) or 0) != int(current.get(key, 0) or 0))
