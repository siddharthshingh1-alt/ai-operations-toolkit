"""Domain logic for the Report Generator (CLAUDE.md Section 15).

Two halves, kept apart on purpose.

`build_facts` computes. It slices the dataset into a period, hands each window
to the Operations Dashboard's `analyse()`, and subtracts one result from the
other. Every number in a report is produced here, before any model exists in
the picture.

`narrate` asks. One request, prose only.

There is no trend detection and no anomaly detection in this module, and there
must never be. Those come from the analytics service via `analyse()` — the same
call the dashboard makes — and Section 15 says this project reports on that
analysis rather than rebuilding it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd
from aiops_dashboard.analysis import analyse
from aiops_dashboard.models import Analysis

from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult
from aiops_config import Settings, get_settings
from aiops_report import prompts
from aiops_report.periods import Period, Window, compare, split
from aiops_report.schema import (
    FindingView,
    MetricChangeView,
    ReportFacts,
    ReportNarrative,
    UsageInfo,
    WindowView,
)
from aiops_utils import ValidationError, get_logger

logger = get_logger(__name__)


def _window_view(window: Window) -> WindowView:
    return WindowView(
        start=window.start,
        end=window.end,
        row_count=window.row_count,
        description=window.describe(),
    )


def _findings(analysis: Analysis) -> list[FindingView]:
    """Trends and anomalies, in the analytics service's own words.

    `describe()` is printed verbatim. The sentence stating what an anomaly is
    lives in the service that detects it, and there is no second copy of that
    wording here or in the Command Center.
    """
    findings = [
        FindingView(kind="trend", column=trend.column, statement=trend.describe())
        for trend in analysis.trends
    ]
    findings.extend(
        FindingView(kind="anomaly", column=anomaly.column, statement=anomaly.describe())
        for anomaly in analysis.anomalies
    )
    return findings


def build_facts(
    frame: pd.DataFrame,
    *,
    dataset: str,
    dataset_label: str,
    period: Period,
) -> tuple[ReportFacts, Analysis]:
    """Compute everything a report states. No AI, and no cost.

    Runs `analyse()` twice — once per window — and compares the two. The
    analysis of the current window is returned alongside, because the page
    shows the same charts the dashboard would.
    """
    if frame.empty:
        raise ValidationError(
            "The dataset is empty.",
            user_message="That file has no rows in it, so there is nothing to report on.",
        )

    current, previous = split(frame, period)
    whole_dataset = current.start is None

    current_analysis = analyse(current.frame, dataset=dataset) if not current.is_empty else None
    previous_analysis = analyse(previous.frame, dataset=dataset) if not previous.is_empty else None

    if current_analysis is None:
        # A period with no rows is a real answer — "nothing happened in the
        # window you asked about" — not an error. The report says so, and the
        # KPI table is empty rather than fabricated.
        empty = analyse(frame.iloc[0:0], dataset=dataset)
        facts = ReportFacts(
            dataset=dataset,
            dataset_label=dataset_label,
            period=period,
            period_label=period.label,
            current=_window_view(current),
            previous=_window_view(previous),
            whole_dataset=whole_dataset,
            kpis=[],
            findings=[],
            row_count=0,
            column_count=len(frame.columns),
            generated_at=datetime.now(UTC),
        )
        return facts, empty

    changes = compare(
        current_analysis.kpis,
        previous_analysis.kpis if previous_analysis is not None else [],
    )

    facts = ReportFacts(
        dataset=dataset,
        dataset_label=dataset_label,
        period=period,
        period_label=period.label,
        current=_window_view(current),
        previous=_window_view(previous),
        whole_dataset=whole_dataset,
        kpis=[
            MetricChangeView(
                label=change.label,
                unit=change.unit,
                current=change.current,
                previous=change.previous,
                change_pct=change.change_pct,
                direction=change.direction,
            )
            for change in changes
        ],
        findings=_findings(current_analysis),
        row_count=current_analysis.row_count,
        column_count=current_analysis.column_count,
        generated_at=datetime.now(UTC),
    )
    return facts, current_analysis


# ------------------------------------------------------------------------ AI


def _usage_of(result: AIResult[Any]) -> UsageInfo:
    return UsageInfo(
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_demo_cache=getattr(result, "from_demo_cache", False),
    )


def narrate(
    facts: ReportFacts,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
) -> tuple[ReportNarrative, UsageInfo]:
    """Ask the model to write the prose. One AI request.

    Takes the facts it is given rather than recomputing them, so the narrative
    describes exactly the table the reader is looking at. For an uploaded file
    that is not merely tidier — the file is not stored, so recomputing is not
    an option.
    """
    resolved = settings or get_settings()
    provider = provider_override or get_provider(resolved)

    result = provider.generate_structured_output(
        prompts.report_prompt(facts),
        output_model=ReportNarrative,
        system=prompts.REPORT_SYSTEM,
    )
    narrative = result.value

    known = {kpi.label for kpi in facts.kpis}
    cleaned: list[Any] = []
    for item in narrative.action_items[:5]:
        metric = item.metric if item.metric in known else None
        if item.metric and metric is None:
            # Drop the reference, keep the action. A report pointing at a
            # metric that is not in its own table invites the reader to
            # distrust the table.
            logger.warning(
                "model referenced an unknown metric; dropping the reference",
                extra={"claimed_metric": str(item.metric)[:64]},
            )
        cleaned.append(item.model_copy(update={"metric": metric}))

    narrative = narrative.model_copy(update={"action_items": cleaned})

    logger.info(
        "report narrative generated",
        extra={
            "project": "ai-report-generator",
            "dataset": facts.dataset,
            "report_period": facts.period.value,
            "kpi_count": len(facts.kpis),
            "model": result.model,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )
    return narrative, _usage_of(result)


__all__ = ["build_facts", "narrate"]
