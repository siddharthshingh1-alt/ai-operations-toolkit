"""HTTP routes for the Report Generator.

Mounted by `apps/api` under `/api/reports`.

Four routes, and only one of them costs anything. Computing a report is free
and happens on selection; the narrative is a separate POST behind a button; the
export is a third call that spends nothing and renders exactly what it is
given.
"""

from __future__ import annotations

from typing import Annotated, Literal

from aiops_dashboard.samples import available_samples, load_sample
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from aiops_config import Settings, get_settings
from aiops_docproc import (
    MAX_UPLOAD_BYTES,
    Document,
    DocumentSection,
    ExportFormat,
    get_exporter,
    read_table,
)
from aiops_report import service
from aiops_report.periods import Period
from aiops_report.schema import (
    ExportReportRequest,
    GenerateReportRequest,
    ReportFacts,
    ReportFactsResponse,
    ReportNarrative,
    ReportNarrativeResponse,
    SampleOption,
)
from aiops_utils import ValidationError

router = APIRouter(prefix="/api/reports", tags=["report-generator"])

SettingsDep = Annotated[Settings, Depends(get_settings)]

PeriodQuery = Annotated[Period, Query(description="daily, weekly or monthly")]


@router.get("/samples", response_model=list[SampleOption], summary="Datasets to report on")
def samples() -> list[SampleOption]:
    """The same bundled datasets the Operations Dashboard offers."""
    return [
        SampleOption(key=s.key, name=s.name, description=s.description) for s in available_samples()
    ]


@router.get(
    "/samples/{key}",
    response_model=ReportFactsResponse,
    summary="Compute a report from a bundled dataset (no AI)",
)
def report_from_sample(key: str, period: PeriodQuery = Period.WEEKLY) -> ReportFactsResponse:
    """Every figure in the report. Costs nothing — no model is called."""
    frame = load_sample(key)
    label = next((s.name for s in available_samples() if s.key == key), key)
    facts, analysis = service.build_facts(frame, dataset=key, dataset_label=label, period=period)
    return ReportFactsResponse(facts=facts, analysis=analysis)


@router.post(
    "/analyse",
    response_model=ReportFactsResponse,
    summary="Compute a report from an uploaded file (no AI)",
)
async def report_from_upload(
    file: Annotated[UploadFile, File()], period: PeriodQuery = Period.WEEKLY
) -> ReportFactsResponse:
    """Upload a CSV or Excel file and get the computed report.

    Reading the file reuses `aiops_docproc.read_table`, the same path the
    Operations Dashboard's upload takes — including its size and type limits.
    """
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Upload of {len(data)} bytes exceeds the limit.",
            user_message=(
                f"That file is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
            ),
        )

    name = file.filename or "upload"
    frame = read_table(data, name)
    facts, analysis = service.build_facts(frame, dataset=name, dataset_label=name, period=period)
    return ReportFactsResponse(facts=facts, analysis=analysis)


@router.post(
    "/narrative",
    response_model=ReportNarrativeResponse,
    summary="Write the report narrative (1 AI request)",
)
def narrative(request: GenerateReportRequest, settings: SettingsDep) -> ReportNarrativeResponse:
    """Executive summary, recommendations and action items.

    Takes the computed facts in the request body rather than recomputing them:
    the prose must describe the table already on the reader's screen, and for
    an uploaded file there is nothing stored to recompute from.
    """
    written, usage = service.narrate(request.facts, settings=settings)
    return ReportNarrativeResponse(narrative=written, usage=usage)


@router.post("/export", summary="Download a report")
def export(
    request: ExportReportRequest,
    fmt: Annotated[Literal["markdown", "html", "pdf"], Query(alias="format")] = "pdf",
) -> Response:
    """Render a report through the shared exporter.

    Spends no AI request. The narrative is optional — a report of computed
    figures with no prose is a legitimate thing to export, and is what you get
    if you never press the button.
    """
    exporter = get_exporter(ExportFormat(fmt))
    document = _as_document(request.facts, request.narrative)
    body = exporter.render(document)

    stem = f"{request.facts.period.value}-report-{request.facts.dataset}"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in stem).strip("-")
    filename = f"{safe or 'report'}.{exporter.extension}"
    return Response(
        content=body,
        media_type=exporter.media_type,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def _as_document(facts: ReportFacts, narrative: ReportNarrative | None) -> Document:
    """Turn a report into the shared export shape.

    Section order follows Section 15: executive summary, KPI table, trends,
    anomalies, recommendations, action items.
    """
    sections: list[DocumentSection] = []

    if narrative is not None:
        sections.append(
            DocumentSection(heading="Executive summary", body=narrative.executive_summary)
        )
    else:
        sections.append(
            DocumentSection(
                heading="Executive summary",
                body=(
                    "No narrative was generated for this report. Every figure below "
                    "was computed from the data."
                ),
            )
        )

    kpi_lines = []
    for kpi in facts.kpis:
        value = f"{kpi.current:,.2f}{kpi.unit}"
        if kpi.change_pct is None:
            kpi_lines.append(f"{kpi.label}: {value} (no comparable previous period)")
        else:
            kpi_lines.append(
                f"{kpi.label}: {value} — {kpi.change_pct:+.1f}% vs "
                f"{kpi.previous:,.2f}{kpi.unit} previously"
            )
    sections.append(
        DocumentSection(
            heading="Key metrics",
            body="" if kpi_lines else "No numeric metrics were computable for this period.",
            bullets=kpi_lines,
        )
    )

    trends = [f.statement for f in facts.findings if f.kind == "trend"]
    anomalies = [f.statement for f in facts.findings if f.kind == "anomaly"]
    sections.append(
        DocumentSection(
            heading="Trends",
            body="" if trends else "No trends were detected in this period.",
            bullets=trends,
        )
    )
    sections.append(
        DocumentSection(
            heading="Anomalies",
            body="" if anomalies else "No anomalies were detected in this period.",
            bullets=anomalies,
        )
    )

    if narrative is not None:
        sections.append(
            DocumentSection(heading="Recommendations", bullets=narrative.recommendations)
        )
        sections.append(
            DocumentSection(
                heading="Action items",
                bullets=[
                    f"{item.action}"
                    + (f" — {item.owner_hint}" if item.owner_hint else "")
                    + (f" [{item.metric}]" if item.metric else "")
                    for item in narrative.action_items
                ],
            )
        )

    return Document(
        title=f"{facts.period_label} operations report",
        subtitle=facts.dataset_label,
        metadata={
            "Period": facts.current.description,
            "Compared with": facts.previous.description if not facts.whole_dataset else "—",
            "Rows analysed": str(facts.row_count),
            "Generated": facts.generated_at.date().isoformat(),
            "Data": "Synthetic",
        },
        sections=sections,
        footer=(
            "Figures computed from the dataset by the analytics service. "
            "Narrative written by an AI model from those figures. "
            "All data is synthetic."
        ),
    )
