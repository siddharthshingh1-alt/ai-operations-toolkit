"""Analytics tests: type inference, trends, anomalies.

These cover CLAUDE.md Section 25's minimum list — valid input, invalid input,
empty data, and missing fields — for the deterministic layer that AI sits on.
"""

from __future__ import annotations

import pandas as pd
import pytest

from aiops_analytics import (
    ColumnKind,
    TrendDirection,
    detect_anomalies,
    detect_trend,
    infer_column_kind,
    profile_dataframe,
)
from aiops_utils import ValidationError

# --------------------------------------------------------- type inference


def test_numeric_column_is_detected() -> None:
    series = pd.Series([1.5, 2.5, 3.5, 4.0])
    assert infer_column_kind(series, "gross_value_inr") is ColumnKind.NUMERIC


def test_id_shaped_numeric_column_is_an_identifier_not_a_measure() -> None:
    """Averaging a booking id would be meaningless, so it must not be numeric."""
    series = pd.Series([101, 102, 103, 104])
    assert infer_column_kind(series, "booking_id") is ColumnKind.IDENTIFIER


def test_date_strings_are_detected_by_name_and_parseability() -> None:
    series = pd.Series(["2026-01-01", "2026-01-02", "2026-01-03"])
    assert infer_column_kind(series, "created_at") is ColumnKind.DATE


def test_date_named_column_that_does_not_parse_is_not_a_date() -> None:
    """Name hints must not override the data itself."""
    series = pd.Series(["not a date", "also not", "definitely not"])
    assert infer_column_kind(series, "update_date") is not ColumnKind.DATE


def test_low_cardinality_strings_are_categorical() -> None:
    series = pd.Series(["confirmed", "cancelled", "confirmed", "pending"] * 30)
    assert infer_column_kind(series, "status") is ColumnKind.CATEGORICAL


def test_high_cardinality_free_text_is_text() -> None:
    series = pd.Series([f"A unique complaint number {i}" for i in range(500)])
    assert infer_column_kind(series, "body") is ColumnKind.TEXT


def test_all_null_column_is_empty() -> None:
    series = pd.Series([None, None, None], dtype="object")
    assert infer_column_kind(series, "notes") is ColumnKind.EMPTY


def test_boolean_column_is_detected() -> None:
    series = pd.Series([True, False, True])
    assert infer_column_kind(series, "is_overdue") is ColumnKind.BOOLEAN


# ------------------------------------------------------------- profiling


def test_profile_reports_nulls_and_statistics() -> None:
    frame = pd.DataFrame(
        {
            "value": [10.0, 20.0, None, 40.0],
            "status": ["ok", "ok", "bad", "ok"],
        }
    )
    profile = profile_dataframe(frame)

    assert profile.row_count == 4
    value = next(c for c in profile.columns if c.name == "value")
    assert value.null_count == 1
    assert value.minimum == 10.0
    assert value.maximum == 40.0
    assert value.null_ratio == 0.25

    status = next(c for c in profile.columns if c.name == "status")
    assert status.kind is ColumnKind.CATEGORICAL
    assert "ok" in status.top_values


def test_profile_of_a_file_with_no_columns_is_rejected() -> None:
    with pytest.raises(ValidationError, match="no columns"):
        profile_dataframe(pd.DataFrame())


def test_date_column_helper_finds_the_time_axis() -> None:
    frame = pd.DataFrame({"created_at": ["2026-01-01", "2026-01-02", "2026-01-03"], "n": [1, 2, 3]})
    assert profile_dataframe(frame).date_column is not None


# ----------------------------------------------------------------- trends


def test_rising_trend_is_detected() -> None:
    trend = detect_trend(pd.Series([6.0, 8.0, 10.0, 12.0]), column="rate")
    assert trend is not None
    assert trend.direction is TrendDirection.RISING
    assert trend.change_pct == 100.0


def test_falling_trend_is_detected() -> None:
    trend = detect_trend(pd.Series([100.0, 80.0, 60.0]), column="rate")
    assert trend is not None
    assert trend.direction is TrendDirection.FALLING


def test_small_movement_is_flat_not_a_trend() -> None:
    trend = detect_trend(pd.Series([100.0, 100.5, 101.0]), column="rate")
    assert trend is not None
    assert trend.direction is TrendDirection.FLAT


def test_too_few_points_yields_no_trend() -> None:
    """Better to say nothing than to claim a trend from two points."""
    assert detect_trend(pd.Series([1.0, 2.0]), column="rate") is None


def test_trend_description_states_only_facts() -> None:
    trend = detect_trend(pd.Series([8.0, 10.0, 13.0]), column="cancellation_rate")
    assert trend is not None
    description = trend.describe()
    assert "cancellation_rate" in description
    # No causal language may appear in an observation.
    for causal_word in ("because", "caused", "due to"):
        assert causal_word not in description.lower()


# -------------------------------------------------------------- anomalies


def test_clear_outlier_is_flagged() -> None:
    series = pd.Series([10.0] * 20 + [95.0])
    anomalies = detect_anomalies(series, column="rate")
    assert len(anomalies) == 1
    assert anomalies[0].value == 95.0


def test_constant_series_has_no_anomalies() -> None:
    """Zero variance must not produce a divide-by-zero or a false positive."""
    assert detect_anomalies(pd.Series([5.0] * 20), column="rate") == []


def test_too_few_points_yields_no_anomalies() -> None:
    assert detect_anomalies(pd.Series([1.0, 99.0]), column="rate") == []


def test_non_numeric_values_are_ignored_not_fatal() -> None:
    series = pd.Series(["10", "10", "10", "not a number", "95"])
    anomalies = detect_anomalies(series, column="rate")
    assert all(isinstance(a.value, float) for a in anomalies)


def test_invalid_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError, match="greater than zero"):
        detect_anomalies(pd.Series([1.0, 2.0, 3.0]), column="rate", z_threshold=0)
