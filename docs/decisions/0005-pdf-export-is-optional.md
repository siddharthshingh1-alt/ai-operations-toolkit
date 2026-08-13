# 5. PDF export degrades rather than blocking

**Date:** 2026-08-13 · **Status:** Accepted

## Context

CLAUDE.md Section 3 specifies WeasyPrint as the shared PDF exporter. WeasyPrint
depends on native GTK/Pango libraries that are absent from a stock Windows
install — the development machine here among them.

## Decision

WeasyPrint is an optional dependency (`pip install .[pdf]`). `PdfExporter`
imports it lazily and, when unavailable, raises a `ConfigurationError` naming
the exact packages to install per platform. `available_formats()` and
`/health/ready` report which formats actually work.

## Reasoning

Making PDF a hard dependency would make `pip install` fail on Windows, blocking
everything for a feature no project needs yet. Silently skipping it would let a
reviewer click Export and get nothing.

Reporting the limitation on the health endpoint means it is visible before
anyone relies on it.

## Consequences

- Markdown and HTML always work.
- The deployed API image is Linux-based, where the GTK libraries install
  cleanly, so the live demo will have PDF available.
- `HtmlExporter` renders the markup WeasyPrint converts, so the two outputs
  cannot drift apart.
