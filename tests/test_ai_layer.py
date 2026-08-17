"""Tests for the shared AI layer.

The important case here is the one Section 2 cares about: Demo Mode must
*refuse* to answer when it has no recording, rather than inventing something.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from aiops_ai import (
    AIResult,
    DemoProvider,
    DemoRecordingMissing,
    Usage,
    estimate_cost,
    get_provider,
    strict_json_schema,
)
from aiops_ai.base import AIProvider
from aiops_ai.providers.demo import RecordingProvider, cache_key
from aiops_ai.types import TranscriptResult
from aiops_config import Settings
from aiops_utils import AIProviderError, AIQuotaExhausted, provider_http_error

# ------------------------------------------------------------------ pricing


def test_cost_is_estimated_for_a_known_model() -> None:
    # 1M input at $5 + 1M output at $25 = $30.
    assert estimate_cost("claude-opus-5", 1_000_000, 1_000_000) == 30.0


def test_cost_is_none_for_an_unknown_model() -> None:
    """A missing price must produce None, never a guessed number."""
    assert estimate_cost("some-model-we-have-not-priced", 1000, 1000) is None


def test_small_calls_keep_sub_cent_precision() -> None:
    cost = estimate_cost("claude-haiku-4-5", 500, 200)
    assert cost is not None and 0 < cost < 0.01


# ------------------------------------------------------------------- schema


class _Example(BaseModel):
    name: str
    count: int


def test_strict_schema_tightens_objects() -> None:
    """Providers reject schemas that allow unlisted properties."""
    schema = strict_json_schema(_Example)
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["count", "name"]


# ---------------------------------------------------------------- demo mode


def test_demo_mode_refuses_when_no_recording_exists(temp_cache_dir: Path) -> None:
    """The central guarantee: Demo Mode never fabricates an answer."""
    provider = DemoProvider(cache_dir=temp_cache_dir)
    with pytest.raises(DemoRecordingMissing) as excinfo:
        provider.generate_text("Anything at all")

    # The error must tell the user how to fix it.
    assert "record" in str(excinfo.value.detail).lower()


def test_demo_mode_replays_a_recording(temp_cache_dir: Path) -> None:
    """A recorded output is replayed verbatim and flagged as cached."""
    prompt, system = "Summarise the delay", None
    key = cache_key("complete_text", prompt, system)
    (temp_cache_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "key": key,
                "operation": "complete_text",
                "recorded_provider": "anthropic",
                "recorded_model": "claude-opus-5",
                "duration_ms": 1234,
                "usage": {"input_tokens": 50, "output_tokens": 20, "estimated_cost_usd": 0.00075},
                "value": "Three bookings are affected.",
            }
        ),
        encoding="utf-8",
    )

    result = DemoProvider(cache_dir=temp_cache_dir).generate_text(prompt)
    assert result.value == "Three bookings are affected."
    assert result.from_demo_cache is True
    # The recording reports the model that really produced it.
    assert result.model == "claude-opus-5"
    assert result.usage.estimated_cost_usd == 0.00075


def test_recording_round_trips(temp_cache_dir: Path) -> None:
    """What RecordingProvider writes, DemoProvider can read back."""

    class _Stub(AIProvider):
        name = "stub"

        def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
            return AIResult[str](
                value="recorded answer",
                provider="stub",
                model="stub-model",
                duration_ms=7,
                usage=Usage(input_tokens=3, output_tokens=2),
            )

        def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
            raise NotImplementedError

        def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
            raise NotImplementedError

        def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
            raise NotImplementedError

    recorder = RecordingProvider(_Stub(), cache_dir=temp_cache_dir)
    recorder.generate_text("a question")

    replayed = DemoProvider(cache_dir=temp_cache_dir).generate_text("a question")
    assert replayed.value == "recorded answer"
    assert replayed.from_demo_cache is True


class _CountingStub(AIProvider):
    """Counts how many times the live provider was actually asked."""

    name = "counting-stub"

    def __init__(self) -> None:
        self.calls = 0

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        self.calls += 1
        return AIResult[str](
            value=f"answer {self.calls}",
            provider="stub",
            model="stub-model",
            duration_ms=1,
            usage=Usage(input_tokens=1, output_tokens=1),
        )

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        raise NotImplementedError

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


def test_recording_reuses_an_existing_recording(temp_cache_dir: Path) -> None:
    """Re-running the recorder must not re-spend quota on unchanged prompts.

    The free tiers this targets allow 20 requests a day, and the script is
    re-run whenever one example is added.
    """
    inner = _CountingStub()
    recorder = RecordingProvider(inner, cache_dir=temp_cache_dir)

    first = recorder.generate_text("a question")
    second = recorder.generate_text("a question")

    assert inner.calls == 1, "the second call should have been served from disk"
    assert second.value == first.value
    assert second.from_demo_cache is True
    assert recorder.reused == 1

    # A prompt with no recording still reaches the live provider.
    recorder.generate_text("a different question")
    assert inner.calls == 2


def test_recording_can_be_forced_to_refresh(temp_cache_dir: Path) -> None:
    """A changed prompt template needs its recordings genuinely re-made."""
    inner = _CountingStub()
    RecordingProvider(inner, cache_dir=temp_cache_dir).generate_text("a question")

    forced = RecordingProvider(inner, cache_dir=temp_cache_dir, reuse_existing=False)
    forced.generate_text("a question")

    assert inner.calls == 2
    assert forced.reused == 0


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED. You exceeded your current quota.",
        "Quota exceeded for quota metric 'Generate requests'",
        "rate limit reached for model",
        "Too Many Requests",
    ],
)
def test_gemini_quota_errors_are_named_as_such(monkeypatch: Any, message: str) -> None:
    """A spent quota must not be reported as a generic provider failure.

    The public demo runs live on a free tier, so this is the expected end of a
    day's budget rather than a fault, and a visitor needs to be told that
    waiting until tomorrow is what fixes it.
    """
    from aiops_ai.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = SimpleNamespace(ai_max_retries=2)  # type: ignore[assignment]

    def _boom() -> None:
        raise RuntimeError(message)

    with pytest.raises(AIQuotaExhausted) as caught:
        provider._with_retries(_boom, what="generation")

    assert caught.value.status_code == 429
    assert caught.value.code == "ai_quota_exhausted"
    assert "free AI tier" in caught.value.user_message
    assert "tomorrow" in caught.value.user_message


def test_gemini_quota_error_is_not_retried(monkeypatch: Any) -> None:
    """Retrying a spent quota only makes the visitor wait to hear the same thing."""
    from aiops_ai.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = SimpleNamespace(ai_max_retries=3)  # type: ignore[assignment]

    calls = 0

    def _boom() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    with pytest.raises(AIQuotaExhausted):
        provider._with_retries(_boom, what="generation")

    assert calls == 1


def test_a_transient_failure_is_still_retried(monkeypatch: Any) -> None:
    """The quota check must not have swallowed the retry behaviour around it."""
    from aiops_ai.providers.gemini_provider import GeminiProvider

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = SimpleNamespace(ai_max_retries=2)  # type: ignore[assignment]

    calls = 0

    def _flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("connection reset by peer")
        return "recovered"

    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    assert provider._with_retries(_flaky, what="generation") == "recovered"
    assert calls == 2


def test_a_429_from_other_providers_is_a_quota_error() -> None:
    """Every provider treats a spent quota the same way."""
    assert isinstance(provider_http_error("spent", status_code=429), AIQuotaExhausted)
    quota = provider_http_error("spent", status_code=429)
    assert quota.code == "ai_quota_exhausted"

    other = provider_http_error("broken", status_code=500)
    assert isinstance(other, AIProviderError)
    assert not isinstance(other, AIQuotaExhausted)


def test_cache_key_ignores_model_but_not_prompt() -> None:
    """Recordings survive a model change; a different prompt is a different key."""
    assert cache_key("op", "prompt", None) == cache_key("op", "prompt", None)
    assert cache_key("op", "prompt a", None) != cache_key("op", "prompt b", None)
    assert cache_key("op", "prompt", "system a") != cache_key("op", "prompt", "system b")


def test_demo_recording_count(temp_cache_dir: Path) -> None:
    provider = DemoProvider(cache_dir=temp_cache_dir)
    assert provider.available_recordings() == 0
    (temp_cache_dir / "abc.json").write_text("{}", encoding="utf-8")
    assert provider.available_recordings() == 1


# ------------------------------------------------------------------ factory


def test_factory_returns_demo_provider_in_demo_mode(demo_settings: Settings) -> None:
    assert isinstance(get_provider(demo_settings), DemoProvider)


def test_bring_your_own_key_overrides_demo_mode(demo_settings: Settings) -> None:
    """A reviewer pasting a key gets the live provider, not a replay."""
    provider = get_provider(demo_settings, api_key="sk-ant-test-not-a-real-key")
    assert provider.name == "anthropic"
    assert not isinstance(provider, DemoProvider)


def test_bring_your_own_key_can_be_disabled() -> None:
    from aiops_utils import ConfigurationError

    settings = Settings(_env_file=None, allow_bring_your_own_key=False)  # type: ignore[call-arg]
    with pytest.raises(ConfigurationError, match="disabled"):
        get_provider(settings, api_key="sk-ant-test")


def test_live_provider_without_a_key_fails_clearly() -> None:
    from aiops_utils import ConfigurationError

    settings = Settings(_env_file=None, demo_mode=False, anthropic_api_key=None)  # type: ignore[call-arg]
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        get_provider(settings)


# --------------------------------------------------------------- validation


def test_structured_output_rejects_a_mismatched_response(temp_cache_dir: Path) -> None:
    """A response that does not fit the model is a loud failure, not a shrug."""

    class _BadJson(AIProvider):
        name = "bad"

        def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
            raise NotImplementedError

        def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
            return AIResult[dict[str, Any]](
                value={"unexpected": "shape"},
                provider="bad",
                model="bad-model",
                duration_ms=1,
            )

        def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
            raise NotImplementedError

        def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
            raise NotImplementedError

    with pytest.raises(AIProviderError, match="does not match"):
        _BadJson().generate_structured_output("x", output_model=_Example)


# ------------------------------------------------- the Gemini model chain
#
# Added with Project 5. The chain exists because the public demo runs live on a
# free tier: when one model's daily allowance is spent, the next model often
# has its own. It is an attempt, not a guarantee — a project-wide cap looks
# identical from the error — so these tests pin the behaviour rather than the
# promise.


def _chain_settings(**overrides: object) -> Any:
    from aiops_config import ProviderName, Settings

    defaults: dict[str, object] = {
        "_env_file": None,
        "demo_mode": False,
        "ai_provider": ProviderName.GEMINI,
        "google_api_key": "test-key-not-real",
        "database_url": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_the_model_chain_starts_with_the_requested_model() -> None:
    from aiops_ai.providers.gemini_provider import GeminiProvider

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["second", "third"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    assert provider._model_chain(None) == ["primary", "second", "third"]


def test_an_explicit_model_overrides_the_default_but_keeps_the_fallbacks() -> None:
    from aiops_ai.providers.gemini_provider import GeminiProvider

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["second", "third"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    assert provider._model_chain("chosen") == ["chosen", "second", "third"]


def test_the_chain_never_tries_the_same_model_twice() -> None:
    """A fallback list naming the default must not spend two attempts on it."""
    from aiops_ai.providers.gemini_provider import GeminiProvider

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["primary", "second"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    assert provider._model_chain(None) == ["primary", "second"]


def test_an_empty_fallback_list_leaves_a_chain_of_one() -> None:
    from aiops_ai.providers.gemini_provider import GeminiProvider

    settings = _chain_settings(gemini_model="only", gemini_fallback_models=[])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    assert provider._model_chain(None) == ["only"]


def test_a_spent_quota_advances_to_the_next_model() -> None:
    from aiops_ai.providers.gemini_provider import GeminiProvider
    from aiops_ai.types import Usage
    from aiops_utils import AIQuotaExhausted

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["second", "third"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    tried: list[str] = []

    def _fake(
        prompt: str,
        *,
        system: str | None,
        model: str,
        max_tokens: int | None,
        json_mode: bool = False,
        response_schema: Any = None,
    ) -> Any:
        tried.append(model)
        if model != "third":
            raise AIQuotaExhausted(f"{model} is spent")
        return "answered", Usage(input_tokens=1, output_tokens=1), model, 5

    provider._generate_with = _fake  # type: ignore[assignment]
    text, _usage, used, _ms = provider._generate("p", system=None, model=None, max_tokens=None)

    assert tried == ["primary", "second", "third"]
    assert text == "answered"
    assert used == "third", "the answer must report the model that actually produced it"


def test_when_every_model_is_spent_the_quota_error_survives() -> None:
    """The visitor must be told the budget is gone, not given a vaguer error."""
    from aiops_ai.providers.gemini_provider import GeminiProvider
    from aiops_utils import AIQuotaExhausted

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["second"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    def _always_spent(
        prompt: str,
        *,
        system: str | None,
        model: str,
        max_tokens: int | None,
        json_mode: bool = False,
        response_schema: Any = None,
    ) -> Any:
        raise AIQuotaExhausted(f"{model} is spent")

    provider._generate_with = _always_spent  # type: ignore[assignment]
    with pytest.raises(AIQuotaExhausted):
        provider._generate("p", system=None, model=None, max_tokens=None)


def test_a_non_quota_failure_does_not_walk_the_chain() -> None:
    """A malformed request fails the same way on every model.

    Retrying it would turn one clear error into three slow ones, so only a
    spent quota advances.
    """
    from aiops_ai.providers.gemini_provider import GeminiProvider
    from aiops_utils import AIProviderError

    settings = _chain_settings(gemini_model="primary", gemini_fallback_models=["second", "third"])
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._settings = settings  # type: ignore[attr-defined]
    provider._default_model = settings.gemini_model  # type: ignore[attr-defined]

    tried: list[str] = []

    def _bad_request(
        prompt: str,
        *,
        system: str | None,
        model: str,
        max_tokens: int | None,
        json_mode: bool = False,
        response_schema: Any = None,
    ) -> Any:
        tried.append(model)
        raise AIProviderError("schema rejected")

    provider._generate_with = _bad_request  # type: ignore[assignment]
    with pytest.raises(AIProviderError):
        provider._generate("p", system=None, model=None, max_tokens=None)

    assert tried == ["primary"], "only a spent quota may advance the chain"
