"""Project 7 — AI Report Generator (CLAUDE.md Section 15).

Daily, weekly and monthly operational reports: executive summary, KPI table,
trends, anomalies, recommendations and action items, exportable to PDF,
Markdown and HTML.

**It computes nothing the analytics service already computes.** KPIs, trends
and anomalies come from `analyse()` — the same call the Operations Dashboard
makes — and trend and anomaly statements are printed in that service's own
words via `describe()`. Section 15 is explicit that reporting is "reporting on
top of existing data, not a new analysis engine".

The one new calculation is in `periods.py`: slice the dataset into a window,
slice the window before it, and subtract one set of computed KPIs from the
other. That subtraction is what turns "cancellations were 11.8%" into
"cancellations were 11.8%, up 12% on last week", which is the only reason a
periodic report is worth reading. It is not a detector, and a test asserts it
never becomes one.

Nothing is stored. A report is derived from a dataset and a period, so a saved
copy would be a stale duplicate of something reproducible — and the exported
document is the artifact worth keeping.
"""

from aiops_report.periods import MetricChange, Period, Window, compare, date_column_of, split
from aiops_report.router import router
from aiops_report.schema import (
    ActionItem,
    ExportReportRequest,
    GenerateReportRequest,
    ReportFacts,
    ReportNarrative,
)
from aiops_report.service import build_facts, narrate

__all__ = [
    "ActionItem",
    "ExportReportRequest",
    "GenerateReportRequest",
    "MetricChange",
    "Period",
    "ReportFacts",
    "ReportNarrative",
    "Window",
    "build_facts",
    "compare",
    "date_column_of",
    "narrate",
    "router",
    "split",
]
