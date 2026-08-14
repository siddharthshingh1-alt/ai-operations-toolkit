"""OpenAI provider.

Doubles as the default embeddings and speech-to-text backend, because Anthropic
offers neither. See `EMBEDDING_PROVIDER` / `TRANSCRIBE_PROVIDER` in `.env.example`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openai

from aiops_ai.base import AIProvider
from aiops_ai.pricing import estimate_cost
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_config import Settings
from aiops_utils import (
    AIProviderError,
    AIProviderTimeout,
    ConfigurationError,
    Stopwatch,
    ValidationError,
    provider_http_error,
)


class OpenAIProvider(AIProvider):
    """OpenAI-backed implementation of the shared AI interface."""

    name = "openai"

    def __init__(self, settings: Settings, *, api_key: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise ConfigurationError(
                "OPENAI_API_KEY is not set. Either set it, paste a key using "
                "'bring your own key', or leave DEMO_MODE=true."
            )
        self._settings = settings
        self._default_model = settings.openai_model
        self._client = openai.OpenAI(
            api_key=key,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    # ------------------------------------------------------------------ helpers

    def _chat(
        self,
        prompt: str,
        *,
        system: str | None,
        model: str | None,
        max_tokens: int | None,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, Usage, str, int]:
        chosen_model = model or self._default_model
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "max_completion_tokens": max_tokens or self._settings.ai_max_output_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            with Stopwatch() as sw:
                response = self._client.chat.completions.create(**kwargs)
        except openai.APITimeoutError as exc:
            raise AIProviderTimeout(f"OpenAI timed out: {exc}") from exc
        except openai.APIStatusError as exc:
            raise provider_http_error(
                f"OpenAI returned {exc.status_code}: {exc}", status_code=exc.status_code
            ) from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError(f"Could not reach OpenAI: {exc}") from exc

        choice = response.choices[0]
        if choice.finish_reason == "content_filter":
            raise AIProviderError(
                "OpenAI's content filter blocked this request.",
                user_message=(
                    "The AI service declined to process this request. "
                    "Please rephrase it or review the input."
                ),
            )

        text = (choice.message.content or "").strip()
        if not text:
            raise AIProviderError(
                f"OpenAI returned no text (finish_reason={choice.finish_reason})."
            )

        api_usage = response.usage
        input_tokens = api_usage.prompt_tokens if api_usage else 0
        output_tokens = api_usage.completion_tokens if api_usage else 0
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
        text, usage, used_model, duration = self._chat(
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
        text, usage, used_model, duration = self._chat(
            prompt,
            system=system,
            model=model,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.get("title", "result"),
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"OpenAI returned invalid JSON: {exc}") from exc

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

        model = self._settings.openai_embedding_model
        try:
            with Stopwatch() as sw:
                response = self._client.embeddings.create(model=model, input=texts)
        except openai.APITimeoutError as exc:
            raise AIProviderTimeout(f"OpenAI embeddings timed out: {exc}") from exc
        except openai.APIStatusError as exc:
            raise provider_http_error(
                f"OpenAI embeddings returned {exc.status_code}: {exc}",
                status_code=exc.status_code,
            ) from exc

        # The API may return items out of order; `index` is authoritative.
        vectors = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        return AIResult[list[list[float]]](
            value=vectors,
            provider=self.name,
            model=model,
            duration_ms=sw.elapsed_ms,
            usage=Usage(
                input_tokens=input_tokens,
                estimated_cost_usd=estimate_cost(model, input_tokens, 0),
            ),
        )

    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        path = Path(audio_path)
        if not path.is_file():
            raise ValidationError(f"Audio file not found: {path}")

        model = self._settings.openai_transcribe_model
        try:
            with Stopwatch() as sw, path.open("rb") as handle:
                response = self._client.audio.transcriptions.create(model=model, file=handle)
        except openai.APITimeoutError as exc:
            raise AIProviderTimeout(f"OpenAI transcription timed out: {exc}") from exc
        except openai.APIStatusError as exc:
            raise provider_http_error(
                f"OpenAI transcription returned {exc.status_code}: {exc}",
                status_code=exc.status_code,
            ) from exc

        return AIResult[TranscriptResult](
            value=TranscriptResult(text=response.text),
            provider=self.name,
            model=model,
            duration_ms=sw.elapsed_ms,
            # Audio is billed per minute, not per token, so token-based costing
            # does not apply here.
            usage=Usage(),
        )
