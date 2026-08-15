"""Database tables for travel-operations incidents and their communications.

Two tables, and the split is the point.

`travel_incidents` is what happened — a delay, an overbooking, a cancellation —
together with the operational judgement about it: how severe, why, who is
affected. `travel_communications` is what someone proposes to *say* to a travel
agent about it, and carries its own approval state.

Keeping them apart is what makes human-in-the-loop auditable rather than
implied. An incident can be assessed without anything being said to anyone, and
every message has its own row recording who approved it and when. A single
table with a "message" column could not answer "who authorised this" after the
fact, which is the question that matters when something goes wrong.

Bookings are deliberately **not** a table here. They are read through
`BookingProvider`, which has no method that creates or charges anything
(CLAUDE.md Sections 3c and 14). Nothing in this project can write to a booking
system, real or otherwise.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id


class IncidentKind(StrEnum):
    """What went wrong. Mirrors the categories in the support-ticket data."""

    FLIGHT_DELAY = "flight_delay"
    FLIGHT_CANCELLATION = "flight_cancellation"
    HOTEL_OVERBOOKING = "hotel_overbooking"
    SCHEDULE_CHANGE = "schedule_change"
    OTHER = "other"


class Severity(StrEnum):
    """Assigned by the model, always with a stated reason (Section 5)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ASSESSED = "assessed"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"


class CommunicationStatus(StrEnum):
    """The lifecycle of one drafted message.

    There is no `SENT`, and there is deliberately no `RECORDED` either.

    No `SENT`, because the mock adapter transmits nothing and a status claiming
    otherwise would be the fake functionality Section 2 bans.

    No `RECORDED`, because recording happens when the *incident's* workflow
    resumes — which is once every draft on it has been decided, not the instant
    one is approved. A status of "recorded" on a message whose
    `recorded_message_id` is still empty would be false for exactly as long as
    its neighbours sat undecided. `APPROVED` is true the moment it is set;
    whether the recording step has run yet is answered by
    `recorded_message_id`, which is either a reference or nothing.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class TravelIncident(Base, TimestampMixin):
    """One operational incident affecting travel-agent bookings."""

    __tablename__ = "travel_incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("inc"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: What the affected-booking lookup keys on.
    route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=IncidentStatus.OPEN.value
    )

    # ---- assessment: written by the model, never by the lookup -------------
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    severity_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    traveller_impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- lookup: computed, never generated ---------------------------------
    affected_booking_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affected_value_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    affected_agent_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    #: The workflow run, stored whole so the execution log survives a reload.
    #: This is the audit trail CLAUDE.md Section 5 asks for: which node ran,
    #: what it produced, what it cost, and where a person intervened.
    execution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    communications: Mapped[list[TravelCommunication]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="TravelCommunication.created_at",
    )

    __table_args__ = (
        Index("ix_travel_incidents_status", "status"),
        Index("ix_travel_incidents_occurred_at", "occurred_at"),
    )


class TravelCommunication(Base, TimestampMixin):
    """A message drafted for one travel agent about one incident."""

    __tablename__ = "travel_communications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("comm"))
    incident_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("travel_incidents.id", ondelete="CASCADE"), nullable=False
    )

    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    booking_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CommunicationStatus.DRAFT.value
    )

    # ---- the approval record ------------------------------------------------
    #
    # Nullable because a draft has not been decided on yet. Once set, these are
    # the answer to "who authorised this", which is the only question worth
    # asking after a message goes out wrong.
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Returned by the mock email adapter. Records that a send was *logged*,
    #: not that a message reached anyone. Nothing is transmitted.
    recorded_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    incident: Mapped[TravelIncident] = relationship(back_populates="communications")

    __table_args__ = (Index("ix_travel_communications_incident", "incident_id"),)
