"""HTTP routes for the Operations Inbox.

Mounted by `apps/api` under `/api/inbox`.

Reading the inbox is free. The two AI routes are separate POSTs because they
are separate decisions and separate costs. The approval route is the only path
that reaches the email adapter's send, and it cannot be called without a named
approver.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aiops_config import Settings, get_settings
from aiops_db import get_db
from aiops_inbox import service
from aiops_inbox.models import Category
from aiops_inbox.prompts import CATEGORIES
from aiops_inbox.schema import (
    ApprovalRequest,
    InboxListResponse,
    ThreadResponse,
    TriageResponse,
)
from aiops_inbox.threads import UNANSWERED_AFTER_HOURS

router = APIRouter(prefix="/api/inbox", tags=["operations-inbox"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=InboxListResponse, summary="The operations inbox (no AI)")
def list_inbox(
    db: DbDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=200)] = service.DEFAULT_LIMIT,
    category: Annotated[Category | None, Query()] = None,
    unanswered_only: Annotated[bool, Query()] = False,
) -> InboxListResponse:
    """Messages with every computed fact attached. Costs nothing.

    Which messages are unanswered, how old they are and how long their threads
    run are calculated here. What each message *is* comes from triaging it,
    which is a separate, paid call.
    """
    items, counts = service.list_inbox(
        db,
        limit=limit,
        category=category.value if category else None,
        unanswered_only=unanswered_only,
        settings=settings,
    )
    return InboxListResponse(
        items=items,
        counts=counts,
        accuracy=service.accuracy(db),
        categories=list(CATEGORIES),
        unanswered_after_hours=UNANSWERED_AFTER_HOURS,
    )


@router.get("/threads/{thread_id}", response_model=ThreadResponse, summary="One thread (no AI)")
def get_thread(thread_id: str, db: DbDep, settings: SettingsDep) -> ThreadResponse:
    return service.get_thread(db, thread_id, settings=settings)


@router.post(
    "/threads/{thread_id}/triage",
    response_model=TriageResponse,
    summary="Classify, judge urgency, summarise, extract tasks (1 AI request)",
)
def triage(thread_id: str, db: DbDep, settings: SettingsDep) -> TriageResponse:
    """One request covering everything the model reads out of the message.

    Category, urgency, reasoning, summary, tasks and follow-up come back
    together because they are one judgement about one piece of text — splitting
    them would spend several requests to answer the same question.
    """
    thread, usage = service.triage_thread(db, thread_id, settings=settings)
    return TriageResponse(thread=thread, usage=usage)


@router.post(
    "/threads/{thread_id}/draft",
    response_model=TriageResponse,
    summary="Draft a reply (1 AI request)",
)
def draft(thread_id: str, db: DbDep, settings: SettingsDep) -> TriageResponse:
    """Write a reply. It is a draft: nothing is sent by this route."""
    thread, usage = service.draft_reply(db, thread_id, settings=settings)
    return TriageResponse(thread=thread, usage=usage)


@router.post(
    "/threads/{thread_id}/decision",
    response_model=ThreadResponse,
    summary="Approve or reject a drafted reply",
)
def decide(
    thread_id: str, request: ApprovalRequest, db: DbDep, settings: SettingsDep
) -> ThreadResponse:
    """The only route that can reach a send, and it needs a name.

    `approved_by` is taken from the request body and passed straight to the
    adapter, which rejects an empty one. There is no default and no fallback,
    so a send that nobody approved cannot be expressed here or below here.
    """
    return service.decide(
        db,
        thread_id,
        approved=request.approved,
        approved_by=request.approved_by,
        note=request.note,
        settings=settings,
    )
