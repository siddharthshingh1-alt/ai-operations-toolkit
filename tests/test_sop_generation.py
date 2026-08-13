"""SOP schema, validation, and generation tests.

Covers CLAUDE.md Section 25's required cases: valid input, invalid input, AI
failure, empty data, large data, and missing required fields. No test here
makes a network call — the AI provider is substituted with a stub.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiops_sop import service
from aiops_sop.prompts import build_generation_prompt
from aiops_sop.schema import (
    GenerateSopRequest,
    ProcedureStep,
    SopContent,
    SopStatus,
)
from pydantic import ValidationError as PydanticValidationError

from aiops_ai import AIResult, Usage
from aiops_ai.base import AIProvider
from aiops_ai.types import TranscriptResult
from aiops_utils import AIProviderError, ValidationError


class _StubProvider(AIProvider):
    """Returns a fixed SOP without touching the network."""

    name = "stub"

    def __init__(self, content: SopContent | None = None, fail: Exception | None = None) -> None:
        self._content = content or SopContent(
            title="Handling Flight Delays",
            purpose="Notify travel agents promptly when a flight is delayed.",
            scope="Flights delayed by more than three hours.",
            procedure=[ProcedureStep(number=1, instruction="Confirm the delay.")],
        )
        self._fail = fail

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        raise NotImplementedError

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        if self._fail:
            raise self._fail
        return AIResult[dict[str, Any]](
            value=self._content.model_dump(mode="json"),
            provider="stub",
            model="stub-model",
            duration_ms=12,
            usage=Usage(input_tokens=100, output_tokens=200, estimated_cost_usd=0.001),
        )

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


# ------------------------------------------------------------ input validation


def test_valid_request_is_accepted() -> None:
    request = GenerateSopRequest(
        process_description="When a flight is delayed we tell the affected agents quickly.",
        role="Operations Associate",
    )
    assert request.role == "Operations Associate"


def test_missing_required_description_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        GenerateSopRequest()  # type: ignore[call-arg]


def test_empty_description_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        GenerateSopRequest(process_description="   " * 20)


def test_too_short_description_is_rejected() -> None:
    """A three-word description cannot produce a useful SOP."""
    with pytest.raises(PydanticValidationError):
        GenerateSopRequest(process_description="do the thing")


def test_oversized_description_is_rejected() -> None:
    """Large data must fail validation, not be silently sent to the model."""
    with pytest.raises(PydanticValidationError):
        GenerateSopRequest(process_description="x" * 20_001)


def test_large_but_allowed_description_is_accepted() -> None:
    request = GenerateSopRequest(process_description="x" * 19_999)
    assert len(request.process_description) == 19_999


# -------------------------------------------------------------------- prompts


def test_prompt_includes_every_supplied_input() -> None:
    prompt = build_generation_prompt(
        GenerateSopRequest(
            process_description="Handle delays for affected agent bookings.",
            role="Operations Associate",
            department="Flight Ops",
            objective="Contact agents within 30 minutes",
            existing_sop="Old procedure text",
            document_text="Extracted document text",
        )
    )
    for expected in (
        "Handle delays",
        "Operations Associate",
        "Flight Ops",
        "within 30 minutes",
        "Old procedure text",
        "Extracted document text",
    ):
        assert expected in prompt


def test_prompt_omits_absent_optional_inputs() -> None:
    prompt = build_generation_prompt(
        GenerateSopRequest(process_description="Handle delays for affected bookings.")
    )
    assert "EXISTING SOP" not in prompt
    assert "SUPPORTING DOCUMENT" not in prompt


# ----------------------------------------------------------------- generation


def test_generation_returns_content_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "get_provider", lambda *a, **k: _StubProvider())
    result = service.generate_sop(
        GenerateSopRequest(process_description="Handle delays for affected agent bookings.")
    )
    assert result.content.title == "Handling Flight Delays"
    assert result.input_tokens == 100
    assert result.estimated_cost_usd == 0.001


def test_ai_failure_surfaces_as_a_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An AI outage must be reported, never silently swallowed."""
    monkeypatch.setattr(
        service,
        "get_provider",
        lambda *a, **k: _StubProvider(fail=AIProviderError("provider is down")),
    )
    with pytest.raises(AIProviderError):
        service.generate_sop(
            GenerateSopRequest(process_description="Handle delays for affected bookings.")
        )


def test_generation_never_writes_to_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Human-in-the-loop: generating is not saving (CLAUDE.md Section 5).

    `generate_sop` takes no session argument at all, so there is no way for it
    to persist anything — the guarantee is structural, and this test pins it.
    """
    import inspect

    assert "session" not in inspect.signature(service.generate_sop).parameters


# --------------------------------------------------------------- search text


def test_search_text_includes_the_operational_content() -> None:
    content = SopContent(
        title="Flight Delay Handling",
        purpose="Notify agents",
        scope="Delays over 3 hours",
        checklist=["Agent notified"],
        procedure=[ProcedureStep(number=1, instruction="Confirm the delay")],
    )
    text = content.to_search_text()
    assert "Flight Delay Handling" in text
    assert "Confirm the delay" in text
    assert "Agent notified" in text


def test_search_text_excludes_meta_commentary() -> None:
    """Improvement suggestions are about the process, not part of it."""
    content = SopContent(
        title="T",
        purpose="P",
        scope="S",
        improvement_suggestions=["Consider automating the notification step"],
    )
    assert "automating" not in content.to_search_text()


def test_empty_sop_produces_usable_search_text() -> None:
    content = SopContent(title="Title only", purpose="", scope="")
    assert content.to_search_text().strip() == "Title only"


def test_status_values_match_the_spec() -> None:
    assert {s.value for s in SopStatus} == {"draft", "active", "under_review", "retired"}


def test_saving_without_a_title_is_rejected() -> None:
    from aiops_sop.schema import SaveSopRequest

    request = SaveSopRequest(content=SopContent(title="   ", purpose="p", scope="s"))
    with pytest.raises(ValidationError, match="needs a title"):
        service.create_sop(None, request, actor="tester")  # type: ignore[arg-type]
