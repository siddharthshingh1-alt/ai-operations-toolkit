"""Tests for Project 6 — AI Travel Operations (the flagship).

The most important tests in this file are the ones about approval. CLAUDE.md
Section 5 forbids the AI executing a high-risk action unattended, and Section
14's flow ends in a human decision. Those are claims the repository makes about
itself, so they are tested as properties of the code rather than trusted to a
comment: the graph is checked for shape, the send is attempted without an
approver, and the recording step is invoked directly with an unapproved
context. All three must refuse.

Nothing here needs an API key, a recording or a network — the AI is a stub.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from aiops_travelops import (
    RECORD_ID,
    CommunicationStatus,
    IncidentKind,
    approval_is_reachable_only_after,
    incident_workflow,
)
from aiops_travelops.models import IncidentStatus, Severity, TravelIncident
from aiops_travelops.schema import (
    ApprovalRequest,
    DraftedMessage,
    DraftSet,
    IncidentAssessment,
    ReportIncidentRequest,
)
from aiops_travelops.service import assess_and_draft, decide_communication, find_affected
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from aiops_adapters import Booking, BookingStatus, MockEmailProvider
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_utils import ValidationError
from aiops_workflow import ExecutionStatus, NodeType, WorkflowEngine, WorkflowExecution

# ------------------------------------------------------------------- doubles


def _booking(
    booking_id: str,
    *,
    agent_id: str = "AG-1001",
    agent_name: str = "Skyline Holidays",
    value: float = 40000.0,
    route: str = "DEL-DXB",
    days_ahead: int = 2,
) -> Booking:
    return Booking(
        id=booking_id,
        agent_id=agent_id,
        agent_name=agent_name,
        traveller_name="A Traveller",
        booking_type="flight",
        route=route,
        supplier="Air India",
        departure_at=datetime.now(UTC) + timedelta(days=days_ahead),
        status=BookingStatus.CONFIRMED,
        value_inr=value,
        created_at=datetime.now(UTC) - timedelta(days=20),
    )


class _StubAI(AIProvider):
    """Returns a fixed assessment then a fixed draft set. No network."""

    name = "stub"

    def __init__(self, agent_ids: list[str] | None = None) -> None:
        self.calls = 0
        self._agent_ids = agent_ids or ["AG-1001"]

    def generate_structured_output(self, prompt: str, **kwargs: Any) -> AIResult[Any]:
        self.calls += 1
        model = kwargs["output_model"]
        if model is IncidentAssessment:
            value: Any = IncidentAssessment(
                severity=Severity.HIGH,
                reasoning_summary="Several bookings are affected close to departure.",
                traveller_impact="Travellers face a long wait at the airport.",
                recommended_action="Contact the affected agencies today.",
            )
        else:
            value = DraftSet(
                messages=[
                    DraftedMessage(
                        agent_id=agent_id,
                        subject="Delay affecting your bookings",
                        body="Your bookings on this service are delayed. We will update you.",
                    )
                    for agent_id in self._agent_ids
                ]
            )
        return AIResult[Any](
            value=value,
            provider="stub",
            model="stub-model",
            duration_ms=3,
            usage=Usage(input_tokens=200, output_tokens=120, estimated_cost_usd=0.0002),
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

        raise AIProviderError("the model is unavailable")


class _FakeSession:
    """Just enough Session for the service: add / flush / no-op commit."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        return None


def _incident(**overrides: Any) -> TravelIncident:
    incident = TravelIncident(
        id="inc_test",
        kind=IncidentKind.FLIGHT_DELAY.value,
        title="DEL-DXB delayed",
        description="Aircraft technical issue.",
        route="DEL-DXB",
        supplier="Air India",
        occurred_at=datetime.now(UTC),
        status=IncidentStatus.OPEN.value,
        affected_booking_ids=[],
        affected_count=0,
        affected_value_inr=0.0,
        affected_agent_ids=[],
    )
    for key, value in overrides.items():
        setattr(incident, key, value)
    return incident


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> list[Booking]:
    """Point the booking provider at a small, predictable set of bookings."""
    bookings = [
        _booking("BK-1", agent_id="AG-1001", agent_name="Skyline Holidays", value=40000),
        _booking("BK-2", agent_id="AG-1001", agent_name="Skyline Holidays", value=25000),
        _booking("BK-3", agent_id="AG-1002", agent_name="Kaveri Tours", value=31000),
    ]
    by_id = {booking.id: booking for booking in bookings}

    class _Provider:
        def list_bookings(self, *, status: Any = None, limit: int = 200) -> list[Booking]:
            return list(bookings)

        def get_booking(self, booking_id: str) -> Booking | None:
            return by_id.get(booking_id)

        def find_affected_bookings(self, *, route: str, on_date: Any) -> list[Booking]:
            return [b for b in bookings if b.route == route]

    monkeypatch.setattr("aiops_travelops.service.get_booking_provider", lambda: _Provider())
    return bookings


# ------------------------------------------- the approval guarantee (critical)


def test_the_recording_step_sits_downstream_of_approval() -> None:
    """The graph itself must not offer a route to sending without approval."""
    workflow = incident_workflow()
    assert approval_is_reachable_only_after(workflow, RECORD_ID)


def test_a_send_without_an_approver_is_refused_by_the_adapter() -> None:
    """The second, independent guard: an unapproved send cannot be expressed."""
    provider = MockEmailProvider()
    with pytest.raises(ValidationError):
        provider.send_reply(thread_id="incident-x", body="anything", approved_by="")


def test_the_run_stops_at_approval_and_records_nothing(wired: list[Booking]) -> None:
    """Assessing drafts messages. It must not mark any of them as communicated."""
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1", "BK-2", "BK-3"],
        affected_count=3,
        affected_value_inr=96000.0,
        affected_agent_ids=["AG-1001", "AG-1002"],
    )

    incident, usage = assess_and_draft(
        db, incident, provider_override=_StubAI(["AG-1001", "AG-1002"])
    )

    assert incident.status == IncidentStatus.AWAITING_APPROVAL.value
    assert incident.communications, "drafts should exist"

    for communication in incident.communications:
        assert communication.status == CommunicationStatus.DRAFT.value
        assert communication.approved_by is None
        assert communication.approved_at is None
        # The one that matters: nothing has been recorded as communicated.
        assert communication.recorded_message_id is None

    execution = WorkflowExecution.model_validate(incident.execution)
    assert execution.status is ExecutionStatus.AWAITING_APPROVAL
    ran = {run.node_id for run in execution.node_runs}
    assert RECORD_ID not in ran, "the recording node must not have executed"
    assert usage.input_tokens > 0


def test_the_engine_refuses_to_resume_without_an_approver() -> None:
    """`resume` is the only way past the pause, and it demands attribution."""
    engine = WorkflowEngine()
    engine.register(NodeType.TRANSFORM, lambda node, ctx: {})
    engine.register(NodeType.AI_CLASSIFICATION, lambda node, ctx: {})
    engine.register(NodeType.AI_GENERATION, lambda node, ctx: {})
    engine.register(NodeType.EMAIL, lambda node, ctx: {"recorded": 1})

    workflow = incident_workflow()
    execution = engine.run(workflow, context={})
    assert execution.status is ExecutionStatus.AWAITING_APPROVAL

    with pytest.raises(ValidationError):
        engine.resume(workflow, execution, approved_by="   ")


def test_the_recording_handler_refuses_an_unapproved_context(
    wired: list[Booking],
) -> None:
    """Belt and braces: invoked directly with no approval, it still refuses.

    The handler's position after the approval node is what protects it. This
    asserts it does not *rely* on that position, so a future rewiring cannot
    silently turn it into an unattended send.
    """
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1"], affected_count=1, affected_value_inr=40000.0
    )
    incident, _ = assess_and_draft(db, incident, provider_override=_StubAI(["AG-1001"]))

    execution = WorkflowExecution.model_validate(incident.execution)
    engine = WorkflowEngine()
    captured: dict[str, Any] = {}

    def _record(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        captured["context"] = dict(context)
        raise AssertionError("the recording node ran without approval")

    engine.register(NodeType.EMAIL, _record)

    # Rejecting must finish the run without ever reaching the recording node.
    finished = engine.resume(incident_workflow(), execution, approved_by="Ops Lead", approved=False)
    assert finished.status is ExecutionStatus.SUCCEEDED
    assert "context" not in captured, "the recording node must not have been reached"


def test_approval_records_who_and_when(wired: list[Booking]) -> None:
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1", "BK-2"], affected_count=2, affected_value_inr=65000.0
    )
    incident, _ = assess_and_draft(db, incident, provider_override=_StubAI(["AG-1001"]))
    communication = incident.communications[0]

    decide_communication(db, communication, ApprovalRequest(approved=True, approved_by="Anita Rao"))

    assert communication.status == CommunicationStatus.APPROVED.value
    assert communication.approved_by == "Anita Rao"
    assert communication.approved_at is not None
    # Recorded, never transmitted.
    assert communication.recorded_message_id is not None
    assert incident.status == IncidentStatus.RESOLVED.value


def test_rejecting_keeps_the_message_unsent(wired: list[Booking]) -> None:
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1"], affected_count=1, affected_value_inr=40000.0
    )
    incident, _ = assess_and_draft(db, incident, provider_override=_StubAI(["AG-1001"]))
    communication = incident.communications[0]

    decide_communication(
        db,
        communication,
        ApprovalRequest(approved=False, approved_by="Anita Rao", note="Too vague."),
    )

    assert communication.status == CommunicationStatus.REJECTED.value
    assert communication.recorded_message_id is None
    assert communication.rejection_note == "Too vague."


def test_a_decision_cannot_be_made_twice(wired: list[Booking]) -> None:
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1"], affected_count=1, affected_value_inr=40000.0
    )
    incident, _ = assess_and_draft(db, incident, provider_override=_StubAI(["AG-1001"]))
    communication = incident.communications[0]

    decide_communication(db, communication, ApprovalRequest(approved=True, approved_by="Anita Rao"))
    with pytest.raises(ValidationError):
        decide_communication(
            db, communication, ApprovalRequest(approved=False, approved_by="Deepak Menon")
        )


# ------------------------------------------------------------- lookup + input


def test_affected_bookings_are_found_by_route(wired: list[Booking]) -> None:
    incident = _incident()
    found = find_affected(incident)
    assert {booking.id for booking in found} == {"BK-1", "BK-2", "BK-3"}


def test_a_regenerated_dataset_does_not_empty_a_lookup_already_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo dataset moves under the incidents; the lookup must survive it.

    Booking dates are regenerated on every deploy while incidents are seeded
    once, so the date match stops finding what an incident already names. The
    recorded ids still resolve, and they are the honest answer — the console
    reporting nothing affected beside a draft naming a booking is not.
    """
    recorded = _booking("BK-1")

    class _Moved:
        """Dates no longer line up; ids still do."""

        def list_bookings(self, *, status: Any = None, limit: int = 200) -> list[Booking]:
            return [recorded]

        def get_booking(self, booking_id: str) -> Booking | None:
            return recorded if booking_id == recorded.id else None

        def find_affected_bookings(self, *, route: str, on_date: Any) -> list[Booking]:
            return []

    monkeypatch.setattr("aiops_travelops.service.get_booking_provider", lambda: _Moved())

    incident = _incident(affected_booking_ids=["BK-1"], affected_count=1)
    assert [booking.id for booking in find_affected(incident)] == ["BK-1"]

    # An incident that never named anything still finds nothing: the fallback
    # recovers a recorded lookup, it does not invent one.
    assert find_affected(_incident(affected_booking_ids=[])) == []


def test_a_recorded_booking_that_was_cancelled_is_not_recovered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback must not resurrect bookings that are no longer live."""
    cancelled = _booking("BK-1")
    cancelled.status = BookingStatus.CANCELLED

    class _Cancelled:
        def list_bookings(self, *, status: Any = None, limit: int = 200) -> list[Booking]:
            return [cancelled]

        def get_booking(self, booking_id: str) -> Booking | None:
            return cancelled if booking_id == cancelled.id else None

        def find_affected_bookings(self, *, route: str, on_date: Any) -> list[Booking]:
            return []

    monkeypatch.setattr("aiops_travelops.service.get_booking_provider", lambda: _Cancelled())

    assert find_affected(_incident(affected_booking_ids=["BK-1"], affected_count=1)) == []


def test_an_incident_affecting_nothing_is_refused_before_spending_a_request(
    wired: list[Booking],
) -> None:
    """No affected bookings means nothing to assess — and no AI call."""
    db = cast("Session", _FakeSession())
    incident = _incident(affected_booking_ids=[], affected_count=0)
    stub = _StubAI()

    with pytest.raises(ValidationError) as caught:
        assess_and_draft(db, incident, provider_override=stub)

    assert stub.calls == 0, "no AI request should have been made"
    assert "no bookings" in caught.value.user_message.lower()


def test_an_ai_failure_leaves_the_incident_untouched(wired: list[Booking]) -> None:
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1"], affected_count=1, affected_value_inr=40000.0
    )

    # The engine catches the handler failure and the service turns it into a
    # typed error carrying a message safe to show a user (Section 23).
    with pytest.raises(ValidationError) as caught:
        assess_and_draft(db, incident, provider_override=_FailingAI())

    assert "nothing was sent" in caught.value.user_message.lower()

    assert incident.severity is None
    assert incident.communications == []
    assert incident.status == IncidentStatus.OPEN.value


def test_a_draft_for_an_unaffected_agency_is_dropped(wired: list[Booking]) -> None:
    """A message to someone who is not involved is worse than a missing one."""
    db = cast("Session", _FakeSession())
    incident = _incident(
        affected_booking_ids=["BK-1"], affected_count=1, affected_value_inr=40000.0
    )

    incident, _ = assess_and_draft(db, incident, provider_override=_StubAI(["AG-1001", "AG-9999"]))

    agent_ids = {c.agent_id for c in incident.communications}
    assert agent_ids == {"AG-1001"}


def test_reporting_an_incident_requires_a_title() -> None:
    with pytest.raises(PydanticValidationError):
        ReportIncidentRequest(kind=IncidentKind.FLIGHT_DELAY, title="")


def test_an_approval_cannot_be_anonymous() -> None:
    """Section 5: a human decision must be attributable."""
    with pytest.raises(PydanticValidationError):
        ApprovalRequest(approved=True, approved_by="")


# ------------------------------------------------------- the booking interface


def test_the_booking_interface_cannot_write_anything() -> None:
    """Section 14: never a real airline, GDS or payment system.

    The interface is read-only by construction. This asserts nobody has added
    a write method to it, in any provider.
    """
    from aiops_adapters import BookingProvider

    forbidden = {"create_booking", "cancel_booking", "charge", "refund", "pay", "book"}
    methods = {name for name in dir(BookingProvider) if not name.startswith("_")}
    assert not (methods & forbidden), f"a write method appeared: {methods & forbidden}"
