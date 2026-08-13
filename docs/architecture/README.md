# Architecture

## Shape

A **modular monolith**, not microservices. One API process, one web app, and a
set of shared Python packages consumed in-process. CLAUDE.md Section 30 is
explicit that complexity should only be added where it demonstrates something
relevant — nine projects that each need their own deployment would demonstrate
the opposite.

```
                    ┌──────────────────────────┐
  browser  ───────► │  apps/web  (Next.js)     │
                    │  server components only  │
                    └────────────┬─────────────┘
                                 │ HTTP (server-side fetch)
                    ┌────────────▼─────────────┐
                    │  apps/api  (FastAPI)     │
                    └────────────┬─────────────┘
                                 │ in-process imports
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
┌──────▼───────┐        ┌────────▼────────┐       ┌────────▼────────┐
│  packages/   │        │   services/     │       │  packages/      │
│  ai          │        │   workflow-     │       │  database       │
│  adapters    │        │   engine        │       │  (Postgres +    │
│  config      │        │   analytics     │       │   pgvector)     │
│  utils       │        │   document-     │       └─────────────────┘
└──────────────┘        │   processing    │
                        └─────────────────┘
```

## Why the API keys never reach the browser

Every page is a React Server Component, and the only client component is the
sidebar (which needs `usePathname`). The browser talks to Next; Next talks to
FastAPI. No API key is ever serialised into a page payload, which is what
CLAUDE.md Section 24's "no API keys in frontend" requires structurally rather
than by convention.

## The three abstractions everything else hangs off

| Abstraction | Lives in | Why it exists |
|---|---|---|
| `AIProvider` | `packages/ai` | One AI integration, not nine. Adding a provider means implementing four primitives; the higher-level verbs (`summarize`, `classify`, `extract`, `analyze`) are derived once in the base class. |
| `EmailProvider` / `CalendarProvider` / `BookingProvider` | `packages/adapters` | The seam where a real integration would attach. v1 is mock-only, enforced in config. |
| `WorkflowEngine` | `services/workflow-engine` | One engine. Project 4 is a visual editor *on top of* it, not a second implementation. |

## Two design rules worth knowing before reading the code

**Demo Mode replays; it never invents.** `DemoProvider` reads recorded real
outputs from `data/demo-cache/`. When a recording is missing it raises
`DemoRecordingMissing` rather than producing something plausible. This is the
line CLAUDE.md Section 2 draws between "cached demo output" (required) and
"fake API responses" (banned), and it is enforced in code, not documentation.

**Missing cost data reports as missing.** `estimate_cost()` returns `None` for
a model with no price entry rather than guessing. For a portfolio arguing that
AI spend should be tracked, a plausible-but-wrong figure would undercut the
whole thesis.

## Package dependency direction

```
config  ◄── utils ◄── ai
                  ◄── database
                  ◄── adapters
                  ◄── workflow-engine
                  ◄── analytics
                  ◄── document-processing
```

Dependencies only point left. `config` and `utils` know nothing about AI,
databases, or HTTP, so they stay trivially testable and importable from
anywhere — including the standalone scripts.

## Where the database is optional

The API starts, serves, and reports healthy-but-degraded without
`DATABASE_URL`. That is deliberate: a reviewer should be able to run the
toolkit with no Postgres and no API key and still see it work. Projects that
genuinely need persistence check `settings.database_configured` and say so.

## Related documents

- [`../decisions/`](../decisions/) — the architectural decisions and their reasoning
- [`../business-cases/`](../business-cases/) — per-project problem and impact write-ups
