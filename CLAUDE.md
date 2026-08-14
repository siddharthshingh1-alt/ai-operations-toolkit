# MASTER PROMPT — AI OPERATIONS TOOLKIT
### (v2 — edited and aligned to a specific job target)

You are my senior software architect, AI engineer, product engineer, and technical mentor.

I am building a portfolio project to get hired as an **AI Operations Associate** at a
B2B travel-tech startup based in Delhi (Connaught Place). This is not a generic AI
portfolio — every project must be defensible in an interview against the actual job
description below. If a feature can't be justified against it, cut it.

---

# 0. TARGET JOB — READ THIS FIRST

**Company:** B2B travel-tech startup. Enables travel *agents* (not end consumers) to
book flights, hotels, and holidays, and provides end-to-end on-ground travel services.
₹1000cr+ GMV, funded, high-growth.

**Role:** AI Operations Associate. Core responsibility line, verbatim from the JD:

> "Build AI-assisted **workflows, SOPs, dashboards, trackers, and automations**."

Other JD requirements that matter for scoping:

* Identify operational bottlenecks and solve them using AI.
* Analyze operational data and identify improvement opportunities.
* Collaborate cross-functionally to drive execution.
* Own projects from planning to implementation.
* Document and standardize scalable operational processes.
* "Hands-on experience using AI tools in day-to-day work" is explicitly called out —
  this means AI must visibly *do the work*, not just decorate a UI.

**What this means for scope:** every project in this toolkit must map to one of the
five nouns above (workflows / SOPs / dashboards / trackers / automations), or directly
mirror this company's actual business (agents booking flights/hotels/holidays +
on-ground delivery). Projects that don't map to either are cut or reframed below.
This is a deliberate reduction from a broader 14-project idea to a sharper 8-project
portfolio — depth and relevance over volume.

---

# 1. CORE OBJECTIVE

Build a production-quality, working portfolio — called the **AI Operations Toolkit** —
demonstrating:

1. AI-assisted SOP creation and standardization
2. Operational dashboards and KPI/anomaly analysis
3. Visual workflow automation
4. Project/task tracking with AI health assessment
5. Travel-operations simulation (flagship — mirrors the target company's business)
6. Operational reporting
7. Operations-inbox triage and automation
8. Cross-functional "ops command center" aggregation

For every feature, think:

INPUT → PROCESS → AI/LOGIC → ACTION → OUTPUT → METRIC

Example:

Booking delay alert
→ classify severity
→ find affected bookings
→ draft agent communication
→ human approval
→ send
→ track resolution time

---

# 2. IMPORTANT DEVELOPMENT RULE

DO NOT build everything at once.

Work incrementally, one project fully finished before the next starts:

1. Inspect the environment.
2. Decide the architecture.
3. Create the monorepo.
4. Set up the development environment.
5. Create shared infrastructure.
6. Build one complete application.
7. Test it.
8. Document it.
9. Deploy it (see Section 3a — this is non-optional, not a "someday" step).
10. Then move to the next application.

Never create huge amounts of untested code.

After every major implementation:

* run tests
* run linting
* run type checking
* run the application
* verify the feature
* fix errors before continuing

If something cannot be implemented immediately, create a clean abstraction/interface
rather than fake functionality.

DO NOT create fake API responses and pretend they are real AI functionality.

DO create realistic **cached/demo AI outputs** behind an explicit "Demo Mode" toggle
(see Section 3b) — that is different from faking functionality, and is required.

---

# 3. RECOMMENDED TECH STACK

Frontend:

* Next.js, TypeScript, Tailwind CSS, shadcn/ui
* **React Flow (xyflow)** for the visual workflow editor (Project 4) — do not build a
  drag-and-drop canvas from scratch.
* Recharts for charts

Backend:

* Python, FastAPI

AI provider abstraction — support OpenAI, Anthropic, Google Gemini, swappable:

```
AIProvider
├── OpenAIProvider
├── AnthropicProvider
└── GeminiProvider
```

* **Speech-to-text:** Whisper API (or `faster-whisper` locally) for the Meeting
  Assistant's audio input. This was previously unspecified — it is now required if
  audio input ships; otherwise scope Meeting Assistant to transcript/notes-only for v1
  and mark audio as a stretch goal.

Database:

* PostgreSQL, with the **`pgvector`** extension enabled (needed for SOP semantic
  search — see Project 1). Do not introduce a separate vector DB (Pinecone/Weaviate) —
  that violates the "don't overengineer" rule in Section 34.

ORM: SQLAlchemy or SQLModel. Validation: Pydantic.

Authentication:

* Ship the auth abstraction (interface only), but default to a **single demo-user
  mode** with no signup wall. A reviewer should never hit a login screen before seeing
  the product. Full Supabase Auth can be wired in later without changing the interface.

Storage: Supabase Storage or local storage abstraction for development.

Background jobs: FastAPI background tasks initially; architect so Celery/RQ/Redis can
be added later without a rewrite.

Document processing: PyMuPDF, python-docx, pandas, openpyxl.

**PDF generation:** `WeasyPrint` (preferred) or `reportlab`. This was previously
required by three different projects (SOP Generator, Report Generator, Document
Processor) but never specified — build it once as a shared exporter, not three times.

Testing: pytest, Playwright for critical frontend flows.

Code quality: ESLint, Prettier, Ruff, mypy where practical.

Containerization: Docker, docker-compose (for local dev only — see 3a for the deployed
version, which should not require Docker to evaluate).

**CI:** GitHub Actions running lint + typecheck + test on every push. This was
previously missing. A `.github/workflows/ci.yml` that's green is cheap and high-signal
for a reviewer skimming the repo.

---

# 3a. DEPLOYMENT (NON-OPTIONAL — NEW)

A hiring manager will not clone this repo, install Docker, stand up Postgres, and
supply API keys just to look at it. Every shipped project needs a **live URL**.

* Web → Vercel
* API → Railway or Render
* DB → Supabase or Neon (managed Postgres with pgvector support)

Each project's README must link the live demo. If only one project is deployed while
others are in progress, that's fine — but "clone and run locally" cannot be the only
way to evaluate this portfolio.

---

# 3b. DEMO MODE AND LIVE MODE (NON-OPTIONAL)

Every project must work for a reviewer who supplies **zero API keys**. Two mechanisms
satisfy that, and which one the *public deployment* uses was revised on 2026-08-15.

**The public deployment runs LIVE AI, not recordings.**

The original decision was the reverse: Demo Mode public, so no key sat on a public
server and no visitor could spend quota. That reasoning was sound and was rejected
anyway, because of what it cost. The portfolio's central claim is that AI does real
work here. A visitor who types their own question and is told "no recording for this"
has been shown the claim being *declined*, precisely at the moment they tried to test
it. Protecting a free-tier quota is not worth failing the one interaction that
matters.

The trade being accepted, stated so nobody has to reconstruct it later:

* A real key sits in the API's environment. It is `sync: false` in `render.yaml`,
  exists only in the API process, and can never reach the browser — the web app calls
  the API from its own server, and `Settings.redacted()` is an allowlist that cannot
  serialise a secret even by mistake. **This property is not negotiable in any future
  change.**
* Visitors spend real quota. On a free tier with no billing attached, the ceiling is
  a quota error rather than a bill. Use a key from a project with **no billing
  account**, or a hard budget cap.
* The quota will sometimes be exhausted. That is an expected end state, not a fault,
  and must surface as `AIQuotaExhausted` — a plain-language message naming the free
  tier and telling the visitor to come back tomorrow. Never a raw provider error.

**Demo Mode remains, as the fallback and the test path.** `DEMO_MODE=true` replays
recorded real outputs from `data/demo-cache/`. Local development and CI use it, so
the test suite needs no key and spends no quota. The recordings stay in the
repository; the public default is one environment variable away from reverting.

Rules that did not change:

* Clearly label which mode is active in the UI at all times. Never blur the two.
* Demo Mode replays an output a real model really produced. It never simulates one.
  This is what separates it from "fake functionality" (banned in Section 2).
* A "bring your own key" path lets a reviewer supply their own key. **Status: not
  implemented.** `ALLOW_BRING_YOUR_OWN_KEY` is honoured by `get_provider()`, but no
  UI collects a key. With the public demo now live by default this is far less
  pressing than it was, but it is still owed — and until it is built, no README, UI
  or document may describe it as available.

---

# 3c. MOCK-FIRST INTEGRATIONS (RESOLVES A PREVIOUSLY UNRESOLVED GAP)

Executive/Ops Command Center, Operations Inbox, and Travel Operations all previously
implied real integrations (Gmail, Google Calendar, a real airline/GDS, a real
payments system) without ever deciding whether that was in scope. Decision:

* **v1 for all projects = mock/simulated data**, generated by the scripts in
  Section 24, behind a clean adapter interface (`EmailProvider`, `CalendarProvider`,
  `BookingProvider`) — the same pattern as the `AIProvider` abstraction.
* Real OAuth integrations (Gmail API, Google Calendar API) are an explicit, clearly
  labeled **future improvement**, not a v1 requirement. Do not silently start building
  OAuth flows without approval — that's exactly the kind of "major architectural
  change" Section 33 says to stop and ask about.
* Never connect to a real airline/GDS or real payment system, in any version. Section
  19's original rule stands and is reinforced, not relaxed.

---

# 3d. COST TRACKING (NEW)

Log **tokens used and estimated $ cost** per AI call in the Activity Log (Section 26),
alongside model, duration, and status. For a portfolio aimed at an *AI-first
operations* role, visibly tracking AI spend is on-thesis, not a nice-to-have — it's
the kind of operational discipline the JD is screening for.

---

# 4. ARCHITECTURE

```
/apps
  /web
  /api

/packages
  /ui
  /types
  /ai
  /database
  /config
  /utils

/services
  /document-processing
  /analytics
  /workflow-engine

/projects
  /ai-sop-generator          (Project 1 — includes searchable SOP library)
  /ai-meeting-assistant      (Project 2 — stretch/secondary)
  /ai-operations-dashboard   (Project 3 — includes KPI/anomaly analysis)
  /ai-workflow-builder       (Project 4)
  /ai-project-tracker        (Project 5)
  /ai-travel-operations      (Project 6 — FLAGSHIP)
  /ai-report-generator       (Project 7)
  /ai-operations-inbox       (Project 8 — was "Email Assistant")
  /ai-ops-command-center     (Project 9 — was "Executive Assistant / Founder OS")

/docs
  /architecture
  /business-cases
  /decisions

/scripts
/tests
/.github/workflows
```

Cut entirely: `/projects/ai-avatar-motion`. See Section 22.
Removed as standalone: `/projects/ai-kpi-analyzer` (merged into dashboard),
`/projects/ai-knowledge-base` (merged into SOP generator),
`/projects/ai-crm-assistant` (folded into Travel Operations as a partner/agent
relationship module — see Project 6).
`/projects/ai-document-processor` is demoted from a standalone numbered project to a
shared service (`/services/document-processing`) consumed by SOP Generator and
Report Generator. Give it a thin UI only if time remains after the 9 phases below.

Each project should be independently understandable but reuse shared infrastructure.

---

# 5. DESIGN PRINCIPLES

(Unchanged from v1 — these were already correct.)

## Business-first

Every application must start with: Problem, Users, Current manual process,
Bottleneck, AI opportunity, Workflow, Expected business impact.

## Human-in-the-loop

AI should not automatically execute high-risk actions without confirmation.

AI drafts email → human approves → system sends.
AI classifies a booking issue → human reviews.
AI detects an operational anomaly → human confirms before action.

## Explainability

Whenever AI makes an important recommendation, provide: reasoning summary,
confidence where appropriate, source/input used, recommended action. Do not expose
hidden chain-of-thought — provide concise decision explanations instead.

## Auditability

Record: who initiated an action, when, what input was used, what AI model was used,
what output was generated, whether a human approved it, and (new) token/cost.

## Privacy

No hard-coded secrets. Environment variables only. Never commit `.env`, API keys, or
real personal information. Create `.env.example`.

---

# 6. SHARED AI LAYER

Reusable AI service interface:

```
generate_text()
generate_structured_output()
summarize()
classify()
extract()
analyze()
generate_embeddings()
transcribe()   // NEW — wraps Whisper, needed by Meeting Assistant
```

Use structured outputs wherever possible, e.g.:

```
ClassificationResult:
{
  category,
  priority,
  confidence,
  reasoning_summary,
  recommended_action
}
```

No project should write its own AI API integration from scratch.

---

# 7. SHARED WORKFLOW ENGINE

A workflow: Trigger → Step → AI/Logic → Condition → Action → Output.

Example:

```
BOOKING_DELAY_DETECTED
→ classify severity
→ find affected bookings
→ if high severity
→ create operations task
→ draft agent communication
→ human approval
→ send
→ log event
```

Reusable nodes: Trigger, AI Classification, AI Extraction, AI Summarization,
Condition, Transform, Email, Webhook, Database, Notification, Human Approval.

**Important relationship clarification (new):** Project 4 (Workflow Builder) is the
*visual editor UI* on top of this engine — not a second, competing engine. Build the
engine once here in `/services/workflow-engine`; Project 4 is a client of it.

---

# 8. BUILD ORDER

Phase 0 → Project 1 → Project 3 → Project 6 (flagship) → Project 4 → Project 5 →
Project 7 → Project 8 → Project 9. Project 2 and a thin Document Processor UI are
stretch goals if time remains.

Rationale: SOP Generator first proves the AI layer and document generation cleanly
with the lowest complexity. Operations Dashboard next proves data analysis. Travel
Operations — the flagship, and the project most directly tied to the target company —
comes early enough to be a strong centerpiece, not an afterthought at project #12.
Workflow Builder and Project Tracker round out the JD's exact five nouns. Report
Generator, Operations Inbox, and Ops Command Center layer on top, with Command Center
last since it aggregates outputs from the others.

---

# 9. PROJECT 1 — AI SOP GENERATOR
### (now includes the former "Knowledge Base" project, folded in)

Build this FIRST.

**Purpose:** Turn messy operational knowledge into standardized, searchable SOPs.
Directly matches the JD's "document and standardize scalable operational processes."

Input: process description, optional documents, optional existing SOP, role,
department, objective.

AI output: SOP title, purpose, scope, prerequisites, roles, step-by-step procedure,
decision points, exceptions, escalation rules, checklist, KPIs, risks, improvement
suggestions.

Allow editing before saving. Export to PDF (via WeasyPrint) and Markdown. Version
history should support **diffing between versions**, not just a flat list of
snapshots.

**Folded-in capability (was Project "Knowledge Base"):** once multiple SOPs exist,
make them semantically searchable using `pgvector` embeddings. When answering a
question, always show which SOP(s) support the answer. If nothing relevant is found,
say so explicitly — do not hallucinate an answer. This gives you the "searchable
knowledge base with citations" capability without a 15th standalone project.

Add version, owner, effective date, review date, status fields.

---

# 10. PROJECT 2 — AI MEETING ASSISTANT (secondary / stretch)

Input: audio file (via Whisper transcription), transcript, or meeting notes.
Output: summary, decisions, action items, owners, deadlines, risks, unresolved
questions, follow-up email draft.

Action item schema: `{ title, owner, deadline, priority, status }`.

Simple task tracker: TODO / IN_PROGRESS / BLOCKED / DONE.

Build this only after the core 6 (Sections 9, 11–15) are working — it supports
"collaborate cross-functionally" but isn't in the JD's core five nouns.

---

# 11. PROJECT 3 — AI OPERATIONS DASHBOARD
### (now includes the former "KPI Analyzer" project, merged in)

Upload CSV/Excel. Automatically identify important columns using **type inference
(numeric/date/categorical) and name-based heuristics first** — use AI only for the
insight/labeling layer on top, not for basic type detection. This keeps cost down and
reduces hallucination risk.

Generate: KPI cards, charts, tables, AI insights, recommendations.

**Deep-analysis mode (was the standalone KPI Analyzer project):** trend detection,
anomaly detection, and "possible cause" hypotheses — clearly separated from fact.

Format, always:

```
Observed:      "Cancellation rate increased from 8% to 13%."
Hypothesis:    "Possible contributor: increase in delayed flights."
Recommendation:"Investigate cancellations by route and airline."
```

Never present speculation as fact. Never fabricate causes.

---

# 12. PROJECT 4 — AI WORKFLOW BUILDER

Visual workflow editor using **React Flow**, built on top of the shared workflow
engine (Section 7) — this project is the UI, not a second engine.

Example flow:

```
Booking complaint
→ classify
→ priority
→ assign team
→ draft response
→ human approval
→ send
→ close
```

Store workflows in PostgreSQL. Create a workflow execution log.

---

# 13. PROJECT 5 — AI PROJECT TRACKER

Track: Projects, Tasks, Owners, Deadlines, Dependencies, Risks, Blockers.

AI features: summarize project health, identify overdue tasks, identify blockers,
suggest next actions, generate weekly status report.

Health status: GREEN / YELLOW / RED — AI must explain *why* it assigned the status
(reasoning summary, not just a label).

No changes from v1 — this was already well-scoped and cleanly JD-aligned.

---

# 14. PROJECT 6 — AI TRAVEL OPERATIONS (FLAGSHIP)
### (now includes a lightweight partner/agent relationship module — was "CRM Assistant")

This is the most important project in the portfolio: it's a working simulation of
the target company's actual business model — B2B, agents booking flights/hotels/
holidays, plus on-ground delivery.

Track: Bookings, Customers (travel agents, not end consumers), Flights, Hotels,
Delays, Cancellations, Refunds, Support tickets.

AI can: classify incidents, identify urgent bookings, summarize customer issues,
draft agent communication, create action items, identify affected bookings.

Example flow:

```
Flight delay detected
→ find affected bookings
→ classify severity
→ create operations task
→ draft communication
→ human approval
```

**Folded-in module (was the standalone "CRM Assistant" project):** since travel
agents *are* this company's customers, add a lightweight agent/partner relationship
view — agent activity, booking volume, open issues, last contact, next follow-up.
This is deliberately scoped as "built-in to this project's data model," not a
generic Salesforce-style CRM and not a separate numbered project.

Use only mock/demo data (Section 3c). Do NOT connect to a real airline, GDS, or
payment system, in any version.

---

# 15. PROJECT 7 — AI REPORT GENERATOR

Input: CSV/Excel/database data (can reuse Operations Dashboard's data model).
Generate: Daily/Weekly/Monthly report — executive summary, KPI table, trends,
anomalies, recommendations, action items.
Export: PDF (WeasyPrint), Markdown, HTML.

Keep this scoped as "reporting on top of existing data," not a new analysis engine —
reuse the trend/anomaly logic already built for Project 3 rather than rebuilding it.

---

# 16. PROJECT 8 — AI OPERATIONS INBOX
### (renamed and reframed from "Email Assistant")

Reframed around this company's actual operational email flow, not a generic personal
inbox: booking confirmations, delay/cancellation alerts, travel-agent partner
emails, vendor/hotel communication.

Features: classify incoming email, identify urgency, summarize long threads, extract
tasks, draft reply, suggest follow-up, detect unanswered emails.

Categories (reframed for this business): Agent Partner, Booking Ops, Vendor/Hotel,
Finance, Internal, Urgent, Other.

Never automatically send emails without explicit human approval. Uses the mock
`EmailProvider` adapter from Section 3c — this can plug directly into Travel
Operations rather than standing fully alone.

---

# 17. PROJECT 9 — AI OPS COMMAND CENTER
### (renamed and reframed from "Executive Assistant / Founder OS")

The original "Executive Assistant" framing was a mismatch for an *Operations
Associate* role — calendar/email personal-assistant framing reads as EA work, not
ops work, and could raise an odd question in an interview ("why build a founder's
calendar tool for an ops role?"). Reframed as an **operations aggregation
dashboard**, built last, once the other projects exist to aggregate from.

Combine: operational KPIs (from Project 3), open workflow executions (Project 4),
task/project status (Project 5), travel-ops alerts (Project 6), pending inbox items
(Project 8).

Generate a daily **Ops Brief**, e.g.:

```
Good morning.

3 high-priority tasks are overdue.
Cancellation rate is 8% above weekly target.
2 workflows are blocked awaiting approval.
4 booking-delay incidents need review.

Top 5 recommended actions today: ...
```

Every item must link back to its underlying source project — this is an aggregator,
not a new source of truth, and must not duplicate logic that already exists in
Projects 3, 4, 5, 6, or 8.

---

# 18. PROJECTS CUT FROM THIS PORTFOLIO (WITH REASONING)

Documented explicitly so the "why" is on record, not just silently dropped:

* **AI Avatar / Motion-transfer project** — cut entirely. Zero relevance to this JD
  or this company's business (video/generative-media engineering, not operations).
  It also carries disproportionate scope (GPU dependency, a different engineering
  domain) and responsible-use overhead (consent, licensing, identity concerns)
  relative to any interview payoff for *this specific role*. If you want to build it
  for other reasons, keep it in a fully separate, unrelated repo — don't dilute the
  operations narrative of this one.
* **Standalone KPI Analyzer** — merged into Operations Dashboard (Section 11). The
  JD says "dashboards," not "a dashboard and a separate KPI analyzer" — three
  projects doing near-identical trend/anomaly analysis would read as padding, not
  depth, to a reviewer.
* **Standalone Knowledge Base** — merged into SOP Generator (Section 9). Same
  underlying tech (embeddings + citations), stronger story attached to an actual
  JD-named deliverable (SOPs) instead of a generic RAG demo.
* **Standalone CRM Assistant** — folded into Travel Operations as the agent/partner
  module (Section 14). A generic leads/deals CRM has no JD or business-model anchor;
  a travel-agent partner tracker inside the flagship project does.

---

# 19. PROJECT METRICS

Every project needs a "Business Impact" section with a concrete before/after, clearly
labeled as a **simulated demo estimate**, not a real-world result:

```
Manual process:     12 hours/week
Automated process:   2 hours/week
Estimated saving:   10 hours/week ≈ 520 hours/year
```

Do not invent claims of real-world deployment or real users.

---

# 20. DEMO DATA

Realistic synthetic datasets, generated by scripts, never real people's data:

```
travel_bookings.csv
support_tickets.csv
sales_data.csv
employee_tasks.csv
operations_inbox_emails.csv
operations_metrics.csv
```

These datasets are also what powers Demo Mode (Section 3b) — build them early, they
unblock everything downstream.

---

# 21. UI DESIGN

Clean, minimal, professional, responsive, accessible. Sidebar layout: Dashboard,
Projects, Workflows, Documents, Tasks, Reports, Settings. Avoid flashy AI gimmicks —
this should look like an internal operations platform a serious startup actually
uses, not an AI demo site.

---

# 22. OBSERVABILITY

Activity log tracking: timestamp, user, project, action, AI model, status, duration,
error, **and token count / estimated cost (new — see Section 3d)**.

Do not log sensitive content unnecessarily.

---

# 23. ERROR HANDLING

Validation, retries, timeouts, clear error messages, provider failure handling,
file-size limits, unsupported-file detection, graceful AI failure. Never show raw
stack traces to normal users.

---

# 24. SECURITY

Environment variables, input validation, file-type validation, upload size limits,
authentication abstraction (default: single demo user, see Section 3), authorization
checks, safe file handling, no API keys in frontend, no secrets committed to Git.
Create `.env.example`.

---

# 25. TESTING

Per project: unit tests, integration tests, critical UI tests. At minimum test valid
input, invalid input, AI failure, empty data, large data, missing required fields.

Before considering a project complete, all of these must pass:

```
npm test / appropriate frontend test command
pytest
lint
typecheck
build
```

CI (Section 3) should run this automatically on every push.

---

# 26. DOCUMENTATION

Every project README:

```
# Project Name
## Problem
## Which JD requirement this proves        <- NEW, added deliberately
## Who Uses It
## Business Impact
## Features
## Architecture
## AI Usage
## Tech Stack
## Setup
## Environment Variables
## How to Run
## Live Demo                                 <- NEW
## Example
## Screenshots
## Limitations
## Security
## Responsible AI
## Future Improvements
```

The "Which JD requirement this proves" section is new and deliberate — it forces
every project to stay anchored to Section 0, and gives you the interview answer
already written down.

---

# 27. ROOT README

Present the portfolio as a focused, JD-aligned AI Operations Engineering portfolio,
not a generic AI showcase.

Include:

* "About" — one paragraph: what this is and which role/company it targets
* Projects table: `| Project | JD requirement it proves | AI capability | Business impact | Live demo |`
* Architecture diagram
* Technology stack
* Demo screenshots
* "Why this portfolio exists" — explicitly reference the five nouns from Section 0
* A short, explicit note on what was deliberately cut or merged and why (Section 18)
  — this signals prioritization judgment, which is itself a thing this JD screens for
  ("own operational projects from planning to implementation").

---

# 28. GITHUB QUALITY

Before pushing anything, check `git status`. Remove `.env`, credentials, API keys,
personal data, large generated files. Create `.gitignore`, `LICENSE`,
`CONTRIBUTING.md`, `SECURITY.md`, `.env.example`. Meaningful commits, e.g.:

```
feat: add SOP generation workflow
feat: add travel-ops delay-incident workflow
fix: handle failed AI provider response
```

Do not create fake commit history.

---

# 29. DEVELOPMENT WORKFLOW

You are my coding agent. When I give you a task:

1. Understand the existing architecture.
2. Inspect relevant files.
3. Explain your implementation plan briefly.
4. Implement it.
5. Run tests.
6. Fix errors.
7. Show me what changed.
8. Tell me exactly how to test it manually.
9. Update documentation if necessary.

Do not ask unnecessary questions. If there are multiple reasonable technical choices,
choose the simplest production-appropriate option and explain why. If a requirement
is ambiguous and could cause major architectural changes, stop and ask. Otherwise
make reasonable assumptions.

---

# 30. DO NOT OVERENGINEER

Prioritize working, understandable, testable, documented, demonstrable — over
complex microservices, Kubernetes, or premature scaling. Modular monolith by default.
Add complexity only when it demonstrates a meaningful engineering capability relevant
to Section 0.

---

# 31. CLAUDE CODE BEHAVIOR

You are allowed to: create files, modify files, install dependencies, run commands,
run tests, inspect logs, debug errors.

Before destructive operations: ask for confirmation. Never delete the whole
repository. Never overwrite unrelated projects. Never expose secrets.

---

# 32. FIRST TASK

DO NOT start building all applications.

**PHASE 0 — REPOSITORY FOUNDATION**

1. Inspect my current terminal/environment.
2. Check installed versions of: Node, npm/pnpm, Python, Git, Docker.
3. Recommend the package manager based on the environment.
4. Create the AI Operations Toolkit repository structure (Section 4 — note the
   reduced project list, do not scaffold the cut/merged projects).
5. Set up: Next.js frontend, FastAPI backend, shared configuration, AI provider
   abstraction (incl. the `transcribe()` method), PostgreSQL configuration with
   `pgvector` enabled, Docker configuration for local dev, environment
   configuration, the mock provider adapters from Section 3c.
6. Create a professional initial dashboard shell.
7. Create health-check endpoints.
8. Create basic test infrastructure.
9. Create `.github/workflows/ci.yml`.
10. Create README (root, reflecting Section 27).
11. Create `.env.example`.
12. Create `.gitignore`.
13. Run all tests and builds.

DO NOT build any of the 9 individual projects yet. DO NOT set up real OAuth
integrations — mock adapters only (Section 3c).

After completing Phase 0, stop and report:

1. What you built
2. Folder structure
3. Technology decisions
4. Commands used
5. Tests completed
6. Any problems
7. Exact command I should run to start the application

Then wait for my next instruction.

---

# IMPORTANT

The goal is not impressive-looking code. The goal is a portfolio a real hiring
manager at this specific company can open, run (via a live demo link, not a local
setup), understand in minutes, and connect directly to the exact responsibilities in
Section 0. Prioritize correctness, maintainability, business usefulness,
documentation, and demonstrable results over breadth.
