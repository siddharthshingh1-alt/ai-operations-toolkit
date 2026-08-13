"""Shared types for the AI layer.

Every AI call returns an `AIResult`, which carries the value *and* the metadata
the Activity Log needs (CLAUDE.md Sections 22 and 3d): model, provider, duration,
tokens, and estimated cost.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Token counts and estimated spend for a single AI call."""

    input_tokens: int = 0
    output_tokens: int = 0
    #: None when the model has no price entry — never guess a cost.
    estimated_cost_usd: float | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AIResult[T](BaseModel):
    """The value returned by an AI call, plus everything worth auditing."""

    value: T
    provider: str
    model: str
    duration_ms: int
    usage: Usage = Field(default_factory=Usage)
    #: True when this result was replayed from a recording rather than
    #: generated live. Surfaced in the UI so the two are never confused.
    from_demo_cache: bool = False

    def log_fields(self) -> dict[str, object]:
        """Metadata for the activity log. Deliberately excludes the value itself.

        CLAUDE.md Section 22: "Do not log sensitive content unnecessarily."
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "duration_ms": self.duration_ms,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "estimated_cost_usd": self.usage.estimated_cost_usd,
            "from_demo_cache": self.from_demo_cache,
        }


class Priority(StrEnum):
    """Shared urgency scale used by classification across every project."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ClassificationResult(BaseModel):
    """Standard classification shape from CLAUDE.md Section 6.

    `reasoning_summary` is a short, human-readable justification — not hidden
    chain-of-thought (Section 5, Explainability).
    """

    category: str
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    recommended_action: str


class SummaryResult(BaseModel):
    """Output of `summarize()`."""

    summary: str
    key_points: list[str] = Field(default_factory=list)


class AnalysisFinding(BaseModel):
    """One finding, with fact and speculation kept strictly separate.

    CLAUDE.md Section 11 mandates this exact shape:
    "Never present speculation as fact. Never fabricate causes."
    """

    observed: str
    hypothesis: str | None = None
    recommendation: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    """Output of `analyze()`."""

    findings: list[AnalysisFinding] = Field(default_factory=list)
    summary: str = ""


class ExtractionResult(BaseModel):
    """Output of `extract()` — arbitrary fields plus a note on what was missing."""

    fields: dict[str, object] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class TranscriptResult(BaseModel):
    """Output of `transcribe()`."""

    text: str
    language: str | None = None
    duration_seconds: float | None = None
