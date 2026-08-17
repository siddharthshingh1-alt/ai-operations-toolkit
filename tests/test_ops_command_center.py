"""Tests for Project 9 — AI Ops Command Center.

Three things carry the weight.

**Resilience.** Four sources, and any of them can fail. A brief produced from
three working sources is useful; a blank page because one query threw is not,
and it actively hides the three that were fine. Every collector runs inside its
own guard, and that is tested one source at a time.

**Non-duplication.** Section 17 forbids this project from becoming a second
source of truth. That is asserted against the source itself — the collectors
must not contain overdue arithmetic, severity rules, or anomaly thresholds,
because those belong to Projects 5, 6 and 3.

**The read-API shape guard.** This is the only project that imports from other
projects, so a rename in any of the four silently breaks it. The guard calls
each source's read functions and checks the fields this project relies on, so
the breakage surfaces in CI rather than on the deployed site.

Nothing here needs an API key or a network — the AI is a stub.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from aiops_command import (
    BriefNarrative,
    Signal,
    SourceStatus,
    changed_since,
    gather,
    rank,
)
from aiops_command.prompts import brief_prompt

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage

TODAY = date(2026, 6, 15)


# ------------------------------------------------------------------- fixtures


class _StubAI(AIProvider):
    """Returns a valid brief. No network."""

    name = "stub"

    def __init__(self, signal_id: str | None = None) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self._signal_id = signal_id

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        self.prompts.append(prompt)
        value = BriefNarrative(
            summary="Two approvals are waiting and one project is overdue.",
            actions=[{"action": "Clear the waiting approval.", "signal_id": self._signal_id}],
        )
        return AIResult[Any](
            value=value,
            provider="stub",
            model="stub-model",
            duration_ms=5,
            usage=Usage(input_tokens=400, output_tokens=110, estimated_cost_usd=0.0004),
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
def command_client() -> Any:
    """The Command Center's routes over a real (in-memory) database.

    Every source project's tables are created, because this project reads all
    of them. That is the point of the fixture: an aggregator tested against
    mocks of its sources proves nothing about whether it can read them.
    """
    import aiops_builder.models  # noqa: F401  (registers tables)
    import aiops_command.models  # noqa: F401
    import aiops_tracker.models  # noqa: F401
    import aiops_travelops.models  # noqa: F401
    from aiops_command.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from aiops_db import get_db
    from aiops_db.base import Base
    from app.errors import register_error_handlers

    if not hasattr(command_client, "_compiled"):

        @compiles(JSONB, "sqlite")
        def _jsonb_as_json(type_: Any, compiler: Any, **kw: Any) -> str:
            return "JSON"

        command_client._compiled = True  # type: ignore[attr-defined]

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    names = (
        "tracked_projects",
        "tracked_tasks",
        "workflows",
        "workflow_executions",
        "travel_incidents",
        "travel_communications",
        "ops_briefs",
    )
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in names])
    session_factory = sessionmaker(bind=engine)

    def _db() -> Any:
        session = session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    client.session_factory = session_factory  # type: ignore[attr-defined]
    return client


# ------------------------------------------------------------------- ranking


def test_ranking_is_deterministic_and_puts_critical_first() -> None:
    signals = [
        Signal("a", "dashboard", "info", "Info", "", "/", score=10),
        Signal("b", "tracker", "critical", "Critical", "", "/tasks", score=100),
        Signal("c", "workflows", "warning", "Warning", "", "/workflows", score=40),
    ]
    ordered = rank(signals)
    assert [s.id for s in ordered] == ["b", "c", "a"]
    # Same input, same order — a reader refreshing must not see it shuffle.
    assert [s.id for s in rank(list(reversed(signals)))] == ["b", "c", "a"]


def test_ranking_an_empty_list_is_empty() -> None:
    assert rank([]) == []


# ------------------------------------------------------------------ staleness


def test_no_stored_counts_means_nothing_has_changed() -> None:
    assert changed_since(None, {"tracker": 3}) == 0
    assert changed_since({}, {"tracker": 3}) == 0


def test_identical_counts_are_not_stale() -> None:
    counts = {"tracker": 3, "workflows": 1}
    assert changed_since(counts, dict(counts)) == 0


def test_a_moved_count_is_reported() -> None:
    assert changed_since({"tracker": 3, "workflows": 1}, {"tracker": 5, "workflows": 1}) == 1


def test_a_source_appearing_or_vanishing_counts_as_change() -> None:
    assert changed_since({"tracker": 3}, {"tracker": 3, "dashboard": 2}) == 1
    assert changed_since({"tracker": 3, "dashboard": 2}, {"tracker": 3}) == 1


# --------------------------------------------------- one source unavailable


@pytest.mark.parametrize(
    "broken",
    ["collect_tracker", "collect_workflows", "collect_travel_ops", "collect_dashboard"],
)
def test_one_failed_source_does_not_take_the_brief_down(
    command_client: Any, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    """Each source, broken in turn. The other three must still report."""
    import aiops_command.signals as sig

    def _explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(f"{broken} is down")

    monkeypatch.setattr(sig, broken, _explode)

    response = command_client.get("/api/command-center")
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["sources"]) == 4
    failed = [s for s in body["sources"] if not s["available"]]
    assert len(failed) == 1
    # The reason must be carried, not swallowed. "Unavailable" alone tells an
    # operator nothing they can act on.
    assert "is down" in failed[0]["detail"]
    assert sum(1 for s in body["sources"] if s["available"]) == 3


def test_every_source_failing_still_returns_a_page(
    command_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worst case is an empty brief that explains itself, not a 500."""
    import aiops_command.signals as sig

    for name in ("collect_tracker", "collect_workflows", "collect_travel_ops", "collect_dashboard"):
        monkeypatch.setattr(sig, name, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))

    response = command_client.get("/api/command-center")
    assert response.status_code == 200
    body = response.json()
    assert body["signals"] == []
    assert all(not s["available"] for s in body["sources"])


def test_a_failed_source_is_recorded_on_the_brief_it_produced(
    command_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A brief written blind to one source must not later look complete."""
    import aiops_command.service as svc
    import aiops_command.signals as sig

    monkeypatch.setattr(
        sig, "collect_dashboard", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no data"))
    )
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI())

    response = command_client.post("/api/command-center/brief")
    assert response.status_code == 200
    assert response.json()["brief"]["unavailable_sources"] == ["dashboard"]


def test_the_prompt_tells_the_model_the_picture_is_incomplete() -> None:
    """A model unaware a source was missing writes a falsely complete brief."""
    sources = [
        SourceStatus("tracker", True, "3 projects read.", 2),
        SourceStatus("dashboard", False, "sample file missing", 0),
    ]
    prompt = brief_prompt([], sources, today="2026-06-15")
    assert "UNAVAILABLE" in prompt
    assert "incomplete" in prompt.lower()


def test_the_prompt_survives_having_no_signals_at_all() -> None:
    """Section 25's empty-data case: a quiet morning is a valid morning."""
    prompt = brief_prompt([], [SourceStatus("tracker", True, "0 projects.", 0)], today="2026-06-15")
    assert "no signals" in prompt.lower()


# ------------------------------------------------------------- the AI, stubbed


def test_generating_a_brief_stores_it(command_client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import aiops_command.service as svc

    stub = _StubAI()
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: stub)

    response = command_client.post("/api/command-center/brief")
    assert response.status_code == 200
    body = response.json()
    assert body["brief"]["summary"]
    assert body["usage"]["model"] == "stub-model"
    assert stub.calls == 1

    # And it comes back on the next page load, without another request.
    overview = command_client.get("/api/command-center").json()
    assert overview["brief"]["summary"] == body["brief"]["summary"]
    assert stub.calls == 1


def test_a_brief_action_referencing_an_unknown_signal_loses_the_reference(
    command_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The advice survives; a link that leads nowhere does not."""
    import aiops_command.service as svc

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI(signal_id="totally:made:up"))

    body = command_client.post("/api/command-center/brief").json()
    actions = body["brief"]["actions"]
    assert len(actions) == 1
    assert actions[0]["signal_id"] is None
    assert actions[0]["action"]


def test_an_ai_failure_surfaces_and_stores_nothing(
    command_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Section 25's AI-failure case."""
    import aiops_command.service as svc

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _FailingAI())

    response = command_client.post("/api/command-center/brief")
    assert response.status_code >= 500 or response.status_code == 502
    assert command_client.get("/api/command-center").json()["brief"] is None


def test_the_overview_costs_no_ai_request(
    command_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A page opened every morning may not spend a request to render."""
    import aiops_command.service as svc

    stub = _StubAI()
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: stub)

    for _ in range(3):
        assert command_client.get("/api/command-center").status_code == 200
    assert stub.calls == 0


# ------------------------------------------------------ aggregation, for real


def test_signals_are_collected_from_the_real_sources(command_client: Any) -> None:
    """End to end: seed the sources, then read them through the aggregator.

    Deliberately not mocked. The whole claim of this project is that it can
    read four others; a test against fakes would not check that.
    """
    from aiops_builder import service as builder
    from aiops_tracker import service as tracker

    session = command_client.session_factory()  # type: ignore[attr-defined]
    try:
        tracker.seed_if_empty(session)
        builder.seed_templates(session)
        session.commit()
    finally:
        session.close()

    body = command_client.get("/api/command-center").json()

    sources = {s["source"]: s for s in body["sources"]}
    assert sources["tracker"]["available"]
    assert sources["workflows"]["available"]

    # The seeded tracker data has overdue and blocked work; those must appear.
    tracker_signals = [s for s in body["signals"] if s["source"] == "tracker"]
    assert tracker_signals, "the tracker's overdue/blocked work did not reach the brief"

    # Section 17: every item links back to the project that owns it.
    assert all(s["link"] for s in body["signals"])
    for signal in body["signals"]:
        assert signal["link"].startswith("/"), signal


def test_every_signal_links_back_to_its_source_project(command_client: Any) -> None:
    from aiops_command.signals import SOURCE_LINKS

    body = command_client.get("/api/command-center").json()
    for signal in body["signals"]:
        base = SOURCE_LINKS[signal["source"]]
        assert signal["link"] == base or signal["link"].startswith(base.rstrip("/") + "/"), signal


def test_severity_counts_match_the_signals(command_client: Any) -> None:
    body = command_client.get("/api/command-center").json()
    severities = [s["severity"] for s in body["signals"]]
    assert body["critical_count"] == severities.count("critical")
    assert body["warning_count"] == severities.count("warning")
    assert body["info_count"] == severities.count("info")


def test_the_dashboard_dataset_is_named(command_client: Any) -> None:
    """The brief reads a bundled dataset; the page must say which."""
    assert command_client.get("/api/command-center").json()["dashboard_dataset"]


# ------------------------------------------- the guard: no second source of truth


def test_this_project_recomputes_nothing_the_sources_own() -> None:
    """Section 17: an aggregator, not a second source of truth.

    Asserted against the source rather than a docstring. If the collectors
    started deciding what "overdue" means, they would need date arithmetic
    against today; if they started judging incidents, they would need severity
    thresholds. Those belong to Projects 5 and 6.
    """
    import inspect

    import aiops_command.service as service
    import aiops_command.signals as signals

    source = inspect.getsource(signals) + inspect.getsource(service)

    # Signs of re-deriving what a source already decided.
    for marker in (
        "due_date <",
        "due_date >",
        "timedelta(",
        "z_score >",
        "std_dev",
        "TaskStatus.DONE",
    ):
        assert marker not in source, f"{marker!r} suggests Project 9 is recomputing a source's job"

    # And the positive fact: it asks the owning projects.
    assert "tracker.list_item_of" in source
    assert "builder.issues_for" in source
    assert "travelops.to_summary" in source
    assert "analyse(" in source


def test_the_anomaly_wording_is_the_analytics_services_own() -> None:
    """The sentence describing an anomaly must be written in exactly one place."""
    import inspect

    import aiops_command.signals as signals

    source = inspect.getsource(signals)
    assert "anomaly.describe()" in source
    assert "trend.describe()" in source


# ------------------------------------------------- the read-API shape guard


def test_the_source_read_apis_still_have_the_shape_this_project_relies_on(
    command_client: Any,
) -> None:
    """Fail loudly here rather than quietly on the deployed site.

    This is the only project that imports from other projects, so a rename in
    any of the four breaks it in a way its own tests would not catch. This
    calls each source's read functions and asserts the specific fields the
    collectors read.
    """
    from aiops_builder import service as builder
    from aiops_dashboard.analysis import analyse
    from aiops_dashboard.samples import load_sample
    from aiops_tracker import service as tracker
    from aiops_travelops import service as travelops

    session = command_client.session_factory()  # type: ignore[attr-defined]
    try:
        tracker.seed_if_empty(session)
        builder.seed_templates(session)
        session.commit()

        # --- Project 5, the tracker
        projects = tracker.list_projects(session)
        assert projects, "the tracker seeded nothing to read"
        item = tracker.list_item_of(projects[0])
        for attribute in (
            "id",
            "name",
            "state",
            "health",
            "health_reasoning",
            "task_count",
            "done_count",
            "overdue_count",
            "blocked_count",
            "completion_percent",
        ):
            assert hasattr(item, attribute), f"tracker ProjectListItem lost .{attribute}"

        # --- Project 4, the builder
        workflows = builder.list_workflows(session)
        assert workflows, "the builder seeded nothing to read"
        issues = builder.issues_for(workflows[0])
        assert isinstance(issues, list)
        for issue in issues:
            assert hasattr(issue, "blocks_execution"), "ValidationIssue lost .blocks_execution"
            assert hasattr(issue, "message")

        from aiops_builder.models import ExecutionRecord

        assert hasattr(ExecutionRecord, "status"), "ExecutionRecord lost .status"
        assert hasattr(ExecutionRecord, "workflow_id")

        # --- Project 6, travel operations
        assert callable(travelops.list_incidents)
        assert callable(travelops.to_summary)
        from aiops_travelops.schema import IncidentSummary

        for attribute in (
            "id",
            "title",
            "status",
            "severity",
            "affected_count",
            "affected_value_inr",
            "awaiting_approval_count",
        ):
            assert attribute in IncidentSummary.model_fields, (
                f"travel-ops IncidentSummary lost .{attribute}"
            )

        # --- Project 3, the dashboard
        analysis = analyse(load_sample("operations_metrics"), dataset="operations_metrics")
        assert hasattr(analysis, "anomalies") and hasattr(analysis, "trends")
        assert hasattr(analysis, "row_count")
        for anomaly in analysis.anomalies[:1]:
            assert callable(anomaly.describe), "Anomaly lost .describe()"
            assert anomaly.describe()
        for trend in analysis.trends[:1]:
            assert callable(trend.describe), "Trend lost .describe()"
            assert trend.describe()
            assert hasattr(trend, "change_pct") and hasattr(trend, "direction")
    finally:
        session.close()


def test_the_dependency_direction_stays_one_way() -> None:
    """None of the four sources may learn that Project 9 exists."""
    import inspect

    import aiops_builder.service as builder
    import aiops_dashboard.analysis as dashboard
    import aiops_tracker.service as tracker
    import aiops_travelops.service as travelops

    for module in (tracker, builder, travelops, dashboard):
        source = inspect.getsource(module)
        assert "aiops_command" not in source, (
            f"{module.__name__} imports the aggregator — the dependency must stay one-way"
        )


def test_gather_reports_all_four_sources(command_client: Any) -> None:
    """A source silently dropped from the gather would shrink the brief."""
    session = command_client.session_factory()  # type: ignore[attr-defined]
    try:
        result = gather(session, today=TODAY)
    finally:
        session.close()

    assert {s.source for s in result.sources} == {
        "tracker",
        "workflows",
        "travel_ops",
        "dashboard",
    }
    assert isinstance(result.collected_at, datetime)
    assert result.collected_at.tzinfo is not None
    _ = UTC
