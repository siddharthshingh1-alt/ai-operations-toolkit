"""Semantic search across the SOP library, with citations.

This is the folded-in "Knowledge Base" capability from CLAUDE.md Section 9. The
requirement it turns on is specific:

    "When answering a question, always show which SOP(s) support the answer.
     If nothing relevant is found, say so explicitly — do not hallucinate."

Two mechanisms enforce that:

1. A **similarity floor**. If no SOP clears it, the AI is never called at all —
   there is nothing to answer from, so the question returns "not found" without
   an opportunity to invent something.
2. The prompt only ever contains retrieved SOP text, and the answer model has
   an explicit `answered: false` path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aiops_ai import get_embedding_provider, get_provider
from aiops_ai.base import AIProvider
from aiops_config import Settings, get_settings
from aiops_sop.models import Sop, SopVersion
from aiops_sop.prompts import ANSWER_SYSTEM, build_answer_prompt
from aiops_sop.schema import AnswerResult, Citation, SopContent
from aiops_utils import get_logger

logger = get_logger(__name__)

#: Cosine similarity below this counts as "not relevant".
#:
#: Tuned against the seeded SOPs: a genuinely related question scores well
#: above it, while an unrelated one ("how do I reset my laptop password")
#: scores below. Set too low, the AI gets handed irrelevant SOPs and is
#: tempted to stretch them; too high, and real matches get rejected.
SIMILARITY_FLOOR = 0.55


class _RankedSop(BaseModel):
    """An SOP version retrieved as a candidate answer source."""

    sop_id: str
    title: str
    version: int
    similarity: float
    content: SopContent


class SearchHit(BaseModel):
    """A search result, for the plain search list (no AI involved)."""

    sop_id: str
    title: str
    version: int
    similarity: float
    owner: str = ""
    status: str = ""
    snippet: str = ""


class AskOutcome(BaseModel):
    """An answer plus the cost metadata the activity log needs."""

    result: AnswerResult
    model: str = ""
    provider: str = ""
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    from_demo_cache: bool = False
    #: True when the similarity floor rejected everything, so no AI call was made.
    skipped_ai: bool = False


class _AnswerModel(BaseModel):
    """What the AI is asked to return. Mirrors AnswerResult minus citations,
    which are supplied by the retrieval layer rather than the model — the model
    cannot cite an SOP that was not actually retrieved."""

    answered: bool = Field(description="False if the provided SOPs do not contain the answer.")
    answer: str
    reasoning_summary: str


def _retrieve(
    session: Session,
    question: str,
    *,
    top_k: int,
    settings: Settings,
    embedding_override: AIProvider | None = None,
) -> list[_RankedSop]:
    """Find the SOP versions most similar to the question."""
    provider = embedding_override or get_embedding_provider(settings)
    query_vector = provider.generate_embeddings([question]).value[0]

    # Only the current version of each SOP is searchable — older versions would
    # return stale procedure text as if it were live.
    stmt = (
        select(
            SopVersion,
            Sop,
            # pgvector's <=> is cosine distance; similarity is 1 - distance.
            (1 - SopVersion.embedding.cosine_distance(query_vector)).label("similarity"),
        )
        .join(Sop, Sop.id == SopVersion.sop_id)
        .where(
            SopVersion.embedding.is_not(None),
            SopVersion.version == Sop.current_version,
        )
        .order_by(SopVersion.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )

    ranked: list[_RankedSop] = []
    for version, sop, similarity in session.execute(stmt):
        ranked.append(
            _RankedSop(
                sop_id=sop.id,
                title=sop.title,
                version=version.version,
                similarity=round(float(similarity), 4),
                content=SopContent.model_validate(version.content),
            )
        )
    return ranked


def search_sops(
    session: Session, query: str, *, top_k: int = 5, settings: Settings | None = None
) -> list[SearchHit]:
    """Plain semantic search — ranked SOPs, no AI answer."""
    settings = settings or get_settings()
    hits = _retrieve(session, query, top_k=top_k, settings=settings)

    results: list[SearchHit] = []
    for hit in hits:
        sop = session.get(Sop, hit.sop_id)
        results.append(
            SearchHit(
                sop_id=hit.sop_id,
                title=hit.title,
                version=hit.version,
                similarity=hit.similarity,
                owner=sop.owner if sop else "",
                status=sop.status if sop else "",
                snippet=hit.content.purpose[:200],
            )
        )
    return results


def answer_question(
    session: Session,
    question: str,
    *,
    top_k: int = 4,
    settings: Settings | None = None,
    api_key: str | None = None,
    provider_override: AIProvider | None = None,
    embedding_override: AIProvider | None = None,
) -> AskOutcome:
    """Answer a question from the SOP library, with citations.

    The `*_override` arguments exist for `scripts/record_demo_outputs.py`,
    which wraps the live providers to capture their responses.
    """
    settings = settings or get_settings()

    candidates = _retrieve(
        session,
        question,
        top_k=top_k,
        settings=settings,
        embedding_override=embedding_override,
    )
    relevant = [c for c in candidates if c.similarity >= SIMILARITY_FLOOR]

    if not relevant:
        # Nothing cleared the floor. Return without calling the AI at all —
        # there is no source material, so there is nothing to answer from.
        best = max((c.similarity for c in candidates), default=0.0)
        logger.info(
            "question had no relevant SOP",
            extra={
                "project": "ai-sop-generator",
                "best_similarity": best,
                "floor": SIMILARITY_FLOOR,
            },
        )
        return AskOutcome(
            result=AnswerResult(
                answered=False,
                answer=(
                    "No SOP in the library covers this. Rather than guess, this "
                    "is being reported as a gap — it may be worth writing an SOP "
                    "for it."
                ),
                citations=[],
                reasoning_summary=(
                    f"Searched {len(candidates)} SOP(s); the closest match scored "
                    f"{best:.0%}, below the {SIMILARITY_FLOOR:.0%} relevance threshold."
                ),
            ),
            skipped_ai=True,
        )

    blocks = [
        f"SOP: {c.title} (version {c.version})\n{c.content.to_search_text()}" for c in relevant
    ]
    provider = provider_override or get_provider(settings, api_key=api_key)
    ai = provider.generate_structured_output(
        build_answer_prompt(question, blocks),
        output_model=_AnswerModel,
        system=ANSWER_SYSTEM,
    )

    # Citations come from what was retrieved, never from the model's text.
    citations = [
        Citation(sop_id=c.sop_id, title=c.title, version=c.version, similarity=c.similarity)
        for c in relevant
    ]

    return AskOutcome(
        result=AnswerResult(
            answered=ai.value.answered,
            answer=ai.value.answer,
            # An unanswered question cites nothing — showing sources next to
            # "I don't know" would imply they were used.
            citations=citations if ai.value.answered else [],
            reasoning_summary=ai.value.reasoning_summary,
        ),
        model=ai.model,
        provider=ai.provider,
        duration_ms=ai.duration_ms,
        input_tokens=ai.usage.input_tokens,
        output_tokens=ai.usage.output_tokens,
        estimated_cost_usd=ai.usage.estimated_cost_usd,
        from_demo_cache=ai.from_demo_cache,
    )
