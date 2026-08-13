"""Mock adapter implementations backed by the synthetic datasets.

These read the CSVs produced by `scripts/generate_demo_data.py`. No network
call is made and no real personal data is involved (CLAUDE.md Section 20).

If a dataset is missing, these raise a clear error telling you to generate it
rather than silently returning an empty list — an empty dashboard that looks
"working" is worse than an honest failure.
"""

from __future__ import annotations

import csv
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from aiops_adapters.interfaces import (
    Booking,
    BookingProvider,
    BookingStatus,
    CalendarEvent,
    CalendarProvider,
    Email,
    EmailProvider,
)
from aiops_config import generated_data_dir
from aiops_utils import ConfigurationError, NotFoundError, ValidationError, get_logger

logger = get_logger(__name__)


def _read_csv(filename: str) -> list[dict[str, str]]:
    """Load a generated dataset, or explain how to create it."""
    path: Path = generated_data_dir() / filename
    if not path.is_file():
        raise ConfigurationError(
            f"Demo dataset {filename} is missing. Generate it with: npm run demo-data",
            user_message="Demo data has not been generated yet.",
        )
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=8)
def _cached_csv(filename: str) -> tuple[dict[str, str], ...]:
    """Datasets are static per process, so read each file at most once."""
    return tuple(_read_csv(filename))


def _dt(value: str) -> datetime:
    """Parse an ISO timestamp from a dataset."""
    return datetime.fromisoformat(value)


def _optional_dt(value: str | None) -> datetime | None:
    return _dt(value) if value else None


def clear_dataset_cache() -> None:
    """Drop cached datasets. Call after regenerating demo data."""
    _cached_csv.cache_clear()


class MockEmailProvider(EmailProvider):
    """Operations inbox backed by `operations_inbox_emails.csv`."""

    FILENAME = "operations_inbox_emails.csv"

    def _all(self) -> list[Email]:
        return [
            Email(
                id=row["id"],
                thread_id=row["thread_id"],
                sender=row["sender"],
                recipient=row["recipient"],
                subject=row["subject"],
                body=row["body"],
                received_at=_dt(row["received_at"]),
                is_read=row["is_read"].lower() == "true",
                has_reply=row["has_reply"].lower() == "true",
                labels=[label for label in row["labels"].split("|") if label],
            )
            for row in _cached_csv(self.FILENAME)
        ]

    def list_emails(self, *, limit: int = 50, unread_only: bool = False) -> list[Email]:
        emails = self._all()
        if unread_only:
            emails = [email for email in emails if not email.is_read]
        emails.sort(key=lambda email: email.received_at, reverse=True)
        return emails[:limit]

    def get_thread(self, thread_id: str) -> list[Email]:
        thread = [email for email in self._all() if email.thread_id == thread_id]
        if not thread:
            raise NotFoundError(f"No email thread with id {thread_id!r}")
        thread.sort(key=lambda email: email.received_at)
        return thread

    def send_reply(self, *, thread_id: str, body: str, approved_by: str) -> str:
        if not approved_by.strip():
            raise ValidationError("A reply cannot be sent without a human approver.")
        self.get_thread(thread_id)  # raises NotFoundError for an unknown thread

        # Mock adapter: the send is recorded, never transmitted. Real delivery
        # is a documented future improvement (CLAUDE.md Section 3c).
        message_id = f"mock-sent-{thread_id}"
        logger.info(
            "mock email reply recorded (not sent)",
            extra={
                "thread_id": thread_id,
                "approved_by": approved_by,
                "body_length": len(body),
            },
        )
        return message_id


class MockCalendarProvider(CalendarProvider):
    """Team calendar backed by `operations_calendar.csv`."""

    FILENAME = "operations_calendar.csv"

    def list_events(self, *, start: datetime, end: datetime) -> list[CalendarEvent]:
        if end < start:
            raise ValidationError("Calendar window end must not precede its start.")

        events = [
            CalendarEvent(
                id=row["id"],
                title=row["title"],
                starts_at=_dt(row["starts_at"]),
                ends_at=_dt(row["ends_at"]),
                attendees=[a for a in row["attendees"].split("|") if a],
                location=row.get("location") or None,
                notes=row.get("notes") or None,
            )
            for row in _cached_csv(self.FILENAME)
        ]
        # Overlap, not containment: an event straddling the window still counts.
        overlapping = [e for e in events if e.starts_at < end and e.ends_at > start]
        overlapping.sort(key=lambda event: event.starts_at)
        return overlapping


class MockBookingProvider(BookingProvider):
    """Booking data backed by `travel_bookings.csv`.

    Read-only, and never connected to a real airline, GDS, or payment system.
    """

    FILENAME = "travel_bookings.csv"

    def _all(self) -> list[Booking]:
        return [self._to_booking(row) for row in _cached_csv(self.FILENAME)]

    @staticmethod
    def _to_booking(row: dict[str, Any]) -> Booking:
        return Booking(
            id=row["id"],
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            traveller_name=row["traveller_name"],
            booking_type=row["booking_type"],
            route=row.get("route") or None,
            supplier=row.get("supplier") or None,
            departure_at=_optional_dt(row.get("departure_at")),
            status=BookingStatus(row["status"]),
            value_inr=float(row["value_inr"]),
            created_at=_dt(row["created_at"]),
        )

    def list_bookings(
        self, *, status: BookingStatus | None = None, limit: int = 200
    ) -> list[Booking]:
        bookings = self._all()
        if status is not None:
            bookings = [b for b in bookings if b.status == status]
        bookings.sort(key=lambda booking: booking.created_at, reverse=True)
        return bookings[:limit]

    def get_booking(self, booking_id: str) -> Booking | None:
        return next((b for b in self._all() if b.id == booking_id), None)

    def find_affected_bookings(self, *, route: str, on_date: datetime) -> list[Booking]:
        target = on_date.date()
        return [
            booking
            for booking in self._all()
            if booking.route == route
            and booking.departure_at is not None
            and booking.departure_at.date() == target
            and booking.status not in (BookingStatus.CANCELLED, BookingStatus.REFUNDED)
        ]
