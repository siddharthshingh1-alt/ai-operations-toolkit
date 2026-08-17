"""HTTP routes for the Ops Command Center.

Mounted by `apps/api` under `/api/command-center`.

Two routes. `GET /` collects from every source and costs nothing, because a
page meant to be opened every morning cannot spend a request to render. `POST
/brief` is the one AI call, and it is the only thing behind a button.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aiops_command import service
from aiops_command.schema import CommandCenterResponse, GenerateBriefResponse
from aiops_config import Settings, get_settings
from aiops_db import get_db

router = APIRouter(prefix="/api/command-center", tags=["ops-command-center"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=CommandCenterResponse, summary="Collected signals (no AI)")
def overview(db: DbDep) -> CommandCenterResponse:
    """Every signal the other projects are currently reporting.

    Free. No model is called, so this is safe to open repeatedly and safe to
    make the first page of the day.
    """
    return service.overview(db)


@router.post(
    "/brief",
    response_model=GenerateBriefResponse,
    summary="Write the daily Ops Brief (1 AI request)",
)
def generate(db: DbDep, settings: SettingsDep) -> GenerateBriefResponse:
    """Write the morning brief over the current signals.

    Re-gathers before generating, so the paragraph describes the situation at
    the moment of the request rather than whatever the page last rendered.
    """
    brief, usage = service.generate_brief(db, settings=settings)
    return GenerateBriefResponse(brief=service.brief_response(db, brief), usage=usage)
