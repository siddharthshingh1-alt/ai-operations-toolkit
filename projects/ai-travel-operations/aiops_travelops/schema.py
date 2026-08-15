"""Request, response and AI output shapes for Travel Operations.

The AI schemas are where CLAUDE.md Section 5's explainability rule is enforced.
A severity is never allowed to arrive as a bare label: `reasoning_summary` is a
required field, so a model that assigns "critical" without saying why has
produced an invalid response rather than an unhelpful one.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from aiops_adapters import Booking
from aiops_travelops.models import IncidentKind, Severity

# ------------------------------------------------------------------ AI output


class IncidentAssessment(BaseModel):
    """The model's judgement of one incident.

    Every field here is an opinion. The counts and values it reasons about were
    computed before the model was called and are not its to change.
    """

    severity: Severity = Field(
        description="How serious this is for the agents and travellers affected."
    )
    reasoning_summary: str = Field(
        description=(
            "Two or three sentences explaining the severity, referring to the "
            "affected booking count, value and timing given. Not chain of thought."
        )
    )
    traveller_impact: str = Field(
        description="What the travellers actually experience, in one or two sentences."
    )
    recommended_action: str = Field(
        description="The single most useful next step for the operations team."
    )


class DraftedMessage(BaseModel):
    """One agent-facing message the model proposes sending."""

    agent_id: str = Field(description="The agent this message is addressed to.")
    subject: str = Field(description="An email subject line, under 90 characters.")
    body: str = Field(
        description=(
            "The message body. Professional, specific, addressed to a travel "
            "agency partner rather than to a traveller."
        )
    )


class DraftSet(BaseModel):
    """Messages for every agent affected by an incident."""

    messages: list[DraftedMessage] = Field(
        description="One message per affected agent, in the order the agents were given."
    )


# ------------------------------------------------------------------- requests


class ReportIncidentRequest(BaseModel):
    """Report a new incident. Nothing here reaches a real airline or supplier."""

    kind: IncidentKind
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=4000)
    route: str | None = Field(default=None, max_length=64)
    supplier: str | None = Field(default=None, max_length=120)
    occurred_at: datetime | None = None


class ApprovalRequest(BaseModel):
    """Approve or reject one drafted communication.

    `approved_by` has no default. CLAUDE.md Section 5 requires a human decision
    to be attributable, and a default would let an unattributed approval
    through the type system.
    """

    approved: bool
    approved_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


# ------------------------------------------------------------------ responses


class AffectedBooking(BaseModel):
    """A booking caught by an incident, as the UI needs it."""

    id: str
    agent_id: str
    agent_name: str
    traveller_name: str
    booking_type: str
    route: str | None
    supplier: str | None
    departure_at: datetime | None
    status: str
    value_inr: float

    @classmethod
    def of(cls, booking: Booking) -> AffectedBooking:
        return cls(
            id=booking.id,
            agent_id=booking.agent_id,
            agent_name=booking.agent_name,
            traveller_name=booking.traveller_name,
            booking_type=booking.booking_type,
            route=booking.route,
            supplier=booking.supplier,
            departure_at=booking.departure_at,
            status=booking.status.value,
            value_inr=booking.value_inr,
        )


class CommunicationView(BaseModel):
    """One drafted message and its approval state."""

    id: str
    agent_id: str
    agent_name: str
    booking_ids: list[str]
    subject: str
    body: str
    status: str
    approved_by: str | None
    approved_at: datetime | None
    rejection_note: str | None
    recorded_message_id: str | None


class IncidentSummary(BaseModel):
    """One incident in the console list."""

    id: str
    kind: str
    title: str
    route: str | None
    supplier: str | None
    occurred_at: datetime | None
    status: str
    severity: str | None
    affected_count: int
    affected_value_inr: float
    draft_count: int
    awaiting_approval_count: int


class IncidentDetail(BaseModel):
    """Everything one incident page needs."""

    id: str
    kind: str
    title: str
    description: str
    route: str | None
    supplier: str | None
    occurred_at: datetime | None
    status: str
    severity: str | None
    severity_reasoning: str | None
    traveller_impact: str | None
    recommended_action: str | None
    affected_count: int
    affected_value_inr: float
    affected_bookings: list[AffectedBooking]
    communications: list[CommunicationView]
    execution: dict | None
    created_at: datetime


class UsageInfo(BaseModel):
    """Cost metadata for an AI step (Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class AssessResponse(BaseModel):
    incident: IncidentDetail
    usage: UsageInfo


class AgentPartner(BaseModel):
    """The folded-in partner relationship view (Section 14, was 'CRM')."""

    agent_id: str
    agent_name: str
    booking_count: int
    total_value_inr: float
    confirmed: int
    delayed: int
    cancelled: int
    open_tickets: int
    urgent_tickets: int
    last_booking_at: datetime | None
    incidents_involved: int
    awaiting_approval: int
    #: Derived, not generated: the oldest unapproved draft is the follow-up.
    next_follow_up: str | None
