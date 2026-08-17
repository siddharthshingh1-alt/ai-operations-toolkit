"""Tests for Project 8 — AI Operations Inbox.

The one that matters most is the last section. Section 16 forbids sending
email without explicit human approval, and this project is the only one whose
whole job is handling email — so "nothing is sent without a named person" is
asserted three ways: at the adapter, at the service, and structurally against
the source, so a future code path cannot quietly acquire a default approver.

The rest covers the computed half (unanswered detection, thread grouping) as
arithmetic, and the model's half through a stub.

Nothing here needs an API key or a network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aiops_inbox import (
    UNANSWERED_AFTER_HOURS,
    Category,
    DraftedReply,
    ExtractedTask,
    TriageResult,
    Urgency,
    age_hours,
    agency_of,
    group_threads,
    is_unanswered,
    seeded_category,
)
from pydantic import ValidationError as PydanticValidationError

from aiops_adapters import Email
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_utils import ValidationError

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------------- fixtures


def _email(
    email_id: str = "EM-1",
    *,
    thread_id: str = "TH-1",
    hours_ago: float = 1.0,
    has_reply: bool = False,
    labels: list[str] | None = None,
    subject: str = "Change request for BK-00349",
    body: str = "Our client needs to move BK-00349 to the following week.",
) -> Email:
    return Email(
        id=email_id,
        thread_id=thread_id,
        sender="contact@northgatebusinesstravel.test",
        recipient="ops@example-travel.test",
        subject=subject,
        body=body,
        received_at=NOW - timedelta(hours=hours_ago),
        is_read=False,
        has_reply=has_reply,
        labels=labels if labels is not None else ["Booking Ops", "AG-1004"],
    )


class _StubAI(AIProvider):
    """Returns a valid triage, then a valid draft."""

    name = "stub"

    def __init__(self, category: Category = Category.BOOKING_OPS) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self._category = category

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        self.prompts.append(prompt)
        model = kwargs["output_model"]
        if model is TriageResult:
            value: Any = TriageResult(
                category=self._category,
                urgency=Urgency.HIGH,
                reasoning="The sender asks for a date change and a fare-rule answer.",
                summary="The agency wants to move a booking and needs the fare difference.",
                tasks=[ExtractedTask(title="Quote the fare difference", owner_hint="Booking Ops")],
                follow_up="Confirm the new date once the agency accepts the fare.",
            )
        elif model is DraftedReply:
            value = DraftedReply(
                body="Thank you — we are checking the fare rules and will confirm."
            )
        else:  # pragma: no cover
            raise AssertionError(f"unexpected output_model {model!r}")
        return AIResult[Any](
            value=value,
            provider="stub",
            model="stub-model",
            duration_ms=4,
            usage=Usage(input_tokens=280, output_tokens=95, estimated_cost_usd=0.0003),
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
def inbox_client() -> Any:
    """The inbox routes over a real (in-memory) database and the mock adapter."""
    import aiops_inbox.models  # noqa: F401  (registers the table)
    from aiops_inbox.router import router
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

    if not hasattr(inbox_client, "_compiled"):

        @compiles(JSONB, "sqlite")
        def _jsonb_as_json(type_: Any, compiler: Any, **kw: Any) -> str:
            return "JSON"

        inbox_client._compiled = True  # type: ignore[attr-defined]

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["inbox_triage"]])
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


# ------------------------------------------------- computed: unanswered mail


def test_a_replied_email_is_never_unanswered() -> None:
    old_but_answered = _email(hours_ago=500, has_reply=True)
    assert is_unanswered(old_but_answered, at=NOW) is False


def test_a_fresh_email_is_new_not_unanswered() -> None:
    """A list that flags everything that arrived an hour ago stops being read."""
    assert is_unanswered(_email(hours_ago=1), at=NOW) is False


def test_the_threshold_boundary_is_inclusive() -> None:
    just_under = _email(hours_ago=UNANSWERED_AFTER_HOURS - 0.1)
    exactly = _email(hours_ago=UNANSWERED_AFTER_HOURS)
    just_over = _email(hours_ago=UNANSWERED_AFTER_HOURS + 0.1)

    assert is_unanswered(just_under, at=NOW) is False
    assert is_unanswered(exactly, at=NOW) is True
    assert is_unanswered(just_over, at=NOW) is True


def test_age_is_measured_in_hours() -> None:
    assert age_hours(_email(hours_ago=36), at=NOW) == pytest.approx(36.0)


def test_a_naive_timestamp_is_treated_as_utc() -> None:
    """A adapter returning a naive datetime must not crash the arithmetic."""
    naive = _email()
    naive.received_at = datetime(2026, 6, 14, 12, 0)  # no tzinfo
    assert age_hours(naive, at=NOW) == pytest.approx(24.0)


# ------------------------------------------------------ computed: threading


def test_threads_are_grouped_and_ordered_oldest_first() -> None:
    """A thread only makes sense read forwards, whatever order it arrived in."""
    emails = [
        _email("EM-3", thread_id="TH-1", hours_ago=1),
        _email("EM-1", thread_id="TH-1", hours_ago=10),
        _email("EM-2", thread_id="TH-1", hours_ago=5),
    ]
    threads = group_threads(emails)
    assert len(threads) == 1
    assert [e.id for e in threads[0].emails] == ["EM-1", "EM-2", "EM-3"]
    assert threads[0].latest.id == "EM-3"
    assert threads[0].first.id == "EM-1"


def test_threads_are_listed_by_most_recent_activity() -> None:
    emails = [
        _email("EM-1", thread_id="TH-OLD", hours_ago=100),
        _email("EM-2", thread_id="TH-NEW", hours_ago=2),
    ]
    assert [t.thread_id for t in group_threads(emails)] == ["TH-NEW", "TH-OLD"]


def test_a_single_message_thread_is_not_long() -> None:
    threads = group_threads([_email()])
    assert threads[0].message_count == 1
    assert threads[0].is_long is False


def test_a_three_message_thread_is_long_enough_to_summarise() -> None:
    emails = [_email(f"EM-{i}", thread_id="TH-1", hours_ago=10 - i) for i in range(3)]
    assert group_threads(emails)[0].is_long is True


def test_grouping_an_empty_inbox_is_empty() -> None:
    assert group_threads([]) == []


# ------------------------------------------------------------------ labels


def test_the_agency_is_read_from_the_labels() -> None:
    assert agency_of(_email(labels=["Finance", "AG-1002"])) == "AG-1002"


def test_an_email_with_no_agency_label_has_none() -> None:
    assert agency_of(_email(labels=["Internal"])) is None


def test_the_seeded_category_is_readable_but_separate() -> None:
    """Available for evaluation, never as an input to classification."""
    assert seeded_category(_email(labels=["Vendor/Hotel", "AG-1001"])) == "Vendor/Hotel"
    assert seeded_category(_email(labels=["AG-1001"])) is None


def test_the_triage_prompt_never_contains_the_seeded_category() -> None:
    """A classifier handed the answer is not a classifier."""
    from aiops_inbox.prompts import triage_prompt

    email = _email(labels=["Finance", "AG-1004"], subject="Invoice query", body="Commission query.")
    prompt = triage_prompt([email])
    assert "Finance" not in prompt
    assert "AG-1004" not in prompt


# ---------------------------------------------------- the model's judgement


def test_an_invented_category_is_rejected() -> None:
    """The seven categories are a closed set, enforced by the type."""
    with pytest.raises(PydanticValidationError):
        TriageResult.model_validate(
            {
                "category": "Refunds",
                "urgency": "high",
                "reasoning": "Because.",
                "summary": "A refund query.",
            }
        )


def test_a_classification_with_no_reasoning_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        TriageResult.model_validate(
            {"category": "Finance", "urgency": "low", "summary": "A query."}
        )


def test_empty_reasoning_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        TriageResult.model_validate(
            {"category": "Finance", "urgency": "low", "reasoning": "", "summary": "A query."}
        )


def test_an_invented_urgency_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        TriageResult.model_validate(
            {
                "category": "Finance",
                "urgency": "extremely urgent",
                "reasoning": "Because.",
                "summary": "A query.",
            }
        )


def test_a_valid_triage_needs_no_tasks() -> None:
    """Not every email asks for something; inventing one would be worse."""
    result = TriageResult.model_validate(
        {
            "category": "Internal",
            "urgency": "low",
            "reasoning": "An FYI with no request in it.",
            "summary": "Weekly summary shared for information.",
        }
    )
    assert result.tasks == []


def test_an_empty_draft_body_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        DraftedReply.model_validate({"body": ""})


# --------------------------------------------------------------- the API


def test_the_inbox_lists_messages_without_any_ai(inbox_client: Any) -> None:
    response = inbox_client.get("/api/inbox")
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["counts"]["total"] > 0
    assert body["unanswered_after_hours"] == UNANSWERED_AFTER_HOURS
    assert len(body["categories"]) == 7
    # Nothing is triaged until someone asks.
    assert body["counts"]["triaged"] == 0
    assert all(item["triage"] is None for item in body["items"])


def test_the_unanswered_filter_narrows_the_list(inbox_client: Any) -> None:
    everything = inbox_client.get("/api/inbox?limit=200").json()
    filtered = inbox_client.get("/api/inbox?limit=200&unanswered_only=true").json()
    assert len(filtered["items"]) <= len(everything["items"])
    assert all(item["email"]["is_unanswered"] for item in filtered["items"])


def test_an_invalid_category_filter_is_rejected(inbox_client: Any) -> None:
    assert inbox_client.get("/api/inbox?category=Nonsense").status_code == 422


def test_an_unknown_thread_is_a_clean_404(inbox_client: Any) -> None:
    response = inbox_client.get("/api/inbox/threads/TH-does-not-exist")
    assert response.status_code == 404


def test_triaging_stores_the_category_with_its_reasoning(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiops_inbox.service as svc

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI())
    thread_id = inbox_client.get("/api/inbox").json()["items"][0]["email"]["thread_id"]

    response = inbox_client.post(f"/api/inbox/threads/{thread_id}/triage")
    assert response.status_code == 200
    triage = response.json()["thread"]["triage"]
    assert triage["category"] == "Booking Ops"
    assert triage["reasoning"]
    assert triage["summary"]
    assert triage["tasks"]
    assert response.json()["usage"]["model"] == "stub-model"


def test_agreement_with_the_seeded_category_is_recorded(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The evaluation signal, available only because the data is seeded."""
    import aiops_inbox.service as svc

    listing = inbox_client.get("/api/inbox?limit=200").json()
    # Find a message whose seeded category is Booking Ops, so the stub agrees.
    target = next(item for item in listing["items"] if "Change request" in item["email"]["subject"])
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI(Category.BOOKING_OPS))
    inbox_client.post(f"/api/inbox/threads/{target['email']['thread_id']}/triage")

    accuracy = inbox_client.get("/api/inbox").json()["accuracy"]
    assert accuracy["triaged"] >= 1
    assert accuracy["percent"] is not None


def test_a_disagreement_is_recorded_as_such(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiops_inbox.service as svc

    listing = inbox_client.get("/api/inbox?limit=200").json()
    target = next(item for item in listing["items"] if "Change request" in item["email"]["subject"])
    # Deliberately the wrong answer for a Booking Ops email.
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI(Category.FINANCE))
    body = inbox_client.post(f"/api/inbox/threads/{target['email']['thread_id']}/triage").json()
    assert body["thread"]["triage"]["agreed_with_seed"] is False


def test_an_ai_failure_leaves_no_triage_behind(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiops_inbox.service as svc

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _FailingAI())
    thread_id = inbox_client.get("/api/inbox").json()["items"][0]["email"]["thread_id"]

    response = inbox_client.post(f"/api/inbox/threads/{thread_id}/triage")
    assert response.status_code >= 500
    assert inbox_client.get(f"/api/inbox/threads/{thread_id}").json()["triage"] is None


def test_reading_the_inbox_spends_no_ai_request(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiops_inbox.service as svc

    stub = _StubAI()
    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: stub)
    for _ in range(3):
        inbox_client.get("/api/inbox")
        inbox_client.get("/api/inbox?unanswered_only=true")
    assert stub.calls == 0


# ------------------------------------------- nothing is sent without a person


def _drafted(inbox_client: Any, monkeypatch: pytest.MonkeyPatch) -> str:
    import aiops_inbox.service as svc

    monkeypatch.setattr(svc, "get_provider", lambda *a, **k: _StubAI())
    thread_id = inbox_client.get("/api/inbox").json()["items"][0]["email"]["thread_id"]
    inbox_client.post(f"/api/inbox/threads/{thread_id}/triage")
    response = inbox_client.post(f"/api/inbox/threads/{thread_id}/draft")
    assert response.status_code == 200
    assert response.json()["thread"]["triage"]["draft_status"] == "draft"
    return thread_id


def test_a_draft_is_a_draft_and_goes_nowhere(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = _drafted(inbox_client, monkeypatch)
    triage = inbox_client.get(f"/api/inbox/threads/{thread_id}").json()["triage"]
    assert triage["draft_body"]
    assert triage["draft_status"] == "draft"
    assert triage["approved_by"] is None
    assert triage["recorded_message_id"] is None


def test_approving_requires_a_named_person(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = _drafted(inbox_client, monkeypatch)
    response = inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": True, "approved_by": ""},
    )
    assert response.status_code == 422


def test_a_whitespace_approver_is_refused(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`min_length` alone would let three spaces through."""
    thread_id = _drafted(inbox_client, monkeypatch)
    response = inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": True, "approved_by": "   "},
    )
    assert response.status_code == 422


def test_approval_records_who_and_when(inbox_client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    thread_id = _drafted(inbox_client, monkeypatch)
    body = inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": True, "approved_by": "Anita Rao"},
    ).json()
    triage = body["triage"]
    assert triage["draft_status"] == "approved"
    assert triage["approved_by"] == "Anita Rao"
    assert triage["approved_at"]
    # Recorded, never transmitted.
    assert triage["recorded_message_id"]


def test_rejecting_records_nothing_as_sent(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = _drafted(inbox_client, monkeypatch)
    triage = inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": False, "approved_by": "Anita Rao", "note": "Too vague."},
    ).json()["triage"]
    assert triage["draft_status"] == "rejected"
    assert triage["rejection_note"] == "Too vague."
    assert triage["recorded_message_id"] is None
    assert triage["approved_by"] is None


def test_deciding_with_no_draft_is_refused(inbox_client: Any) -> None:
    thread_id = inbox_client.get("/api/inbox").json()["items"][0]["email"]["thread_id"]
    response = inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": True, "approved_by": "Anita Rao"},
    )
    assert response.status_code == 404


def test_redrafting_clears_a_previous_decision(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An approval recorded against text that has since changed would be a lie."""
    thread_id = _drafted(inbox_client, monkeypatch)
    inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": False, "approved_by": "Anita Rao", "note": "Redo it."},
    )
    triage = inbox_client.post(f"/api/inbox/threads/{thread_id}/draft").json()["thread"]["triage"]
    assert triage["draft_status"] == "draft"
    assert triage["rejection_note"] is None
    assert triage["approved_by"] is None


def test_an_approved_thread_is_not_redrafted(
    inbox_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = _drafted(inbox_client, monkeypatch)
    inbox_client.post(
        f"/api/inbox/threads/{thread_id}/decision",
        json={"approved": True, "approved_by": "Anita Rao"},
    )
    response = inbox_client.post(f"/api/inbox/threads/{thread_id}/draft")
    assert response.status_code == 422


def test_the_adapter_itself_refuses_an_unapproved_send() -> None:
    """Below the service, the seam refuses too. Defence in depth."""
    from aiops_adapters import get_email_provider

    provider = get_email_provider()
    thread_id = provider.list_emails(limit=1)[0].thread_id
    with pytest.raises(ValidationError):
        provider.send_reply(thread_id=thread_id, body="anything", approved_by="")


def test_no_code_path_supplies_its_own_approver() -> None:
    """The structural guard: an approver may only come from a request.

    A future convenience — defaulting to the demo user, falling back to
    "system", reusing the last approver — would make an unattributed send
    expressible again without any test noticing. This reads the source and
    refuses those shapes.
    """
    import importlib
    import inspect

    # `aiops_inbox.router` as an attribute is the APIRouter re-exported by the
    # package __init__; the module has to be asked for by name.
    service = importlib.import_module("aiops_inbox.service")
    router = importlib.import_module("aiops_inbox.router")

    package = inspect.getsource(service) + inspect.getsource(router)

    forbidden = (
        'approved_by="system"',
        "approved_by='system'",
        'approved_by="automated"',
        "approved_by=settings.demo_user_name",
        "approved_by=demo_user",
        'approved_by="AI"',
        "approved_by=None",
    )
    for marker in forbidden:
        assert marker not in package, f"{marker!r} would allow an unattributed send"

    # And the positive fact: the one send call takes the request's approver.
    send_calls = [line for line in package.splitlines() if "send_reply(" in line]
    assert len(send_calls) == 1, "there must be exactly one path to a send"
    assert "approved_by=approver" in inspect.getsource(service)


def test_the_inbox_never_copies_an_email_into_the_database() -> None:
    """Storage holds this project's output, not the mail."""
    from aiops_inbox.models import InboxTriage

    columns = set(InboxTriage.__table__.columns.keys())
    for leaked in ("subject", "body", "sender", "recipient", "received_at"):
        assert leaked not in columns, f"{leaked!r} copies the email into the database"
    assert "email_id" in columns and "thread_id" in columns
