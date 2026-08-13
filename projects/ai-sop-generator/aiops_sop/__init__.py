"""Project 1 — AI SOP Generator (CLAUDE.md Section 9).

Turns messy operational knowledge into standardised, versioned, searchable SOPs.
Includes the folded-in Knowledge Base capability: semantic search over the SOP
library with citations, and an explicit "no relevant SOP" answer rather than a
hallucinated one.
"""

from aiops_sop.diffing import ChangeKind, FieldDiff, SopDiff, diff_sop_content
from aiops_sop.models import EMBEDDING_DIMENSIONS, Sop, SopVersion
from aiops_sop.schema import (
    AnswerResult,
    AskRequest,
    Citation,
    GenerateSopRequest,
    SaveSopRequest,
    SopContent,
    SopMetadata,
    SopStatus,
)
from aiops_sop.search import SIMILARITY_FLOOR, answer_question, search_sops

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "SIMILARITY_FLOOR",
    "AnswerResult",
    "AskRequest",
    "ChangeKind",
    "Citation",
    "FieldDiff",
    "GenerateSopRequest",
    "SaveSopRequest",
    "Sop",
    "SopContent",
    "SopDiff",
    "SopMetadata",
    "SopStatus",
    "SopVersion",
    "answer_question",
    "diff_sop_content",
    "search_sops",
]
