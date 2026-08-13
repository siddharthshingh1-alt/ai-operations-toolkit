"""Google Gemini provider.

Structured output note: Gemini's `response_schema` does not accept the same
JSON Schema dialect the other two providers use (it rejects
`additionalProperties` and does not resolve `$ref`/`$defs`). Rather than ship a
lossy schema translator, this provider asks for `application/json` and states
the required schema in the system instruction. The base class still validates
the result against the Pydantic model, so a non-conforming response is a loud
failure, not a silent one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types

from aiops_ai.base import AIProvider
from aiops_ai.pricing import estimate_cost
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_config import Settings
from aiops_utils import (
    AIProviderError,
    ConfigurationError,
    Stopwatch,
    ValidationError,
)

_NO_TRANSCRIPTION = (
    "Speech-to-text is routed to Whisper. Set TRANSCRIBE_PROVIDER=openai and supply OPENAI_API_KEY."
)


class GeminiProvider(AIProvider):
    """Gemini-backed implementation of the shared AI interface."""

    name = "gemini"

    def __init__(self, settings: Settings, *, api_key: str | None = None) -> None:
        key = api_key or settings.google_api_key
        if not key:
            raise ConfigurationError(
                "GOOGLE_API_KEY is not set. Either set it, paste a key using "
                "'bring your own key', or leave DEMO_MODE=true."
            )
        self._settings = settings
        self._default_model = settings.gemini_model
        self._client = genai.Client(
            api_key=key,
            http_options=genai_types.HttpOptions(
                timeout=int(settings.ai_timeout_seconds * 1000)  # milliseconds
            ),
        )

    # ------------------------------------------------------------------ helpers

    def _generate(
        self,
        prompt: str,
        *,
        system: str | None,
        model: str | None,
        max_tokens: int | None,
        json_mode: bool = False,
    ) -> tuple[str, Usage, str, int]:
        chosen_model = model or self._default_model
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens or self._settings.ai_max_output_tokens,
            response_mime_type="application/json" if json_mode else None,
        )

        try:
            with Stopwatch() as sw:
                response = self._client.models.generate_content(
                    model=chosen_model, contents=prompt, config=config
                )
        except Exception as exc:  # noqa: BLE001 — SDK raises a broad error family
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

        text = (response.text or "").strip()
        if not text:
            raise AIProviderError("Gemini returned an empty response.")

        meta = response.usage_metadata
        input_tokens = (meta.prompt_token_count or 0) if meta else 0
        output_tokens = (meta.candidates_token_count or 0) if meta else 0
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost(chosen_model, input_tokens, output_tokens),
        )
        return text, usage, chosen_model, sw.elapsed_ms

    # --------------------------------------------------------------- primitives

    def _complete_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[str]:
        text, usage, used_model, duration = self._generate(
            prompt, system=system, model=model, max_tokens=max_tokens
        )
        return AIResult[str](
            value=text,
            provider=self.name,
            model=used_model,
            duration_ms=duration,
            usage=usage,
        )

    def _complete_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResult[dict[str, Any]]:
        schema_instruction = (
            "Reply with a single JSON object and nothing else. It must satisfy "
            f"this JSON Schema exactly:\n{json.dumps(schema, indent=2)}"
        )
        combined_system = f"{system}\n\n{schema_instruction}" if system else schema_instruction

        text, usage, used_model, duration = self._generate(
            prompt,
            system=combined_system,
            model=model,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"Gemini returned invalid JSON: {exc}") from exc

        return AIResult[dict[str, Any]](
            value=payload,
            provider=self.name,
            model=used_model,
            duration_ms=duration,
            usage=usage,
        )

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        if not texts:
            raise ValidationError("generate_embeddings() needs at least one string.")

        model = self._settings.gemini_embedding_model
        try:
            with Stopwatch() as sw:
                response = self._client.models.embed_content(model=model, contents=texts)
        except Exception as exc:  # noqa: BLE001 — SDK raises a broad error family
            raise AIProviderError(f"Gemini embeddings failed: {exc}") from exc

        embeddings = response.embeddings or []
        vectors = [list(item.values or []) for item in embeddings]
        if len(vectors) != len(texts):
            raise AIProviderError(
                f"Gemini returned {len(vectors)} embeddings for {len(texts)} inputs."
            )

        return AIResult[list[list[float]]](
            value=vectors,
            provider=self.name,
            model=model,
            duration_ms=sw.elapsed_ms,
            usage=Usage(),
        )

    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        raise ConfigurationError(_NO_TRANSCRIPTION)
