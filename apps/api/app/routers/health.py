"""Health and readiness endpoints (CLAUDE.md Section 32, item 7).

Three endpoints, three audiences:

  GET /health        load balancers — is the process alive?
  GET /health/ready  operators      — is every dependency usable?
  GET /api/system    the frontend   — which mode am I in, and what works?

`/health/ready` deliberately reports *degraded* rather than *unhealthy* when an
optional dependency is missing. A toolkit running in Demo Mode with no database
and no PDF libraries is working exactly as designed, and should not page anyone.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aiops_ai import DemoProvider, known_models
from aiops_config import Settings, get_settings
from aiops_db import connection_error, has_pgvector
from aiops_docproc import PdfExporter, available_formats
from aiops_utils import utcnow

router = APIRouter(tags=["system"])

Status = Literal["ok", "degraded", "unhealthy"]


class Check(BaseModel):
    """One dependency's status."""

    name: str
    status: Literal["ok", "not_configured", "unavailable"]
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "aiops-api"
    version: str = "0.1.0"
    checked_at: str


class ReadinessResponse(BaseModel):
    status: Status
    checked_at: str
    checks: list[Check] = Field(default_factory=list)


class SystemInfoResponse(BaseModel):
    """What the UI needs to label the current mode honestly (Section 3b)."""

    app_name: str
    app_env: str
    demo_mode: bool
    allow_bring_your_own_key: bool
    ai_provider: str
    auth_mode: str
    database_configured: bool
    demo_recordings: int
    export_formats: list[str]
    priced_models: list[str]


#: Maps a connection failure to something actionable. Deliberately keyed on
#: substrings of the driver's message rather than on exception types, because
#: psycopg reports most of these as the same OperationalError.
_DB_HINTS: list[tuple[tuple[str, ...], str]] = [
    (
        ("password authentication failed", "authentication failed"),
        "The username or password is wrong. On Supabase's session pooler the "
        "username includes the project ref, e.g. 'postgres.abcdefgh' — not "
        "plain 'postgres'.",
    ),
    (
        ("could not translate host name", "name or service not known", "getaddrinfo"),
        "The hostname does not resolve. Check it for typos.",
    ),
    (
        ("timeout", "timed out"),
        "The host did not answer. If the host is 'db.<ref>.supabase.co' that is "
        "the direct connection, which is IPv6-only and unreachable from most "
        "cloud hosts — use the session pooler instead.",
    ),
    (
        ("connection refused",),
        "The host answered but refused the port. Check the port number.",
    ),
    (
        ("does not exist",),
        "The database or role named in the URL does not exist.",
    ),
    (
        ("ssl", "certificate"),
        "TLS negotiation failed. Supabase requires SSL; do not disable it.",
    ),
]


def _database_check(settings: Settings) -> Check:
    if not settings.database_configured:
        return Check(
            name="database",
            status="not_configured",
            detail="No DATABASE_URL set. Demo Mode does not require one.",
        )

    error = connection_error(settings)
    if error is None:
        vector = "with pgvector" if has_pgvector(settings) else "without pgvector"
        return Check(name="database", status="ok", detail=f"Connected {vector}.")

    # Report *why* it failed, not just that it did — but never echo the URL,
    # which contains the password.
    lowered = error.lower()
    for markers, hint in _DB_HINTS:
        if any(marker in lowered for marker in markers):
            return Check(name="database", status="unavailable", detail=hint)

    return Check(
        name="database",
        status="unavailable",
        detail="The database did not respond. Check the service logs for the driver error.",
    )


def _ai_check(settings: Settings) -> Check:
    if settings.demo_mode:
        count = DemoProvider().available_recordings()
        if count == 0:
            return Check(
                name="ai",
                status="not_configured",
                detail=(
                    "Demo Mode is on but no recordings exist yet. "
                    "Run 'npm run record-demo' once with a real API key."
                ),
            )
        return Check(
            name="ai",
            status="ok",
            detail=f"Demo Mode: replaying {count} recorded outputs.",
        )

    if not settings.api_key_for(settings.ai_provider):
        return Check(
            name="ai",
            status="not_configured",
            detail=f"DEMO_MODE is off but no API key is set for {settings.ai_provider}.",
        )
    return Check(
        name="ai",
        status="ok",
        detail=f"Live: {settings.ai_provider} / {settings.model_for(settings.ai_provider)}.",
    )


def _pdf_check() -> Check:
    if PdfExporter.is_available():
        return Check(name="pdf_export", status="ok", detail="WeasyPrint available.")
    return Check(
        name="pdf_export",
        status="not_configured",
        detail="WeasyPrint's native libraries are missing. Markdown and HTML still work.",
    )


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Always 200 while the process is running. Does not touch dependencies."""
    return HealthResponse(checked_at=utcnow().isoformat())


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness probe")
def readiness() -> ReadinessResponse:
    """Report every dependency. Optional ones missing means degraded, not down."""
    settings = get_settings()
    checks = [_database_check(settings), _ai_check(settings), _pdf_check()]

    if any(check.status == "unavailable" for check in checks):
        status: Status = "unhealthy"
    elif any(check.status == "not_configured" for check in checks):
        status = "degraded"
    else:
        status = "ok"

    return ReadinessResponse(status=status, checked_at=utcnow().isoformat(), checks=checks)


@router.get("/api/system", response_model=SystemInfoResponse, summary="Current configuration")
def system_info() -> SystemInfoResponse:
    """Non-secret configuration, for the UI's mode badge.

    Uses `Settings.redacted()`, which cannot leak an API key by construction.
    """
    settings = get_settings()
    return SystemInfoResponse(
        app_name=settings.app_name,
        app_env=settings.app_env,
        demo_mode=settings.demo_mode,
        allow_bring_your_own_key=settings.allow_bring_your_own_key,
        ai_provider=settings.ai_provider.value,
        auth_mode=settings.auth_mode.value,
        database_configured=settings.database_configured,
        demo_recordings=DemoProvider().available_recordings(),
        export_formats=[fmt.value for fmt in available_formats()],
        priced_models=known_models(),
    )
