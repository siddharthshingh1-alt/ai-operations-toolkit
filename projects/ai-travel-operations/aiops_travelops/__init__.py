"""Project 6 — AI Travel Operations (CLAUDE.md Section 14). The flagship.

A working simulation of the target company's business: travel agencies booking
flights, hotels and holidays, and an operations team handling what goes wrong.

Includes the folded-in agent/partner relationship module (was the standalone
"CRM Assistant", Section 18).

Never connects to a real airline, GDS or payment system, and never transmits an
email. All data is synthetic.
"""

from aiops_travelops.models import (
    CommunicationStatus,
    IncidentKind,
    IncidentStatus,
    Severity,
    TravelCommunication,
    TravelIncident,
)
from aiops_travelops.partners import get_partner, list_partners
from aiops_travelops.service import (
    assess_and_draft,
    decide_communication,
    find_affected,
    get_communication,
    get_incident,
    list_incidents,
    report_incident,
    seed_incidents,
    to_detail,
    to_summary,
)
from aiops_travelops.workflow import (
    APPROVAL_ID,
    RECORD_ID,
    approval_is_reachable_only_after,
    incident_workflow,
)

__all__ = [
    "APPROVAL_ID",
    "RECORD_ID",
    "CommunicationStatus",
    "IncidentKind",
    "IncidentStatus",
    "Severity",
    "TravelCommunication",
    "TravelIncident",
    "approval_is_reachable_only_after",
    "assess_and_draft",
    "decide_communication",
    "find_affected",
    "get_communication",
    "get_incident",
    "get_partner",
    "incident_workflow",
    "list_incidents",
    "list_partners",
    "report_incident",
    "seed_incidents",
    "to_detail",
    "to_summary",
]
