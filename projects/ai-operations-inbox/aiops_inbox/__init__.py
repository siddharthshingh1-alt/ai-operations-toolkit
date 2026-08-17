"""Project 8 — AI Operations Inbox (CLAUDE.md Section 16).

Triage of the operations inbox: booking changes, delay alerts, agency partner
questions, supplier confirmations, invoice queries. Not a personal inbox — the
categories and the prompts are the ones this business actually runs on.

Three properties hold this project together:

**Nothing is ever sent.** `EmailProvider.send_reply` requires `approved_by` and
rejects an empty one, so an unapproved send cannot be expressed. The only route
that reaches it takes the approver from the request body — no default, no
fallback to a demo user. The mock adapter records the send and transmits
nothing, and a test asserts no code path here supplies an approver from
anywhere else.

**Emails are never stored.** They are read through the adapter on every
request. The one table holds only what this project produces: the triage, the
drafted reply, and who approved it.

**The code counts; the model reads.** Whether a message is unanswered, how old
it is, and how long its thread runs are computed in `threads.py`. What the
message *is* — category, urgency, what it asks for — is the model's judgement,
and it has to explain it.

The classification is measured, not asserted: the synthetic dataset carries the
category its generator used, the model never sees it, and agreement is reported
as an accuracy figure. That evaluation exists only because the data is seeded,
which the UI says rather than letting a reader assume otherwise.
"""

from aiops_inbox.models import Category, DraftStatus, InboxTriage, Urgency
from aiops_inbox.prompts import CATEGORIES
from aiops_inbox.router import router
from aiops_inbox.schema import (
    ApprovalRequest,
    DraftedReply,
    ExtractedTask,
    InboxItem,
    ThreadResponse,
    TriageResult,
)
from aiops_inbox.threads import (
    UNANSWERED_AFTER_HOURS,
    ThreadView,
    age_hours,
    agency_of,
    group_threads,
    is_unanswered,
    seeded_category,
)

__all__ = [
    "CATEGORIES",
    "UNANSWERED_AFTER_HOURS",
    "ApprovalRequest",
    "Category",
    "DraftStatus",
    "DraftedReply",
    "ExtractedTask",
    "InboxItem",
    "InboxTriage",
    "ThreadResponse",
    "ThreadView",
    "TriageResult",
    "Urgency",
    "age_hours",
    "agency_of",
    "group_threads",
    "is_unanswered",
    "router",
    "seeded_category",
]
