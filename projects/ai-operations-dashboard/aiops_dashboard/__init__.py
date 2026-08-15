"""Project 3 — AI Operations Dashboard (CLAUDE.md Section 11).

Includes the merged-in KPI Analyzer: trend detection, anomaly detection and
"possible cause" hypotheses, kept clearly separate from measured fact.
"""

from aiops_dashboard.analysis import analyse
from aiops_dashboard.insights import build_prompt, clear_cache, explain
from aiops_dashboard.models import (
    Analysis,
    ChartSeries,
    Insight,
    InsightReport,
    InsightResponse,
    KpiCard,
    SampleDataset,
    SeriesPoint,
)
from aiops_dashboard.samples import available_samples, load_sample

__all__ = [
    "Analysis",
    "ChartSeries",
    "Insight",
    "InsightReport",
    "InsightResponse",
    "KpiCard",
    "SampleDataset",
    "SeriesPoint",
    "analyse",
    "available_samples",
    "build_prompt",
    "clear_cache",
    "explain",
    "load_sample",
]
