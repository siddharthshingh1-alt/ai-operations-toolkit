"""Tests for Project 3 — AI Operations Dashboard.

Two things are being defended here.

**The measured layer must never need a model.** Every test below that touches
analysis runs with no API key, no recordings and no network. That is not a
convenience — CLAUDE.md Section 11 puts trend and anomaly detection in
deterministic code precisely so the numbers are reproducible, and a test that
needed a provider to check arithmetic would mean the boundary had been crossed.

**Bad input must produce a message a person can act on.** A dashboard that
renders nothing is a bug report; one that says which row is ragged is a file
someone can fix (Section 23).
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import pytest
from aiops_dashboard import analyse, build_prompt, clear_cache, explain
from aiops_dashboard.models import InsightReport
from fastapi.testclient import TestClient

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_docproc import MAX_ROWS, read_table
from aiops_utils import AIProviderError, NotFoundError, ValidationError

# --------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def _empty_insight_cache() -> None:
    """The insight cache is process-global; tests must not see each other's."""
    clear_cache()


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


HEALTHY = _csv(
    "date,bookings,cancellation_rate_pct\n"
    "2026-01-01,100,5.0\n"
    "2026-01-02,110,5.2\n"
    "2026-01-03,105,5.1\n"
    "2026-01-04,120,5.4\n"
    "2026-01-05,118,9.9\n"
)


class _StubProvider(AIProvider):
    """A provider that returns a fixed report without any network call."""

    name = "stub"

    def __init__(self, report: InsightReport | None = None) -> None:
        self.calls = 0
        self._report = report or InsightReport(
            summary="Cancellations rose over the period.",
            insights=[],
        )

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        self.last_prompt = prompt
        return AIResult[Any](
            value=self._report,
            provider="stub",
            model="stub-model",
            duration_ms=5,
            usage=Usage(input_tokens=100, output_tokens=50, estimated_cost_usd=0.0001),
        )

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        raise NotImplementedError

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        raise NotImplementedError

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


# ------------------------------------------------------- valid input


def test_a_valid_file_produces_a_dashboard() -> None:
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")

    assert analysis.row_count == 5
    assert analysis.column_count == 3
    assert analysis.date_column == "date"
    assert analysis.kpis, "a numeric column should produce at least one KPI"
    assert analysis.series, "a numeric column should produce at least one series"


def test_rates_are_headlined_before_raw_counts() -> None:
    """A cancellation rate is a health indicator; a row count is export size."""
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    assert analysis.kpis[0].label == "Cancellation rate"
    assert analysis.kpis[0].unit == "%"


def test_the_kpi_reports_the_latest_value_not_the_mean() -> None:
    """An operations team acts on today's number, not the period average."""
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    rate = next(kpi for kpi in analysis.kpis if kpi.label == "Cancellation rate")
    assert rate.value == pytest.approx(9.9)


def test_rows_are_ordered_by_date_before_trending() -> None:
    """Otherwise 'first' and 'last' mean whatever order the file happened to be in."""
    shuffled = _csv(
        "date,value\n2026-01-05,50\n2026-01-01,10\n2026-01-03,30\n2026-01-02,20\n2026-01-04,40\n"
    )
    analysis = analyse(read_table(shuffled, "s.csv"), dataset="s.csv")
    trend = analysis.trends[0]
    assert trend.first_value == 10.0
    assert trend.last_value == 50.0
    assert trend.direction == "rising"


def test_an_outlier_is_flagged_on_the_series() -> None:
    spiky = _csv(
        "date,value\n" + "".join(f"2026-01-{d:02d},10\n" for d in range(1, 21)) + "2026-01-21,900\n"
    )
    analysis = analyse(read_table(spiky, "spike.csv"), dataset="spike.csv")

    assert analysis.anomalies, "a 90x spike should be detected"
    assert analysis.anomalies[0].value == 900.0
    flagged = [point for point in analysis.series[0].points if point.is_anomaly]
    assert [point.value for point in flagged] == [900.0]


def test_an_excel_file_is_read() -> None:
    buffer = io.BytesIO()
    pd.DataFrame({"date": ["2026-01-01", "2026-01-02", "2026-01-03"], "value": [1, 2, 3]}).to_excel(
        buffer, index=False
    )
    analysis = analyse(read_table(buffer.getvalue(), "book.xlsx"), dataset="book.xlsx")
    assert analysis.row_count == 3


# ------------------------------------------------------- invalid input


def test_an_unsupported_file_type_is_rejected_by_name() -> None:
    with pytest.raises(ValidationError) as caught:
        read_table(b"whatever", "notes.pdf")
    assert "CSV or Excel" in caught.value.user_message


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(ValidationError) as caught:
        read_table(b"", "empty.csv")
    assert "empty" in caught.value.user_message.lower()


def test_a_headers_only_file_says_so_rather_than_analysing_nothing() -> None:
    with pytest.raises(ValidationError) as caught:
        read_table(_csv("date,value\n"), "headers.csv")
    assert "no data rows" in caught.value.user_message.lower()


def test_a_ragged_file_names_the_problem() -> None:
    """The row count mismatch is the one fact that makes the file fixable."""
    ragged = _csv("a,b,c\n1,2,3\n4,5,6,7,8\n9,10,11\n")
    with pytest.raises(ValidationError) as caught:
        read_table(ragged, "ragged.csv")

    message = caught.value.user_message.lower()
    assert "column" in message
    assert "stack" not in message and "traceback" not in message


def test_an_oversized_file_is_rejected_before_parsing() -> None:
    from aiops_docproc.tabular import MAX_UPLOAD_BYTES

    with pytest.raises(ValidationError) as caught:
        read_table(b"x" * (MAX_UPLOAD_BYTES + 1), "huge.csv")
    assert "too large" in caught.value.user_message.lower()


def test_too_many_rows_is_rejected_with_the_limit_named() -> None:
    frame = pd.DataFrame({"value": range(MAX_ROWS + 5)})
    with pytest.raises(ValidationError) as caught:
        read_table(frame.to_csv(index=False).encode("utf-8"), "long.csv")
    assert f"{MAX_ROWS:,}" in caught.value.user_message


def test_a_non_utf8_file_still_reads() -> None:
    """Excel on Windows exports cp1252; rejecting it over one accent is wrong."""
    frame = read_table("name,value\nJos\xe9,1\nAna,2\n".encode("latin-1"), "cp1252.csv")
    assert len(frame) == 2


def test_a_missing_sample_dataset_is_a_clean_404() -> None:
    from aiops_dashboard.samples import load_sample

    with pytest.raises(NotFoundError):
        load_sample("no_such_dataset")


def test_a_file_with_no_numeric_columns_still_analyses() -> None:
    """Nothing to chart is a valid outcome, not an error."""
    text_only = _csv("name,city\nAnita,Delhi\nDeepak,Mumbai\nSana,Pune\n")
    analysis = analyse(read_table(text_only, "people.csv"), dataset="people.csv")
    assert analysis.row_count == 3
    assert analysis.kpis == []
    assert analysis.preview_rows


# ------------------------------------------------------- the AI layer


def test_the_model_is_given_findings_and_never_the_rows() -> None:
    """The central Section 11 guarantee: the AI cannot invent a number.

    It cannot, because it is never shown one it could distort — the prompt
    carries computed findings, not the dataset.
    """
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    prompt = build_prompt(analysis)

    assert "MEASURED TRENDS" in prompt
    assert "MEASURED ANOMALIES" in prompt
    # No raw row from the file appears in the prompt.
    for row in analysis.preview_rows:
        assert ",".join(row.values()) not in prompt


def test_insights_use_the_injected_provider_and_no_key() -> None:
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    stub = _StubProvider()

    response = explain(analysis, provider_override=stub)

    assert stub.calls == 1
    assert response.report.summary.startswith("Cancellations rose")
    assert response.from_cache is False
    assert response.input_tokens == 100


def test_identical_findings_reuse_the_answer_rather_than_spending_a_request() -> None:
    """Twenty requests a day does not survive two visitors clicking the same button."""
    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    stub = _StubProvider()

    explain(analysis, provider_override=stub)
    second = explain(analysis, provider_override=stub)

    assert stub.calls == 1, "the second call should have been served from cache"
    assert second.from_cache is True
    assert second.estimated_cost_usd == 0.0


def test_different_findings_do_not_share_a_cached_answer() -> None:
    first = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")
    other = analyse(
        read_table(_csv("date,value\n2026-01-01,1\n2026-01-02,5\n2026-01-03,9\n"), "b.csv"),
        dataset="b.csv",
    )
    assert first.facts_key != other.facts_key

    stub = _StubProvider()
    explain(first, provider_override=stub)
    explain(other, provider_override=stub)
    assert stub.calls == 2


def test_an_ai_failure_does_not_destroy_the_measured_analysis() -> None:
    """The numbers are the product; the commentary is an extra."""

    class _Failing(_StubProvider):
        def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
            raise AIProviderError("the model is unavailable")

    analysis = analyse(read_table(HEALTHY, "ops.csv"), dataset="ops.csv")

    with pytest.raises(AIProviderError):
        explain(analysis, provider_override=_Failing())

    # The analysis object is untouched and still fully renderable.
    assert analysis.kpis and analysis.series and analysis.preview_rows


# ------------------------------------------------------- through HTTP


@pytest.fixture
def client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


def test_samples_are_listed(client: TestClient) -> None:
    response = client.get("/api/dashboard/samples")
    assert response.status_code == 200
    keys = {sample["key"] for sample in response.json()["samples"]}
    assert "operations_metrics" in keys


def test_a_sample_analyses_over_http(client: TestClient) -> None:
    response = client.get("/api/dashboard/samples/operations_metrics")
    assert response.status_code == 200

    body = response.json()
    assert body["row_count"] > 0
    assert body["kpis"]
    assert body["date_column"] == "date"


def test_an_unknown_sample_is_404_not_500(client: TestClient) -> None:
    response = client.get("/api/dashboard/samples/not_a_dataset")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_upload_analyses_over_http(client: TestClient) -> None:
    response = client.post(
        "/api/dashboard/analyse",
        files={"file": ("ops.csv", HEALTHY, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["row_count"] == 5


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        ("notes.pdf", b"%PDF-1.4 not a table", "csv or excel"),
        ("empty.csv", b"", "empty"),
        ("headers.csv", b"date,value\n", "no data rows"),
        ("ragged.csv", b"a,b,c\n1,2,3\n4,5,6,7,8\n", "column"),
    ],
)
def test_a_broken_upload_returns_a_readable_message(
    client: TestClient, filename: str, content: bytes, expected: str
) -> None:
    """Section 23: never a stack trace, always something the user can act on."""
    response = client.post(
        "/api/dashboard/analyse",
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert expected in body["message"].lower()
    assert "traceback" not in body["message"].lower()
    # The response carries a message and a code, and nothing else that could
    # leak internals.
    assert set(body) == {"code", "message"}
