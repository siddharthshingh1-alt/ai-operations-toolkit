"""Request, response and AI output shapes for the Ops Command Center."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ------------------------------------------------------------------ AI output


class BriefAction(BaseModel):
    """One recommended action, tied to a signal that actually exists."""

    action: str = Field(min_length=1, description="What to do, phrased as an instruction.")
    signal_id: str | None = Field(
        default=None,
        description=(
            "The id of the signal this addresses, exactly as supplied. "
            "Null if it concerns the whole picture rather than one item."
        ),
    )


class BriefNarrative(BaseModel):
    """The model's morning brief over signals it did not produce.

    Every figure the model writes about was collected from another project
    before it was called. It is interpreting a situation, not measuring one.
    """

    summary: str = Field(
        min_length=1,
        description=(
            "Three to five sentences an operations lead could read at 9am: what "
            "needs attention today and why. Plain prose, no bullet points, no "
            "greeting, no preamble."
        ),
    )
    actions: list[BriefAction] = Field(
        default_factory=list,
        description="Up to five recommended actions for today, most important first.",
    )


# ------------------------------------------------------------------ responses


class SignalView(BaseModel):
    """One signal, as the page renders it."""

    id: str
    source: str
    source_label: str
    severity: str
    title: str
    detail: str
    #: Where this came from. Section 17 requires every item to link back.
    link: str


class SourceView(BaseModel):
    """Whether one source answered."""

    source: str
    label: str
    available: bool
    detail: str
    signal_count: int
    link: str


class BriefView(BaseModel):
    """A stored narrative, and whether it still describes the current picture."""

    id: str
    summary: str
    actions: list[BriefAction]
    generated_at: datetime
    #: How many per-source counts have moved since generation. 0 means current.
    changed_since: int = 0
    unavailable_sources: list[str] = Field(default_factory=list)


class UsageInfo(BaseModel):
    """Cost metadata for an AI step (Section 3d)."""

    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False


class CommandCenterResponse(BaseModel):
    """Everything the Command Center page needs."""

    collected_at: datetime
    signals: list[SignalView]
    sources: list[SourceView]
    #: The most recent stored brief, if one exists.
    brief: BriefView | None = None
    #: Counts by severity, for the header. Computed, never generated.
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    #: What generating a brief costs, so the button can say so first.
    ai_requests_per_brief: int = 1
    #: The bundled dataset the dashboard signals came from, named so nobody
    #: mistakes it for live production data.
    dashboard_dataset: str = ""


class GenerateBriefResponse(BaseModel):
    brief: BriefView
    usage: UsageInfo
