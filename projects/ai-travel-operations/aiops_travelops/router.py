"""HTTP routes for Travel Operations.

Mounted by `apps/api` under `/api/travel`.

The endpoint split mirrors what each step costs. Listing incidents, reading one
and seeing who is affected are free and always work. `/assess` is the only
route that spends an AI request, and it is reached by pressing a button rather
than by loading a page. `/approve` spends nothing and is the only route that
can cause a message to be recorded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiops_config import Settings, get_settings
from aiops_db import get_db
from aiops_travelops import partners, service
from aiops_travelops.schema import (
    AgentPartner,
    ApprovalRequest,
    AssessResponse,
    CommunicationView,
    IncidentDetail,
    IncidentSummary,
    ReportIncidentRequest,
)

router = APIRouter(prefix="/api/travel", tags=["travel-operations"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


class IncidentListResponse(BaseModel):
    incidents: list[IncidentSummary]
    seeded: int = 0


class PartnerListResponse(BaseModel):
    partners: list[AgentPartner]


@router.get("/incidents", response_model=IncidentListResponse, summary="Incident console")
def list_incidents(db: DbDep) -> IncidentListResponse:
    """Every incident, newest first.

    Seeds from the delays already present in the booking data on first use, so
    the console opens with real work on it rather than an empty state.
    """
    seeded = service.seed_incidents(db)
    incidents = service.list_incidents(db)
    return IncidentListResponse(
        incidents=[service.to_summary(incident) for incident in incidents], seeded=seeded
    )


@router.post("/incidents", response_model=IncidentDetail, summary="Report an incident")
def report_incident(request: ReportIncidentRequest, db: DbDep) -> IncidentDetail:
    """Record an incident and look up which bookings it affects. No AI."""
    incident = service.report_incident(db, request)
    return service.to_detail(incident)


@router.get("/incidents/{incident_id}", response_model=IncidentDetail, summary="One incident")
def get_incident(incident_id: str, db: DbDep) -> IncidentDetail:
    return service.to_detail(service.get_incident(db, incident_id))


@router.post(
    "/incidents/{incident_id}/assess",
    response_model=AssessResponse,
    summary="Assess severity and draft agent communications",
)
def assess_incident(incident_id: str, db: DbDep, settings: SettingsDep) -> AssessResponse:
    """Run the incident workflow up to the approval pause.

    This is the only route here that costs an AI request, and it stops at the
    human-approval node. Nothing is recorded as communicated by this call.
    """
    incident = service.get_incident(db, incident_id)
    incident, usage = service.assess_and_draft(db, incident, settings=settings)
    return AssessResponse(incident=service.to_detail(incident), usage=usage)


@router.post(
    "/communications/{communication_id}/decision",
    response_model=CommunicationView,
    summary="Approve or reject a drafted communication",
)
def decide(communication_id: str, request: ApprovalRequest, db: DbDep) -> CommunicationView:
    """A human decision on one drafted message.

    Approving records the decision with the approver's name and the time. It
    does not transmit anything: the email adapter is a mock that logs the send,
    and this deployment never contacts a real recipient.
    """
    communication = service.get_communication(db, communication_id)
    decided = service.decide_communication(db, communication, request)
    return CommunicationView(
        id=decided.id,
        agent_id=decided.agent_id,
        agent_name=decided.agent_name,
        booking_ids=list(decided.booking_ids or []),
        subject=decided.subject,
        body=decided.body,
        status=decided.status,
        approved_by=decided.approved_by,
        approved_at=decided.approved_at,
        rejection_note=decided.rejection_note,
        recorded_message_id=decided.recorded_message_id,
    )


@router.get("/partners", response_model=PartnerListResponse, summary="Agency partners")
def list_partners(db: DbDep) -> PartnerListResponse:
    """The folded-in partner relationship view (Section 14)."""
    return PartnerListResponse(partners=partners.list_partners(db))


@router.get("/partners/{agent_id}", response_model=AgentPartner, summary="One agency partner")
def get_partner(agent_id: str, db: DbDep) -> AgentPartner:
    return partners.get_partner(db, agent_id)
