"""Search and citation tests.

The most important tests in Project 1 are here. CLAUDE.md Section 9 requires:

    "When answering a question, always show which SOP(s) support the answer.
     If nothing relevant is found, say so explicitly — do not hallucinate."

These pin both halves of that, without any network call.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiops_sop import search as search_module
from aiops_sop.schema import ProcedureStep, SopContent
from aiops_sop.search import SIMILARITY_FLOOR, _RankedSop, answer_question

from aiops_ai import AIResult, Usage
from aiops_ai.base import AIProvider
from aiops_ai.types import TranscriptResult


def _ranked(similarity: float, title: str = "Flight Delay Handling") -> _RankedSop:
    return _RankedSop(
        sop_id="sop_test1",
        title=title,
        version=1,
        similarity=similarity,
        content=SopContent(
            title=title,
            purpose="Notify agents when a flight is delayed.",
            scope="Delays over three hours.",
            procedure=[ProcedureStep(number=1, instruction="Confirm the delay.")],
        ),
    )


class _AnsweringProvider(AIProvider):
    """Stands in for the AI. Records whether it was called at all."""

    name = "stub"

    def __init__(self, *, answered: bool = True) -> None:
        self.answered = answered
        self.call_count = 0

    def _complete_text(self, prompt: str, **kwargs: Any) -> AIResult[str]:
        raise NotImplementedError

    def _complete_json(self, prompt: str, **kwargs: Any) -> AIResult[dict[str, Any]]:
        self.call_count += 1
        return AIResult[dict[str, Any]](
            value={
                "answered": self.answered,
                "answer": "Contact the agent within 30 minutes."
                if self.answered
                else "The SOPs provided do not cover this.",
                "reasoning_summary": "Based on the delay handling SOP.",
            },
            provider="stub",
            model="stub-model",
            duration_ms=5,
            usage=Usage(input_tokens=50, output_tokens=25, estimated_cost_usd=0.0005),
        )

    def generate_embeddings(self, texts: list[str]) -> AIResult[list[list[float]]]:
        raise NotImplementedError

    def transcribe(self, audio_path: Any) -> AIResult[TranscriptResult]:
        raise NotImplementedError


# ------------------------------------------- the no-hallucination guarantee


def test_irrelevant_question_does_not_call_the_ai_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The central guarantee.

    When nothing clears the relevance floor there is no source material, so the
    AI is never invoked — it cannot invent an answer it was never asked for.
    """
    provider = _AnsweringProvider()
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [_ranked(0.20)])
    monkeypatch.setattr(search_module, "get_provider", lambda *a, **k: provider)

    outcome = answer_question(None, "How do I reset the wifi router?")  # type: ignore[arg-type]

    assert outcome.result.answered is False
    assert outcome.skipped_ai is True
    assert provider.call_count == 0, "the AI must not be called when nothing is relevant"


def test_refusal_cites_nothing() -> None:
    """Showing sources beside 'I don't know' would imply they were used."""

    def _no_matches(*a: Any, **k: Any) -> list[_RankedSop]:
        return []

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(search_module, "_retrieve", _no_matches)
        outcome = answer_question(None, "Anything at all")  # type: ignore[arg-type]

    assert outcome.result.answered is False
    assert outcome.result.citations == []


def test_refusal_explains_why(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user should learn it is a gap, not a failure."""
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [_ranked(0.31)])
    outcome = answer_question(None, "Unrelated question")  # type: ignore[arg-type]

    assert "31%" in outcome.result.reasoning_summary
    assert f"{SIMILARITY_FLOOR:.0%}" in outcome.result.reasoning_summary


def test_empty_library_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty data: a library with no SOPs answers nothing."""
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [])
    outcome = answer_question(None, "How do we handle delays?")  # type: ignore[arg-type]

    assert outcome.result.answered is False
    assert outcome.skipped_ai is True


# ------------------------------------------------------- the answering path


def test_relevant_question_is_answered_with_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _AnsweringProvider(answered=True)
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [_ranked(0.82)])
    monkeypatch.setattr(search_module, "get_provider", lambda *a, **k: provider)

    outcome = answer_question(None, "How quickly must we contact agents?")  # type: ignore[arg-type]

    assert outcome.result.answered is True
    assert provider.call_count == 1
    assert len(outcome.result.citations) == 1
    assert outcome.result.citations[0].title == "Flight Delay Handling"
    assert outcome.result.citations[0].similarity == 0.82


def test_citations_come_from_retrieval_not_from_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The model cannot cite an SOP that was never retrieved.

    Citations are built from the retrieval results, so a model that invented a
    document name in its prose still cannot produce a fake source link.
    """
    monkeypatch.setattr(
        search_module,
        "_retrieve",
        lambda *a, **k: [_ranked(0.9, "Real SOP A"), _ranked(0.7, "Real SOP B")],
    )
    monkeypatch.setattr(search_module, "get_provider", lambda *a, **k: _AnsweringProvider())

    outcome = answer_question(None, "A relevant question")  # type: ignore[arg-type]
    titles = {c.title for c in outcome.result.citations}
    assert titles == {"Real SOP A", "Real SOP B"}


def test_model_saying_unanswered_drops_the_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieval found something, but the model judged it insufficient."""
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [_ranked(0.8)])
    monkeypatch.setattr(
        search_module, "get_provider", lambda *a, **k: _AnsweringProvider(answered=False)
    )

    outcome = answer_question(None, "Something only partly covered")  # type: ignore[arg-type]
    assert outcome.result.answered is False
    assert outcome.result.citations == []


def test_only_sops_above_the_floor_are_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """A weak match must not be smuggled in alongside a strong one."""
    monkeypatch.setattr(
        search_module,
        "_retrieve",
        lambda *a, **k: [_ranked(0.90, "Strong match"), _ranked(0.10, "Weak match")],
    )
    monkeypatch.setattr(search_module, "get_provider", lambda *a, **k: _AnsweringProvider())

    outcome = answer_question(None, "A question")  # type: ignore[arg-type]
    assert [c.title for c in outcome.result.citations] == ["Strong match"]


def test_cost_is_reported_for_an_answered_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_module, "_retrieve", lambda *a, **k: [_ranked(0.8)])
    monkeypatch.setattr(search_module, "get_provider", lambda *a, **k: _AnsweringProvider())

    outcome = answer_question(None, "A question")  # type: ignore[arg-type]
    assert outcome.input_tokens == 50
    assert outcome.estimated_cost_usd == 0.0005


def test_floor_is_a_sane_value() -> None:
    """A floor of 0 would defeat the guarantee; 1.0 would reject everything."""
    assert 0.3 < SIMILARITY_FLOOR < 0.9
