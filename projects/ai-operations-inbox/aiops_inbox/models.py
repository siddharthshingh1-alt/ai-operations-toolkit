"""Storage for the Operations Inbox (CLAUDE.md Section 16).

**One table, and it holds no email.**

Messages are read through `EmailProvider` on every request and are never
copied here. What is stored is only what this project produces: the model's
triage of a message, the reply someone drafted from it, and the record of who
approved or rejected that reply.

The approval fields are the point. Section 16 forbids sending without explicit
human approval, and the adapter enforces that at the seam — but "who said this
could go out, and when" is a question that has to be answerable afterwards,
which means it has to be written down.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aiops_db.base import Base, TimestampMixin
from aiops_utils import new_id


class Category(StrEnum):
    """The categories from Section 16, reframed for this business."""

    AGENT_PARTNER = "Agent Partner"
    BOOKING_OPS = "Booking Ops"
    VENDOR_HOTEL = "Vendor/Hotel"
    FINANCE = "Finance"
    INTERNAL = "Internal"
    URGENT = "Urgent"
    OTHER = "Other"


class Urgency(StrEnum):
    """How soon this needs a person. Assigned by the model, always with a reason."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DraftStatus(StrEnum):
    """The lifecycle of one drafted reply.

    There is no `SENT`. The mock adapter records a send and transmits nothing,
    and a status claiming otherwise would be the fake functionality Section 2
    bans. `APPROVED` is true the moment someone approves; whether the adapter
    has recorded it is answered by `recorded_message_id`.
    """

    NONE = "none"
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class InboxTriage(Base, TimestampMixin):
    """What this project knows about one email. Never the email itself."""

    __tablename__ = "inbox_triage"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("trg"))

    #: The adapter's email id. Unique — one triage per message.
    email_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # ---- the model's reading, written together with its reasoning ----------
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Extracted tasks, each `{title, owner_hint}`.
    tasks: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: Whether the model's category matched the one the synthetic generator
    #: used. Only meaningful because this data is seeded; recorded so the UI
    #: can report accuracy honestly rather than claiming it.
    agreed_with_seed: Mapped[bool | None] = mapped_column(nullable=True)

    # ---- the drafted reply and its approval --------------------------------
    draft_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DraftStatus.NONE.value
    )
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Returned by the mock adapter. Records that a send was *logged*, not that
    #: a message reached anyone. Nothing is transmitted.
    recorded_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_inbox_triage_thread", "thread_id"),
        Index("ix_inbox_triage_status", "draft_status"),
        Index("ix_inbox_triage_urgency", "urgency"),
    )
