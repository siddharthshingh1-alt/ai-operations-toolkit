"""Shared AI layer for the AI Operations Toolkit (CLAUDE.md Section 6).

    from aiops_ai import get_provider

    ai = get_provider()
    result = ai.classify(email_body, categories=["Booking Ops", "Vendor/Hotel"])
    print(result.value.category, result.usage.estimated_cost_usd)

No project should talk to an AI SDK directly.
"""

from aiops_ai.base import AIProvider, strict_json_schema
from aiops_ai.factory import (
    get_embedding_provider,
    get_provider,
    get_transcription_provider,
)
from aiops_ai.pricing import estimate_cost, known_models
from aiops_ai.providers.demo import DemoProvider, DemoRecordingMissing, RecordingProvider
from aiops_ai.types import (
    AIResult,
    AnalysisFinding,
    AnalysisResult,
    ClassificationResult,
    ExtractionResult,
    Priority,
    SummaryResult,
    TranscriptResult,
    Usage,
)

__all__ = [
    "AIProvider",
    "AIResult",
    "AnalysisFinding",
    "AnalysisResult",
    "ClassificationResult",
    "DemoProvider",
    "DemoRecordingMissing",
    "ExtractionResult",
    "Priority",
    "RecordingProvider",
    "SummaryResult",
    "TranscriptResult",
    "Usage",
    "estimate_cost",
    "get_embedding_provider",
    "get_provider",
    "get_transcription_provider",
    "known_models",
    "strict_json_schema",
]
