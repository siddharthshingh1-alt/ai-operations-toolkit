# 6. Integration adapters live in their own package

**Date:** 2026-08-13 · **Status:** Accepted

## Context

CLAUDE.md Section 4's tree lists `/packages/{ui,types,ai,database,config,utils}`.
Section 3c requires `EmailProvider`, `CalendarProvider`, and `BookingProvider`
adapters, but does not say where they live.

## Decision

A seventh package, `packages/adapters`.

## Reasoning

The candidates were `packages/ai` (semantically wrong — an inbox reader is not
an AI concern) or `services/` (which holds cross-cutting capabilities, not
integration seams). Neither fits, and jamming them into either would obscure
the thing Section 3c cares about: that these are the swap points for real
integrations.

Adding one clearly-named package is a smaller cost than a misfiled one, and it
is recorded here rather than left as an undocumented deviation.

## Consequences

- The Section 4 tree in the root README shows this addition explicitly.
