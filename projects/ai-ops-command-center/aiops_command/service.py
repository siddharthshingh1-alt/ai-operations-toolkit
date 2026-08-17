"""Domain logic for the Ops Command Center (CLAUDE.md Section 17).

Thin by design. Gathering belongs to `signals.py`, which delegates to the four
owning projects; this module assembles what came back into a response, stores
the one thing this project produces, and asks the model for a paragraph.

There is no computation here about tasks, workflows, incidents or metrics, and
there must never be. The moment this file starts deciding whether a task is
overdue, Project 9 has become a second source of truth and Section 17 is
broken.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_ai.types import AIResult
from aiops_command import prompts
from aiops_command.models import OpsBrief
from aiops_command.schema import (
    BriefAction,
    BriefNarrative,
    BriefView,
    CommandCenterResponse,
    SignalView,
    SourceView,
    UsageInfo,
)
from aiops_command.signals import (
    DASHBOARD_DATASET,
    SOURCE_LABELS,
    SOURCE_LINKS,
    SignalSet,
    changed_since,
    gather,
)
from aiops_config import Settings, get_settings
from aiops_utils import get_logger

logger = get_logger(__name__)


# ------------------------------------------------------------------- assembly


def _signal_views(signal_set: SignalSet) -> list[SignalView]:
    return [
        SignalView(
            id=s.id,
            source=s.source,
            source_label=SOURCE_LABELS.get(s.source, s.source),
            severity=s.severity,
            title=s.title,
            detail=s.detail,
            link=s.link,
        )
        for s in signal_set.signals
    ]


def _source_views(signal_set: SignalSet) -> list[SourceView]:
    return [
        SourceView(
            source=s.source,
            label=SOURCE_LABELS.get(s.source, s.source),
            available=s.available,
            detail=s.detail,
            signal_count=s.signal_count,
            link=SOURCE_LINKS.get(s.source, "/"),
        )
        for s in signal_set.sources
    ]


def latest_brief(db: Session) -> OpsBrief | None:
    return db.scalar(select(OpsBrief).order_by(OpsBrief.created_at.desc()).limit(1))


def _brief_view(brief: OpsBrief, current_counts: dict[str, int]) -> BriefView:
    return BriefView(
        id=brief.id,
        summary=brief.summary,
        actions=[BriefAction.model_validate(a) for a in (brief.actions or [])],
        generated_at=brief.created_at,
        changed_since=changed_since(brief.signal_counts, current_counts),
        unavailable_sources=list(brief.unavailable_sources or []),
    )


def overview(db: Session, *, today: date | None = None) -> CommandCenterResponse:
    """Collect from every source and assemble the page.

    No AI. Opening the Command Center costs nothing, which is the only way a
    page like this can be the first thing someone looks at every morning.
    """
    signal_set = gather(db, today=today)
    counts = signal_set.counts()

    brief = latest_brief(db)
    severities = [s.severity for s in signal_set.signals]

    return CommandCenterResponse(
        collected_at=signal_set.collected_at,
        signals=_signal_views(signal_set),
        sources=_source_views(signal_set),
        brief=_brief_view(brief, counts) if brief else None,
        critical_count=severities.count("critical"),
        warning_count=severities.count("warning"),
        info_count=severities.count("info"),
        dashboard_dataset=DASHBOARD_DATASET,
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


def generate_brief(
    db: Session,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
    today: date | None = None,
) -> tuple[OpsBrief, UsageInfo]:
    """Ask the model to write the morning brief. One AI request.

    Runs a fresh gather first, so the narrative describes the situation now
    rather than whatever the page was showing when the button was pressed. A
    source being unavailable does not block generation — the prompt is told,
    and the brief records which sources were missing so it cannot later look
    more complete than it was.
    """
    resolved = settings or get_settings()
    provider = provider_override or get_provider(resolved)

    signal_set = gather(db, today=today)
    day = (today or datetime.now(UTC).date()).isoformat()

    result = provider.generate_structured_output(
        prompts.brief_prompt(signal_set.signals, signal_set.sources, today=day),
        output_model=BriefNarrative,
        system=prompts.BRIEF_SYSTEM,
    )

    known = {s.id for s in signal_set.signals}
    actions: list[dict] = []
    for action in result.value.actions[:5]:
        signal_id = action.signal_id if action.signal_id in known else None
        if action.signal_id and signal_id is None:
            # Drop the reference, keep the advice. A link that leads nowhere is
            # worse than no link.
            logger.warning(
                "model referenced an unknown signal; dropping the reference",
                extra={"claimed_signal_id": str(action.signal_id)[:64]},
            )
        actions.append({"action": action.action, "signal_id": signal_id})

    unavailable = [s.source for s in signal_set.sources if not s.available]
    brief = OpsBrief(
        summary=result.value.summary,
        actions=actions,
        signal_counts=signal_set.counts(),
        unavailable_sources=unavailable,
    )
    db.add(brief)
    db.flush()

    logger.info(
        "ops brief generated",
        extra={
            "project": "ai-ops-command-center",
            "brief_id": brief.id,
            "signal_count": len(signal_set.signals),
            "unavailable_sources": unavailable,
            "model": result.model,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )
    return brief, _usage_of(result)


def brief_response(db: Session, brief: OpsBrief, *, today: date | None = None) -> BriefView:
    """Re-read the sources so the returned brief knows if it is already stale."""
    return _brief_view(brief, gather(db, today=today).counts())


__all__ = [
    "brief_response",
    "generate_brief",
    "latest_brief",
    "overview",
]
