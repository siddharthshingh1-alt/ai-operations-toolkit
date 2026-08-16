"""Domain logic for Travel Operations.

The order of operations here is the argument the project is making. A lookup
establishes who is affected; a model then judges and drafts; a person then
decides; only then is anything recorded as said. Each stage can only see the
output of the one before it, which is why the model is never in a position to
invent a booking reference or a headcount.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aiops_adapters import Booking, BookingStatus, get_booking_provider, get_email_provider
from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_config import Settings, get_settings
from aiops_travelops.models import (
    CommunicationStatus,
    IncidentKind,
    IncidentStatus,
    Severity,
    TravelCommunication,
    TravelIncident,
)
from aiops_travelops.prompts import ASSESS_SYSTEM, DRAFT_SYSTEM
from aiops_travelops.schema import (
    AffectedBooking,
    ApprovalRequest,
    CommunicationView,
    DraftSet,
    IncidentAssessment,
    IncidentDetail,
    IncidentSummary,
    ReportIncidentRequest,
    UsageInfo,
)
from aiops_travelops.workflow import (
    incident_workflow,
)
from aiops_utils import NotFoundError, ValidationError, get_logger
from aiops_workflow import ExecutionStatus, NodeType, WorkflowEngine, WorkflowExecution

logger = get_logger(__name__)

#: Cap on drafts per incident. Eight agents exist in the dataset; a wider
#: incident would still only ask the model for this many, because a request
#: that large is slow, expensive, and produces messages nobody reads.
MAX_DRAFTS = 6

#: Bookings returned for the incident page. The lookup itself is unbounded —
#: the count and value are computed over everything affected — but the table
#: shows a workable slice.
MAX_LISTED_BOOKINGS = 50


# --------------------------------------------------------------- affected lookup


def find_affected(incident: TravelIncident) -> list[Booking]:
    """Bookings caught by this incident. Deterministic, no model involved.

    Falls back to matching on supplier when the incident has no route, which is
    what a hotel overbooking looks like — the dataset stores the hotel name in
    `supplier` and leaves `route` empty.
    """
    provider = get_booking_provider()

    if incident.route and incident.occurred_at:
        return provider.find_affected_bookings(route=incident.route, on_date=incident.occurred_at)

    # No route, or no date: match what we do have rather than returning nothing.
    candidates = provider.list_bookings(limit=1000)
    live = [
        booking
        for booking in candidates
        if booking.status not in (BookingStatus.CANCELLED, BookingStatus.REFUNDED)
    ]

    if incident.supplier:
        live = [booking for booking in live if booking.supplier == incident.supplier]
    if incident.route:
        live = [booking for booking in live if booking.route == incident.route]
    if incident.occurred_at:
        target = incident.occurred_at.date()
        live = [
            booking
            for booking in live
            if booking.departure_at is not None and booking.departure_at.date() == target
        ]
    return live


def _apply_lookup(incident: TravelIncident, bookings: list[Booking]) -> None:
    """Write the lookup result onto the incident."""
    incident.affected_booking_ids = [booking.id for booking in bookings]
    incident.affected_count = len(bookings)
    incident.affected_value_inr = round(sum(booking.value_inr for booking in bookings), 2)
    incident.affected_agent_ids = sorted({booking.agent_id for booking in bookings})


# ------------------------------------------------------------------- reporting


def report_incident(db: Session, request: ReportIncidentRequest) -> TravelIncident:
    """Record a new incident and run the affected-booking lookup.

    No AI runs here. Reporting an incident is free, so the console is useful
    with the day's model budget entirely unspent.
    """
    incident = TravelIncident(
        kind=request.kind.value,
        title=request.title.strip(),
        description=request.description.strip(),
        route=(request.route or "").strip() or None,
        supplier=(request.supplier or "").strip() or None,
        occurred_at=request.occurred_at,
        status=IncidentStatus.OPEN.value,
    )
    _apply_lookup(incident, find_affected(incident))

    db.add(incident)
    db.flush()
    logger.info(
        "travel incident reported",
        extra={
            "project": "ai-travel-operations",
            "incident_id": incident.id,
            "kind": incident.kind,
            "affected": incident.affected_count,
        },
    )
    return incident


# -------------------------------------------------------------- assess + draft


def _agent_groups(bookings: list[Booking]) -> dict[str, list[Booking]]:
    grouped: dict[str, list[Booking]] = {}
    for booking in bookings:
        grouped.setdefault(booking.agent_id, []).append(booking)
    # Largest exposure first, so a capped draft set covers the agents that
    # matter most rather than whichever happened to sort first.
    return dict(
        sorted(
            grouped.items(),
            key=lambda item: sum(b.value_inr for b in item[1]),
            reverse=True,
        )
    )


def _assessment_prompt(incident: TravelIncident, bookings: list[Booking]) -> str:
    groups = _agent_groups(bookings)
    soonest = min(
        (b.departure_at for b in bookings if b.departure_at is not None),
        default=None,
    )
    hours_away = (
        round((soonest - datetime.now(UTC)).total_seconds() / 3600, 1)
        if soonest is not None
        else None
    )

    lines = [
        f"Incident type: {incident.kind}",
        f"Title: {incident.title}",
        f"Description: {incident.description or '(none given)'}",
        f"Route: {incident.route or '(not route-specific)'}",
        f"Supplier: {incident.supplier or '(not supplier-specific)'}",
        f"Occurred at: {incident.occurred_at.isoformat() if incident.occurred_at else '(unknown)'}",
        "",
        "COMPUTED FACTS — these are measured, not for you to change:",
        f"- Affected bookings: {incident.affected_count}",
        f"- Total value at risk: INR {incident.affected_value_inr:,.0f}",
        f"- Travel agencies affected: {len(groups)}",
    ]
    if soonest is not None and hours_away is not None:
        lines.append(
            f"- Soonest affected departure: {soonest.isoformat()} ({hours_away} hours from now)"
        )
    lines.append("")
    lines.append("Per agency:")
    for agent_id, group in list(groups.items())[:MAX_DRAFTS]:
        value = sum(b.value_inr for b in group)
        lines.append(
            f"- {group[0].agent_name} ({agent_id}): {len(group)} booking(s), INR {value:,.0f}"
        )
    return "\n".join(lines)


def _draft_prompt(incident: TravelIncident, bookings: list[Booking]) -> str:
    groups = _agent_groups(bookings)
    lines = [
        f"Incident: {incident.title}",
        f"Type: {incident.kind}",
        f"Route: {incident.route or 'n/a'}   Supplier: {incident.supplier or 'n/a'}",
        f"Severity assessed as: {incident.severity or 'not yet assessed'}",
        f"Traveller impact: {incident.traveller_impact or '(not stated)'}",
        f"Operations plan: {incident.recommended_action or '(not stated)'}",
        "",
        "Write one message per agency below, using its agent_id exactly:",
    ]
    for agent_id, group in list(groups.items())[:MAX_DRAFTS]:
        lines.append("")
        lines.append(f"Agency: {group[0].agent_name}  (agent_id: {agent_id})")
        for booking in group[:12]:
            when = booking.departure_at.isoformat() if booking.departure_at else "date unknown"
            lines.append(
                f"  - {booking.id}: {booking.traveller_name}, {booking.booking_type}, "
                f"{booking.route or booking.supplier or 'n/a'}, departs {when}, "
                f"INR {booking.value_inr:,.0f}"
            )
        if len(group) > 12:
            lines.append(f"  - ...and {len(group) - 12} more booking(s)")
    return "\n".join(lines)


def _usage_of(result: Any) -> UsageInfo:
    return UsageInfo(
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_demo_cache=result.from_demo_cache,
    )


def _combine(first: UsageInfo, second: UsageInfo) -> UsageInfo:
    return UsageInfo(
        model=second.model or first.model,
        provider=second.provider or first.provider,
        duration_ms=first.duration_ms + second.duration_ms,
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        estimated_cost_usd=(
            None
            if first.estimated_cost_usd is None and second.estimated_cost_usd is None
            else round((first.estimated_cost_usd or 0) + (second.estimated_cost_usd or 0), 6)
        ),
        from_demo_cache=first.from_demo_cache and second.from_demo_cache,
    )


def assess_and_draft(
    db: Session,
    incident: TravelIncident,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
) -> tuple[TravelIncident, UsageInfo]:
    """Run the incident workflow up to the approval pause.

    Executes the whole Section 14 flow as one workflow run: lookup, severity
    assessment, drafting, then a stop. It returns with the execution paused —
    the recording node beyond the pause has not run and cannot run until a
    person approves.
    """
    settings = settings or get_settings()
    provider = provider_override or get_provider(settings)

    if incident.affected_count == 0:
        raise ValidationError(
            "This incident affects no bookings, so there is nothing to assess.",
            user_message=(
                "No bookings match this incident, so there is nothing to assess or "
                "draft. Check the route, supplier and date."
            ),
        )

    bookings = [
        booking
        for booking in (
            get_booking_provider().get_booking(booking_id)
            for booking_id in incident.affected_booking_ids
        )
        if booking is not None
    ]
    if not bookings:
        raise ValidationError(
            "The affected bookings recorded on this incident no longer resolve.",
            user_message=(
                "The bookings recorded against this incident could not be read. "
                "Re-report the incident to refresh the lookup."
            ),
        )

    usage = UsageInfo()
    engine = WorkflowEngine()

    def _lookup(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        # Re-runs the lookup inside the workflow so the execution log records
        # it as a step. Deterministic and free, so repeating it costs nothing.
        found = find_affected(incident)
        _apply_lookup(incident, found)
        return {
            "affected_count": incident.affected_count,
            "affected_value_inr": incident.affected_value_inr,
            "agencies": len(_agent_groups(found)),
        }

    def _assess(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        nonlocal usage
        result = provider.generate_structured_output(
            _assessment_prompt(incident, bookings),
            output_model=IncidentAssessment,
            system=ASSESS_SYSTEM,
        )
        usage = _combine(usage, _usage_of(result))
        assessment = result.value
        incident.severity = assessment.severity.value
        incident.severity_reasoning = assessment.reasoning_summary
        incident.traveller_impact = assessment.traveller_impact
        incident.recommended_action = assessment.recommended_action
        return {
            "severity": assessment.severity.value,
            "reasoning_summary": assessment.reasoning_summary,
            "_ai_model": result.model,
            "_ai_cost": result.usage.estimated_cost_usd,
        }

    def _draft(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        nonlocal usage
        result = provider.generate_structured_output(
            _draft_prompt(incident, bookings),
            output_model=DraftSet,
            system=DRAFT_SYSTEM,
        )
        usage = _combine(usage, _usage_of(result))

        groups = _agent_groups(bookings)
        # Replace any previous drafts; re-assessing should not leave stale text
        # sitting next to fresh text.
        incident.communications.clear()

        written = 0
        for message in result.value.messages:
            group = groups.get(message.agent_id)
            if group is None:
                # The model addressed an agency that is not affected. Dropping
                # it is the honest response: sending it would be worse.
                logger.warning(
                    "dropped a draft for an unaffected agent",
                    extra={"incident_id": incident.id, "agent_id": message.agent_id},
                )
                continue
            incident.communications.append(
                TravelCommunication(
                    incident_id=incident.id,
                    agent_id=message.agent_id,
                    agent_name=group[0].agent_name,
                    booking_ids=[b.id for b in group],
                    subject=message.subject.strip()[:300],
                    body=message.body.strip(),
                    status=CommunicationStatus.DRAFT.value,
                )
            )
            written += 1

        if written == 0:
            raise ValidationError("The model produced no usable drafts for the affected agencies.")
        return {
            "drafts": written,
            "_ai_model": result.model,
            "_ai_cost": result.usage.estimated_cost_usd,
        }

    def _record(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Record the approved communications. Only reachable after approval.

        Guarded anyway. The engine cannot walk here without `resume()`, and
        `resume()` requires an approver — but a handler that quietly trusted
        its position in a graph would be one refactor away from being wrong.
        """
        approver = str(context.get("approved_by") or "").strip()
        if not context.get("approved") or not approver:
            raise ValidationError("The recording step ran without an approval in context.")

        email = get_email_provider()
        recorded = 0
        for communication in incident.communications:
            if communication.status != CommunicationStatus.APPROVED.value:
                continue
            if communication.recorded_message_id:
                continue
            # The mock adapter logs the send and transmits nothing. It also
            # refuses an empty approver, which is the second guard.
            communication.recorded_message_id = email.send_message(
                recipient=f"{communication.agent_id}@agency.example-travel.test",
                subject=communication.subject,
                body=communication.body,
                approved_by=approver,
            )
            recorded += 1
        return {"recorded": recorded, "transmitted": 0}

    engine.register(NodeType.TRANSFORM, _lookup)
    engine.register(NodeType.AI_CLASSIFICATION, _assess)
    engine.register(NodeType.AI_GENERATION, _draft)
    engine.register(NodeType.EMAIL, _record)

    workflow = incident_workflow()
    execution = engine.run(
        workflow,
        context={"incident_id": incident.id, "kind": incident.kind},
    )

    if execution.status is ExecutionStatus.FAILED:
        # Leave the incident as it was. A failed assessment must not make an
        # untouched incident look like a reviewed one.
        raise ValidationError(
            execution.error or "The incident workflow failed.",
            user_message=(
                "The assessment could not be completed. Nothing was sent and the "
                "incident is unchanged."
            ),
        )

    incident.execution = execution.model_dump(mode="json")
    incident.status = (
        IncidentStatus.AWAITING_APPROVAL.value
        if execution.status is ExecutionStatus.AWAITING_APPROVAL
        else IncidentStatus.ASSESSED.value
    )
    db.flush()
    logger.info(
        "incident assessed and drafted",
        extra={
            "project": "ai-travel-operations",
            "incident_id": incident.id,
            "severity": incident.severity,
            "drafts": len(incident.communications),
            "execution_status": execution.status.value,
            "estimated_cost_usd": usage.estimated_cost_usd,
        },
    )
    return incident, usage


# ---------------------------------------------------------------- approval


def decide_communication(
    db: Session, communication: TravelCommunication, request: ApprovalRequest
) -> TravelCommunication:
    """Approve or reject one drafted message.

    Approving marks the draft. It does **not** transmit anything, and does not
    itself reach the recording step — that happens once every draft on the
    incident has been decided, by resuming the paused workflow.
    """
    if communication.status != CommunicationStatus.DRAFT.value:
        raise ValidationError(
            f"Communication {communication.id} is already {communication.status}.",
            user_message="That message has already been decided on.",
        )

    incident = communication.incident
    approver = request.approved_by.strip()

    if request.approved:
        communication.status = CommunicationStatus.APPROVED.value
        communication.approved_by = approver
        communication.approved_at = datetime.now(UTC)
    else:
        communication.status = CommunicationStatus.REJECTED.value
        communication.approved_by = approver
        communication.approved_at = datetime.now(UTC)
        communication.rejection_note = (request.note or "").strip() or None

    db.flush()

    undecided = [c for c in incident.communications if c.status == CommunicationStatus.DRAFT.value]
    if not undecided:
        _close_out(db, incident, approver=approver)

    logger.info(
        "communication decided",
        extra={
            "project": "ai-travel-operations",
            "incident_id": incident.id,
            "communication_id": communication.id,
            "approved": request.approved,
            "approved_by": approver,
        },
    )
    return communication


def _close_out(db: Session, incident: TravelIncident, *, approver: str) -> None:
    """Resume the paused workflow now every draft has been decided."""
    if not incident.execution:
        incident.status = IncidentStatus.RESOLVED.value
        return

    execution = WorkflowExecution.model_validate(incident.execution)
    if execution.status is not ExecutionStatus.AWAITING_APPROVAL:
        incident.status = IncidentStatus.RESOLVED.value
        return

    any_approved = any(
        c.status == CommunicationStatus.APPROVED.value for c in incident.communications
    )

    engine = WorkflowEngine()

    def _record(node: Any, context: dict[str, Any]) -> dict[str, Any]:
        approved_by = str(context.get("approved_by") or "").strip()
        if not context.get("approved") or not approved_by:
            raise ValidationError("The recording step ran without an approval in context.")

        email = get_email_provider()
        recorded = 0
        for communication in incident.communications:
            if communication.status != CommunicationStatus.APPROVED.value:
                continue
            if communication.recorded_message_id:
                continue
            communication.recorded_message_id = email.send_message(
                recipient=f"{communication.agent_id}@agency.example-travel.test",
                subject=communication.subject,
                body=communication.body,
                approved_by=approved_by,
            )
            recorded += 1
        return {"recorded": recorded, "transmitted": 0}

    engine.register(NodeType.EMAIL, _record)

    execution = engine.resume(
        incident_workflow(), execution, approved_by=approver, approved=any_approved
    )
    incident.execution = execution.model_dump(mode="json")
    incident.status = IncidentStatus.RESOLVED.value
    db.flush()


# ------------------------------------------------------------------- reading


def _views(incident: TravelIncident) -> list[CommunicationView]:
    return [
        CommunicationView(
            id=c.id,
            agent_id=c.agent_id,
            agent_name=c.agent_name,
            booking_ids=list(c.booking_ids or []),
            subject=c.subject,
            body=c.body,
            status=c.status,
            approved_by=c.approved_by,
            approved_at=c.approved_at,
            rejection_note=c.rejection_note,
            recorded_message_id=c.recorded_message_id,
        )
        for c in incident.communications
    ]


def to_detail(incident: TravelIncident) -> IncidentDetail:
    provider = get_booking_provider()
    bookings = [
        booking
        for booking in (
            provider.get_booking(booking_id)
            for booking_id in (incident.affected_booking_ids or [])[:MAX_LISTED_BOOKINGS]
        )
        if booking is not None
    ]
    return IncidentDetail(
        id=incident.id,
        kind=incident.kind,
        title=incident.title,
        description=incident.description,
        route=incident.route,
        supplier=incident.supplier,
        occurred_at=incident.occurred_at,
        status=incident.status,
        severity=incident.severity,
        severity_reasoning=incident.severity_reasoning,
        traveller_impact=incident.traveller_impact,
        recommended_action=incident.recommended_action,
        affected_count=incident.affected_count,
        affected_value_inr=incident.affected_value_inr,
        affected_bookings=[AffectedBooking.of(b) for b in bookings],
        communications=_views(incident),
        execution=incident.execution,
        created_at=incident.created_at,
    )


def to_summary(incident: TravelIncident) -> IncidentSummary:
    drafts = [c for c in incident.communications if c.status == CommunicationStatus.DRAFT.value]
    return IncidentSummary(
        id=incident.id,
        kind=incident.kind,
        title=incident.title,
        route=incident.route,
        supplier=incident.supplier,
        occurred_at=incident.occurred_at,
        status=incident.status,
        severity=incident.severity,
        affected_count=incident.affected_count,
        affected_value_inr=incident.affected_value_inr,
        draft_count=len(incident.communications),
        awaiting_approval_count=len(drafts),
    )


def list_incidents(db: Session, *, limit: int = 100) -> list[TravelIncident]:
    return list(
        db.scalars(select(TravelIncident).order_by(TravelIncident.created_at.desc()).limit(limit))
    )


def get_incident(db: Session, incident_id: str) -> TravelIncident:
    incident = db.get(TravelIncident, incident_id)
    if incident is None:
        raise NotFoundError(
            f"No incident {incident_id!r}.", user_message="That incident does not exist."
        )
    return incident


def get_communication(db: Session, communication_id: str) -> TravelCommunication:
    communication = db.get(TravelCommunication, communication_id)
    if communication is None:
        raise NotFoundError(
            f"No communication {communication_id!r}.",
            user_message="That message does not exist.",
        )
    return communication


# --------------------------------------------------------------------- seeding


def seed_incidents(db: Session) -> int:
    """Create incidents from delays already present in the booking data.

    The console is far more convincing with real-looking work waiting on it
    than with an empty state and a "report an incident" button, and these are
    derived from the synthetic dataset rather than invented separately — the
    delays being reported are delays the data actually contains.

    Wrapped so a seeding failure cannot take the incident list down with it:
    seeding is a convenience, the list is the feature.
    """
    try:
        return _seed_incidents(db)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            "could not seed travel incidents; continuing without them",
            extra={"error": str(exc).splitlines()[0][:200]},
        )
        return 0


def _seed_incidents(db: Session) -> int:
    if db.scalar(select(TravelIncident.id).limit(1)) is not None:
        return 0

    delayed = get_booking_provider().list_bookings(status=BookingStatus.DELAYED, limit=200)
    if not delayed:
        return 0

    # Group the delayed flights by route and departure date: one incident per
    # disrupted departure, which is how an operations team would see it.
    grouped: dict[tuple[str, Any], list[Booking]] = {}
    for booking in delayed:
        if not booking.route or booking.departure_at is None:
            continue
        grouped.setdefault((booking.route, booking.departure_at.date()), []).append(booking)

    created = 0
    for (route, day), group in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)[
        :5
    ]:
        supplier = group[0].supplier
        occurred = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
        incident = TravelIncident(
            kind=IncidentKind.FLIGHT_DELAY.value,
            title=f"{route} delayed — {supplier or 'carrier'} service on {day.isoformat()}",
            description=(
                f"{len(group)} booking(s) on {route} are marked delayed for departure "
                f"on {day.isoformat()}. Agencies have not yet been contacted."
            ),
            route=route,
            supplier=supplier,
            occurred_at=occurred,
            status=IncidentStatus.OPEN.value,
        )
        _apply_lookup(incident, find_affected(incident))
        db.add(incident)
        created += 1

    db.flush()
    # `created` is a reserved LogRecord attribute; passing it raises KeyError.
    logger.info("seeded travel incidents", extra={"seeded": created})
    return created


__all__ = [
    "MAX_DRAFTS",
    "Severity",
    "assess_and_draft",
    "decide_communication",
    "find_affected",
    "get_communication",
    "get_incident",
    "list_incidents",
    "report_incident",
    "seed_incidents",
    "to_detail",
    "to_summary",
]
