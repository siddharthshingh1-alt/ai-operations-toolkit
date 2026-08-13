"""The shape of an SOP.

Every field in `SopContent` comes from CLAUDE.md Section 9's required AI output
list. This model is what the AI is asked to fill in, what the editor renders,
what gets versioned, and what gets exported — one definition, so those four
things cannot drift apart.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SopStatus(StrEnum):
    """Lifecycle of an SOP (CLAUDE.md Section 9: status field)."""

    DRAFT = "draft"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


class ProcedureStep(BaseModel):
    """One numbered step of the procedure."""

    number: int = Field(ge=1)
    instruction: str
    #: Who performs this step. Blank means "the SOP's primary role".
    responsible: str = ""
    #: How the operator knows the step worked.
    expected_result: str = ""


class DecisionPoint(BaseModel):
    """A branch in the procedure — "if X then Y, otherwise Z"."""

    at_step: int | None = None
    question: str
    if_yes: str
    if_no: str


class Exception_(BaseModel):
    """Something that can go wrong, and what to do about it.

    Named with a trailing underscore because `Exception` is a Python builtin.
    """

    situation: str
    action: str


class EscalationRule(BaseModel):
    """When to hand a problem upward."""

    trigger: str
    escalate_to: str
    within: str = ""  # e.g. "30 minutes", "same working day"


class Kpi(BaseModel):
    """How the process is measured."""

    name: str
    target: str = ""
    how_measured: str = ""


class Risk(BaseModel):
    """A risk in the process, with its mitigation."""

    description: str
    severity: str = "medium"  # low | medium | high
    mitigation: str = ""


class SopContent(BaseModel):
    """The body of an SOP — everything Section 9 requires the AI to produce."""

    title: str
    purpose: str
    scope: str
    prerequisites: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    procedure: list[ProcedureStep] = Field(default_factory=list)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    exceptions: list[Exception_] = Field(default_factory=list)
    escalation_rules: list[EscalationRule] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    kpis: list[Kpi] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)

    @field_validator("procedure")
    @classmethod
    def _renumber_steps(cls, steps: list[ProcedureStep]) -> list[ProcedureStep]:
        """Force steps to be numbered 1..n in order.

        Models occasionally skip or repeat a number. Renumbering here means the
        rest of the app — editor, export, diff — can trust the sequence.
        """
        for index, step in enumerate(steps, start=1):
            step.number = index
        return steps

    def to_search_text(self) -> str:
        """Flatten the SOP into the text that gets embedded for search.

        Deliberately includes the parts an operator would actually search for
        (title, purpose, scope, steps, exceptions) and omits meta-commentary
        such as improvement suggestions, which would add noise.
        """
        parts = [self.title, self.purpose, self.scope]
        parts += self.prerequisites
        parts += [
            f"{s.number}. {s.instruction} {s.expected_result}".strip() for s in self.procedure
        ]
        parts += [f"{d.question} {d.if_yes} {d.if_no}" for d in self.decision_points]
        parts += [f"{e.situation} {e.action}" for e in self.exceptions]
        parts += [f"{e.trigger} escalate to {e.escalate_to}" for e in self.escalation_rules]
        parts += self.checklist
        return "\n".join(part for part in parts if part and part.strip())


class SopMetadata(BaseModel):
    """The governance fields Section 9 requires alongside the content."""

    owner: str = ""
    department: str = ""
    status: SopStatus = SopStatus.DRAFT
    effective_date: date | None = None
    review_date: date | None = None


class GenerateSopRequest(BaseModel):
    """What the user submits to have an SOP written."""

    process_description: str = Field(min_length=20, max_length=20_000)
    role: str = ""
    department: str = ""
    objective: str = ""
    #: Text of an existing SOP to standardise and improve, if any.
    existing_sop: str | None = Field(default=None, max_length=50_000)
    #: Text extracted from an uploaded document, if any.
    document_text: str | None = Field(default=None, max_length=100_000)

    @field_validator("process_description")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Describe the process — an empty description cannot be used.")
        return value.strip()


class SaveSopRequest(BaseModel):
    """Saving reviewed content, either as a new SOP or a new version."""

    content: SopContent
    metadata: SopMetadata = Field(default_factory=SopMetadata)
    #: Short note describing what changed. Shown in the version history.
    change_note: str = ""


class AskRequest(BaseModel):
    """A question to answer from the SOP library."""

    question: str = Field(min_length=3, max_length=1_000)
    #: How many SOPs to consider as supporting evidence.
    top_k: int = Field(default=4, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Ask a question — an empty question cannot be answered.")
        return value.strip()


class Citation(BaseModel):
    """Which SOP supported an answer, and how strongly it matched."""

    sop_id: str
    title: str
    version: int
    similarity: float = Field(ge=0.0, le=1.0)


class AnswerResult(BaseModel):
    """The AI's answer, with its sources.

    `answered` is False when nothing in the library was relevant. Section 9 is
    explicit: say so rather than hallucinating.
    """

    answered: bool
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    reasoning_summary: str = ""
