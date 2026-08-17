"""Domain logic for the Operations Inbox (CLAUDE.md Section 16).

Three things are worth stating plainly about this module.

**Emails are never stored.** They are read through `EmailProvider` on every
request. The one table here holds this project's own output: a triage, a
drafted reply, and the record of who approved it.

**Nothing is ever sent without a named human.** `send_reply` takes
`approved_by` as a required argument and rejects an empty one, so an
unapproved send cannot be expressed. This module never supplies that argument
from anywhere but the approval request itself — no default, no fallback to a
demo user, no "system". A test asserts it.

**The model reads; the code counts.** Whether an email is unanswered, how old
it is, and which thread it belongs to are computed in `threads.py`. What the
message *is* — its category, its urgency, what it asks for — is the model's
judgement, and it must explain it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_adapters import Email, get_email_provider
from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult
from aiops_config import Settings, get_settings
from aiops_inbox import prompts, threads
from aiops_inbox.models import Category, DraftStatus, InboxTriage
from aiops_inbox.schema import (
    AccuracyView,
    DraftedReply,
    EmailView,
    ExtractedTask,
    InboxCounts,
    InboxItem,
    ThreadResponse,
    TriageResult,
    TriageView,
    UsageInfo,
)
from aiops_utils import NotFoundError, ValidationError, get_logger

logger = get_logger(__name__)

#: How many messages the list shows. The dataset holds 180; a page that
#: rendered all of them would be a scroll, not an inbox.
DEFAULT_LIMIT = 40


# ------------------------------------------------------------------ reading


def _email_view(email: Email, *, at: datetime | None = None) -> EmailView:
    return EmailView(
        id=email.id,
        thread_id=email.thread_id,
        sender=email.sender,
        subject=email.subject,
        body=email.body,
        received_at=email.received_at,
        is_read=email.is_read,
        has_reply=email.has_reply,
        agency_id=threads.agency_of(email),
        age_hours=round(threads.age_hours(email, at=at), 1),
        is_unanswered=threads.is_unanswered(email, at=at),
    )


def _triage_view(record: InboxTriage | None) -> TriageView | None:
    if record is None:
        return None
    return TriageView(
        category=record.category,
        urgency=record.urgency,
        reasoning=record.reasoning,
        summary=record.summary,
        tasks=[ExtractedTask.model_validate(task) for task in (record.tasks or [])],
        follow_up=record.follow_up,
        triaged_at=record.triaged_at,
        agreed_with_seed=record.agreed_with_seed,
        draft_status=record.draft_status,
        draft_body=record.draft_body,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        rejection_note=record.rejection_note,
        recorded_message_id=record.recorded_message_id,
    )


def triage_records(db: Session, email_ids: list[str]) -> dict[str, InboxTriage]:
    if not email_ids:
        return {}
    rows = db.scalars(select(InboxTriage).where(InboxTriage.email_id.in_(email_ids)))
    return {row.email_id: row for row in rows}


def get_triage(db: Session, email_id: str) -> InboxTriage | None:
    return db.scalar(select(InboxTriage).where(InboxTriage.email_id == email_id))


def accuracy(db: Session) -> AccuracyView:
    """How often the model's category matched the seeded one.

    Available only because the inbox is synthetic. Reported rather than
    claimed: a real inbox has no answer key, and the UI says so.
    """
    rows = list(db.scalars(select(InboxTriage).where(InboxTriage.agreed_with_seed.is_not(None))))
    if not rows:
        return AccuracyView()
    agreed = sum(1 for row in rows if row.agreed_with_seed)
    return AccuracyView(
        triaged=len(rows),
        agreed=agreed,
        percent=round(100.0 * agreed / len(rows), 1),
    )


def list_inbox(
    db: Session,
    *,
    limit: int = DEFAULT_LIMIT,
    category: str | None = None,
    unanswered_only: bool = False,
    settings: Settings | None = None,
    at: datetime | None = None,
) -> tuple[list[InboxItem], InboxCounts]:
    """The inbox, with every computed fact attached. No AI, and no cost."""
    provider = get_email_provider(settings or get_settings())
    # Read generously, then filter — the adapter's limit is a fetch size, and
    # filtering after it keeps "unanswered only" from silently showing fewer
    # than it should.
    emails = provider.list_emails(limit=500)

    thread_sizes = {
        thread.thread_id: thread.message_count for thread in threads.group_threads(emails)
    }
    records = triage_records(db, [email.id for email in emails])

    counts_by_category: dict[str, int] = {}
    for email in emails:
        record = records.get(email.id)
        if record and record.category:
            counts_by_category[record.category] = counts_by_category.get(record.category, 0) + 1

    unanswered_total = sum(1 for email in emails if threads.is_unanswered(email, at=at))
    awaiting = sum(
        1 for record in records.values() if record.draft_status == DraftStatus.DRAFT.value
    )

    selected = emails
    if unanswered_only:
        selected = [email for email in selected if threads.is_unanswered(email, at=at)]
    if category:
        # A category only exists once a message has been triaged, so filtering
        # by one necessarily hides everything untriaged. That is the honest
        # behaviour — the alternative is guessing a category in code, which is
        # the classifier this project deliberately does not have.
        def _matches(email: Email) -> bool:
            record = records.get(email.id)
            return record is not None and record.category == category

        selected = [email for email in selected if _matches(email)]

    items = [
        InboxItem(
            email=_email_view(email, at=at),
            triage=_triage_view(records.get(email.id)),
            message_count=thread_sizes.get(email.thread_id, 1),
        )
        for email in selected[:limit]
    ]

    counts = InboxCounts(
        total=len(emails),
        unanswered=unanswered_total,
        triaged=len(records),
        awaiting_approval=awaiting,
        by_category=counts_by_category,
    )
    return items, counts


def get_thread(
    db: Session,
    thread_id: str,
    *,
    settings: Settings | None = None,
    at: datetime | None = None,
) -> ThreadResponse:
    """One conversation, oldest first, with any triage of its latest message."""
    provider = get_email_provider(settings or get_settings())
    messages = provider.get_thread(thread_id)  # raises NotFoundError if unknown

    latest = messages[-1]
    record = get_triage(db, latest.id)
    return ThreadResponse(
        thread_id=thread_id,
        emails=[_email_view(email, at=at) for email in messages],
        message_count=len(messages),
        is_long=len(messages) >= 3,
        triage=_triage_view(record),
    )


# ------------------------------------------------------------------------ AI


def _usage_of(result: AIResult[Any]) -> UsageInfo:
    return UsageInfo(
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_demo_cache=getattr(result, "from_demo_cache", False),
    )


def _record_for(db: Session, latest: Email) -> InboxTriage:
    record = get_triage(db, latest.id)
    if record is None:
        record = InboxTriage(email_id=latest.id, thread_id=latest.thread_id)
        db.add(record)
    return record


def triage_thread(
    db: Session,
    thread_id: str,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    at: datetime | None = None,
) -> tuple[ThreadResponse, UsageInfo]:
    """Classify, judge urgency, summarise and extract tasks. One AI request.

    The whole thread is sent when there is one, so the summary reflects where
    the conversation stands rather than only its most recent message.

    The model is not told the category the generator used. Agreement with it is
    recorded afterwards as an evaluation signal, never used as an input.
    """
    resolved = settings or get_settings()
    email_provider = get_email_provider(resolved)
    messages = email_provider.get_thread(thread_id)
    latest = messages[-1]

    ai = provider_override or get_provider(resolved)
    result = ai.generate_structured_output(
        prompts.triage_prompt(messages),
        output_model=TriageResult,
        system=prompts.TRIAGE_SYSTEM,
    )
    triage: TriageResult = result.value

    record = _record_for(db, latest)
    record.category = triage.category.value
    record.urgency = triage.urgency.value
    record.reasoning = triage.reasoning
    record.summary = triage.summary
    record.tasks = [task.model_dump() for task in triage.tasks]
    record.follow_up = triage.follow_up or None
    record.triaged_at = datetime.now(UTC)

    seeded = threads.seeded_category(latest)
    record.agreed_with_seed = (seeded == triage.category.value) if seeded else None

    db.flush()
    logger.info(
        "email triaged",
        extra={
            "project": "ai-operations-inbox",
            "email_id": latest.id,
            "assigned_category": record.category,
            "urgency": record.urgency,
            "agreed_with_seed": record.agreed_with_seed,
            "model": result.model,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )
    return get_thread(db, thread_id, settings=resolved, at=at), _usage_of(result)


def draft_reply(
    db: Session,
    thread_id: str,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    at: datetime | None = None,
) -> tuple[ThreadResponse, UsageInfo]:
    """Write a reply. One AI request. It is a draft and goes nowhere."""
    resolved = settings or get_settings()
    email_provider = get_email_provider(resolved)
    messages = email_provider.get_thread(thread_id)
    latest = messages[-1]

    record = get_triage(db, latest.id)
    if record is not None and record.draft_status == DraftStatus.APPROVED.value:
        raise ValidationError(
            f"Thread {thread_id} already has an approved reply.",
            user_message=(
                "A reply to this thread has already been approved. Drafting "
                "another would leave two versions of what was agreed."
            ),
        )

    ai = provider_override or get_provider(resolved)
    result = ai.generate_structured_output(
        prompts.draft_prompt(messages, record.summary if record else None),
        output_model=DraftedReply,
        system=prompts.DRAFT_SYSTEM,
    )

    record = _record_for(db, latest)
    record.draft_body = result.value.body
    record.draft_status = DraftStatus.DRAFT.value
    # A fresh draft clears any previous decision — an approval recorded against
    # text that has since been replaced would be a lie about what was approved.
    record.approved_by = None
    record.approved_at = None
    record.rejection_note = None
    record.recorded_message_id = None
    db.flush()

    return get_thread(db, thread_id, settings=resolved, at=at), _usage_of(result)


# ------------------------------------------------------------------ approval


def decide(
    db: Session,
    thread_id: str,
    *,
    approved: bool,
    approved_by: str,
    note: str | None = None,
    settings: Settings | None = None,
    at: datetime | None = None,
) -> ThreadResponse:
    """Approve or reject a drafted reply. The only path to a send.

    `approved_by` comes from the request and from nowhere else. There is no
    default, no fallback to the configured demo user, and no "system" — an
    approval that cannot name a person is not an approval, and the adapter
    would refuse it anyway.
    """
    resolved = settings or get_settings()
    approver = approved_by.strip()
    if not approver:
        raise ValidationError(
            "An approval must name a person.",
            user_message="Enter your name before approving or rejecting.",
        )

    email_provider = get_email_provider(resolved)
    messages = email_provider.get_thread(thread_id)
    latest = messages[-1]

    record = get_triage(db, latest.id)
    if record is None or record.draft_status != DraftStatus.DRAFT.value:
        raise NotFoundError(
            f"No draft awaiting a decision on thread {thread_id}.",
            user_message="There is no drafted reply on this thread to decide on.",
        )

    if not approved:
        record.draft_status = DraftStatus.REJECTED.value
        record.rejection_note = note
        record.approved_by = None
        record.approved_at = None
        db.flush()
        logger.info(
            "reply rejected",
            extra={
                "project": "ai-operations-inbox",
                "email_id": latest.id,
                "decided_by": approver,
            },
        )
        return get_thread(db, thread_id, settings=resolved, at=at)

    # Approved. The adapter records the send; it transmits nothing.
    message_id = email_provider.send_reply(
        thread_id=thread_id,
        body=record.draft_body or "",
        approved_by=approver,
    )
    record.draft_status = DraftStatus.APPROVED.value
    record.approved_by = approver
    record.approved_at = datetime.now(UTC)
    record.rejection_note = None
    record.recorded_message_id = message_id
    db.flush()

    logger.info(
        "reply approved and recorded",
        extra={
            "project": "ai-operations-inbox",
            "email_id": latest.id,
            "approved_by": approver,
            "recorded_message_id": message_id,
            "transmitted": 0,
        },
    )
    return get_thread(db, thread_id, settings=resolved, at=at)


__all__ = [
    "DEFAULT_LIMIT",
    "Category",
    "accuracy",
    "decide",
    "draft_reply",
    "get_thread",
    "get_triage",
    "list_inbox",
    "triage_thread",
]
