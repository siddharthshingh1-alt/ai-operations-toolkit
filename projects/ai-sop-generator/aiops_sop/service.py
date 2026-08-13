"""SOP generation, storage, and versioning.

The rule this file exists to enforce: **the AI never writes to the database.**
Generation returns a draft to the caller; saving is a separate, explicit action
taken after a human has reviewed it (CLAUDE.md Section 5, human-in-the-loop).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_ai import AIResult, get_embedding_provider, get_provider
from aiops_ai.base import AIProvider
from aiops_config import Settings, get_settings
from aiops_db import ActivityLog
from aiops_sop.diffing import SopDiff, diff_sop_content
from aiops_sop.models import Sop, SopVersion
from aiops_sop.prompts import GENERATE_SYSTEM, build_generation_prompt
from aiops_sop.schema import (
    GenerateSopRequest,
    SaveSopRequest,
    SopContent,
    SopMetadata,
)
from aiops_utils import NotFoundError, ValidationError, get_logger

logger = get_logger(__name__)

PROJECT = "ai-sop-generator"


@dataclass
class GeneratedSop:
    """A draft SOP plus the metadata about how it was produced."""

    content: SopContent
    model: str
    provider: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    from_demo_cache: bool


# ---------------------------------------------------------------- generation


def generate_sop(
    request: GenerateSopRequest,
    *,
    settings: Settings | None = None,
    api_key: str | None = None,
    provider_override: AIProvider | None = None,
) -> GeneratedSop:
    """Ask the AI to draft an SOP. Writes nothing to the database.

    `provider_override` exists for `scripts/record_demo_outputs.py`, which wraps
    the live provider to capture its responses. Application code never uses it.
    """
    settings = settings or get_settings()
    provider = provider_override or get_provider(settings, api_key=api_key)

    result: AIResult[SopContent] = provider.generate_structured_output(
        build_generation_prompt(request),
        output_model=SopContent,
        system=GENERATE_SYSTEM,
    )

    logger.info(
        "sop generated",
        extra={"project": PROJECT, "action": "generate", **result.log_fields()},
    )

    return GeneratedSop(
        content=result.value,
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_demo_cache=result.from_demo_cache,
    )


# ------------------------------------------------------------------ storage


def _embed_version(
    content: SopContent,
    *,
    settings: Settings,
    embedding_override: AIProvider | None = None,
) -> tuple[list[float] | None, str | None]:
    """Embed an SOP's searchable text.

    Returns `(None, None)` on failure rather than raising: an SOP that saves
    but is temporarily unsearchable is far better than losing the user's edits
    because an embedding call timed out.
    """
    try:
        provider = embedding_override or get_embedding_provider(settings)
        result = provider.generate_embeddings([content.to_search_text()])
        return result.value[0], result.model
    except Exception as exc:  # noqa: BLE001 — degraded search, not a save failure
        logger.warning(
            "could not embed SOP; it will save but not appear in search",
            extra={"project": PROJECT, "error": str(exc)},
        )
        return None, None


def _log_activity(
    session: Session,
    *,
    action: str,
    summary: str,
    generated: GeneratedSop | None,
    actor: str,
) -> None:
    """Record the action in the shared activity log (CLAUDE.md Sections 22, 3d)."""
    session.add(
        ActivityLog(
            actor=actor,
            project=PROJECT,
            action=action,
            summary=summary,
            status="success",
            duration_ms=generated.duration_ms if generated else 0,
            ai_provider=generated.provider if generated else None,
            ai_model=generated.model if generated else None,
            input_tokens=generated.input_tokens if generated else None,
            output_tokens=generated.output_tokens if generated else None,
            estimated_cost_usd=generated.estimated_cost_usd if generated else None,
            from_demo_cache=generated.from_demo_cache if generated else False,
            # A saved SOP is by definition human-reviewed — the UI cannot save
            # without the editor step.
            human_approved=True,
            approved_by=actor,
        )
    )


def create_sop(
    session: Session,
    request: SaveSopRequest,
    *,
    actor: str,
    generated: GeneratedSop | None = None,
    settings: Settings | None = None,
    embedding_override: AIProvider | None = None,
) -> Sop:
    """Save a reviewed SOP as version 1."""
    settings = settings or get_settings()
    if not request.content.title.strip():
        raise ValidationError("An SOP needs a title before it can be saved.")

    embedding, embed_model = _embed_version(
        request.content, settings=settings, embedding_override=embedding_override
    )
    meta = request.metadata

    sop = Sop(
        title=request.content.title.strip(),
        owner=meta.owner,
        department=meta.department,
        status=meta.status.value,
        effective_date=meta.effective_date,
        review_date=meta.review_date,
        current_version=1,
    )
    sop.versions.append(
        SopVersion(
            version=1,
            content=request.content.model_dump(mode="json"),
            change_note=request.change_note or "Initial version",
            created_by=actor,
            ai_generated=generated is not None,
            ai_model=generated.model if generated else None,
            embedding=embedding,
        )
    )
    session.add(sop)
    session.flush()  # assign the id before logging references it

    _log_activity(
        session,
        action="create_sop",
        summary=f"Created SOP {sop.title!r} (embedded with {embed_model or 'none'})",
        generated=generated,
        actor=actor,
    )
    logger.info("sop created", extra={"project": PROJECT, "sop_id": sop.id})
    return sop


def add_version(
    session: Session,
    sop_id: str,
    request: SaveSopRequest,
    *,
    actor: str,
    settings: Settings | None = None,
) -> SopVersion:
    """Save edited content as the next version of an existing SOP."""
    settings = settings or get_settings()
    sop = get_sop(session, sop_id)

    embedding, _ = _embed_version(request.content, settings=settings)
    next_version = sop.current_version + 1

    version = SopVersion(
        sop_id=sop.id,
        version=next_version,
        content=request.content.model_dump(mode="json"),
        change_note=request.change_note or f"Version {next_version}",
        created_by=actor,
        ai_generated=False,  # a new version is always a human edit
        embedding=embedding,
    )
    session.add(version)

    # Governance fields live on the SOP, so they update in place.
    meta = request.metadata
    sop.title = request.content.title.strip() or sop.title
    sop.owner = meta.owner or sop.owner
    sop.department = meta.department or sop.department
    sop.status = meta.status.value
    sop.effective_date = meta.effective_date or sop.effective_date
    sop.review_date = meta.review_date or sop.review_date
    sop.current_version = next_version

    _log_activity(
        session,
        action="update_sop",
        summary=f"Saved version {next_version} of {sop.title!r}",
        generated=None,
        actor=actor,
    )
    logger.info(
        "sop version added",
        extra={"project": PROJECT, "sop_id": sop.id, "version": next_version},
    )
    return version


# ------------------------------------------------------------------ reading


def list_sops(session: Session, *, limit: int = 100) -> list[Sop]:
    """Every SOP, most recently updated first."""
    stmt = select(Sop).order_by(Sop.updated_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


def get_sop(session: Session, sop_id: str) -> Sop:
    """One SOP, or a clear error."""
    sop = session.get(Sop, sop_id)
    if sop is None:
        raise NotFoundError(f"No SOP with id {sop_id!r}")
    return sop


def get_version(session: Session, sop_id: str, version: int) -> SopVersion:
    """One specific version of an SOP."""
    stmt = select(SopVersion).where(SopVersion.sop_id == sop_id, SopVersion.version == version)
    found = session.execute(stmt).scalar_one_or_none()
    if found is None:
        raise NotFoundError(f"SOP {sop_id!r} has no version {version}")
    return found


def content_of(version: SopVersion) -> SopContent:
    """Parse a stored version back into the typed model."""
    return SopContent.model_validate(version.content)


def metadata_of(sop: Sop) -> SopMetadata:
    """The governance fields as a typed model."""
    return SopMetadata(
        owner=sop.owner,
        department=sop.department,
        status=sop.status,  # type: ignore[arg-type]
        effective_date=sop.effective_date,
        review_date=sop.review_date,
    )


def diff_versions(session: Session, sop_id: str, from_version: int, to_version: int) -> SopDiff:
    """Compare two versions of an SOP."""
    if from_version == to_version:
        raise ValidationError("Choose two different versions to compare.")

    old = get_version(session, sop_id, from_version)
    new = get_version(session, sop_id, to_version)
    return diff_sop_content(
        content_of(old),
        content_of(new),
        from_version=from_version,
        to_version=to_version,
    )
