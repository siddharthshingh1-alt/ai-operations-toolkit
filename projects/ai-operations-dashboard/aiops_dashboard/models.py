"""The shapes the Dashboard API returns.

The split that matters here is between *measured* and *interpreted*.
`Analysis` contains only things a computer worked out from the file and can
prove. `Insight` contains a model's reading of those facts. They are separate
types, travel in separate responses, and render differently — because CLAUDE.md
Section 11 forbids presenting speculation as fact, and the cheapest way to
honour that is to make the two impossible to confuse in the first place.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aiops_analytics import Anomaly, ColumnProfile, Trend


class KpiCard(BaseModel):
    """One headline number, with the movement that gives it meaning."""

    label: str
    value: float
    #: Rendered after the value, e.g. "%" or "hrs". Empty for a plain count.
    unit: str = ""
    #: Percentage change across the period, when a trend was computable.
    change_pct: float | None = None
    direction: str | None = None


class SeriesPoint(BaseModel):
    """One point on the trend chart."""

    label: str
    value: float
    #: True when the deterministic detector flagged this point as an outlier.
    is_anomaly: bool = False


class ChartSeries(BaseModel):
    """A single numeric column plotted over the dataset's time axis."""

    column: str
    points: list[SeriesPoint]


class Analysis(BaseModel):
    """Everything measured from the file. No model was involved in any of it."""

    dataset: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    #: The column used as the x-axis, when the profiler found a usable one.
    date_column: str | None = None
    kpis: list[KpiCard] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    trends: list[Trend] = Field(default_factory=list)
    anomalies: list[Anomaly] = Field(default_factory=list)
    #: First rows, for the table. Values are stringified for transport.
    preview_rows: list[dict[str, str]] = Field(default_factory=list)
    preview_columns: list[str] = Field(default_factory=list)
    #: Stable hash of the measured facts, so identical analyses reuse insights.
    facts_key: str = ""


class Insight(BaseModel):
    """One finding in the three-part form CLAUDE.md Section 11 mandates.

    The field names are the contract. `observed` restates something already
    computed; `hypothesis` is explicitly a guess; `recommendation` is an action
    to take. A model that merges them has produced an invalid response, and the
    schema rejects it rather than the UI having to guess which is which.
    """

    observed: str = Field(
        description="A fact taken from the supplied analysis. Never a new number."
    )
    hypothesis: str = Field(
        description="A possible contributor, stated as a possibility. Never asserted as the cause."
    )
    recommendation: str = Field(description="A specific next step an operations team could take.")


class InsightReport(BaseModel):
    """The model's reading of one analysis."""

    summary: str = Field(description="Two sentences on the overall state of the data.")
    insights: list[Insight] = Field(
        description="Between one and four findings, most material first."
    )


class InsightResponse(BaseModel):
    """An insight report plus the cost of producing it (Section 3d)."""

    report: InsightReport
    model: str
    provider: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None = None
    from_cache: bool = False


class SampleDataset(BaseModel):
    """A bundled dataset a visitor can analyse without uploading anything."""

    key: str
    name: str
    description: str
    row_count: int
