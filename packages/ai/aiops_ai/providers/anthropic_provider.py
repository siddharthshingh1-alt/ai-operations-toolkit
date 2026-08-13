"""Anthropic (Claude) provider.

The default chat provider. Note two real limitations, handled explicitly rather
than faked: Anthropic offers no embeddings endpoint and no speech-to-text
endpoint, so `generate_embeddings()` and `transcribe()` raise a clear
configuration error pointing at the provider that does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

from aiops_ai.base import AIProvider
from aiops_ai.pricing import estimate_cost
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_config import Settings
from aiops_utils import (
    AIProviderError,
    AIProviderTimeout,
    ConfigurationError,
    Stopwatch,
)

_NO_EMBEDDINGS = (
    "Anthropic does not provide an embeddings endpoint. Set EMBEDDING_PROVIDER "
    "(default: openai) and supply that provider's API key."
)
_NO_TRANSCRIPTION = (
    "Anthropic does not provide a speech-to-text endpoint. Set "
    "TRANSCRIBE_PROVIDER (default: openai, which uses Whisper) and supply that "
    "provider's API key."
)


class AnthropicProvider(AIProvider):
    """Claude-backed implementation of the shared AI interface."""

    name = "anthropic"

    def __init__(self, settings: Settings, *, api_key: str | None = None) -> None:
        key = api_key or settings.anthropic_api_key
        if not key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set. Either set it, paste a key using "
                "'bring your own key', or leave DEMO_MODE=true."
            )
        self._settings = settings
        self._default_model = settings.anthropic_model
        self._client = anthropic.Anthropic(
            api_key=key,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )

    # ------------------------------------------------------------------ helpers

    def _call(
        self,
        prompt: str,
        *,
        system: str | None,
        model: str | None,
        max_tokens: int | None,
        output_config: dict[str, Any] | None = None,
    ) -> tuple[str, Usage, str, int]:
        """Issue one request and return (text, usage, model, duration_ms)."""
        chosen_model = model or self._default_model
        kwargs: dict[str, Any] = {
            "model": chosen_model,
            "max_tokens": max_tokens or self._settings.ai_max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if output_config:
            kwargs["output_config"] = output_config

        try:
            with Stopwatch() as sw:
                response = self._client.messages.create(**kwargs)
        except anthropic.APITimeoutError as exc:
            raise AIProviderTimeout(f"Anthropic timed out: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError(f"Anthropic returned {exc.status_code}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderError(f"Could not reach Anthropic: {exc}") from exc

        # A safety decline arrives as a normal 200 with an empty/partial body,
        # so it must be checked before reading content.
        if response.stop_reason == "refusal":
            raise AIProviderError(
                "Anthropic declined this request on safety grounds.",
                user_message=(
                    "The AI service declined to process this request. "
                    "Please rephrase it or review the input."
                ),
            )

        # Claude Opus 5 thinks by default; thinking blocks are not text blocks.
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise AIProviderError(
                f"Anthropic returned no text (stop_reason={response.stop_reason}). "
                "If stop_reason is 'max_tokens', raise AI_MAX_OUTPUT_TOKENS."
            )

        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            estimated_cost_usd=estimate_cost(
                chosen_model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            ),
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
        text, usage, used_model, duration = self._call(
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
        text, usage, used_model, duration = self._call(
            prompt,
            system=system,
            model=model,
            max_tokens=max_tokens,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIProviderError(f"Anthropic returned invalid JSON: {exc}") from exc

        return AIResult[dict[str, Any]](
            value=payload,
            provider=self.name,
            model=used_model,
            duration_ms=duration,
            usage=usage,
        )

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise ConfigurationError(_NO_EMBEDDINGS)

    def transcribe(self, audio_path: str | Path) -> AIResult[TranscriptResult]:
        raise ConfigurationError(_NO_TRANSCRIPTION)
