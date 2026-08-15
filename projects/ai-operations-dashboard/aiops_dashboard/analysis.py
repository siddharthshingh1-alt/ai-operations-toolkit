"""Turn a dataframe into a dashboard. No AI anywhere in this module.

CLAUDE.md Section 11 is explicit that column identification uses type inference
and name heuristics first, and that AI is confined to the insight layer on top.
This module is where that boundary is enforced: everything here is arithmetic a
reader could reproduce in a spreadsheet, which is what makes the numbers
trustworthy. `insights.py` is the only place a model is called, and it is given
this module's output rather than the file.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from aiops_analytics import (
    Anomaly,
    ColumnKind,
    Trend,
    detect_anomalies,
    detect_trend,
    profile_dataframe,
)
from aiops_dashboard.models import Analysis, ChartSeries, KpiCard, SeriesPoint
from aiops_utils import get_logger

logger = get_logger(__name__)

#: Numeric columns shown as KPI cards and plotted. More than this and the page
#: becomes a wall of charts nobody reads.
MAX_METRICS = 6
#: Rows returned for the preview table. The browser renders this, not the file.
PREVIEW_ROWS = 25
#: Points plotted per series. A 5,000-row file makes an unreadable line chart
#: and a large payload; sampling keeps both usable.
MAX_POINTS = 180

#: Column-name fragments that usually indicate a rate or percentage, which is
#: worth surfacing ahead of a raw count when choosing what to headline.
_RATE_HINTS = ("rate", "pct", "percent", "ratio", "score")


def _humanise(column: str) -> str:
    """`cancellation_rate_pct` -> `Cancellation rate`."""
    words = column.replace("-", "_").split("_")
    dropped = [word for word in words if word.lower() not in {"pct", "percent"}]
    label = " ".join(dropped or words)
    return label[:1].upper() + label[1:]


def _unit_for(column: str) -> str:
    lowered = column.lower()
    if "pct" in lowered or "percent" in lowered or lowered.endswith("_rate"):
        return "%"
    if "hours" in lowered or lowered.endswith("_hrs"):
        return "hrs"
    if "inr" in lowered:
        return "₹"
    return ""


def _rank_metrics(names: list[str]) -> list[str]:
    """Order numeric columns by how much they belong on a dashboard.

    Rates and percentages first: a cancellation rate is a health indicator,
    where a row count is usually just the size of the export. Identifier-shaped
    columns never reach here — the profiler classifies those separately.
    """
    return sorted(names, key=lambda name: (not _looks_like_rate(name), name))


def _looks_like_rate(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in _RATE_HINTS)


def _ordered_by_date(frame: pd.DataFrame, date_column: str | None) -> pd.DataFrame:
    """Sort by the time axis so 'first' and 'last' mean what they should.

    Without this, a trend is computed over whatever order the file happened to
    be in — which produces a confident, precise, meaningless number.
    """
    if not date_column or date_column not in frame.columns:
        return frame

    parsed = pd.to_datetime(frame[date_column], errors="coerce", format="mixed")
    if parsed.isna().all():
        return frame

    ordered = frame.assign(_sort_key=parsed).sort_values("_sort_key").drop(columns="_sort_key")
    return ordered


def _sample_evenly(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    """Thin a long series while keeping its first and last points."""
    if len(frame) <= limit:
        return frame
    step = len(frame) / limit
    positions = sorted({int(index * step) for index in range(limit)} | {len(frame) - 1})
    return frame.iloc[positions]


def _facts_key(dataset: str, trends: list[Trend], anomalies: list[Anomaly]) -> str:
    """A stable fingerprint of the measured findings.

    Insights are cached against this rather than the filename, so re-analysing
    the same data does not spend a second AI request — which matters when the
    whole day's budget is about twenty of them.
    """
    payload = json.dumps(
        {
            "dataset": dataset,
            "trends": [trend.model_dump() for trend in trends],
            "anomalies": [anomaly.model_dump() for anomaly in anomalies[:10]],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def analyse(frame: pd.DataFrame, *, dataset: str) -> Analysis:
    """Profile a dataframe and compute its KPIs, series, trends and anomalies."""
    profile = profile_dataframe(frame)
    date_profile = profile.date_column
    date_column = date_profile.name if date_profile else None

    ordered = _ordered_by_date(frame, date_column)

    numeric_names = _rank_metrics([column.name for column in profile.of_kind(ColumnKind.NUMERIC)])
    headline = numeric_names[:MAX_METRICS]

    kpis: list[KpiCard] = []
    series: list[ChartSeries] = []
    trends: list[Trend] = []
    anomalies: list[Anomaly] = []

    for name in headline:
        column = pd.to_numeric(ordered[name], errors="coerce").dropna()
        if column.empty:
            continue

        trend = detect_trend(ordered[name], column=name)
        found = detect_anomalies(ordered[name], column=name)

        if trend is not None:
            trends.append(trend)
        anomalies.extend(found)

        kpis.append(
            KpiCard(
                label=_humanise(name),
                # The latest value is the one an operations team acts on; the
                # mean of a 90-day export tells nobody what today looks like.
                value=round(float(column.iloc[-1]), 2),
                unit=_unit_for(name),
                change_pct=trend.change_pct if trend else None,
                direction=trend.direction.value if trend else None,
            )
        )

        anomalous_labels = {anomaly.index_label for anomaly in found}
        plotted = _sample_evenly(ordered, MAX_POINTS)
        labels = (
            plotted[date_column].astype(str)
            if date_column and date_column in plotted.columns
            else plotted.index.astype(str)
        )
        points = [
            SeriesPoint(
                label=str(label),
                value=round(float(value), 4),
                is_anomaly=str(index) in anomalous_labels,
            )
            for index, label, value in zip(
                plotted.index,
                labels,
                pd.to_numeric(plotted[name], errors="coerce"),
                strict=False,
            )
            if pd.notna(value)
        ]
        if points:
            series.append(ChartSeries(column=_humanise(name), points=points))

    anomalies.sort(key=lambda anomaly: abs(anomaly.z_score), reverse=True)

    preview = ordered.head(PREVIEW_ROWS)
    preview_rows = [
        {str(key): ("" if pd.isna(value) else str(value)) for key, value in row.items()}
        for row in preview.to_dict(orient="records")
    ]

    logger.info(
        "analysed dataset",
        extra={
            "project": "ai-operations-dashboard",
            "dataset": dataset,
            "rows": len(frame),
            "metrics": len(kpis),
            "anomalies": len(anomalies),
        },
    )

    return Analysis(
        dataset=dataset,
        row_count=int(profile.row_count),
        column_count=int(profile.column_count),
        columns=profile.columns,
        date_column=date_column,
        kpis=kpis,
        series=series,
        trends=trends,
        anomalies=anomalies[:20],
        preview_rows=preview_rows,
        preview_columns=[str(name) for name in preview.columns],
        facts_key=_facts_key(dataset, trends, anomalies),
    )
