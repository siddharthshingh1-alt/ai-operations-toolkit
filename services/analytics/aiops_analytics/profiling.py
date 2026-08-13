"""Column type inference and dataset profiling.

CLAUDE.md Section 11 is explicit: identify column roles with **type inference
and name-based heuristics first**, and use AI only for the insight layer on top.
That keeps cost down and removes a whole class of hallucination risk — a column
either parses as a date or it does not; no model needs to be asked.
"""

from __future__ import annotations

from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, Field

from aiops_utils import ValidationError


class ColumnKind(StrEnum):
    """The role a column plays in a dashboard."""

    NUMERIC = "numeric"
    DATE = "date"
    CATEGORICAL = "categorical"
    IDENTIFIER = "identifier"
    TEXT = "text"
    BOOLEAN = "boolean"
    EMPTY = "empty"


# Name fragments that hint at a role when the dtype alone is ambiguous.
_ID_HINTS = ("id", "code", "ref", "number", "no", "pnr", "sku")
_DATE_HINTS = ("date", "time", "at", "on", "day", "month", "year", "created", "updated")

#: A low-cardinality column is categorical; a high-cardinality string column is
#: free text. 5% of rows (or 25 distinct values) is a practical dividing line.
_CATEGORICAL_RATIO = 0.05
_CATEGORICAL_MAX_DISTINCT = 25


class ColumnProfile(BaseModel):
    """What we know about one column, derived deterministically."""

    name: str
    kind: ColumnKind
    dtype: str
    non_null_count: int
    null_count: int
    distinct_count: int
    #: Populated for NUMERIC columns only.
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    #: Populated for CATEGORICAL columns only — the most frequent values.
    top_values: list[str] = Field(default_factory=list)

    @property
    def null_ratio(self) -> float:
        total = self.non_null_count + self.null_count
        return round(self.null_count / total, 4) if total else 0.0


class DatasetProfile(BaseModel):
    """The profile of a whole uploaded file."""

    row_count: int
    column_count: int
    columns: list[ColumnProfile]

    def of_kind(self, kind: ColumnKind) -> list[ColumnProfile]:
        """Every column playing a given role."""
        return [column for column in self.columns if column.kind is kind]

    @property
    def date_column(self) -> ColumnProfile | None:
        """The best candidate for a time axis, if any."""
        dates = self.of_kind(ColumnKind.DATE)
        return dates[0] if dates else None


def _name_suggests(name: str, hints: tuple[str, ...]) -> bool:
    parts = {part for part in name.lower().replace("-", "_").split("_") if part}
    return any(hint in parts for hint in hints)


def infer_column_kind(series: pd.Series, name: str) -> ColumnKind:
    """Classify one column by dtype first, then by name, then by cardinality."""
    non_null = series.dropna()
    if non_null.empty:
        return ColumnKind.EMPTY

    if pd.api.types.is_bool_dtype(series):
        return ColumnKind.BOOLEAN

    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnKind.DATE

    if pd.api.types.is_numeric_dtype(series):
        # A numeric column that is unique per row and named like an id is an
        # identifier, not a measure — averaging it would be meaningless.
        if _name_suggests(name, _ID_HINTS) and non_null.nunique() == len(non_null):
            return ColumnKind.IDENTIFIER
        return ColumnKind.NUMERIC

    # Object dtype: try dates before falling back to text.
    if _name_suggests(name, _DATE_HINTS):
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.9:
            return ColumnKind.DATE

    distinct = non_null.nunique()
    if distinct == len(non_null) and _name_suggests(name, _ID_HINTS):
        return ColumnKind.IDENTIFIER

    threshold = max(_CATEGORICAL_MAX_DISTINCT, int(len(non_null) * _CATEGORICAL_RATIO))
    if distinct <= threshold:
        return ColumnKind.CATEGORICAL

    return ColumnKind.TEXT


def profile_dataframe(frame: pd.DataFrame) -> DatasetProfile:
    """Profile every column of a dataframe."""
    if frame.empty and not len(frame.columns):
        raise ValidationError("The uploaded file contains no columns.")

    columns: list[ColumnProfile] = []
    for name in frame.columns:
        series = frame[name]
        non_null = series.dropna()
        kind = infer_column_kind(series, str(name))

        profile = ColumnProfile(
            name=str(name),
            kind=kind,
            dtype=str(series.dtype),
            non_null_count=int(non_null.size),
            null_count=int(series.isna().sum()),
            distinct_count=int(non_null.nunique()),
        )

        if kind is ColumnKind.NUMERIC and not non_null.empty:
            profile.minimum = float(non_null.min())
            profile.maximum = float(non_null.max())
            profile.mean = round(float(non_null.mean()), 4)
        elif kind is ColumnKind.CATEGORICAL and not non_null.empty:
            profile.top_values = [str(value) for value in non_null.value_counts().head(5).index]

        columns.append(profile)

    return DatasetProfile(
        row_count=int(len(frame)),
        column_count=int(len(frame.columns)),
        columns=columns,
    )
