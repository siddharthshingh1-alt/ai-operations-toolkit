"""Period windows, and the comparison between two of them.

This module is the only genuinely new computation in Project 7, and it is
deliberately small: slice a dataframe into a window, slice the window before
it, and subtract one set of already-computed KPIs from the other.

It contains **no trend detection and no anomaly detection**. Those belong to
the analytics service and reach this project through `analyse()`, exactly as
they reach the Operations Dashboard. Section 15 is explicit that reporting sits
on top of the analysis already built for Project 3 rather than rebuilding it,
and a test asserts this file never grows a detector.

What a period comparison buys, and why it is worth the code: a report saying
"cancellations were 11.8%" is a number. A report saying "cancellations were
11.8%, up from 9.2% the week before" is the reason anyone reads a weekly
report at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

import pandas as pd

from aiops_analytics import ColumnKind, profile_dataframe


class Period(StrEnum):
    """The reporting windows Section 15 names."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def days(self) -> int:
        return {Period.DAILY: 1, Period.WEEKLY: 7, Period.MONTHLY: 30}[self]

    @property
    def label(self) -> str:
        return {Period.DAILY: "Daily", Period.WEEKLY: "Weekly", Period.MONTHLY: "Monthly"}[self]


@dataclass(frozen=True)
class Window:
    """One slice of a dataset, and what it covers.

    `start` and `end` are None when the dataset has no usable date column — the
    window is then the whole file, which is stated rather than implied.
    """

    frame: pd.DataFrame
    start: date | None
    end: date | None
    row_count: int

    @property
    def is_empty(self) -> bool:
        return self.row_count == 0

    def describe(self) -> str:
        if self.start is None or self.end is None:
            return f"the whole dataset ({self.row_count} rows)"
        if self.start == self.end:
            return f"{self.start.isoformat()} ({self.row_count} rows)"
        return f"{self.start.isoformat()} to {self.end.isoformat()} ({self.row_count} rows)"


def date_column_of(frame: pd.DataFrame) -> str | None:
    """The column the profiler considers this dataset's date axis.

    Asked of the analytics service rather than guessed here, so a report and
    the dashboard always agree about which column is the timeline.
    """
    profile = profile_dataframe(frame)
    found = profile.date_column
    if found is None:
        return None
    return found.name if found.kind is ColumnKind.DATE else None


def _as_dates(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column], errors="coerce")


def split(frame: pd.DataFrame, period: Period) -> tuple[Window, Window]:
    """Return (current window, preceding window of the same length).

    The windows are anchored to the **latest date in the data**, not to today.
    A dataset whose last row is three weeks old should still produce a report
    about the week it actually covers, rather than an empty one about the week
    nobody recorded anything in.

    With no usable date column the current window is the whole dataset and the
    preceding window is empty. That is a degraded report, not a failed one, and
    the caller is told which it got.
    """
    column = date_column_of(frame)
    if column is None or frame.empty:
        whole = Window(frame=frame, start=None, end=None, row_count=len(frame))
        empty = Window(frame=frame.iloc[0:0], start=None, end=None, row_count=0)
        return whole, empty

    stamps = _as_dates(frame, column)
    valid = stamps.dropna()
    if valid.empty:
        whole = Window(frame=frame, start=None, end=None, row_count=len(frame))
        empty = Window(frame=frame.iloc[0:0], start=None, end=None, row_count=0)
        return whole, empty

    last = valid.max().date()
    span = period.days

    current_start = last - timedelta(days=span - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span - 1)

    days = stamps.dt.date
    current_mask = (days >= current_start) & (days <= last)
    previous_mask = (days >= previous_start) & (days <= previous_end)

    current = frame[current_mask.fillna(False)]
    previous = frame[previous_mask.fillna(False)]

    return (
        Window(frame=current, start=current_start, end=last, row_count=len(current)),
        Window(
            frame=previous,
            start=previous_start,
            end=previous_end,
            row_count=len(previous),
        ),
    )


@dataclass(frozen=True)
class MetricChange:
    """One KPI, this period against the last.

    `change_pct` is None when there is nothing to compare against — no previous
    window, or a previous value of zero. None is reported as "no comparison"
    rather than as 0%, because those mean opposite things and a report that
    confuses them is worse than one that omits the column.
    """

    label: str
    unit: str
    current: float
    previous: float | None
    change_pct: float | None
    direction: str  # "up" | "down" | "flat" | "new"

    def describe(self) -> str:
        value = f"{self.current:,.2f}{self.unit}"
        if self.previous is None or self.change_pct is None:
            return f"{self.label}: {value} (no comparable previous period)"
        return (
            f"{self.label}: {value}, {self.change_pct:+.1f}% against "
            f"{self.previous:,.2f}{self.unit} in the previous period"
        )


def compare(current_kpis: list, previous_kpis: list) -> list[MetricChange]:
    """Subtract one set of computed KPIs from another. Matched on label.

    Both inputs come from `analyse()`. Nothing here measures anything; it pairs
    up figures that were measured elsewhere and states the difference.
    """
    previous_by_label = {kpi.label: kpi for kpi in previous_kpis}
    changes: list[MetricChange] = []

    for kpi in current_kpis:
        earlier = previous_by_label.get(kpi.label)

        if earlier is None:
            changes.append(
                MetricChange(
                    label=kpi.label,
                    unit=kpi.unit,
                    current=kpi.value,
                    previous=None,
                    change_pct=None,
                    direction="new",
                )
            )
            continue

        if earlier.value == 0:
            # A percentage against zero is either undefined or infinite. Both
            # are useless in a report, so the comparison is withheld and the
            # previous value is still shown.
            changes.append(
                MetricChange(
                    label=kpi.label,
                    unit=kpi.unit,
                    current=kpi.value,
                    previous=earlier.value,
                    change_pct=None,
                    direction="up" if kpi.value > 0 else "flat",
                )
            )
            continue

        delta = (kpi.value - earlier.value) / abs(earlier.value) * 100.0
        if abs(delta) < 0.05:
            direction = "flat"
        elif delta > 0:
            direction = "up"
        else:
            direction = "down"

        changes.append(
            MetricChange(
                label=kpi.label,
                unit=kpi.unit,
                current=kpi.value,
                previous=earlier.value,
                change_pct=round(delta, 1),
                direction=direction,
            )
        )

    return changes
