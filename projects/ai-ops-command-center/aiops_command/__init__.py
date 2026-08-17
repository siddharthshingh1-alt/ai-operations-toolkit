"""Project 9 — AI Ops Command Center (CLAUDE.md Section 17).

The aggregator. It reads the operational signals four other projects already
produce and puts them on one page, most urgent first, each linking back to
whichever project owns it.

What it is not: a second source of truth. Nothing here decides whether a task
is overdue, whether a workflow can run, how severe an incident is, or what
counts as an anomaly. Those questions are answered by Projects 5, 4, 6 and 3
respectively, and this package calls their own functions to ask.

Where a source already phrases a fact, that phrasing is reused rather than
restated. `Trend.describe()` and `Anomaly.describe()` are printed verbatim, so
the sentence describing an anomaly is written once, in the service that detects
it.

The dependency direction is one-way and must stay that way: this package
imports from Projects 3, 4, 5 and 6; none of them import from it.
"""

from aiops_command.models import OpsBrief
from aiops_command.router import router
from aiops_command.schema import (
    BriefAction,
    BriefNarrative,
    BriefView,
    CommandCenterResponse,
    SignalView,
    SourceView,
)
from aiops_command.signals import (
    DASHBOARD_DATASET,
    SOURCE_LABELS,
    SOURCE_LINKS,
    Signal,
    SignalSet,
    SourceStatus,
    changed_since,
    collect_dashboard,
    collect_tracker,
    collect_travel_ops,
    collect_workflows,
    gather,
    rank,
)

__all__ = [
    "DASHBOARD_DATASET",
    "SOURCE_LABELS",
    "SOURCE_LINKS",
    "BriefAction",
    "BriefNarrative",
    "BriefView",
    "CommandCenterResponse",
    "OpsBrief",
    "Signal",
    "SignalSet",
    "SignalView",
    "SourceStatus",
    "SourceView",
    "changed_since",
    "collect_dashboard",
    "collect_tracker",
    "collect_travel_ops",
    "collect_workflows",
    "gather",
    "rank",
    "router",
]
