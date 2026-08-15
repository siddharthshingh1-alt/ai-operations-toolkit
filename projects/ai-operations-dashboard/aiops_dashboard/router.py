"""HTTP routes for the Operations Dashboard.

Mounted by `apps/api` under `/api/dashboard`.

The endpoints are split deliberately. `/analyse` is arithmetic and always
works; `/insights` costs an AI request. Keeping them apart means the dashboard
renders in full when the day's AI budget is gone — the visitor loses the
commentary, not the numbers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from aiops_config import Settings, get_settings
from aiops_dashboard.analysis import analyse
from aiops_dashboard.insights import explain
from aiops_dashboard.models import Analysis, InsightResponse, SampleDataset
from aiops_dashboard.samples import available_samples, load_sample
from aiops_docproc import MAX_UPLOAD_BYTES, read_table
from aiops_utils import ValidationError

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class SampleListResponse(BaseModel):
    samples: list[SampleDataset]


class InsightRequest(BaseModel):
    """An analysis to interpret.

    The client posts the analysis back rather than the file. The AI never needs
    the rows, and re-uploading them to get commentary would be both slower and
    a larger attack surface for no benefit.
    """

    analysis: Analysis = Field(description="The analysis returned by /analyse.")


@router.get("/samples", response_model=SampleListResponse, summary="Bundled datasets")
def list_samples() -> SampleListResponse:
    """Datasets a visitor can analyse without uploading anything."""
    return SampleListResponse(samples=available_samples())


@router.get("/samples/{key}", response_model=Analysis, summary="Analyse a bundled dataset")
def analyse_sample(key: str) -> Analysis:
    """Profile, trend and anomaly-check one of the bundled datasets."""
    frame = load_sample(key)
    return analyse(frame, dataset=key)


@router.post("/analyse", response_model=Analysis, summary="Analyse an uploaded file")
async def analyse_upload(file: Annotated[UploadFile, File()]) -> Analysis:
    """Profile, trend and anomaly-check an uploaded CSV or Excel file.

    No AI is involved, so this works with no API key and spends no quota.
    """
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Upload is {len(data):,} bytes.",
            user_message=(
                f"That file is too large. The limit is {MAX_UPLOAD_BYTES // 1_048_576} MB."
            ),
        )

    frame = read_table(data, file.filename or "upload.csv")
    return analyse(frame, dataset=file.filename or "uploaded file")


@router.post("/insights", response_model=InsightResponse, summary="Explain an analysis")
def insights(request: InsightRequest, settings: SettingsDep) -> InsightResponse:
    """Ask the model to interpret findings that were already computed.

    Deliberately not called on page load: on a free tier of roughly twenty
    requests a day, a dashboard that explained itself automatically would spend
    the budget on visitors who never asked for an explanation.
    """
    return explain(request.analysis, settings=settings)
