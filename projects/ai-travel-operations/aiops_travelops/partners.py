"""The agent/partner relationship view (CLAUDE.md Section 14).

This is the folded-in "CRM Assistant". It is deliberately not a generic CRM:
there are no leads, no deals and no pipeline, because the platform's customers
are travel agencies who are already customers. What an operations team actually
needs to know about a partner is how much business they put through, what is
currently going wrong for them, and whether anyone owes them a reply.

Every figure here is derived from the booking and ticket data plus this
project's own incident records. Nothing is generated, so nothing can be wrong
in an interesting way — it can only be out of date, which it never is, because
it is computed per request.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from aiops_adapters import BookingStatus, get_booking_provider
from aiops_config import generated_data_dir
from aiops_travelops.models import CommunicationStatus
from aiops_travelops.schema import AgentPartner
from aiops_travelops.service import list_incidents
from aiops_utils import NotFoundError, get_logger

logger = get_logger(__name__)


def _ticket_counts() -> dict[str, dict[str, int]]:
    """Open and urgent ticket counts per agent, from the support-ticket data."""
    path = generated_data_dir() / "support_tickets.csv"
    if not path.is_file():
        return {}

    frame = pd.read_csv(path)
    counts: dict[str, dict[str, int]] = {}
    for agent_id, group in frame.groupby("agent_id"):
        open_rows = group[group["status"].astype(str).str.lower() != "closed"]
        counts[str(agent_id)] = {
            "open": int(len(open_rows)),
            "urgent": int(
                len(open_rows[open_rows["priority"].astype(str).str.lower() == "urgent"])
            ),
        }
    return counts


def list_partners(db: Session) -> list[AgentPartner]:
    """Every travel agency, ordered by the business they represent."""
    bookings = get_booking_provider().list_bookings(limit=2000)
    tickets = _ticket_counts()

    incidents = list_incidents(db, limit=500)
    involved: dict[str, int] = {}
    awaiting: dict[str, int] = {}
    oldest_draft: dict[str, datetime] = {}

    for incident in incidents:
        for agent_id in incident.affected_agent_ids or []:
            involved[agent_id] = involved.get(agent_id, 0) + 1
        for communication in incident.communications:
            if communication.status == CommunicationStatus.DRAFT.value:
                awaiting[communication.agent_id] = awaiting.get(communication.agent_id, 0) + 1
                existing = oldest_draft.get(communication.agent_id)
                if existing is None or communication.created_at < existing:
                    oldest_draft[communication.agent_id] = communication.created_at

    grouped: dict[str, list] = {}
    for booking in bookings:
        grouped.setdefault(booking.agent_id, []).append(booking)

    partners: list[AgentPartner] = []
    for agent_id, group in grouped.items():
        ticket = tickets.get(agent_id, {"open": 0, "urgent": 0})
        waiting = awaiting.get(agent_id, 0)
        partners.append(
            AgentPartner(
                agent_id=agent_id,
                agent_name=group[0].agent_name,
                booking_count=len(group),
                total_value_inr=round(sum(b.value_inr for b in group), 2),
                confirmed=sum(1 for b in group if b.status is BookingStatus.CONFIRMED),
                delayed=sum(1 for b in group if b.status is BookingStatus.DELAYED),
                cancelled=sum(1 for b in group if b.status is BookingStatus.CANCELLED),
                open_tickets=ticket["open"],
                urgent_tickets=ticket["urgent"],
                last_booking_at=max(
                    (b.created_at for b in group if b.created_at is not None), default=None
                ),
                incidents_involved=involved.get(agent_id, 0),
                awaiting_approval=waiting,
                # Derived rather than written: the follow-up owed to a partner
                # is whatever is sitting undecided in front of a human.
                next_follow_up=(
                    f"{waiting} drafted message(s) awaiting approval"
                    if waiting
                    else (f"{ticket['urgent']} urgent ticket(s) open" if ticket["urgent"] else None)
                ),
            )
        )

    partners.sort(key=lambda partner: partner.total_value_inr, reverse=True)
    return partners


def get_partner(db: Session, agent_id: str) -> AgentPartner:
    partner = next((p for p in list_partners(db) if p.agent_id == agent_id), None)
    if partner is None:
        raise NotFoundError(
            f"No agent {agent_id!r}.", user_message="That travel agency does not exist."
        )
    return partner
