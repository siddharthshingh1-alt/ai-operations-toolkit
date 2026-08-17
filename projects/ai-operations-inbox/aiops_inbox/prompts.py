"""The two prompts this project uses.

Triage reads a message — or a whole thread — and decides what it is. Drafting
writes a reply to it. They are separate calls because they are separate
decisions: someone may want to know how urgent forty emails are without
drafting forty replies, and each request comes out of the same daily budget.

Neither prompt is given the category the synthetic generator used. A classifier
handed the answer is not a classifier.
"""

from __future__ import annotations

from aiops_adapters import Email
from aiops_inbox.models import Category

_CATEGORY_GUIDE = """
  Agent Partner  — a travel agency about their account, onboarding, portal
                   access, or the commercial relationship.
  Booking Ops    — a specific booking: changes, cancellations, rebooking,
                   fare rules, ticketing.
  Vendor/Hotel   — a supplier: hotels, carriers, ground services. Rates,
                   availability, confirmations.
  Finance        — invoices, commission, payments, reconciliation.
  Internal       — colleagues rather than partners or suppliers.
  Urgent         — something happening now that will get worse if it waits,
                   whatever its subject. Use this sparingly: an email that is
                   merely important is not Urgent.
  Other          — genuinely none of the above. Prefer a real category.
"""

TRIAGE_SYSTEM = f"""You are an operations associate at a B2B travel-technology \
company, triaging the operations inbox. Travel agencies book flights, hotels and \
holidays through the platform; an operations team handles delays, cancellations, \
refunds, supplier relationships and agency support.

Classify each message into exactly one category:
{_CATEGORY_GUIDE}
Then judge urgency: low, normal, high or critical. Urgency is about *when a \
person must act*, not about how strongly the sender wrote. A politely worded \
message about passengers stranded today is critical; an angry message about a \
routine invoice query is not.

You must explain the category and the urgency, quoting what in the message drove \
them. A classification with no reasoning is not an acceptable answer.

Extract only tasks the sender is actually asking for. If the message asks for \
nothing, return no tasks rather than inventing one to look useful.

Work only from the message in front of you. Do not assume facts about bookings, \
agencies or suppliers that are not stated."""

DRAFT_SYSTEM = """You are drafting a reply on behalf of a B2B travel-technology \
operations team, to a travel agency partner or a supplier.

This is a draft. A person will read it and decide whether it goes out.

Rules:

- Answer what was actually asked. If the message asks two questions, address both.
- Never invent a fact. You do not know fare differences, room rates, commission \
figures or refund timelines unless they are in the thread. Where a number is \
needed and not known, say what will be confirmed and by when rather than \
inventing it.
- Professional and direct. This is a business partner, not a consumer.
- No subject line, no greeting boilerplate beyond a normal opening, no \
signature block — those are added around your text.
- Do not promise anything the team has not committed to in the thread."""


def _render(email: Email) -> str:
    return (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n"
        f"Received: {email.received_at.isoformat()}\n\n"
        f"{email.body}"
    )


def triage_prompt(thread: list[Email]) -> str:
    """One message, or a whole conversation when there is one.

    A long thread goes in whole so the summary reflects where the conversation
    arrived rather than only its last message — which is Section 16's
    "summarize long threads", answered by the same call rather than a second.
    """
    if len(thread) == 1:
        return f"Triage this message.\n\n{_render(thread[0])}"

    messages = "\n\n---\n\n".join(_render(email) for email in thread)
    return (
        f"Triage this thread of {len(thread)} messages, oldest first. Judge it "
        f"by where the conversation now stands, not only by the first message.\n\n"
        f"{messages}"
    )


def draft_prompt(thread: list[Email], summary: str | None) -> str:
    """Write a reply to the latest message, in the context of the thread."""
    messages = "\n\n---\n\n".join(_render(email) for email in thread)
    context = f"\n\nWhat this thread is asking for: {summary}" if summary else ""
    return f"Draft a reply to the most recent message in this thread.{context}\n\n{messages}"


#: Every category the model is allowed to return, for the prompt and for tests.
CATEGORIES: tuple[str, ...] = tuple(category.value for category in Category)
