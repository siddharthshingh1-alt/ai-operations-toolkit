# 1. Modular monolith over microservices

**Date:** 2026-08-13 · **Status:** Accepted

## Context

Nine projects share an AI layer, a workflow engine, analytics, and document
export. They could be independent services.

## Decision

One FastAPI process and one Next.js app. Shared code lives in Python packages
imported in-process.

## Reasoning

CLAUDE.md Section 30 asks for working, understandable, testable, demonstrable
over complex. Splitting into services would add deployment surface, network
failure modes, and orchestration for no capability gain — and would make the
live-demo requirement (Section 3a) considerably harder to satisfy.

The package boundaries are still real: dependencies point one way only, so
extracting a service later is a build-config change, not a rewrite.

## Consequences

- One deploy target for the API, one for the web app.
- A slow endpoint can affect others; acceptable at portfolio scale.
- `packages/` and `services/` must keep their dependency direction clean or the
  benefit is lost. CI does not enforce this yet — it is a review responsibility.
