# 4. Python 3.12 minimum

**Date:** 2026-08-13 · **Status:** Accepted

## Context

Packages initially declared `>=3.11`, while ruff and mypy were configured for
3.12. The inconsistency surfaced as contradictory tool output: ruff suggested
PEP 695 generics that 3.11 cannot parse, and mypy targeting 3.11 failed on
NumPy's 3.12-only type stubs.

## Decision

`requires-python = ">=3.12"` everywhere, with ruff `target-version = "py312"`
and mypy `python_version = "3.12"` matching it.

## Reasoning

The floor has to be one number. 3.12 is widely available, is what every
intended deployment target runs, and unblocks the modern generic syntax the
type checker and linter both expect. Development happens on 3.14, which is
comfortably above the floor.

## Consequences

- Keep the three settings in sync; the ruff config carries a comment saying so.
- `AIResult[T]` uses PEP 695 syntax, which Pydantic v2 supports natively.
