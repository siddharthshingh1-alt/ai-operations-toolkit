"""Adapter tests, including the rules that must hold in every version."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aiops_adapters import (
    BookingProvider,
    BookingStatus,
    get_booking_provider,
    get_calendar_provider,
    get_email_provider,
)
from aiops_utils import NotFoundError, ValidationError


def test_bookings_load_from_generated_data() -> None:
    bookings = get_booking_provider().list_bookings(limit=5)
    assert len(bookings) == 5
    assert all(booking.id.startswith("BK-") for booking in bookings)


def test_bookings_filter_by_status() -> None:
    cancelled = get_booking_provider().list_bookings(status=BookingStatus.CANCELLED, limit=10)
    assert all(b.status is BookingStatus.CANCELLED for b in cancelled)


def test_unknown_booking_returns_none_rather_than_raising() -> None:
    assert get_booking_provider().get_booking("BK-DOES-NOT-EXIST") is None


def test_affected_bookings_excludes_already_cancelled() -> None:
    """The delay workflow must not 'affect' a booking that is already gone."""
    provider = get_booking_provider()
    flights = [b for b in provider.list_bookings(limit=900) if b.route and b.departure_at]
    assert flights, "generated data should contain flight bookings"

    sample = flights[0]
    assert sample.route is not None and sample.departure_at is not None
    affected = provider.find_affected_bookings(route=sample.route, on_date=sample.departure_at)
    assert all(b.status not in (BookingStatus.CANCELLED, BookingStatus.REFUNDED) for b in affected)


def test_booking_provider_has_no_write_methods() -> None:
    """CLAUDE.md Sections 3c and 14: never touch a real airline, GDS, or payment.

    Encoded as a test so a future change that adds one fails loudly here.
    """
    forbidden = {"create_booking", "cancel_booking", "charge", "refund", "pay"}
    assert not forbidden & set(dir(BookingProvider))


def test_emails_load_and_sort_newest_first() -> None:
    emails = get_email_provider().list_emails(limit=10)
    received = [email.received_at for email in emails]
    assert received == sorted(received, reverse=True)


def test_unread_filter() -> None:
    unread = get_email_provider().list_emails(limit=20, unread_only=True)
    assert all(not email.is_read for email in unread)


def test_thread_is_returned_oldest_first() -> None:
    provider = get_email_provider()
    thread_id = provider.list_emails(limit=1)[0].thread_id
    thread = provider.get_thread(thread_id)
    assert [e.received_at for e in thread] == sorted(e.received_at for e in thread)


def test_unknown_thread_raises() -> None:
    with pytest.raises(NotFoundError):
        get_email_provider().get_thread("TH-DOES-NOT-EXIST")


def test_reply_requires_a_human_approver() -> None:
    """CLAUDE.md Section 16: never send without explicit human approval."""
    provider = get_email_provider()
    thread_id = provider.list_emails(limit=1)[0].thread_id

    with pytest.raises(ValidationError, match="human approver"):
        provider.send_reply(thread_id=thread_id, body="Hello", approved_by="  ")


def test_approved_reply_is_recorded() -> None:
    provider = get_email_provider()
    thread_id = provider.list_emails(limit=1)[0].thread_id
    message_id = provider.send_reply(
        thread_id=thread_id, body="Hello", approved_by="ops.anita@example.test"
    )
    # "mock" in the id makes it obvious in logs that nothing was transmitted.
    assert "mock" in message_id


def test_calendar_returns_overlapping_events() -> None:
    now = datetime.now(UTC)
    events = get_calendar_provider().list_events(
        start=now - timedelta(days=7), end=now + timedelta(days=7)
    )
    assert all(e.starts_at < now + timedelta(days=7) for e in events)
    assert [e.starts_at for e in events] == sorted(e.starts_at for e in events)


def test_backwards_calendar_window_is_rejected() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="precede"):
        get_calendar_provider().list_events(start=now, end=now - timedelta(days=1))
