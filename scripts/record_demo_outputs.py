#!/usr/bin/env python
"""Record real AI outputs so Demo Mode has something honest to replay.

    npm run record-demo

This makes **real API calls** and costs real money. It is the only way
recordings are created: `DemoProvider` cannot invent one, by design
(CLAUDE.md Sections 2 and 3b).

It also seeds the database with the generated SOPs, so a reviewer opening the
app finds a working library rather than an empty page.

Requires DEMO_MODE=false and an API key for the configured provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

from aiops_sop import service
from aiops_sop.schema import SaveSopRequest, SopMetadata, SopStatus
from aiops_sop.search import answer_question

from aiops_ai import RecordingProvider, get_embedding_provider, get_provider
from aiops_config import demo_cache_dir, get_settings
from aiops_db import session_scope
from aiops_utils import AIOpsError, configure_logging

# `scripts/` is a plain directory, not a package, so the sibling module is
# imported by path — the same way the script itself is run.
sys.path.insert(0, str(Path(__file__).parent))
from demo_examples import EXAMPLES  # noqa: E402

#: Questions recorded so the "Ask your SOPs" panel works in Demo Mode.
QUESTIONS = [
    "How quickly must we contact agents after a flight delay?",
    "What do we do if a hotel overbooks a confirmed room?",
    "What are the steps to onboard a new travel agency?",
]

OWNERS = ["Anita Rao", "Deepak Menon", "Sana Qureshi"]


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
    # Search needs the query embeddings recorded as well, or Demo Mode can
    # retrieve nothing and every question looks like a gap.
    embedder = RecordingProvider(get_embedding_provider(settings))
    print(f"Recording with {provider.name} / {settings.model_for(settings.ai_provider)}")
    print(f"Writing to {demo_cache_dir()}")
    print("This makes real API calls and will incur cost.\n")

    total_cost = 0.0
    seeded = 0

    failures: list[str] = []

    # --- SOP generation, one recording per canonical example ---------------
    print("Generating SOPs")
    for index, example in enumerate(EXAMPLES):
        try:
            generated = service.generate_sop(example, settings=settings, provider_override=provider)
            total_cost += generated.estimated_cost_usd or 0.0
            print(f"  {generated.content.title[:66]}")

            with session_scope(settings) as db:
                # Match on the example's department, not the generated title —
                # the model words titles differently on each run, so a title
                # check lets duplicates through.
                if any(s.department == example.department for s in service.list_sops(db)):
                    print("    already in the library, not seeding again")
                    continue

                service.create_sop(
                    db,
                    SaveSopRequest(
                        content=generated.content,
                        metadata=SopMetadata(
                            owner=OWNERS[index % len(OWNERS)],
                            department=example.department,
                            status=SopStatus.ACTIVE,
                        ),
                        change_note="Initial version, drafted by AI and reviewed",
                    ),
                    actor=settings.demo_user_email,
                    generated=generated,
                    settings=settings,
                    embedding_override=embedder,
                )
                seeded += 1

        except (AIOpsError, OSError) as exc:
            # One flaky example must not lose the work already recorded.
            detail = getattr(exc, "detail", str(exc))
            print(f"    skipped: {detail[:90]}")
            failures.append(f"{example.department}: {detail[:70]}")

    # --- question answering ------------------------------------------------
    print("\nRecording answers")
    for question in QUESTIONS:
        try:
            with session_scope(settings) as db:
                outcome = answer_question(
                    db,
                    question,
                    settings=settings,
                    provider_override=provider,
                    embedding_override=embedder,
                )
            total_cost += outcome.estimated_cost_usd or 0.0
            verdict = "answered" if outcome.result.answered else "no relevant SOP"
            print(f"  {verdict:16} {question[:56]}")
        except (AIOpsError, OSError) as exc:
            detail = getattr(exc, "detail", str(exc))
            print(f"  skipped          {question[:44]} — {detail[:44]}")
            failures.append(f"question: {detail[:70]}")

    if failures:
        print(f"\n{len(failures)} item(s) did not record:")
        for failure in failures:
            print(f"  - {failure}")
        print("Re-run to retry them; recording is idempotent.")

    recordings = len(list(demo_cache_dir().glob("*.json")))
    print(f"\nDone. {recordings} recording(s) on disk, {seeded} SOP(s) seeded.")
    print(f"Estimated cost of this run: ${total_cost:.4f}")
    print("\nSet DEMO_MODE=true in .env to replay these with no API key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
