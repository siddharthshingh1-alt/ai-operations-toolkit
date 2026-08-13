"""Integration adapter interfaces (CLAUDE.md Section 3c).

These are the seams where real integrations would attach. v1 ships **mock
implementations only** — a deliberate, documented decision, not an oversight:

* Real Gmail / Google Calendar OAuth is an explicit future improvement.
* A real airline, GDS, or payment system is **never** connected, in any
  version (Section 14).

Because the projects code against these interfaces, swapping in a real
implementation later touches one file and no project.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- email


class Email(BaseModel):
    """One operational email."""

    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    received_at: datetime
    is_read: bool = False
    has_reply: bool = False
    labels: list[str] = Field(default_factory=list)


class EmailProvider(ABC):
    """Read operational email and send approved replies."""

    @abstractmethod
    def list_emails(self, *, limit: int = 50, unread_only: bool = False) -> list[Email]:
        """Return recent emails, newest first."""

    @abstractmethod
    def get_thread(self, thread_id: str) -> list[Email]:
        """Return every message in a thread, oldest first."""

    @abstractmethod
    def send_reply(self, *, thread_id: str, body: str, approved_by: str) -> str:
        """Send a reply and return its message id.

        `approved_by` is required, not optional: CLAUDE.md Section 16 forbids
        sending email without explicit human approval, so the interface makes
        an unapproved send impossible to express.
        """


# ------------------------------------------------------------- calendar


class CalendarEvent(BaseModel):
    """One calendar entry."""

    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    attendees: list[str] = Field(default_factory=list)
    location: str | None = None
    notes: str | None = None


class CalendarProvider(ABC):
    """Read the operations team calendar."""

    @abstractmethod
    def list_events(self, *, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Return events overlapping the window, earliest first."""


# -------------------------------------------------------------- booking


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    PENDING = "pending"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Booking(BaseModel):
    """A booking made by a travel agent on behalf of their traveller."""

    id: str
    agent_id: str
    agent_name: str
    traveller_name: str
    booking_type: str  # flight | hotel | holiday
    route: str | None = None
    supplier: str | None = None
    departure_at: datetime | None = None
    status: BookingStatus = BookingStatus.CONFIRMED
    value_inr: float = 0.0
    created_at: datetime


class BookingProvider(ABC):
    """Read booking data.

    Read-only on purpose. This interface never gains a `create_booking` or
    `charge` method — the toolkit must never touch a real airline, GDS, or
    payment system (CLAUDE.md Sections 3c and 14).
    """

    @abstractmethod
    def list_bookings(
        self, *, status: BookingStatus | None = None, limit: int = 200
    ) -> list[Booking]:
        """Return bookings, newest first, optionally filtered by status."""

    @abstractmethod
    def get_booking(self, booking_id: str) -> Booking | None:
        """Return one booking, or None if it does not exist."""

    @abstractmethod
    def find_affected_bookings(self, *, route: str, on_date: datetime) -> list[Booking]:
        """Bookings on `route` departing on `on_date`.

        This is the lookup behind the flagship delay-incident workflow
        (Section 14): flight delay detected -> find affected bookings.
        """
