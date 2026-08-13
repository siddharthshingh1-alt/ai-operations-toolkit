"""Trend and anomaly detection.

Deliberately statistical, not AI. The model's job (in Project 3) is to *explain*
what these functions find, framed as hypotheses — never to detect it, and never
to assert a cause. See CLAUDE.md Section 11.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd
from pydantic import BaseModel

from aiops_utils import ValidationError


class TrendDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


class Trend(BaseModel):
    """The direction of a metric over the observed period."""

    column: str
    direction: TrendDirection
    first_value: float
    last_value: float
    change_pct: float
    periods: int

    def describe(self) -> str:
        """A plain statement of fact, suitable for the 'Observed:' line."""
        return (
            f"{self.column} moved from {self.first_value:,.2f} to "
            f"{self.last_value:,.2f} ({self.change_pct:+.1f}%) "
            f"over {self.periods} periods."
        )


class Anomaly(BaseModel):
    """A single point that sits far from the column's typical range."""

    column: str
    index_label: str
    value: float
    mean: float
    std_dev: float
    z_score: float

    def describe(self) -> str:
        """A plain statement of fact, suitable for the 'Observed:' line."""
        return (
            f"{self.column} was {self.value:,.2f} at {self.index_label}, "
            f"{abs(self.z_score):.1f} standard deviations from the mean of "
            f"{self.mean:,.2f}."
        )


#: Below this, percentage movement is noise rather than a trend.
_FLAT_THRESHOLD_PCT = 2.0
#: Standard deviations from the mean before a point is called anomalous.
_DEFAULT_Z_THRESHOLD = 2.5
#: Fewer points than this cannot support a meaningful mean or trend.
_MIN_POINTS = 3


def detect_trend(series: pd.Series, *, column: str) -> Trend | None:
    """Compare the first and last values of an ordered numeric series.

    Returns None when there is not enough data to say anything — silence is
    better than a trend claim built on two points.
    """
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < _MIN_POINTS:
        return None

    first = float(values.iloc[0])
    last = float(values.iloc[-1])

    if first == 0:
        # Percentage change from zero is undefined; report direction only.
        change_pct = 0.0 if last == 0 else 100.0 * (1 if last > 0 else -1)
    else:
        change_pct = ((last - first) / abs(first)) * 100

    if abs(change_pct) < _FLAT_THRESHOLD_PCT:
        direction = TrendDirection.FLAT
    elif change_pct > 0:
        direction = TrendDirection.RISING
    else:
        direction = TrendDirection.FALLING

    return Trend(
        column=column,
        direction=direction,
        first_value=round(first, 4),
        last_value=round(last, 4),
        change_pct=round(change_pct, 2),
        periods=len(values),
    )


def detect_anomalies(
    series: pd.Series, *, column: str, z_threshold: float = _DEFAULT_Z_THRESHOLD
) -> list[Anomaly]:
    """Flag points more than `z_threshold` standard deviations from the mean."""
    if z_threshold <= 0:
        raise ValidationError("z_threshold must be greater than zero.")

    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < _MIN_POINTS:
        return []

    mean = float(values.mean())
    std_dev = float(values.std(ddof=0))
    if std_dev == 0:
        # A perfectly constant column has no outliers, by definition.
        return []

    anomalies = [
        Anomaly(
            column=column,
            index_label=str(label),
            value=float(value),
            mean=round(mean, 4),
            std_dev=round(std_dev, 4),
            z_score=round((float(value) - mean) / std_dev, 2),
        )
        for label, value in values.items()
        if abs((float(value) - mean) / std_dev) >= z_threshold
    ]
    anomalies.sort(key=lambda anomaly: abs(anomaly.z_score), reverse=True)
    return anomalies
