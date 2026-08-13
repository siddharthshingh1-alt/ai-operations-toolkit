"""Deterministic analytics shared by the Dashboard (Project 3) and Report
Generator (Project 7). Project 7 reuses this rather than rebuilding it."""

from aiops_analytics.detection import (
    Anomaly,
    Trend,
    TrendDirection,
    detect_anomalies,
    detect_trend,
)
from aiops_analytics.profiling import (
    ColumnKind,
    ColumnProfile,
    DatasetProfile,
    infer_column_kind,
    profile_dataframe,
)

__all__ = [
    "Anomaly",
    "ColumnKind",
    "ColumnProfile",
    "DatasetProfile",
    "Trend",
    "TrendDirection",
    "detect_anomalies",
    "detect_trend",
    "infer_column_kind",
    "profile_dataframe",
]
