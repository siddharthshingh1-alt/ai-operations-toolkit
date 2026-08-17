"""What can be known about the inbox without asking a model.

Section 16 lists "detect unanswered emails" among the AI features. It is done
here instead, in code, for the same reason overdue tasks are computed in the
Project Tracker: `has_reply` is a boolean and age is a subtraction. A model
asked to work those out would usually be right, and "usually" is the wrong
property for the list an operations team works through on a Monday.

What is left for the model is the part only a model can do: reading an email
and deciding what kind of thing it is, how urgent it sounds, and what it is
asking for.

Nothing here writes anything. Emails are read through `EmailProvider` and are
never copied into this project's database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from aiops_adapters import Email

#: How long an unanswered email may sit before it is worth flagging.
#:
#: Two working days. Short enough that a partner is not left waiting a week,
#: long enough that Monday morning does not open on a list of everything that
#: arrived on Friday afternoon.
UNANSWERED_AFTER_HOURS = 48


def now() -> datetime:
    """The current instant, in UTC. A function so tests can freeze it."""
    return datetime.now(UTC)


def age_hours(email: Email, *, at: datetime | None = None) -> float:
    """How long ago this arrived, in hours."""
    moment = at or now()
    received = email.received_at
    if received.tzinfo is None:
        received = received.replace(tzinfo=UTC)
    return (moment - received).total_seconds() / 3600.0


def is_unanswered(email: Email, *, at: datetime | None = None) -> bool:
    """No reply, and old enough to be worth someone's attention.

    An email that arrived an hour ago is not unanswered, it is *new* — flagging
    it would fill the list with things nobody could reasonably have replied to
    yet, and a list that always looks alarming stops being read.
    """
    if email.has_reply:
        return False
    return age_hours(email, at=at) >= UNANSWERED_AFTER_HOURS


@dataclass(frozen=True)
class ThreadView:
    """One conversation, grouped from the flat list the adapter returns."""

    thread_id: str
    emails: list[Email]

    @property
    def latest(self) -> Email:
        return self.emails[-1]

    @property
    def first(self) -> Email:
        return self.emails[0]

    @property
    def message_count(self) -> int:
        return len(self.emails)

    @property
    def is_long(self) -> bool:
        """Long enough that a summary is worth more than reading it."""
        return self.message_count >= 3


def group_threads(emails: list[Email]) -> list[ThreadView]:
    """Group a flat list into threads, each ordered oldest first.

    The adapter returns messages newest first because that is what an inbox
    list wants; a *thread* only makes sense read forwards.
    """
    by_thread: dict[str, list[Email]] = {}
    for email in emails:
        by_thread.setdefault(email.thread_id, []).append(email)

    threads = []
    for thread_id, messages in by_thread.items():
        messages.sort(key=lambda item: item.received_at)
        threads.append(ThreadView(thread_id=thread_id, emails=messages))

    # Newest activity first — the same order the inbox list uses.
    threads.sort(key=lambda thread: thread.latest.received_at, reverse=True)
    return threads


def agency_of(email: Email) -> str | None:
    """The agency id the generator tagged this email with, if any.

    Read from `labels`, where entries look like `AG-1004`. This is metadata the
    adapter carries, not something inferred — and specifically not the category
    label, which this project deliberately never reads (see `seeded_category`).
    """
    for label in email.labels:
        if label.startswith("AG-"):
            return label
    return None


def seeded_category(email: Email) -> str | None:
    """The category the synthetic generator used when writing this email.

    **This is never used to classify anything.** The model is given the subject
    and body and nothing else, because a classifier handed the answer is not a
    classifier. It exists only so the UI can report whether the model agreed —
    an evaluation signal that is available here purely because the data is
    synthetic, and would not exist for a real inbox.
    """
    for label in email.labels:
        if not label.startswith("AG-"):
            return label
    return None
