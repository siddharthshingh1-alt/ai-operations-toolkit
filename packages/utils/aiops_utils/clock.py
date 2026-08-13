"""Time helpers.

Every timestamp in this codebase is timezone-aware UTC. Naive datetimes are a
recurring source of off-by-hours bugs in operational reporting, so there is one
function and it always returns an aware value.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
