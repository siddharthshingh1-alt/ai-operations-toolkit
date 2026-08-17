"""Google Gemini provider.

Structured output: Gemini's `response_schema` does not accept the JSON Schema
dialect Pydantic emits — it rejects `additionalProperties` and does not resolve
`$ref`/`$defs`. `gemini_schema.to_gemini_schema` converts it, so decoding is
constrained by the schema itself rather than by a prompt instruction.

That distinction is load-bearing: asking for JSON in the prompt returned
unclosed objects intermittently, which surfaced as a confusing parse error.
The base class still validates against the Pydantic model afterwards, so a
non-conforming response remains a loud failure rather than a silent one.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from google import genai
from google.genai import types as genai_types

from aiops_ai.base import AIProvider
from aiops_ai.pricing import estimate_cost
from aiops_ai.types import AIResult, TranscriptResult, Usage
from aiops_config import Settings
from aiops_utils import (
    AIProviderError,
    AIQuotaExhausted,
    ConfigurationError,
    Stopwatch,
    ValidationError,
    get_logger,
)

logger = get_logger(__name__)

_T = TypeVar("_T")

#: Substrings identifying a spent quota or rate limit in a Gemini SDK error.
#:
#: Matched on the message rather than an exception type because the SDK reports
#: these as the same broad error family as everything else. `429` and
#: `resource_exhausted` are what the API actually returns; the rest are there
#: because the wording has changed before and a missed match downgrades a clear
#: message back into a generic one.
_QUOTA_MARKERS = (
    "429",
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
)

_NO_TRANSCRIPTION = (
    "Speech-to-text is routed to Whisper. Set TRANSCRIBE_PROVIDER=openai and supply OPENAI_API_KEY."
)


def _unit_normalise(vector: list[float]) -> list[float]:
    """Scale a vector to unit length.

    Gemini's embeddings are normalised at their native 3072 dimensions. Asking
    for fewer truncates the vector (a Matryoshka representation), which leaves
    it slightly off unit length — Google's guidance is to re-normalise. Cosine
    similarity is scale-invariant so this rarely changes ranking, but it keeps
    stored vectors consistent and makes an inner-product index valid.
    """
    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


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

    def _with_retries(self, call: Callable[[], _T], *, what: str) -> _T:
        """Run `call`, retrying transient network failures.

        The Gemini SDK retries HTTP-level errors but not a connection dropped
        mid-response — which on some networks is the most common failure of
        all (`WinError 10054`, "connection forcibly closed"). Long generations
        are the most exposed, so a single dropped socket would otherwise fail a
        request that would have succeeded on a second attempt.

        Only connection-shaped errors are retried. A 404 for a retired model or
        a malformed request fails immediately, because repeating it cannot help.
        """
        attempts = self._settings.ai_max_retries + 1
        last: Exception | None = None

        for attempt in range(attempts):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001 — SDK raises a broad family
                last = exc
                message = str(exc).lower()

                # A spent quota is a final state, not a transient failure.
                # Retrying cannot help, and the backoff would only make the
                # visitor wait 14 seconds to be told the same thing. It is also
                # not an error in the ordinary sense: the public demo runs live
                # AI on a free tier on purpose, so this is the documented end of
                # a day's budget.
                if any(marker in message for marker in _QUOTA_MARKERS):
                    logger.info(
                        "Gemini quota exhausted",
                        extra={"what": what, "error": str(exc)[:160]},
                    )
                    raise AIQuotaExhausted(f"Gemini {what} hit a quota limit: {exc}") from exc

                transient = any(
                    marker in message
                    for marker in (
                        "10054",  # Windows: connection forcibly closed
                        "connection reset",
                        "connection aborted",
                        "connection closed",
                        "broken pipe",
                        "timed out",
                        "timeout",
                        "503",
                        "502",
                        "504",
                        "unavailable",
                    )
                )
                if not transient or attempt == attempts - 1:
                    break

                delay = 2.0 * (2**attempt)  # 2s, 4s, 8s
                logger.warning(
                    "transient Gemini failure, retrying",
                    extra={
                        "what": what,
                        "attempt": attempt + 1,
                        "of": attempts,
                        "retry_in_seconds": delay,
                        "error": str(exc)[:120],
                    },
                )
                time.sleep(delay)

        raise AIProviderError(f"Gemini {what} failed: {last}") from last

    def _model_chain(self, model: str | None) -> list[str]:
        """The models to try, in order, for one logical request.

        The first entry is the model actually asked for. The rest are the
        configured fallbacks, minus any duplicate of the first, so a chain that
        happens to name the default twice does not spend two attempts on it.
        """
        first = model or self._default_model
        chain = [first]
        chain.extend(m for m in self._settings.gemini_fallback_models if m and m != first)
        return chain

    def _generate(
        self,
        prompt: str,
        *,
        system: str | None,
        model: str | None,
        max_tokens: int | None,
        json_mode: bool = False,
        response_schema: dict[str, Any] | None = None,
    ) -> tuple[str, Usage, str, int]:
        """Generate, moving down the model chain when a quota is spent.

        Only `AIQuotaExhausted` advances the chain. Every other failure is
        raised immediately: a malformed request or a safety refusal will fail
        identically on the next model, so retrying it would turn one clear
        error into three slow ones.

        If every model is spent, the *last* exhaustion is raised — by then the
        message is true of the whole chain, which is what the visitor needs to
        be told.
        """
        chain = self._model_chain(model)
        last_quota_error: AIQuotaExhausted | None = None

        for position, candidate in enumerate(chain):
            try:
                return self._generate_with(
                    prompt,
                    system=system,
                    model=candidate,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    response_schema=response_schema,
                )
            except AIQuotaExhausted as exc:
                last_quota_error = exc
                remaining = chain[position + 1 :]
                if not remaining:
                    break
                logger.info(
                    "Gemini model quota spent; trying the next model in the chain",
                    extra={
                        "spent_model": candidate,
                        "next_model": remaining[0],
                        "chain_position": position + 1,
                        "chain_length": len(chain),
                    },
                )

        if last_quota_error is not None:
            raise last_quota_error
        # Unreachable: the chain always holds at least the requested model, so
        # the loop either returns or records an exhaustion. Kept as a real
        # error rather than an assert, which `python -O` would strip.
        raise AIProviderError("Gemini generation produced no result and no error.")

    def _generate_with(
        self,
        prompt: str,
        *,
        system: str | None,
        model: str,
        max_tokens: int | None,
        json_mode: bool = False,
        response_schema: dict[str, Any] | None = None,
    ) -> tuple[str, Usage, str, int]:
        chosen_model = model
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens or self._settings.ai_max_output_tokens,
            response_mime_type="application/json" if json_mode else None,
            # Constrains decoding, so the response cannot come back as
            # malformed or unclosed JSON. Asking for JSON in the prompt alone
            # is a request the model mostly honours; this is a guarantee.
            response_schema=response_schema,
        )

        with Stopwatch() as sw:
            response = self._with_retries(
                lambda: self._client.models.generate_content(
                    model=chosen_model, contents=prompt, config=config
                ),
                what="generation",
            )

        meta = response.usage_metadata
        input_tokens = (meta.prompt_token_count or 0) if meta else 0
        output_tokens = (meta.candidates_token_count or 0) if meta else 0
        thinking_tokens = (meta.thoughts_token_count or 0) if meta else 0

        # Check *why* generation stopped before looking at the text. A response
        # cut off at the token ceiling still has text, but in JSON mode that
        # text is truncated mid-structure — which surfaces downstream as a
        # baffling "invalid JSON" error rather than the real cause.
        candidates = response.candidates or []
        finish_reason = str(candidates[0].finish_reason) if candidates else ""

        if "MAX_TOKENS" in finish_reason:
            budget = max_tokens or self._settings.ai_max_output_tokens
            spent = output_tokens + thinking_tokens
            raise AIProviderError(
                f"Gemini hit the output limit of {budget} tokens "
                f"(used {output_tokens} for the answer"
                + (f" plus {thinking_tokens} thinking" if thinking_tokens else "")
                + f" = {spent}). The response is truncated. "
                "Raise AI_MAX_OUTPUT_TOKENS or ask for a shorter output.",
                user_message=(
                    "The AI ran out of room before finishing. Try a shorter "
                    "description, or ask the operator to raise the output limit."
                ),
            )

        if "SAFETY" in finish_reason or "PROHIBITED" in finish_reason:
            raise AIProviderError(
                f"Gemini stopped for policy reasons (finish_reason={finish_reason}).",
                user_message=(
                    "The AI service declined to complete this request. "
                    "Please rephrase it or review the input."
                ),
            )

        text = (response.text or "").strip()
        if not text:
            raise AIProviderError(
                f"Gemini returned an empty response (finish_reason={finish_reason or 'unknown'})."
            )

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
        dimensions = self._settings.gemini_embedding_dimensions
        with Stopwatch() as sw:
            response = self._with_retries(
                lambda: self._client.models.embed_content(
                    model=model,
                    contents=texts,
                    # Ask for a vector pgvector can index (see the setting's note).
                    config=genai_types.EmbedContentConfig(output_dimensionality=dimensions),
                ),
                what="embeddings",
            )

        embeddings = response.embeddings or []
        vectors = [_unit_normalise(list(item.values or [])) for item in embeddings]
        if len(vectors) != len(texts):
            raise AIProviderError(
                f"Gemini returned {len(vectors)} embeddings for {len(texts)} inputs."
            )
        for vector in vectors:
            if len(vector) != dimensions:
                raise AIProviderError(
                    f"Gemini returned a {len(vector)}-dimension vector, expected "
                    f"{dimensions}. The database column would not accept it."
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
