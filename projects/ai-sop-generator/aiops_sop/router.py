"""HTTP routes for the SOP Generator.

Mounted by `apps/api` under `/api/sop`. The router is thin on purpose — it
validates input, calls the service layer, and shapes responses. All domain
logic lives in `service.py` and `search.py` so it is testable without HTTP.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiops_config import Settings, get_settings
from aiops_db import get_db
from aiops_docproc import Document, DocumentSection, ExportFormat, extract_text, get_exporter
from aiops_sop import service
from aiops_sop.diffing import SopDiff
from aiops_sop.models import Sop
from aiops_sop.schema import (
    AnswerResult,
    AskRequest,
    GenerateSopRequest,
    SaveSopRequest,
    SopContent,
    SopMetadata,
)
from aiops_sop.search import SearchHit, answer_question, search_sops
from aiops_utils import ValidationError

router = APIRouter(prefix="/api/sop", tags=["sop"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


# ------------------------------------------------------------------ responses


class UsageInfo(BaseModel):
    """Cost metadata surfaced to the UI (CLAUDE.md Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class GenerateResponse(BaseModel):
    content: SopContent
    usage: UsageInfo


class SopSummary(BaseModel):
    """A row in the SOP library list."""

    id: str
    title: str
    owner: str
    department: str
    status: str
    current_version: int
    effective_date: str | None = None
    review_date: str | None = None
    updated_at: str


class VersionSummary(BaseModel):
    version: int
    change_note: str
    created_by: str
    created_at: str
    ai_generated: bool
    ai_model: str | None = None
    searchable: bool


class SopDetail(BaseModel):
    id: str
    metadata: SopMetadata
    content: SopContent
    version: int
    versions: list[VersionSummary]


class AskResponse(BaseModel):
    result: AnswerResult
    usage: UsageInfo
    #: True when the relevance floor rejected everything and no AI call was made.
    skipped_ai: bool = False


def _summarise(sop: Sop) -> SopSummary:
    return SopSummary(
        id=sop.id,
        title=sop.title,
        owner=sop.owner,
        department=sop.department,
        status=sop.status,
        current_version=sop.current_version,
        effective_date=sop.effective_date.isoformat() if sop.effective_date else None,
        review_date=sop.review_date.isoformat() if sop.review_date else None,
        updated_at=sop.updated_at.isoformat(),
    )


# ----------------------------------------------------------------- generation


@router.post("/generate", response_model=GenerateResponse, summary="Draft an SOP")
def generate(request: GenerateSopRequest, settings: SettingsDep) -> GenerateResponse:
    """Draft an SOP from a description. Saves nothing — review comes first."""
    generated = service.generate_sop(request, settings=settings)
    return GenerateResponse(
        content=generated.content,
        usage=UsageInfo(
            model=generated.model,
            provider=generated.provider,
            duration_ms=generated.duration_ms,
            input_tokens=generated.input_tokens,
            output_tokens=generated.output_tokens,
            estimated_cost_usd=generated.estimated_cost_usd,
            from_demo_cache=generated.from_demo_cache,
        ),
    )


class ExtractResponse(BaseModel):
    filename: str
    characters: int
    text: str


@router.post("/extract", response_model=ExtractResponse, summary="Read an uploaded document")
async def extract(settings: SettingsDep, file: UploadFile = File(...)) -> ExtractResponse:
    """Pull the text out of an uploaded PDF, Word, or text file."""
    data = await file.read()

    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise ValidationError(
            f"Upload is {len(data)} bytes, over the {limit} byte limit.",
            user_message=f"That file is too large. The limit is {settings.max_upload_mb} MB.",
        )

    text = extract_text(data, file.filename or "upload")
    return ExtractResponse(filename=file.filename or "upload", characters=len(text), text=text)


# -------------------------------------------------------------------- library


@router.get("", response_model=list[SopSummary], summary="List all SOPs")
def list_all(db: DbDep) -> list[SopSummary]:
    return [_summarise(sop) for sop in service.list_sops(db)]


@router.post("", response_model=SopDetail, status_code=201, summary="Save a new SOP")
def create(request: SaveSopRequest, db: DbDep, settings: SettingsDep) -> SopDetail:
    """Save reviewed content as version 1."""
    sop = service.create_sop(db, request, actor=settings.demo_user_email, settings=settings)
    db.flush()
    return _detail(sop, sop.current_version)


@router.get("/{sop_id}", response_model=SopDetail, summary="Read one SOP")
def read(
    sop_id: str,
    db: DbDep,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> SopDetail:
    """Read an SOP, optionally at a specific historical version."""
    sop = service.get_sop(db, sop_id)
    return _detail(sop, version or sop.current_version)


def _detail(sop: Sop, version: int) -> SopDetail:
    target = next((v for v in sop.versions if v.version == version), None)
    if target is None:
        from aiops_utils import NotFoundError

        raise NotFoundError(f"SOP {sop.id!r} has no version {version}")

    return SopDetail(
        id=sop.id,
        metadata=service.metadata_of(sop),
        content=service.content_of(target),
        version=target.version,
        versions=[
            VersionSummary(
                version=v.version,
                change_note=v.change_note,
                created_by=v.created_by,
                created_at=v.created_at.isoformat(),
                ai_generated=v.ai_generated,
                ai_model=v.ai_model,
                searchable=v.embedding is not None,
            )
            for v in sorted(sop.versions, key=lambda v: v.version, reverse=True)
        ],
    )


@router.post("/{sop_id}/versions", response_model=SopDetail, summary="Save a new version")
def add_version(
    sop_id: str, request: SaveSopRequest, db: DbDep, settings: SettingsDep
) -> SopDetail:
    service.add_version(db, sop_id, request, actor=settings.demo_user_email, settings=settings)
    db.flush()
    db.refresh(sop := service.get_sop(db, sop_id))
    return _detail(sop, sop.current_version)


@router.get("/{sop_id}/diff", response_model=SopDiff, summary="Compare two versions")
def diff(
    sop_id: str,
    db: DbDep,
    from_version: Annotated[int, Query(ge=1, alias="from")],
    to_version: Annotated[int, Query(ge=1, alias="to")],
) -> SopDiff:
    return service.diff_versions(db, sop_id, from_version, to_version)


# --------------------------------------------------------------------- export


@router.get("/{sop_id}/export", summary="Download an SOP")
def export(
    sop_id: str,
    db: DbDep,
    fmt: Annotated[Literal["markdown", "html", "pdf"], Query(alias="format")] = "markdown",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    """Download an SOP as Markdown, HTML, or PDF."""
    sop = service.get_sop(db, sop_id)
    stored = service.get_version(db, sop_id, version or sop.current_version)
    content = service.content_of(stored)

    exporter = get_exporter(ExportFormat(fmt))
    document = _as_document(sop, content, stored.version)
    body = exporter.render(document)

    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in sop.title).strip()
    filename = f"{safe_title or 'sop'} v{stored.version}.{exporter.extension}"
    return Response(
        content=body,
        media_type=exporter.media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def _as_document(sop: Sop, content: SopContent, version: int) -> Document:
    """Convert an SOP into the shared export document shape."""
    sections = [
        DocumentSection(heading="Purpose", body=content.purpose),
        DocumentSection(heading="Scope", body=content.scope),
        DocumentSection(heading="Prerequisites", bullets=content.prerequisites),
        DocumentSection(heading="Roles", bullets=content.roles),
        DocumentSection(
            heading="Procedure",
            bullets=[
                f"{s.number}. {s.instruction}"
                + (f" (Responsible: {s.responsible})" if s.responsible else "")
                + (f" Expected: {s.expected_result}" if s.expected_result else "")
                for s in content.procedure
            ],
        ),
        DocumentSection(
            heading="Decision points",
            bullets=[
                f"{d.question} — if yes: {d.if_yes}; if no: {d.if_no}"
                for d in content.decision_points
            ],
        ),
        DocumentSection(
            heading="Exceptions",
            bullets=[f"{e.situation} → {e.action}" for e in content.exceptions],
        ),
        DocumentSection(
            heading="Escalation rules",
            bullets=[
                f"{e.trigger} → {e.escalate_to}" + (f" within {e.within}" if e.within else "")
                for e in content.escalation_rules
            ],
        ),
        DocumentSection(heading="Checklist", bullets=content.checklist),
        DocumentSection(
            heading="KPIs",
            bullets=[
                f"{k.name}"
                + (f" — target {k.target}" if k.target else "")
                + (f" ({k.how_measured})" if k.how_measured else "")
                for k in content.kpis
            ],
        ),
        DocumentSection(
            heading="Risks",
            bullets=[
                f"[{r.severity}] {r.description}"
                + (f" — mitigation: {r.mitigation}" if r.mitigation else "")
                for r in content.risks
            ],
        ),
        DocumentSection(heading="Improvement suggestions", bullets=content.improvement_suggestions),
    ]

    metadata = {
        "Version": str(version),
        "Owner": sop.owner or "unassigned",
        "Department": sop.department or "unassigned",
        "Status": sop.status,
    }
    if sop.effective_date:
        metadata["Effective date"] = sop.effective_date.isoformat()
    if sop.review_date:
        metadata["Review date"] = sop.review_date.isoformat()

    return Document(
        title=content.title,
        subtitle=content.purpose[:160] if content.purpose else None,
        metadata=metadata,
        sections=[s for s in sections if s.body or s.bullets],
        footer=(
            "Generated by the AI Operations Toolkit. Demo data only — this is a "
            "portfolio project, not a real operational document."
        ),
    )


# --------------------------------------------------------------------- search


@router.get("/search/query", response_model=list[SearchHit], summary="Search SOPs")
def search(
    db: DbDep,
    settings: SettingsDep,
    q: Annotated[str, Query(min_length=2)],
    top_k: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[SearchHit]:
    return search_sops(db, q, top_k=top_k, settings=settings)


@router.post("/search/ask", response_model=AskResponse, summary="Ask the SOP library")
def ask(request: AskRequest, db: DbDep, settings: SettingsDep) -> AskResponse:
    """Answer a question from the SOPs, citing which ones were used."""
    outcome = answer_question(db, request.question, top_k=request.top_k, settings=settings)
    return AskResponse(
        result=outcome.result,
        skipped_ai=outcome.skipped_ai,
        usage=UsageInfo(
            model=outcome.model,
            provider=outcome.provider,
            duration_ms=outcome.duration_ms,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            estimated_cost_usd=outcome.estimated_cost_usd,
            from_demo_cache=outcome.from_demo_cache,
        ),
    )
