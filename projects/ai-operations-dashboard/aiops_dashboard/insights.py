"""The one place in this project where a model is called.

Two rules govern everything here, both from CLAUDE.md Section 11:

1. **The model is given findings, never the file.** It receives the trends and
   anomalies already computed in `analysis.py` — a few hundred tokens of
   arithmetic results — and never a single raw row. It therefore cannot invent
   a number, because it is never in a position to produce one; it can only
   restate what was measured. This also makes the call cheap and fast enough
   to matter on a twenty-request daily budget.

2. **Observation, hypothesis and recommendation stay separate.** They are three
   required fields of a schema the provider decodes against, not three
   paragraphs we hope arrive distinguishable. "Never present speculation as
   fact" is enforced by the shape of the response.
"""

from __future__ import annotations

from collections import OrderedDict

from aiops_ai import get_provider
from aiops_config import Settings, get_settings
from aiops_dashboard.models import Analysis, InsightReport, InsightResponse
from aiops_utils import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an operations analyst at a B2B travel-technology company. Travel agents \
book flights, hotels and holidays through the platform, and an operations team \
handles delays, cancellations, refunds and support.

You are given findings that have ALREADY been computed from an operations \
dataset. Your job is to interpret them for the operations team.

Rules, all of which matter more than being interesting:

- Use only the numbers given to you. Never introduce a figure that is not in \
the findings, and never recompute one.
- `observed` must restate a supplied finding in plain language. It is a fact.
- `hypothesis` must be a POSSIBLE contributor, phrased as a possibility. You \
have not seen the underlying causes and cannot know them. If nothing plausible \
suggests itself, say that the cause is not determinable from this data — that \
is a valid and useful answer.
- `recommendation` must be a concrete next step someone could take this week, \
expressed as an investigation or an action, not a platitude.
- Never claim a change is good or bad without saying which direction is \
desirable for that metric.

Prefer fewer, more material findings over a long list.\
"""

#: Insight reports keyed by `Analysis.facts_key`.
#:
#: The public deployment runs live on a free tier of roughly twenty requests a
#: day, shared across every visitor. Without this, two people opening the same
#: sample dataset would spend two of them on identical input. Bounded so a long
#: uptime cannot grow it without limit; process-local on purpose, since a
#: second instance re-earning the cache costs one request, and a shared cache
#: would cost a Redis.
_CACHE: OrderedDict[str, InsightReport] = OrderedDict()
_CACHE_LIMIT = 64


def _remember(key: str, report: InsightReport) -> None:
    _CACHE[key] = report
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Empty the insight cache. Used by tests."""
    _CACHE.clear()


def build_prompt(analysis: Analysis) -> str:
    """Render the computed findings as the model's entire view of the data."""
    lines = [
        f"Dataset: {analysis.dataset}",
        f"Rows: {analysis.row_count}. Columns: {analysis.column_count}.",
    ]
    if analysis.date_column:
        lines.append(f"Time axis: {analysis.date_column}")

    lines.append("")
    lines.append("MEASURED TRENDS:")
    if analysis.trends:
        lines.extend(f"- {trend.describe()}" for trend in analysis.trends)
    else:
        lines.append("- None. No column had enough ordered points to establish a trend.")

    lines.append("")
    lines.append("MEASURED ANOMALIES (points far from their column's mean):")
    if analysis.anomalies:
        lines.extend(f"- {anomaly.describe()}" for anomaly in analysis.anomalies[:8])
    else:
        lines.append("- None. No point sat far enough from its mean to flag.")

    categorical = [column for column in analysis.columns if column.top_values]
    if categorical:
        lines.append("")
        lines.append("CATEGORY BREAKDOWNS (most frequent values):")
        lines.extend(
            f"- {column.name}: {', '.join(column.top_values[:5])}" for column in categorical[:5]
        )

    lines.append("")
    lines.append(
        "Interpret these findings for the operations team. Do not introduce numbers "
        "that do not appear above."
    )
    return "\n".join(lines)


def explain(
    analysis: Analysis,
    *,
    settings: Settings | None = None,
    provider_override: object | None = None,
) -> InsightResponse:
    """Ask the model to interpret an analysis.

    `provider_override` exists so tests can inject a stub and run with no API
    key and no recordings — CI must never need either.
    """
    settings = settings or get_settings()

    cached = _CACHE.get(analysis.facts_key)
    if cached is not None:
        logger.info(
            "served insights from cache",
            extra={"project": "ai-operations-dashboard", "dataset": analysis.dataset},
        )
        return InsightResponse(
            report=cached,
            model="cached",
            provider="cache",
            duration_ms=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            from_cache=True,
        )

    provider = provider_override or get_provider(settings)
    result = provider.generate_structured_output(  # type: ignore[attr-defined]
        build_prompt(analysis),
        output_model=InsightReport,
        system=SYSTEM_PROMPT,
    )

    _remember(analysis.facts_key, result.value)

    logger.info(
        "generated dashboard insights",
        extra={
            "project": "ai-operations-dashboard",
            "dataset": analysis.dataset,
            "model": result.model,
            "duration_ms": result.duration_ms,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "estimated_cost_usd": result.usage.estimated_cost_usd,
        },
    )

    return InsightResponse(
        report=result.value,
        model=result.model,
        provider=result.provider,
        duration_ms=result.duration_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        estimated_cost_usd=result.usage.estimated_cost_usd,
        from_cache=False,
    )
