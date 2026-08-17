"""Tests for Project 7 — AI Report Generator.

The weight is on the period arithmetic, because that is the only thing this
project computes that did not already exist. Everything else — KPIs, trends,
anomalies — comes from the analytics service through `analyse()`, and is
already tested where it lives.

So these cover the edges a periodic report actually meets: a dataset with no
date column, a window with no rows, a window with one row, and a previous value
of zero. Each of those has a wrong answer that looks plausible, which is why
each is pinned.

A guard asserts this project never grows a detector of its own.

Nothing here needs an API key or a network — the AI is a stub.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from aiops_report import Period, ReportNarrative, build_facts, compare, date_column_of, split
from aiops_report.periods import MetricChange

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_utils import ValidationError

# ------------------------------------------------------------------- fixtures


def _frame(days: int, *, start: date = date(2026, 6, 1), value: float = 10.0) -> pd.DataFrame:
    """A dated dataset with one numeric column that rises by 1 each day."""
    return pd.DataFrame(
        {
            "date": [start + pd.Timedelta(days=i) for i in range(days)],
            "bookings": [value + i for i in range(days)],
        }
    )


class _Kpi:
    """Stands in for a `KpiCard` — `compare` only reads these three fields."""

    def __init__(self, label: str, value: float, unit: str = "") -> None:
        self.label = label
        self.value = value
        self.unit = unit


class _StubAI(AIProvider):
    name = "stub"

    def __init__(self, metric: str | None = None) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self._metric = metric

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        self.prompts.append(prompt)
        value = ReportNarrative(
            executive_summary="Bookings rose steadily across the period.",
            recommendations=["Investigate the rise in cancellations by route."],
            action_items=[
                {
                    "action": "Review supplier performance.",
                    "owner_hint": "Supplier management",
                    "metric": self._metric,
                }
            ],
        )
        return AIResult[Any](
            value=value,
            provider="stub",
            model="stub-model",
            duration_ms=4,
            usage=Usage(input_tokens=350, output_tokens=100, estimated_cost_usd=0.0003),
        )

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        raise NotImplementedError

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        raise NotImplementedError

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


class _FailingAI(_StubAI):
    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        from aiops_utils import AIProviderError

        raise AIProviderError("upstream exploded")


@pytest.fixture
def report_client() -> Any:
    from aiops_report.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.errors import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    return TestClient(app)


# --------------------------------------------------------------- the windows


def test_the_window_is_anchored_to_the_data_not_to_today() -> None:
    """A dataset that ends three weeks ago still reports on the week it covers.

    Anchoring to `today` would return an empty report for every historical
    file, which is the wrong answer delivered confidently.
    """
    frame = _frame(30, start=date(2020, 1, 1))
    current, previous = split(frame, Period.WEEKLY)

    assert current.end == date(2020, 1, 30)
    assert current.start == date(2020, 1, 24)
    assert current.row_count == 7
    assert previous.end == date(2020, 1, 23)
    assert previous.start == date(2020, 1, 17)
    assert previous.row_count == 7


def test_the_previous_window_abuts_the_current_one() -> None:
    """No gap, no overlap — a day counted twice would corrupt the comparison."""
    current, previous = split(_frame(60), Period.MONTHLY)
    assert previous.end is not None and current.start is not None
    assert (current.start - previous.end).days == 1


@pytest.mark.parametrize(
    ("period", "expected"), [(Period.DAILY, 1), (Period.WEEKLY, 7), (Period.MONTHLY, 30)]
)
def test_each_period_takes_the_right_number_of_days(period: Period, expected: int) -> None:
    current, _ = split(_frame(90), period)
    assert current.row_count == expected
    assert period.days == expected


def test_a_dataset_with_no_date_column_reports_on_the_whole_file() -> None:
    """Degraded, not failed — and the caller can tell which it got."""
    frame = pd.DataFrame({"agency": ["a", "b", "c"], "bookings": [1.0, 2.0, 3.0]})
    assert date_column_of(frame) is None

    current, previous = split(frame, Period.WEEKLY)
    assert current.start is None and current.end is None
    assert current.row_count == 3
    assert previous.row_count == 0
    assert "whole dataset" in current.describe()


def test_a_dataset_whose_dates_are_all_unparseable_falls_back_the_same_way() -> None:
    frame = pd.DataFrame({"date": ["not a date", "nor this"], "bookings": [1.0, 2.0]})
    current, previous = split(frame, Period.WEEKLY)
    assert current.row_count == 2
    assert current.start is None
    assert previous.row_count == 0


def test_a_period_earlier_than_any_data_is_empty_not_an_error() -> None:
    """Only one day of data, asked for a month: the previous window is empty."""
    current, previous = split(_frame(1), Period.MONTHLY)
    assert current.row_count == 1
    assert previous.row_count == 0
    assert previous.is_empty


def test_an_empty_frame_produces_empty_windows() -> None:
    empty = pd.DataFrame({"date": [], "bookings": []})
    current, previous = split(empty, Period.WEEKLY)
    assert current.row_count == 0
    assert previous.row_count == 0


# ----------------------------------------------------------- the comparison


def test_a_rise_is_reported_as_a_percentage() -> None:
    changes = compare([_Kpi("Bookings", 110.0)], [_Kpi("Bookings", 100.0)])
    assert changes[0].change_pct == 10.0
    assert changes[0].direction == "up"


def test_a_fall_is_negative() -> None:
    changes = compare([_Kpi("Bookings", 90.0)], [_Kpi("Bookings", 100.0)])
    assert changes[0].change_pct == -10.0
    assert changes[0].direction == "down"


def test_an_unchanged_metric_is_flat_not_a_tiny_movement() -> None:
    changes = compare([_Kpi("Bookings", 100.0)], [_Kpi("Bookings", 100.0)])
    assert changes[0].change_pct == 0.0
    assert changes[0].direction == "flat"


def test_a_previous_value_of_zero_withholds_the_percentage() -> None:
    """Division by zero is either undefined or infinite; both are useless.

    The previous value is still reported — the reader can see it went from 0 to
    5 — but no percentage is invented for it.
    """
    changes = compare([_Kpi("Incidents", 5.0)], [_Kpi("Incidents", 0.0)])
    assert changes[0].change_pct is None
    assert changes[0].previous == 0.0
    assert changes[0].direction == "up"


def test_a_metric_with_no_previous_period_is_marked_new() -> None:
    """`None` and `0%` mean opposite things and must not be conflated."""
    changes = compare([_Kpi("Refunds", 12.0)], [])
    assert changes[0].previous is None
    assert changes[0].change_pct is None
    assert changes[0].direction == "new"
    assert "no comparable previous period" in changes[0].describe()


def test_a_metric_only_in_the_previous_period_is_dropped() -> None:
    """A report is about this period. A metric that stopped existing is not news."""
    changes = compare([_Kpi("A", 1.0)], [_Kpi("A", 1.0), _Kpi("B", 5.0)])
    assert [c.label for c in changes] == ["A"]


def test_a_negative_previous_value_uses_magnitude() -> None:
    """Going from -10 to -5 is an improvement of 50%, not -50%."""
    changes = compare([_Kpi("Margin", -5.0)], [_Kpi("Margin", -10.0)])
    assert changes[0].change_pct == 50.0
    assert changes[0].direction == "up"


def test_the_change_description_carries_the_unit() -> None:
    change = MetricChange(
        label="Cancellation rate",
        unit="%",
        current=12.2,
        previous=10.0,
        change_pct=22.0,
        direction="up",
    )
    assert "12.20%" in change.describe()
    assert "+22.0%" in change.describe()


# --------------------------------------------------------------- the facts


def test_building_facts_computes_kpis_and_a_comparison() -> None:
    facts, analysis = build_facts(
        _frame(30), dataset="test", dataset_label="Test data", period=Period.WEEKLY
    )
    assert facts.period is Period.WEEKLY
    assert facts.period_label == "Weekly"
    assert facts.current.row_count == 7
    assert facts.previous.row_count == 7
    assert facts.kpis
    assert analysis.row_count == 7
    assert facts.whole_dataset is False


def test_a_dataset_with_no_dates_is_marked_whole_dataset() -> None:
    frame = pd.DataFrame({"agency": ["a", "b"], "bookings": [1.0, 2.0]})
    facts, _ = build_facts(frame, dataset="t", dataset_label="T", period=Period.WEEKLY)
    assert facts.whole_dataset is True
    # Nothing to compare against, so no percentage is invented.
    assert all(kpi.change_pct is None for kpi in facts.kpis)


def test_an_empty_dataset_is_refused_with_a_readable_message() -> None:
    empty = pd.DataFrame({"date": [], "bookings": []})
    with pytest.raises(ValidationError) as caught:
        build_facts(empty, dataset="t", dataset_label="T", period=Period.WEEKLY)
    assert "no rows" in caught.value.user_message.lower()


def test_a_single_row_period_still_produces_a_report() -> None:
    """One row means no trend is computable. That is a thin report, not a crash."""
    facts, _ = build_facts(_frame(1), dataset="t", dataset_label="T", period=Period.DAILY)
    assert facts.current.row_count == 1
    assert facts.previous.row_count == 0


def test_findings_are_the_analytics_services_own_sentences() -> None:
    facts, analysis = build_facts(_frame(60), dataset="t", dataset_label="T", period=Period.MONTHLY)
    statements = {f.statement for f in facts.findings}
    for trend in analysis.trends:
        assert trend.describe() in statements


# ------------------------------------------------------------- the AI, stubbed


def test_the_prompt_carries_the_computed_figures() -> None:
    from aiops_report import service

    facts, _ = build_facts(_frame(30), dataset="t", dataset_label="T", period=Period.WEEKLY)
    stub = _StubAI()
    service.narrate(facts, provider_override=stub)

    prompt = stub.prompts[0]
    assert "Weekly report on: T" in prompt
    assert "KPIs (computed)" in prompt
    assert facts.kpis[0].label in prompt


def test_the_prompt_says_when_the_period_is_empty() -> None:
    """A model unaware the window is empty will write about nothing at length."""
    from aiops_report import service

    frame = _frame(1)
    facts, _ = build_facts(frame, dataset="t", dataset_label="T", period=Period.DAILY)
    facts = facts.model_copy(update={"current": facts.current.model_copy(update={"row_count": 0})})
    stub = _StubAI()
    service.narrate(facts, provider_override=stub)
    assert "no rows at all" in stub.prompts[0]


def test_an_action_item_citing_an_unknown_metric_loses_the_reference() -> None:
    """The action survives; a pointer into a table that lacks it does not."""
    from aiops_report import service

    facts, _ = build_facts(_frame(30), dataset="t", dataset_label="T", period=Period.WEEKLY)
    narrative, _usage = service.narrate(
        facts, provider_override=_StubAI(metric="Metric That Does Not Exist")
    )
    assert narrative.action_items[0].metric is None
    assert narrative.action_items[0].action


def test_an_action_item_citing_a_real_metric_keeps_it() -> None:
    from aiops_report import service

    facts, _ = build_facts(_frame(30), dataset="t", dataset_label="T", period=Period.WEEKLY)
    real = facts.kpis[0].label
    narrative, _usage = service.narrate(facts, provider_override=_StubAI(metric=real))
    assert narrative.action_items[0].metric == real


def test_an_ai_failure_propagates_rather_than_inventing_a_report() -> None:
    from aiops_report import service

    facts, _ = build_facts(_frame(30), dataset="t", dataset_label="T", period=Period.WEEKLY)
    from aiops_utils import AIProviderError

    with pytest.raises(AIProviderError):
        service.narrate(facts, provider_override=_FailingAI())


# ------------------------------------------------------------------- the API


def test_a_bundled_dataset_reports_without_any_ai(report_client: Any) -> None:
    response = report_client.get("/api/reports/samples/operations_metrics?period=weekly")
    assert response.status_code == 200
    body = response.json()
    assert body["facts"]["kpis"]
    assert body["ai_requests_per_narrative"] == 1


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
def test_every_period_is_accepted(report_client: Any, period: str) -> None:
    response = report_client.get(f"/api/reports/samples/operations_metrics?period={period}")
    assert response.status_code == 200
    assert response.json()["facts"]["period"] == period


def test_an_unknown_period_is_rejected(report_client: Any) -> None:
    response = report_client.get("/api/reports/samples/operations_metrics?period=fortnightly")
    assert response.status_code == 422


def test_an_unknown_dataset_is_rejected(report_client: Any) -> None:
    assert report_client.get("/api/reports/samples/not_a_dataset").status_code in (404, 422)


def test_an_uploaded_csv_is_reported_on(report_client: Any) -> None:
    csv = b"date,bookings\n2026-06-01,10\n2026-06-02,12\n2026-06-03,15\n"
    response = report_client.post(
        "/api/reports/analyse?period=daily",
        files={"file": ("ops.csv", csv, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["facts"]["current"]["row_count"] == 1


def test_an_unsupported_upload_is_refused(report_client: Any) -> None:
    response = report_client.post(
        "/api/reports/analyse", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code in (400, 415, 422)


def test_exporting_spends_no_ai_request_and_produces_a_real_pdf(report_client: Any) -> None:
    """PDF needs WeasyPrint's native libraries, which not every machine has.

    Skipped rather than faked where they are missing — the deployment has them,
    and Markdown and HTML are asserted unconditionally below.
    """
    from aiops_docproc import PdfExporter

    if not PdfExporter.is_available():
        pytest.skip("WeasyPrint's native libraries are not installed here")

    facts = report_client.get("/api/reports/samples/operations_metrics?period=weekly").json()[
        "facts"
    ]
    response = report_client.post("/api/reports/export?format=pdf", json={"facts": facts})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.parametrize("fmt", ["markdown", "html"])
def test_exporting_works_without_any_native_library(report_client: Any, fmt: str) -> None:
    facts = report_client.get("/api/reports/samples/operations_metrics?period=weekly").json()[
        "facts"
    ]
    response = report_client.post(f"/api/reports/export?format={fmt}", json={"facts": facts})
    assert response.status_code == 200
    assert b"Key metrics" in response.content
    assert "attachment" in response.headers["content-disposition"]


def test_a_report_exports_without_a_narrative(report_client: Any) -> None:
    """Computed figures alone are a legitimate report."""
    facts = report_client.get("/api/reports/samples/operations_metrics?period=weekly").json()[
        "facts"
    ]
    response = report_client.post("/api/reports/export?format=markdown", json={"facts": facts})
    assert response.status_code == 200
    assert b"Key metrics" in response.content
    assert b"No narrative was generated" in response.content


def test_the_export_carries_every_section_section_15_asks_for(report_client: Any) -> None:
    facts = report_client.get("/api/reports/samples/operations_metrics?period=weekly").json()[
        "facts"
    ]
    narrative = {
        "executive_summary": "A summary.",
        "recommendations": ["Do the thing."],
        "action_items": [
            {"action": "Assign an owner.", "owner_hint": "Operations", "metric": None}
        ],
    }
    response = report_client.post(
        "/api/reports/export?format=markdown", json={"facts": facts, "narrative": narrative}
    )
    body = response.content.decode()
    for heading in (
        "Executive summary",
        "Key metrics",
        "Trends",
        "Anomalies",
        "Recommendations",
        "Action items",
    ):
        assert heading in body, f"the export lost the {heading!r} section"


def test_an_unknown_export_format_is_rejected(report_client: Any) -> None:
    facts = report_client.get("/api/reports/samples/operations_metrics?period=weekly").json()[
        "facts"
    ]
    response = report_client.post("/api/reports/export?format=powerpoint", json={"facts": facts})
    assert response.status_code == 422


# ------------------------------------- the guard: no second analysis engine


def test_this_project_contains_no_trend_or_anomaly_detection() -> None:
    """Section 15: reporting on existing analysis, not a new analysis engine.

    Asserted against the source. A second detector would need a z-score, a
    standard deviation, or a slope — so the test looks for those, and for the
    positive fact that analysis happens by calling the dashboard's `analyse`.
    """
    import importlib
    import inspect

    # `aiops_report.router` as an attribute is the APIRouter, re-exported by the
    # package __init__ — the module itself has to be asked for by name.
    periods = importlib.import_module("aiops_report.periods")
    service = importlib.import_module("aiops_report.service")
    router = importlib.import_module("aiops_report.router")

    package = "\n".join(inspect.getsource(m) for m in (periods, service, router))

    for marker in ("z_score", "std_dev", "stdev", "detect_anomalies", "detect_trend", "polyfit"):
        assert marker not in package, f"{marker!r} suggests a second analysis engine in Project 7"

    source = inspect.getsource(service)
    assert "analyse(" in source, "the report must get its analysis from the dashboard's analyse()"
    assert "describe()" in source, "trend and anomaly wording must come from the service"


def test_the_exporter_is_the_shared_one() -> None:
    """Section 15 names the shared exporter; three copies of PDF rendering is
    exactly what building it once was meant to avoid."""
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module("aiops_report.router"))
    assert "get_exporter" in source
    for marker in ("weasyprint", "WeasyPrint", "reportlab", "<html>"):
        assert marker not in source, f"{marker!r} suggests a private renderer in Project 7"


def test_report_facts_and_narrative_stay_separate_types() -> None:
    """The computed half and the written half must remain distinguishable."""
    from aiops_report.schema import ReportFacts as Facts

    narrative_fields = set(ReportNarrative.model_fields)
    fact_fields = set(Facts.model_fields)
    assert not (narrative_fields & fact_fields), (
        "a field appears in both the computed facts and the model's narrative"
    )
    _ = datetime.now(UTC)
