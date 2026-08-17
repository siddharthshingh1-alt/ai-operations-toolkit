# AI Project Tracker

Project 5 of the AI Operations Toolkit (CLAUDE.md Section 13).

**Status: shipped.** Live at
**https://ai-operations-toolkit-web.vercel.app/tasks**

## Problem

An operations lead runs six workstreams at once. The question they are asked in
every review is the same — *which of these is in trouble?* — and answering it
means opening six trackers, reading every task, remembering which deadlines
have passed, and working out which of the stalled items are stalled for the
same reason.

The information is all there. Nobody has time to assemble it, so the answer
gets given from memory, and the project that quietly slipped is the one nobody
mentions.

## Which JD requirement this proves

Builds **trackers** — one of the role's five nouns — and covers owning projects
from planning through to implementation, plus documenting and standardising the
status reporting around them.

## Who Uses It

An operations lead or programme manager who needs to know where to spend
Monday, and to circulate a status report on Friday without writing it by hand.

## Business Impact

| | |
|---|---|
| Manual process | ~3.5 hrs/week: reading six trackers, chasing status, writing the weekly report |
| With this | ~45 min: read the computed figures, press assess, edit the drafted report |
| Saving | ~2.75 hours/week ≈ 140 hours/year |

*Simulated demo estimate against the synthetic projects in this repository. Not
a measured result and not a claim of real-world deployment (Section 19).*

## Features

- Projects and tasks with owners, due dates, priorities and recorded risks
- **Task dependencies** — one task waits on another, and the tracker follows the
  chain to name the task actually holding things up
- **Blockers** with a reason, which is discarded when the task stops being blocked
- Overdue and blocked detection, computed exactly, on every read
- **AI health assessment: GREEN / YELLOW / RED, with required reasoning**
- AI next-action suggestions, tied to real task ids
- AI project summary, written for reading aloud in a standup
- **AI weekly status report** across every active project, exportable to PDF,
  Markdown and HTML through the shared exporter

## Architecture

```
Tasks in the database
  └─ facts.py            computed: overdue, blocked, dependencies, % complete
       └─ prompts.py     the figures, rendered as an evidence block
            └─ AI        judges them — health, actions, summary, report
                 └─ stored next to the figures it judged
```

### The split that defines this project

Section 13 lists "identify overdue tasks" and "identify blockers" as AI
features. They are computed in code here instead, and the model is handed the
answers.

| Computed in code | Asked of the model |
|---|---|
| which tasks are overdue | whether that adds up to GREEN, YELLOW or RED |
| which tasks are blocked | why, in terms of those figures |
| what waits on what | what to do next |
| completion percentage | how to say it in a standup |
| days to target | how it reads in a weekly report |

Three reasons. A date comparison is *exact*, and "usually right" is the wrong
property for the number a status report is built on. It is free and instant, so
the twenty-a-day request budget goes to the judgement rather than to
arithmetic. And it is the pattern the rest of this repository already follows —
the Dashboard infers column types in code, and Travel Operations looks up
affected bookings with no AI so the model cannot invent a booking reference.

### Reasoning is a schema requirement, not a prompt request

`HealthAssessment.reasoning` and `.contributing_factors` are required fields
with no defaults. A model that returns `{"health": "red"}` has produced an
**invalid response**: it fails validation inside the provider, nothing is
stored, and the caller gets an error rather than a label nobody can check.

A prompt that asks a model to explain itself is honoured most of the time. A
required field is honoured every time, or the response does not exist. Four
tests assert this directly, including one for reasoning that is present but
empty.

### Dependency cycles

`depends_on_id` is a plain foreign key, so a cycle is expressible. Two defences,
because either alone is insufficient:

1. **Write time** — creating or updating a dependency walks up the proposed
   chain and refuses an edge that closes a loop.
2. **Read time** — the walk that finds a task's real blocker is bounded and
   remembers where it has been, so a cycle that reached the database anyway
   terminates instead of hanging the request.

The write-time check cannot see a cycle formed by two concurrent writes. The
reader must survive whatever is on disk regardless.

## AI Usage

Four calls, each behind its own button, each one request, each labelled with
its cost before it is pressed. Nothing runs on page load.

| Call | Output | Constraint |
|---|---|---|
| Assess health | status, reasoning, contributing factors, confidence | reasoning and factors are required fields — a bare label is invalid |
| Next actions | 1–5 ranked actions with rationale | task ids must match real tasks; invented ones are dropped |
| Summarise | one prose paragraph | figures supplied; the model may not invent any |
| Weekly report | summary, highlights, concerns, risks, actions | one request for all projects, not one per project |

**The model never counts anything.** Every figure it reasons about is computed
first and passed in as a stated fact.

### When the free tier runs out

Added with this project, in the shared AI layer rather than here: Gemini calls
now walk a **model chain**. When the configured model reports its quota spent,
the same call is retried against the next model in `GEMINI_FALLBACK_MODELS`.

This helps when the free tier meters per model — the next model has its own
allowance. It does nothing when the cap is project-wide, and the error looks
identical either way, so it is an attempt rather than a guarantee and is
described that way in the UI. Only a spent quota advances the chain; a
malformed request fails immediately, because repeating it cannot help.

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL · the shared AI layer and document
exporter · Next.js, TypeScript, Tailwind

## Setup

Nothing project-specific; installed via `requirements.txt`. Two tables,
`tracked_projects` and `tracked_tasks`, are created by `create_all()`.

## Environment Variables

None of its own. It uses the shared AI and database settings, plus the new
optional `GEMINI_FALLBACK_MODELS` described above.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/tasks**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/tasks**

## Example

The seeded *Refund turnaround programme* has one task eight days overdue and
blocked on a vendor, one overdue draft task, and a pilot that cannot start
until the blocked integration lands. Pressing **Assess health** returns a
status with its justification attached:

> **YELLOW** — *"Two tasks are overdue and the vendor integration has been
> blocked for eight days, which also holds up the pilot scheduled in seven
> days. The target date is still nine days away, so the programme is
> recoverable if the vendor escalation lands this week."*
>
> Contributing factors: `2 tasks overdue` · `1 task blocked 8 days` ·
> `pilot waiting on blocked integration`

Every number in that sentence — two, eight, seven, nine — was computed before
the model was called and appears on the same page.

## Screenshots

Not committed — see the live demo.

## Limitations

- **Health is a model's opinion.** It is shown as one, with its reasoning next
  to the figures it was given, so a reader can disagree.
- **The dependency model is one edge per task.** A task waits on at most one
  other. A real programme has fan-in; this does not, deliberately — Section 30.
- **No notifications, no time tracking, no Gantt chart, no multi-user
  assignment.** None are in Section 13.
- **Single demo user.** Owners are free-text names, not accounts (Section 3).
- **The weekly report covers active projects only.** Paused and done projects
  are excluded rather than padding the report.
- **All data is synthetic.**

## Security

No secrets of its own. Dependency edges are validated server-side — self,
cross-project and circular are all refused — so a crafted request cannot create
a graph the reader has to defend against. Input length limits are on every
field. No user-supplied text reaches a shell, a file path or a query.

## Responsible AI

The model judges; it never acts. It cannot change a task, close a project, or
alter a figure — every AI route writes only to the assessment fields, and every
number it reasons about was computed before it was called.

A status is never shown without its reasoning, because the schema will not
produce one. Suggested actions referencing a task that does not exist have the
reference stripped before storage rather than being rendered as a working link
to nothing. Seeding installs projects but never a health label: a seeded
judgement would be exactly the fake functionality Section 2 bans.

## Future Improvements

- Fan-in dependencies (a task waiting on several others)
- Trend over time — health assessed weekly and charted, so a project that has
  been YELLOW for a month is visibly different from one that just turned
- Feed the tracker's overdue and blocked counts into the Ops Command Center
  (Project 9), which is designed to aggregate exactly this
