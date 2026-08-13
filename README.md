# AI Operations Toolkit

**An AI Operations Engineering portfolio, built for one specific role.**

A working platform of AI-assisted **workflows, SOPs, dashboards, trackers, and
automations** for a B2B travel-tech company — the kind where travel agents book
flights, hotels, and holidays, and an operations team keeps the on-ground
delivery working.

This is not a general AI showcase. Every project maps to a stated requirement of
the role it targets, and anything that could not be justified against that was
cut or merged rather than kept for volume. The reasoning is on the record below.

> **Current state: Phase 0 complete.** The foundation is built, tested, and
> runs. None of the nine projects is implemented yet — the UI says so, and this
> README will not claim otherwise until they are.

---

## Projects

| # | Project | JD requirement it proves | AI capability | Business impact | Live demo |
|---|---------|--------------------------|---------------|-----------------|-----------|
| 1 | AI SOP Generator | Document and standardize scalable operational processes | Structured generation + citation-backed semantic search (pgvector) | TBM | planned |
| 2 | AI Operations Dashboard | Build dashboards; analyze operational data | Insight layer over deterministic trend/anomaly detection | TBM | planned |
| 3 | **AI Travel Operations** (flagship) | Identify operational bottlenecks and solve them using AI | Incident classification, affected-booking lookup, drafted agent comms | TBM | planned |
| 4 | AI Workflow Builder | Build AI-assisted workflows and automations | AI nodes inside a visual workflow editor | TBM | planned |
| 5 | AI Project Tracker | Own projects from planning to implementation; build trackers | Health assessment with stated reasoning | TBM | planned |
| 6 | AI Report Generator | Analyze operational data and identify improvements | Executive summary over existing analysis | TBM | planned |
| 7 | AI Operations Inbox | Build AI-assisted automations | Classification, thread summarisation, drafted replies | TBM | planned |
| 8 | AI Ops Command Center | Collaborate cross-functionally to drive execution | Daily Ops Brief aggregated from the others | TBM | planned |
| 9 | AI Meeting Assistant (stretch) | Collaborate cross-functionally | Whisper transcription + decision extraction | TBM | planned |

*TBM = to be measured, and it will be labelled a simulated demo estimate against
synthetic data, never a claim of real-world deployment.*

Build order and reasoning: [`CLAUDE.md`](CLAUDE.md) Section 8.

---

## Run it

**Prerequisites:** Node 20+, Python 3.12+. No database and no API key required.

```bash
git clone <this-repo>
cd "AI OPERATIONS TOOLKIT"

# 1. Python environment
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python     -m pip install -r requirements-dev.txt   # macOS / Linux

# 2. JavaScript
npm install

# 3. Synthetic datasets
npm run demo-data

# 4. Start both services
npm run dev
```

Then open **http://localhost:3000**. The API is at **http://localhost:8000**,
with interactive docs at **/docs**.

There is no login screen and no setup wizard. The app runs in Demo Mode by
default, reports exactly which of its dependencies are configured, and works
without any of the optional ones.

### Optional extras

```bash
cp .env.example .env         # only if you want live AI or a database

docker compose up -d db      # Postgres 17 with pgvector, if you want persistence
npm run record-demo          # record real AI outputs for Demo Mode (needs a key, costs money)
```

---

## The two modes

CLAUDE.md Section 3b requires the toolkit to be usable by a reviewer with zero
API keys, without ever blurring real AI work and canned output. Both modes are
labelled in the header on every page.

| | Demo Mode *(default)* | Live |
|---|---|---|
| Needs an API key | No | Yes |
| Where output comes from | Recorded real responses, replayed | The provider, live |
| Cost | Zero | Billed to your account |
| Missing data behaviour | **Says so and stops** | n/a |

**Demo Mode cannot invent an answer.** If no recording exists for a request it
raises an error naming the fix. That is the line between a cached demo output
(required) and a fake API response (banned) — enforced in code, not in a
comment. See [`docs/decisions/0002`](docs/decisions/0002-demo-mode-replays-real-outputs.md).

A technical reviewer who wants to verify the AI is real can paste their own key
in the UI and watch it run live.

---

## Architecture

```
/apps
  /web                     Next.js 16 · TypeScript · Tailwind · server components only
  /api                     FastAPI · health checks · global error handling

/packages
  /ui                      Shared React components
  /types                   TypeScript types mirroring the API
  /ai                      AIProvider abstraction: Anthropic · OpenAI · Gemini · Demo
  /database                PostgreSQL + pgvector · activity log
  /adapters                Email / Calendar / Booking adapters — mock only in v1  ← addition, see ADR 0006
  /config                  Validated settings, single source of truth
  /utils                   Structured logging · IDs · typed errors · timing

/services
  /workflow-engine         The engine. Project 4 is a UI on top of it, not a second one.
  /analytics               Deterministic profiling, trend and anomaly detection
  /document-processing     Markdown / HTML / PDF export, built once

/projects                  Nine project directories (READMEs only — none built yet)
/docs                      architecture · business-cases · decisions
/scripts                   Demo data generator · demo output recorder
/tests                     83 tests
/.github/workflows         CI: lint · typecheck · test · build · secret scan
```

Detail: [`docs/architecture/`](docs/architecture/README.md).

### Technology

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind v4 | Server components keep every API key server-side by construction |
| Backend | FastAPI, Pydantic v2 | Typed request/response models the frontend types mirror |
| Database | PostgreSQL 17 + pgvector | Semantic search without a second vector database |
| AI | Anthropic (default), OpenAI, Gemini | Swappable behind one interface; embeddings and Whisper route to OpenAI, since Anthropic offers neither |
| Workflow | Custom engine | Human approval enforced structurally, not by convention |
| Quality | ruff, mypy, pytest, ESLint, tsc | All green, all in CI |

---

## Design rules the code actually enforces

Six rules that CI would fail if broken:

1. **Demo Mode replays, never invents.** No code path can produce an unrecorded answer.
2. **Unknown cost reports as unknown.** `estimate_cost()` returns `None` rather than a plausible guess — for a portfolio arguing AI spend should be tracked, a wrong figure would undercut the argument.
3. **Human approval is structural.** The workflow engine halts at approval gates; `send_reply()` requires an approver argument.
4. **Observation ≠ hypothesis.** Analysis output separates what the data shows from what might explain it. Never a fabricated cause.
5. **No real airline, GDS, or payment system.** `BookingProvider` declares no write method, and a test fails if one appears.
6. **No secrets past the server.** Only `Settings.redacted()` crosses an HTTP boundary.

---

## What was cut, and why

Prioritisation is itself part of what this role screens for, so the reductions
are on the record rather than silently dropped.

| Cut or merged | Outcome | Reasoning |
|---|---|---|
| AI Avatar / motion transfer | **Cut entirely** | Zero relevance to operations. Different engineering domain, GPU dependency, and consent/licensing overhead for no interview payoff. |
| Standalone KPI Analyzer | **Merged** into the Dashboard | Three projects running near-identical trend analysis reads as padding, not depth. |
| Standalone Knowledge Base | **Merged** into the SOP Generator | Same technology (embeddings + citations), attached to a named deliverable instead of a generic RAG demo. |
| Standalone CRM Assistant | **Folded** into Travel Operations | A generic leads/deals CRM has no anchor here. A travel-agent partner tracker inside the flagship does. |
| Document Processor | **Demoted** to a shared service | It was infrastructure for two other projects, not a project. |

Fourteen ideas became nine projects. Depth and relevance over volume.

---

## Why this portfolio exists

The role's core responsibility line is *"build AI-assisted **workflows, SOPs,
dashboards, trackers, and automations**"*, and it explicitly asks for hands-on
experience using AI tools in day-to-day work.

Every project here maps to one of those five nouns, or directly mirrors the
business — agents booking flights, hotels, and holidays, plus on-ground
delivery. The flagship is a working simulation of that business.

"Hands-on experience using AI tools" is why the AI has to visibly do the work
rather than decorate a screen — and why Demo Mode is built the way it is. A
demo that fakes its output would prove the opposite of the point.

---

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — the full specification this is built against
- [`docs/architecture/`](docs/architecture/README.md) — system design
- [`docs/decisions/`](docs/decisions/) — architectural decisions with reasoning
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — conventions and quality gates
- [`SECURITY.md`](SECURITY.md) — what the code refuses to do, and where that is enforced

## Responsible AI

All data is synthetic. No real person, agency, booking, or email appears
anywhere. AI recommendations carry a reasoning summary and a confidence level,
high-risk actions require human approval, and the activity log records model,
duration, tokens, and cost — but not prompt or response bodies.

## License

MIT — see [`LICENSE`](LICENSE).
