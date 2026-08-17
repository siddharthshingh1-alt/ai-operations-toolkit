"""Tests for Project 5 — AI Project Tracker.

Two things carry most of the weight here.

The first is the **compute/judge split**. Overdue, blocked and dependency state
are calculated in code, so they are tested as arithmetic — exactly, at their
boundaries, including the boundary everyone gets wrong (due *today* is not
overdue). If these were left to a model they could only be tested loosely.

The second is that **a health label without reasoning is not a valid
response**. `HealthAssessment` requires `reasoning` and `contributing_factors`,
so a model returning `{"health": "red"}` fails validation before anything is
stored. That is asserted directly rather than trusted, because it is the whole
claim of Section 13.

Nothing here needs an API key or a network — the AI is a stub.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from aiops_tracker import (
    MAX_DEPENDENCY_DEPTH,
    HealthAssessment,
    NextActions,
    ProjectSummary,
    WeeklyReportContent,
    blocking_task,
    is_overdue,
    project_facts,
)
from aiops_tracker.models import Health, Priority, TaskStatus, TrackedProject, TrackedTask
from pydantic import ValidationError as PydanticValidationError

from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_utils import ValidationError

TODAY = date(2026, 6, 15)


# ------------------------------------------------------------------- fixtures


def _task(
    title: str,
    *,
    status: TaskStatus = TaskStatus.TODO,
    due: date | None = None,
    owner: str = "Someone",
    depends_on: str | None = None,
    task_id: str | None = None,
    position: int = 0,
) -> TrackedTask:
    """An in-memory task. Never added to a session — these test pure functions."""
    task = TrackedTask(
        id=task_id or f"tsk_{title.lower().replace(' ', '_')[:20]}",
        project_id="prj_test",
        title=title,
        owner=owner,
        due_date=due,
        status=status.value,
        priority=Priority.MEDIUM.value,
        depends_on_id=depends_on,
        position=position,
    )
    return task


def _project(tasks: list[TrackedTask], *, target: date | None = None) -> TrackedProject:
    project = TrackedProject(
        id="prj_test",
        name="Test project",
        description="",
        owner="Owner",
        target_date=target,
        risks=[],
    )
    project.tasks = tasks
    for task in tasks:
        task.created_at = datetime.now(UTC)
    return project


class _StubAI(AIProvider):
    """Returns a valid object for whichever schema is asked for. No network."""

    name = "stub"

    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        self.prompts.append(prompt)
        model = kwargs["output_model"]
        value: Any
        if model is HealthAssessment:
            value = HealthAssessment(
                health=Health.YELLOW,
                reasoning="Two tasks are overdue and one is blocked on a vendor.",
                contributing_factors=["2 tasks overdue", "1 task blocked"],
                confidence="medium",
            )
        elif model is NextActions:
            value = NextActions(
                actions=[
                    {
                        "action": "Escalate the vendor credentials request.",
                        "rationale": "It blocks the only remaining integration task.",
                        "task_id": "tsk_integrate",
                    }
                ]
            )
        elif model is ProjectSummary:
            value = ProjectSummary(summary="The project is behind but recoverable.")
        elif model is WeeklyReportContent:
            value = WeeklyReportContent(
                executive_summary="One project is slipping; two are on track.",
                highlights=["Checklist finished"],
                concerns=["Refund integration blocked"],
                risks=["Vendor has missed two deadlines"],
                recommended_actions=["Escalate to the vendor's account manager"],
            )
        else:  # pragma: no cover — a new schema would need a stub branch
            raise AssertionError(f"unexpected output_model {model!r}")

        return AIResult[Any](
            value=value,
            provider="stub",
            model="stub-model",
            duration_ms=4,
            usage=Usage(input_tokens=300, output_tokens=90, estimated_cost_usd=0.0003),
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
    """The provider is reachable and refuses. Section 23: fail gracefully."""

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        from aiops_utils import AIProviderError

        raise AIProviderError("upstream exploded")


class _QuotaExhaustedAI(_StubAI):
    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        from aiops_utils import AIQuotaExhausted

        raise AIQuotaExhausted("free tier spent")


# ------------------------------------------------- computed facts: the overdue


def test_a_task_due_today_is_not_overdue() -> None:
    """The boundary everyone gets wrong. The day is not over yet."""
    assert is_overdue(_task("Today", due=TODAY), today=TODAY) is False


def test_a_task_due_yesterday_is_overdue() -> None:
    assert is_overdue(_task("Yesterday", due=TODAY - timedelta(days=1)), today=TODAY) is True


def test_a_finished_task_is_never_overdue() -> None:
    """A late task that got done is history, not a problem to act on."""
    late_but_done = _task("Done late", status=TaskStatus.DONE, due=TODAY - timedelta(days=30))
    assert is_overdue(late_but_done, today=TODAY) is False


def test_a_task_with_no_due_date_is_never_overdue() -> None:
    assert is_overdue(_task("Undated", due=None), today=TODAY) is False


# ------------------------------------------------ computed facts: dependencies


def test_a_task_waiting_on_an_unfinished_task_is_blocked_by_it() -> None:
    first = _task("Build it", task_id="tsk_a", status=TaskStatus.IN_PROGRESS)
    second = _task("Test it", task_id="tsk_b", depends_on="tsk_a")
    by_id = {t.id: t for t in (first, second)}
    assert blocking_task(second, by_id) is first


def test_a_task_waiting_on_a_finished_task_is_not_blocked() -> None:
    first = _task("Build it", task_id="tsk_a", status=TaskStatus.DONE)
    second = _task("Test it", task_id="tsk_b", depends_on="tsk_a")
    by_id = {t.id: t for t in (first, second)}
    assert blocking_task(second, by_id) is None


def test_the_walk_reaches_past_a_finished_link_to_the_real_blocker() -> None:
    """A -> B -> C where B is done: C is still stuck behind A."""
    a = _task("Vendor access", task_id="tsk_a", status=TaskStatus.BLOCKED)
    b = _task("Integration", task_id="tsk_b", status=TaskStatus.DONE, depends_on="tsk_a")
    c = _task("Pilot", task_id="tsk_c", depends_on="tsk_b")
    by_id = {t.id: t for t in (a, b, c)}
    assert blocking_task(c, by_id) is a


def test_a_dependency_cycle_terminates_instead_of_hanging() -> None:
    """The data model permits a cycle, so the reader must survive one.

    Two writes in the wrong order can create A -> B -> A whatever the write-time
    check does. If the walk did not remember where it had been, this test would
    not fail — it would never finish.
    """
    a = _task("A", task_id="tsk_a", depends_on="tsk_b")
    b = _task("B", task_id="tsk_b", depends_on="tsk_a")
    by_id = {t.id: t for t in (a, b)}
    assert blocking_task(a, by_id) is b  # B is unfinished, so it is the blocker
    # And the walk stops rather than looping for ever.
    b.status = TaskStatus.DONE.value
    assert blocking_task(a, by_id) is None


def test_a_self_dependency_terminates() -> None:
    solo = _task("Impossible", task_id="tsk_a", depends_on="tsk_a")
    assert blocking_task(solo, {"tsk_a": solo}) is None


def test_a_long_chain_is_bounded() -> None:
    """A chain longer than the bound stops rather than walking for ever."""
    chain = [
        _task(f"Step {i}", task_id=f"tsk_{i}", status=TaskStatus.DONE, depends_on=f"tsk_{i + 1}")
        for i in range(MAX_DEPENDENCY_DEPTH + 10)
    ]
    by_id = {t.id: t for t in chain}
    assert blocking_task(chain[0], by_id) is None


def test_a_dependency_pointing_at_a_deleted_task_is_not_a_blocker() -> None:
    orphan = _task("Orphan", task_id="tsk_a", depends_on="tsk_gone")
    assert blocking_task(orphan, {"tsk_a": orphan}) is None


# ------------------------------------------------------------ computed facts


def test_facts_count_what_is_there() -> None:
    project = _project(
        [
            _task("Done", status=TaskStatus.DONE, due=TODAY - timedelta(days=3), position=0),
            _task("Late", due=TODAY - timedelta(days=2), position=1),
            _task("Blocked", status=TaskStatus.BLOCKED, position=2),
            _task(
                "Running", status=TaskStatus.IN_PROGRESS, due=TODAY + timedelta(days=5), position=3
            ),
        ],
        target=TODAY + timedelta(days=10),
    )
    facts = project_facts(project, today=TODAY)

    assert facts.task_count == 4
    assert facts.done_count == 1
    assert facts.blocked_count == 1
    assert facts.overdue_count == 1
    assert facts.overdue_task_titles == ["Late"]
    assert facts.completion_percent == 25.0
    assert facts.days_to_target == 10


def test_an_empty_project_produces_usable_facts() -> None:
    """Empty data must not divide by zero (Section 25's 'empty data' case)."""
    facts = project_facts(_project([]), today=TODAY)
    assert facts.task_count == 0
    assert facts.completion_percent == 0.0
    assert facts.overdue_task_titles == []


def test_a_past_target_date_reports_negative_days() -> None:
    facts = project_facts(_project([], target=TODAY - timedelta(days=4)), today=TODAY)
    assert facts.days_to_target == -4


def test_tasks_with_no_owner_are_counted() -> None:
    project = _project([_task("Nobody's", owner=""), _task("Someone's", owner="Anita")])
    assert project_facts(project, today=TODAY).unassigned_count == 1


# ---------------------------------------- the rule: no label without reasoning


def test_a_health_label_with_no_reasoning_is_rejected() -> None:
    """Section 13's requirement, enforced by the schema rather than the prompt."""
    with pytest.raises(PydanticValidationError):
        HealthAssessment.model_validate({"health": "red"})


def test_a_health_label_with_empty_reasoning_is_rejected() -> None:
    """An empty string is a bare label wearing a coat."""
    with pytest.raises(PydanticValidationError):
        HealthAssessment.model_validate(
            {"health": "red", "reasoning": "", "contributing_factors": ["x"]}
        )


def test_a_health_label_with_no_contributing_factors_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        HealthAssessment.model_validate(
            {"health": "green", "reasoning": "It is fine.", "contributing_factors": []}
        )


def test_an_invented_health_value_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        HealthAssessment.model_validate(
            {"health": "amber", "reasoning": "Some prose.", "contributing_factors": ["x"]}
        )


def test_a_valid_assessment_round_trips() -> None:
    assessment = HealthAssessment.model_validate(
        {
            "health": "yellow",
            "reasoning": "Two overdue tasks against a target ten days away.",
            "contributing_factors": ["2 overdue"],
        }
    )
    assert assessment.health is Health.YELLOW
    assert assessment.confidence == "medium"  # defaulted, not required


def test_next_actions_requires_at_least_one_action() -> None:
    with pytest.raises(PydanticValidationError):
        NextActions.model_validate({"actions": []})


# ------------------------------------------------------------- the AI, stubbed


@pytest.fixture
def tracker_client() -> Any:
    """The tracker's routes over a real (in-memory) database.

    The same harness shape the Workflow Builder uses — SQLite standing in for
    Postgres, with JSONB compiled down, because the bug that harness caught
    (a row keyed differently from its own document) was only visible through
    the HTTP layer against real storage.
    """
    from aiops_tracker.models import TrackedProject as _P  # noqa: F401  (registers tables)
    from aiops_tracker.router import router
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

    if not hasattr(tracker_client, "_compiled"):

        @compiles(JSONB, "sqlite")
        def _jsonb_as_json(type_: Any, compiler: Any, **kw: Any) -> str:
            return "JSON"

        tracker_client._compiled = True  # type: ignore[attr-defined]

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [Base.metadata.tables[n] for n in ("tracked_projects", "tracked_tasks")]
    Base.metadata.create_all(engine, tables=tables)
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
    return TestClient(app)


def test_the_tracker_seeds_itself_on_first_read(tracker_client: Any) -> None:
    body = tracker_client.get("/api/tracker/projects").json()
    assert body["seeded"] == 3
    assert len(body["projects"]) == 3
    # Seeding installs data, never a health label — that judgement is the
    # model's, and a seeded one would be the fake functionality Section 2 bans.
    assert all(p["health"] is None for p in body["projects"])


def test_seeding_happens_once(tracker_client: Any) -> None:
    tracker_client.get("/api/tracker/projects")
    assert tracker_client.get("/api/tracker/projects").json()["seeded"] == 0


def test_a_project_round_trips_through_storage(tracker_client: Any) -> None:
    created = tracker_client.post(
        "/api/tracker/projects",
        json={"name": "Peak season readiness", "owner": "Anita", "risks": ["Vendor capacity"]},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    added = tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks",
        json={"title": "Agree the surge plan", "owner": "Deepak", "priority": "high"},
    )
    assert added.status_code == 200
    assert added.json()["facts"]["task_count"] == 1

    fetched = tracker_client.get(f"/api/tracker/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["tasks"][0]["title"] == "Agree the surge plan"


def test_a_missing_project_is_a_clean_404(tracker_client: Any) -> None:
    response = tracker_client.get("/api/tracker/projects/prj_nope")
    assert response.status_code == 404
    assert response.json()["message"] == "That project does not exist."


def test_an_invalid_project_is_rejected(tracker_client: Any) -> None:
    """Section 25's 'invalid input' and 'missing required fields'."""
    assert tracker_client.post("/api/tracker/projects", json={"name": "x"}).status_code == 422
    assert tracker_client.post("/api/tracker/projects", json={}).status_code == 422


def test_a_task_cannot_depend_on_itself(tracker_client: Any) -> None:
    project_id = tracker_client.post(
        "/api/tracker/projects", json={"name": "Dependency rules"}
    ).json()["id"]
    detail = tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks", json={"title": "Only task"}
    ).json()
    task_id = detail["tasks"][0]["id"]

    response = tracker_client.patch(
        f"/api/tracker/tasks/{task_id}", json={"depends_on_id": task_id}
    )
    assert response.status_code == 422
    assert "itself" in response.json()["message"]


def test_a_circular_dependency_is_refused_at_write_time(tracker_client: Any) -> None:
    project_id = tracker_client.post("/api/tracker/projects", json={"name": "Cycles"}).json()["id"]
    detail = tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks", json={"title": "First"}
    ).json()
    first_id = detail["tasks"][0]["id"]
    detail = tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks",
        json={"title": "Second", "depends_on_id": first_id},
    ).json()
    second_id = [t for t in detail["tasks"] if t["title"] == "Second"][0]["id"]

    # First now waiting on Second would close the loop.
    response = tracker_client.patch(
        f"/api/tracker/tasks/{first_id}", json={"depends_on_id": second_id}
    )
    assert response.status_code == 422
    assert "circular" in response.json()["message"].lower()


def test_a_blocker_note_does_not_outlive_the_block(tracker_client: Any) -> None:
    project_id = tracker_client.post("/api/tracker/projects", json={"name": "Blockers"}).json()[
        "id"
    ]
    detail = tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks",
        json={"title": "Waiting", "status": "blocked", "blocker_note": "Vendor silent"},
    ).json()
    task_id = detail["tasks"][0]["id"]
    assert detail["tasks"][0]["blocker_note"] == "Vendor silent"

    moved = tracker_client.patch(
        f"/api/tracker/tasks/{task_id}", json={"status": "in_progress"}
    ).json()
    assert moved["tasks"][0]["blocker_note"] is None


def test_assessment_stores_the_reasoning_with_the_label() -> None:
    """The service must never write a status without the prose behind it."""
    from aiops_tracker import service

    project = _project([_task("Late", due=TODAY - timedelta(days=2))])
    stub = _StubAI()

    class _Session:
        def flush(self) -> None: ...

    updated, usage = service.assess_health(
        _Session(),  # type: ignore[arg-type]
        project,
        provider_override=stub,
        on=TODAY,
    )
    assert updated.health == Health.YELLOW.value
    assert updated.health_reasoning
    assert updated.health_factors
    assert usage.model == "stub-model"
    assert stub.calls == 1


def test_the_model_is_given_the_computed_figures() -> None:
    """The prompt must carry the facts, or the judgement is uninformed."""
    from aiops_tracker import service

    project = _project(
        [
            _task("Late one", due=TODAY - timedelta(days=2), position=0),
            _task("Blocked one", status=TaskStatus.BLOCKED, position=1),
        ]
    )
    stub = _StubAI()

    class _Session:
        def flush(self) -> None: ...

    service.assess_health(
        _Session(),  # type: ignore[arg-type]
        project,
        provider_override=stub,
        on=TODAY,
    )
    prompt = stub.prompts[0]
    assert "Overdue tasks: 1" in prompt
    assert "Late one" in prompt
    assert "Blocked one" in prompt


def test_an_ai_failure_surfaces_as_a_provider_error(tracker_client: Any) -> None:
    """Section 25's 'AI failure'. Never a stack trace, never a fake status."""
    from aiops_tracker import service

    project = _project([_task("Anything")])

    class _Session:
        def flush(self) -> None: ...

    from aiops_utils import AIProviderError

    with pytest.raises(AIProviderError):
        service.assess_health(
            _Session(),  # type: ignore[arg-type]
            project,
            provider_override=_FailingAI(),
            on=TODAY,
        )
    # And nothing was written: a failed assessment leaves no label behind.
    assert project.health is None
    assert project.health_reasoning is None


def test_a_spent_quota_surfaces_as_quota_exhausted() -> None:
    """Section 3b: an exhausted free tier is an expected end state."""
    from aiops_tracker import service

    from aiops_utils import AIQuotaExhausted

    class _Session:
        def flush(self) -> None: ...

    with pytest.raises(AIQuotaExhausted):
        service.assess_health(
            _Session(),  # type: ignore[arg-type]
            _project([_task("Anything")]),
            provider_override=_QuotaExhaustedAI(),
            on=TODAY,
        )


def test_next_actions_drops_an_invented_task_id() -> None:
    """The advice survives; a link that leads nowhere does not."""
    from aiops_tracker import service

    project = _project([_task("Real task", task_id="tsk_real")])

    class _Session:
        def flush(self) -> None: ...

    updated, _ = service.suggest_next_actions(
        _Session(),  # type: ignore[arg-type]
        project,
        provider_override=_StubAI(),  # returns task_id "tsk_integrate", not present
        on=TODAY,
    )
    assert len(updated.next_actions) == 1
    assert updated.next_actions[0]["task_id"] is None
    assert updated.next_actions[0]["action"]


def test_next_actions_refuses_when_everything_is_done() -> None:
    from aiops_tracker import service

    project = _project([_task("Finished", status=TaskStatus.DONE)])
    stub = _StubAI()

    class _Session:
        def flush(self) -> None: ...

    with pytest.raises(ValidationError):
        service.suggest_next_actions(
            _Session(),  # type: ignore[arg-type]
            project,
            provider_override=stub,
            on=TODAY,
        )
    assert stub.calls == 0, "a request must not be spent to discover there is nothing to do"


# ---------------------------------------------------------------- the AI: HTTP


def test_assessing_through_the_api_stores_and_returns_reasoning(
    tracker_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiops_tracker.service as svc

    project_id = tracker_client.post(
        "/api/tracker/projects", json={"name": "Assessed project"}
    ).json()["id"]
    tracker_client.post(
        f"/api/tracker/projects/{project_id}/tasks",
        json={"title": "A task", "status": "blocked", "blocker_note": "waiting"},
    )

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI())
    response = tracker_client.post(f"/api/tracker/projects/{project_id}/assess")

    assert response.status_code == 200
    body = response.json()
    assert body["project"]["health"] == "yellow"
    assert body["project"]["health_reasoning"]
    assert body["project"]["health_factors"]
    assert body["usage"]["model"] == "stub-model"


def test_the_weekly_report_needs_at_least_one_project() -> None:
    """Section 25's 'empty data' at the report level."""
    from aiops_tracker import service

    class _EmptySession:
        def scalars(self, *a: Any, **k: Any) -> Any:
            return []

        def flush(self) -> None: ...

    with pytest.raises(ValidationError):
        service.weekly_report(
            _EmptySession(),  # type: ignore[arg-type]
            provider_override=_StubAI(),
            on=TODAY,
        )


def test_the_report_exports_without_spending_a_request(tracker_client: Any) -> None:
    """Export renders what is on screen. It must never regenerate anything."""
    content = {
        "executive_summary": "One project is slipping.",
        "highlights": ["A finished"],
        "concerns": ["B blocked"],
        "risks": ["Vendor"],
        "recommended_actions": ["Escalate"],
    }
    response = tracker_client.post(
        "/api/tracker/report/weekly/export?format=markdown", json=content
    )
    assert response.status_code == 200
    assert b"One project is slipping." in response.content
    assert "attachment" in response.headers["content-disposition"]


def test_the_report_export_rejects_an_unknown_format(tracker_client: Any) -> None:
    response = tracker_client.post(
        "/api/tracker/report/weekly/export?format=powerpoint", json={"executive_summary": "x"}
    )
    assert response.status_code == 422
