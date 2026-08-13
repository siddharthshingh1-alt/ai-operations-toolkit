# 2. Demo Mode replays recorded real outputs and never fabricates

**Date:** 2026-08-13 · **Status:** Accepted

## Context

CLAUDE.md Section 3b requires the toolkit to work for a reviewer with zero API
keys. Section 2 bans fake API responses presented as real AI functionality.
Those two requirements are easy to satisfy in a way that quietly violates the
second.

## Decision

`DemoProvider` reads recordings from `data/demo-cache/`, keyed by a hash of
`(operation, prompt, system)`. When no recording exists it raises
`DemoRecordingMissing`. It has no code path that can produce an answer of its
own.

Recordings are created only by `RecordingProvider`, which wraps a live provider
and saves genuine responses — see `scripts/record_demo_outputs.py`.

## Reasoning

The difference between a legitimate demo and a dishonest one is whether the
output was ever really produced by a model. Making that difference structural
means it cannot erode later under time pressure: there is no function to call
that would invent something.

The visible cost is that Demo Mode is inert until someone runs the recorder
once with a real key. That is the correct trade — a reviewer seeing "no
recording yet" learns something true, where a fabricated answer would teach
them something false.

## Consequences

- **No recordings ship in this repo yet.** Phase 0 had no API key available, so
  none could be made honestly. `npm run record-demo` creates them.
- `/health/ready` reports the recording count, so the gap is visible rather than
  discovered by clicking.
- The cache key excludes the model name, so recordings survive a model change
  while still reporting which model actually produced them.
