"""Token pricing, used to estimate the cost of every AI call.

CLAUDE.md Section 3d requires token count *and* estimated dollar cost in the
Activity Log. This module owns the price table.

Rule: if a model has no entry here, `estimate_cost()` returns None rather than
guessing. A missing cost is honest; a wrong cost is worse than none.

Prices are USD per 1,000,000 tokens. Verified 2026-08-13 against Anthropic's
published pricing. Add entries for other providers as you verify their rates —
`AIOPS_EXTRA_PRICING` lets you do that without editing this file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from aiops_utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens."""

    input_per_mtok: float
    output_per_mtok: float


# Anthropic — verified 2026-08-13.
_PRICING: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(5.00, 25.00),
    "claude-opus-4-8": ModelPrice(5.00, 25.00),
    "claude-sonnet-5": ModelPrice(3.00, 15.00),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
    "claude-fable-5": ModelPrice(10.00, 50.00),
}

# OpenAI and Google prices are deliberately absent: they are not verified here,
# and an invented figure would undermine the whole point of cost tracking.
# To add them, set AIOPS_EXTRA_PRICING to a JSON object, e.g.
#   {"gpt-4o-mini": {"input_per_mtok": 0.15, "output_per_mtok": 0.60}}


def _load_extra_pricing() -> dict[str, ModelPrice]:
    raw = os.environ.get("AIOPS_EXTRA_PRICING")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return {
            model: ModelPrice(
                float(entry["input_per_mtok"]),
                float(entry["output_per_mtok"]),
            )
            for model, entry in parsed.items()
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning("AIOPS_EXTRA_PRICING is not valid pricing JSON; ignoring it")
        return {}


def price_for(model: str) -> ModelPrice | None:
    """Return the price entry for `model`, or None if it is unknown."""
    return {**_PRICING, **_load_extra_pricing()}.get(model)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate the USD cost of a call. Returns None when the model is unpriced."""
    price = price_for(model)
    if price is None:
        return None
    cost = (input_tokens * price.input_per_mtok + output_tokens * price.output_per_mtok) / 1_000_000
    # Sub-cent precision matters here: individual calls are often < $0.01.
    return round(cost, 6)


def known_models() -> list[str]:
    """Every model with a price entry. Useful for a settings/diagnostics page."""
    return sorted({**_PRICING, **_load_extra_pricing()})
