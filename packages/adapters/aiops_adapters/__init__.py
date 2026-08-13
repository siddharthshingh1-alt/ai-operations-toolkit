"""Integration adapters. v1 is mock-only (CLAUDE.md Section 3c).

from aiops_adapters import get_booking_provider

bookings = get_booking_provider().list_bookings()
"""

from aiops_adapters.factory import (
    get_booking_provider,
    get_calendar_provider,
    get_email_provider,
)
from aiops_adapters.interfaces import (
    Booking,
    BookingProvider,
    BookingStatus,
    CalendarEvent,
    CalendarProvider,
    Email,
    EmailProvider,
)
from aiops_adapters.mock import (
    MockBookingProvider,
    MockCalendarProvider,
    MockEmailProvider,
    clear_dataset_cache,
)

__all__ = [
    "Booking",
    "BookingProvider",
    "BookingStatus",
    "CalendarEvent",
    "CalendarProvider",
    "Email",
    "EmailProvider",
    "MockBookingProvider",
    "MockCalendarProvider",
    "MockEmailProvider",
    "clear_dataset_cache",
    "get_booking_provider",
    "get_calendar_provider",
    "get_email_provider",
]
