#!/usr/bin/env python
"""Record real AI outputs so Demo Mode has something honest to replay.

    npm run record-demo

This makes **real API calls** and costs real money. It is the only way
recordings are created: `DemoProvider` cannot invent one, by design
(CLAUDE.md Sections 2 and 3b).

Requires DEMO_MODE=false and an API key for the configured provider.
"""

from __future__ import annotations

import sys

from aiops_ai import RecordingProvider, get_provider
from aiops_config import demo_cache_dir, get_settings
from aiops_utils import AIOpsError, configure_logging


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.demo_mode:
        print(
            "DEMO_MODE is true, so there is no live provider to record from.\n"
            "Set DEMO_MODE=false in .env, supply an API key, and run this again.",
            file=sys.stderr,
        )
        return 1

    if not settings.api_key_for(settings.ai_provider):
        print(
            f"No API key set for provider {settings.ai_provider.value!r}.",
            file=sys.stderr,
        )
        return 1

    provider = RecordingProvider(get_provider(settings))
    print(f"Recording with {provider.name} / {settings.model_for(settings.ai_provider)}")
    print(f"Writing to {demo_cache_dir()}\n")
    print("This makes real API calls and will incur cost.\n")

    total_cost = 0.0

    # Phase 0 records one representative call per shared capability, which is
    # enough to prove the replay path end to end. Each project adds its own
    # recordings here as it is built.
    try:
        result = provider.classify(
            "Our client's flight on DEL-BOM tomorrow has been delayed by six "
            "hours. Three of our travellers are affected and one has a "
            "connecting international flight. What should we do?",
            categories=[
                "Agent Partner",
                "Booking Ops",
                "Vendor/Hotel",
                "Finance",
                "Internal",
                "Urgent",
                "Other",
            ],
        )
        total_cost += result.usage.estimated_cost_usd or 0.0
        print(f"  classify   -> {result.value.category} ({result.value.priority})")

        summary = provider.summarize(
            "Cancellation rate rose from 6.3% to 12.2% over the last 90 days, "
            "with most of the increase concentrated in the final fortnight. "
            "Delay incidents on DEL-BOM rose over the same period. Ticket "
            "volume from one agency roughly doubled."
        )
        total_cost += summary.usage.estimated_cost_usd or 0.0
        print(f"  summarize  -> {summary.value.summary[:70]}...")

    except AIOpsError as exc:
        print(f"\nRecording failed: {exc.detail}", file=sys.stderr)
        return 1

    print(f"\nDone. Estimated cost of this run: ${total_cost:.4f}")
    print("Set DEMO_MODE=true again to replay these recordings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
