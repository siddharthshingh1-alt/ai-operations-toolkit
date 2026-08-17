"""Request, response and AI output shapes for the Report Generator.

The split this file encodes: everything in `ReportFacts` was computed by the
analytics service before any model was called, and everything in
`ReportNarrative` is prose a model wrote about those figures. They are separate
types so a reader — and a test — can tell at a glance which half is which.
"""

from __future__ import annotations

from datetime import date, datetime

from aiops_dashboard.models import Analysis
from pydantic import BaseModel, Field

from aiops_report.periods import Period

# ------------------------------------------------------------------ AI output


class ActionItem(BaseModel):
    """One thing to do, tied to a metric that exists."""

    action: str = Field(min_length=1, description="What to do, phrased as an instruction.")
    owner_hint: str = Field(
        default="",
        description="Which function should own it, e.g. 'Operations' or 'Supplier management'.",
    )
    metric: str | None = Field(
        default=None,
        description=(
            "The label of the metric this concerns, exactly as supplied. "
            "Null if it does not concern one specific metric."
        ),
    )


class ReportNarrative(BaseModel):
    """Everything the model contributes. No figures originate here.

    The model is handed the KPI table, the period comparison, the trends and
    the anomalies, and asked only to say what they mean and what to do. It is
    told it may not re-derive any number, because a report whose prose
    disagrees with the table above it is worse than one with no prose.
    """

    executive_summary: str = Field(
        min_length=1,
        description=(
            "Three to five sentences for someone who reads nothing else: what "
            "the period looked like, what moved, and what needs attention."
        ),
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Concrete next steps, most useful first. Investigations count.",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Up to five specific, assignable actions.",
    )


# ------------------------------------------------------------------ responses


class MetricChangeView(BaseModel):
    """One row of the KPI table."""

    label: str
    unit: str
    current: float
    previous: float | None
    change_pct: float | None
    direction: str


class FindingView(BaseModel):
    """A trend or an anomaly, in the analytics service's own words."""

    kind: str  # "trend" | "anomaly"
    column: str
    #: `Trend.describe()` / `Anomaly.describe()`, verbatim.
    statement: str


class WindowView(BaseModel):
    """What one window covered."""

    start: date | None
    end: date | None
    row_count: int
    description: str


class ReportFacts(BaseModel):
    """Everything measured. No model was involved in any of it.

    This is the whole input to the narrative call, and it is a named type for
    the same reason the tracker's `ProjectFacts` is: the exact set of figures
    the prose rests on should be something you can see, test, and put on the
    page next to the prose.
    """

    dataset: str
    dataset_label: str
    period: Period
    period_label: str
    current: WindowView
    previous: WindowView
    #: True when the dataset had no usable date column, so the "period" is the
    #: whole file. Stated rather than implied.
    whole_dataset: bool = False
    kpis: list[MetricChangeView] = Field(default_factory=list)
    findings: list[FindingView] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    generated_at: datetime


class UsageInfo(BaseModel):
    """Cost metadata for an AI step (Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class ReportFactsResponse(BaseModel):
    """The computed half of a report. Free — no AI request is spent."""

    facts: ReportFacts
    #: The full current-window analysis, for anyone wanting the detail.
    analysis: Analysis
    ai_requests_per_narrative: int = 1


class ReportNarrativeResponse(BaseModel):
    narrative: ReportNarrative
    usage: UsageInfo


class SampleOption(BaseModel):
    key: str
    name: str
    description: str


# ------------------------------------------------------------------- requests
#
# Defined after `ReportFacts` because they embed it.


class GenerateReportRequest(BaseModel):
    """Ask for the narrative over facts the caller already has.

    The facts are posted back rather than recomputed, so the prose is written
    about exactly the table on the reader's screen — not about a second
    analysis produced from a re-read of the file, which for an uploaded file
    would not even be available.
    """

    facts: ReportFacts


class ExportReportRequest(BaseModel):
    """Render a report that has already been produced.

    The narrative is optional: a report of computed figures with no prose is a
    perfectly good thing to export, and it costs no AI request at all.
    """

    facts: ReportFacts
    narrative: ReportNarrative | None = None
