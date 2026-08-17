"""Request, response and AI output shapes for the Operations Inbox.

`TriageResult.category` is typed as the `Category` enum, so a model inventing
"Refunds" or "Complaint" produces an invalid response rather than a seventh
category nobody's filters know about. `reasoning` is required for the same
reason it is in the Project Tracker: a label with no justification cannot be
argued with, and an operations team that cannot argue with a classification
stops trusting it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from aiops_inbox.models import Category, Urgency

# ------------------------------------------------------------------ AI output


class ExtractedTask(BaseModel):
    """One thing this email is asking somebody to do."""

    title: str = Field(min_length=1, description="The task, phrased as an instruction.")
    owner_hint: str = Field(
        default="",
        description="Which function should own it, e.g. 'Booking Ops' or 'Finance'.",
    )


class TriageResult(BaseModel):
    """The model's reading of one email or thread.

    Everything here is a judgement about text. The email's age, whether it has
    a reply, and which thread it belongs to are computed before this is asked
    for, and are not the model's to decide.
    """

    category: Category = Field(description="Which of the seven categories this belongs to.")
    urgency: Urgency = Field(description="How soon a person needs to deal with it.")
    reasoning: str = Field(
        min_length=1,
        description=(
            "One or two sentences explaining the category and urgency, quoting "
            "what in the message drove them. A decision summary, not chain of thought."
        ),
    )
    summary: str = Field(
        min_length=1,
        description=(
            "What this message or thread is actually asking for, in one or two "
            "sentences. For a long thread, what the conversation has arrived at."
        ),
    )
    tasks: list[ExtractedTask] = Field(
        default_factory=list,
        description="Anything the sender is asking someone to do. Empty if nothing is.",
    )
    follow_up: str = Field(
        default="",
        description=(
            "The single most useful next step for the operations team, if one "
            "is needed beyond replying."
        ),
    )


class DraftedReply(BaseModel):
    """A reply the model proposes. It is a draft and nothing more."""

    body: str = Field(
        min_length=1,
        description=(
            "The reply body. Professional, specific, addressed to a travel "
            "agency partner or vendor rather than to a traveller. No subject "
            "line and no signature block."
        ),
    )


# ------------------------------------------------------------------- requests


class ApprovalRequest(BaseModel):
    """Approve or reject a drafted reply.

    `approved_by` has no default. Section 16 forbids sending without explicit
    human approval, and a default would let an unattributed approval through
    the type system before the adapter ever saw it.
    """

    approved: bool
    approved_by: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


# ------------------------------------------------------------------ responses


class EmailView(BaseModel):
    """One message, as the UI needs it. Read from the adapter, never stored."""

    id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime
    is_read: bool
    has_reply: bool
    agency_id: str | None = None
    #: Computed, never generated.
    age_hours: float = 0.0
    is_unanswered: bool = False


class TriageView(BaseModel):
    """What the model said about a message, and what happened to the draft."""

    category: str | None = None
    urgency: str | None = None
    reasoning: str | None = None
    summary: str | None = None
    tasks: list[ExtractedTask] = Field(default_factory=list)
    follow_up: str | None = None
    triaged_at: datetime | None = None
    agreed_with_seed: bool | None = None

    draft_status: str = "none"
    draft_body: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_note: str | None = None
    recorded_message_id: str | None = None


class InboxItem(BaseModel):
    """One row of the inbox list."""

    email: EmailView
    triage: TriageView | None = None
    message_count: int = 1


class InboxCounts(BaseModel):
    """Computed totals for the header. No AI involved in any of them."""

    total: int
    unanswered: int
    triaged: int
    awaiting_approval: int
    by_category: dict[str, int] = Field(default_factory=dict)


class AccuracyView(BaseModel):
    """How often the model's category matched the seeded one.

    Present only because this inbox is synthetic. A real inbox has no answer
    key, so this panel would not exist — which the UI says rather than letting
    a reviewer assume otherwise.
    """

    triaged: int = 0
    agreed: int = 0
    percent: float | None = None


class InboxListResponse(BaseModel):
    items: list[InboxItem]
    counts: InboxCounts
    accuracy: AccuracyView
    categories: list[str]
    ai_requests_per_triage: int = 1
    ai_requests_per_draft: int = 1
    unanswered_after_hours: int


class ThreadResponse(BaseModel):
    """One conversation, its computed state, and any triage of its latest message."""

    thread_id: str
    emails: list[EmailView]
    message_count: int
    is_long: bool
    triage: TriageView | None = None


class UsageInfo(BaseModel):
    """Cost metadata for an AI step (Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class TriageResponse(BaseModel):
    thread: ThreadResponse
    usage: UsageInfo
