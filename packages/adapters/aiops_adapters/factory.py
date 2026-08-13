"""Adapter selection.

Only `mock` resolves today. `Settings` rejects any other value outright
(see `aiops_config.settings`), so a half-built real integration cannot be
switched on by an environment variable alone.
"""

from __future__ import annotations

from aiops_adapters.interfaces import BookingProvider, CalendarProvider, EmailProvider
from aiops_adapters.mock import (
    MockBookingProvider,
    MockCalendarProvider,
    MockEmailProvider,
)
from aiops_config import Settings, get_settings
from aiops_utils import ConfigurationError

_EMAIL: dict[str, type[EmailProvider]] = {"mock": MockEmailProvider}
_CALENDAR: dict[str, type[CalendarProvider]] = {"mock": MockCalendarProvider}
_BOOKING: dict[str, type[BookingProvider]] = {"mock": MockBookingProvider}


def _resolve(registry: dict[str, type], name: str, kind: str) -> object:
    try:
        return registry[name]()
    except KeyError as exc:
        raise ConfigurationError(
            f"Unknown {kind} provider {name!r}. Only 'mock' is available in v1 "
            "(CLAUDE.md Section 3c)."
        ) from exc


def get_email_provider(settings: Settings | None = None) -> EmailProvider:
    settings = settings or get_settings()
    return _resolve(_EMAIL, settings.email_provider, "email")  # type: ignore[return-value]


def get_calendar_provider(settings: Settings | None = None) -> CalendarProvider:
    settings = settings or get_settings()
    return _resolve(_CALENDAR, settings.calendar_provider, "calendar")  # type: ignore[return-value]


def get_booking_provider(settings: Settings | None = None) -> BookingProvider:
    settings = settings or get_settings()
    return _resolve(_BOOKING, settings.booking_provider, "booking")  # type: ignore[return-value]
