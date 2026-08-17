"""The single prompt this project uses.

It hands the model a finished KPI table, a period comparison, and the trend and
anomaly statements the analytics service produced, then asks for prose. It does
not ask the model to compute, compare, or detect anything, because all of that
is done before it is called.

The observed / hypothesis / recommendation discipline from CLAUDE.md Section 11
applies here too: a report that presents a guess about *why* a number moved as
though it were a finding is the specific failure that makes operations teams
stop trusting reports.
"""

from __future__ import annotations

from aiops_report.schema import ReportFacts

REPORT_SYSTEM = """You are an operations analyst writing a periodic report for a \
B2B travel-technology company. Travel agencies book flights, hotels and holidays \
through the platform, and an operations team handles delays, cancellations, \
refunds and support.

Every figure you are given has already been computed from the data. Treat them \
as given: never recompute one, never introduce one that is not in front of you, \
and never contradict the table.

Rules that matter more than sounding insightful:

- State what happened before saying what it might mean. A movement is a fact; \
its cause is a hypothesis, and you have not seen the underlying causes.
- Where you suggest a reason, mark it as a possibility in the wording. If \
nothing plausible suggests itself, say the cause is not determinable from this \
data — that is a useful answer, not a failure.
- Never call a change good or bad without saying which direction is desirable \
for that metric.
- Recommendations must be things someone could start this week. An \
investigation is a valid recommendation; "monitor the situation" is not.
- Action items must name a function that would own them.
- Where an action concerns one metric, give that metric's label exactly as \
supplied. Never invent a label.

If the period contains little or no data, say so plainly and keep the report \
short. Padding a thin period with generalities is worse than a two-sentence \
report that admits there was nothing much to report."""


def _kpi_block(facts: ReportFacts) -> str:
    if not facts.kpis:
        return "  (no numeric metrics were computable for this period)"
    lines = []
    for kpi in facts.kpis:
        value = f"{kpi.current:,.2f}{kpi.unit}"
        if kpi.change_pct is None and kpi.previous is None:
            lines.append(f"  {kpi.label}: {value} (no comparable previous period)")
        elif kpi.change_pct is None:
            lines.append(
                f"  {kpi.label}: {value} (previous period was "
                f"{kpi.previous:,.2f}{kpi.unit}; percentage change not meaningful)"
            )
        else:
            lines.append(
                f"  {kpi.label}: {value}, {kpi.change_pct:+.1f}% against "
                f"{kpi.previous:,.2f}{kpi.unit} previously ({kpi.direction})"
            )
    return "\n".join(lines)


def _findings_block(facts: ReportFacts) -> str:
    if not facts.findings:
        return "  (no trends or anomalies were detected in this period)"
    return "\n".join(f"  [{f.kind}] {f.statement}" for f in facts.findings)


def report_prompt(facts: ReportFacts) -> str:
    """Render the computed report as the evidence block for the narrative."""
    if facts.whole_dataset:
        coverage = (
            f"This dataset has no usable date column, so the report covers the "
            f"whole file: {facts.current.description}. There is no previous "
            f"period to compare against."
        )
    else:
        coverage = (
            f"Current period: {facts.current.description}\n"
            f"Previous period: {facts.previous.description}"
        )

    thin = ""
    if facts.current.row_count == 0:
        thin = "\n\nNOTE: the current period contains no rows at all."
    elif facts.current.row_count == 1:
        thin = (
            "\n\nNOTE: the current period contains a single row, so trends "
            "within it are not computable."
        )

    return (
        f"{facts.period_label} report on: {facts.dataset_label}\n"
        f"{coverage}\n\n"
        f"KPIs (computed):\n{_kpi_block(facts)}\n\n"
        f"Trends and anomalies (computed):\n{_findings_block(facts)}"
        f"{thin}\n\n"
        "Write the executive summary, recommendations and action items."
    )
