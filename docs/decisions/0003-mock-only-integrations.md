# 3. Integrations are mock-only in v1, enforced in configuration

**Date:** 2026-08-13 · **Status:** Accepted

## Context

CLAUDE.md Section 3c resolves a previously open question: v1 uses mock data
behind clean adapter interfaces, real OAuth is a future improvement, and a real
airline, GDS, or payment system is never connected in any version.

## Decision

`EmailProvider`, `CalendarProvider`, and `BookingProvider` are abstract
interfaces with exactly one implementation each, reading the synthetic datasets.

`Settings` **rejects** any value other than `mock` for the three provider
settings, raising a validation error at configuration load.

## Reasoning

A comment saying "mock only for now" degrades silently. A validator does not:
switching `EMAIL_PROVIDER=gmail` fails immediately with an explanation, so a
half-built OAuth flow cannot be turned on by an environment variable.

`BookingProvider` is additionally read-only by construction — it declares no
method that could create, cancel, charge, or refund. A test asserts this, so
adding one is a deliberate act that fails CI rather than an oversight.

## Consequences

- Enabling a real integration requires editing code and this document, which is
  the intended amount of friction.
- The adapters need generated demo data; `npm run demo-data` produces it, and
  CI runs the generator before the tests.
