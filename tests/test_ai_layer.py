"""Tests for the shared AI layer.

The important case here is the one Section 2 cares about: Demo Mode must
*refuse* to answer when it has no recording, rather than inventing something.
"""

from __future__ import annotations

import json
from pathlib import Path
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
from aiops_utils import AIProviderError

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
