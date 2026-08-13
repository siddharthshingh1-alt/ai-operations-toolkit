"""The shared AI service interface (CLAUDE.md Section 6).

Every provider implements four primitives:

    _complete_text()        free-form text
    _complete_json()        JSON matching a schema
    generate_embeddings()   vectors, for pgvector semantic search
    transcribe()            speech-to-text

The higher-level verbs the projects actually call — summarize, classify,
extract, analyze — are implemented once, here, on top of `_complete_json`.
That is why "no project should write its own AI API integration from scratch"
holds: adding a provider means implementing four methods, not eight, and every
project gets the same structured shapes and the same cost accounting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aiops_ai.types import (
    AIResult,
    AnalysisResult,
    ClassificationResult,
    ExtractionResult,
    SummaryResult,
    TranscriptResult,
)
from aiops_utils import AIProviderError

# --------------------------------------------------------------------------
# Prompt templates for the derived verbs.
#
# Kept together so the wording of a shared capability is reviewed in one place
# rather than drifting across nine projects.
# --------------------------------------------------------------------------

_SUMMARIZE_SYSTEM = (
    "You are an operations analyst. Summarise the material faithfully. "
    "Include only what the source supports; never add facts of your own."
)

_CLASSIFY_SYSTEM = (
    "You are an operations triage assistant for a B2B travel company whose "
    "customers are travel agents. Classify the item into exactly one of the "
    "allowed categories. Give a one- or two-sentence reasoning summary a "
    "colleague could check, and a concrete recommended action. Set confidence "
    "honestly: below 0.5 when the item is genuinely ambiguous."
)

_EXTRACT_SYSTEM = (
    "You extract structured fields from operational documents. Copy values "
    "exactly as they appear. If a requested field is absent, list it under "
    "missing_fields instead of inventing a value."
)

_ANALYSE_SYSTEM = (
    "You analyse operational data. Keep fact and speculation strictly apart.\n"
    "- observed: only what the data literally shows, with the numbers.\n"
    "- hypothesis: a possible contributor, clearly framed as a possibility.\n"
    "- recommendation: the next investigative step.\n"
    "Never state a cause as established. Never invent figures that are not in "
    "the data."
)


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic model into a schema the structured-output APIs accept.

    Providers require every object to set `additionalProperties: false` and to
    list all its properties as required. Pydantic emits neither, so this walks
    the generated schema and adds them.
    """
    schema = model.model_json_schema()

    def tighten(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                tighten(value)
        elif isinstance(node, list):
            for item in node:
                tighten(item)

    tighten(schema)
    return schema


class AIProvider(ABC):
    """Base class for every AI provider.

    Subclasses implement the four primitives; the derived verbs come free.
    """

    #: Short provider name, e.g. "anthropic". Used in logs and the UI badge.
    name: str = "base"

    # ---------------------------------------------------------------- primitives

    @abstractmethod
    def _complete_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[str]:
        """Return free-form text for `prompt`."""

    @abstractmethod
    def _complete_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[dict[str, Any]]:
        """Return a JSON object conforming to `schema`."""

    @abstractmethod
    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        """Return one embedding vector per input string."""

    @abstractmethod
    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        """Transcribe an audio file to text."""

    # ------------------------------------------------------------ public surface

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[str]:
        """Free-form text generation."""
        return self._complete_text(prompt, system=system, model=model, max_tokens=max_tokens)

    def generate_structured_output[TModel: BaseModel](
        self,
        prompt: str,
        *,
        output_model: type[TModel],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[TModel]:
        """Generate output validated against a Pydantic model.

        Raises `AIProviderError` if the provider returns JSON that does not
        satisfy the model — a real failure, surfaced rather than papered over.
        """
        raw = self._complete_json(
            prompt,
            schema=strict_json_schema(output_model),
            system=system,
            model=model,
            max_tokens=max_tokens,
        )
        try:
            parsed = output_model.model_validate(raw.value)
        except Exception as exc:  # noqa: BLE001 — re-raised as a typed error below
            raise AIProviderError(
                f"{self.name} returned JSON that does not match {output_model.__name__}: {exc}"
            ) from exc

        return AIResult[TModel](
            value=parsed,
            provider=raw.provider,
            model=raw.model,
            duration_ms=raw.duration_ms,
            usage=raw.usage,
            from_demo_cache=raw.from_demo_cache,
        )

    def summarize(
        self, text: str, *, focus: str | None = None, model: str | None = None
    ) -> AIResult[SummaryResult]:
        """Summarise text, optionally biased toward a particular `focus`."""
        instruction = f"\n\nFocus especially on: {focus}" if focus else ""
        return self.generate_structured_output(
            f"Summarise the following.{instruction}\n\n---\n{text}",
            output_model=SummaryResult,
            system=_SUMMARIZE_SYSTEM,
            model=model,
        )

    def classify(
        self, text: str, *, categories: list[str], model: str | None = None
    ) -> AIResult[ClassificationResult]:
        """Classify text into one of `categories`, with reasoning and confidence."""
        allowed = ", ".join(categories)
        return self.generate_structured_output(
            f"Allowed categories: {allowed}\n\nClassify this item:\n\n---\n{text}",
            output_model=ClassificationResult,
            system=_CLASSIFY_SYSTEM,
            model=model,
        )

    def extract(
        self, text: str, *, fields: list[str], model: str | None = None
    ) -> AIResult[ExtractionResult]:
        """Extract named fields from text, reporting any that are absent."""
        wanted = ", ".join(fields)
        return self.generate_structured_output(
            f"Extract these fields: {wanted}\n\n---\n{text}",
            output_model=ExtractionResult,
            system=_EXTRACT_SYSTEM,
            model=model,
        )

    def analyze(
        self, data_description: str, *, question: str, model: str | None = None
    ) -> AIResult[AnalysisResult]:
        """Analyse data, separating observation from hypothesis."""
        return self.generate_structured_output(
            f"Question: {question}\n\nData:\n---\n{data_description}",
            output_model=AnalysisResult,
            system=_ANALYSE_SYSTEM,
            model=model,
        )
