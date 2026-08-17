# AI Ops Command Center

Project 9 of the AI Operations Toolkit (CLAUDE.md Section 17). Built last,
because it aggregates what the others produce.

**Status: shipped.** Live at
**https://ai-operations-toolkit-web.vercel.app/command-center**

## Problem

By the time the toolkit had four working projects it had four places to look.
Overdue tasks are in the tracker. A workflow run paused for approval is in the
builder. An incident nobody has assessed is in travel operations. An anomaly in
the numbers is on the dashboard.

Each of those is somebody's job, and each is visible — but only to whoever
remembers to open that page. The failure is not that a signal is missing; it is
that nothing puts them side by side, so the one that mattered most today is
whichever page got opened first.

## Which JD requirement this proves

Collaborating cross-functionally to drive execution: a single operational view
across four separate systems, where each item is traceable back to the team and
tool that owns it.

## Who Uses It

An operations lead at 9am, deciding where the day goes.

## Business Impact

| | |
|---|---|
| Manual process | ~35 min/day: open four tools, read each, decide what matters |
| With this | ~5 min: one ranked list, one paragraph, links into whatever needs opening |
| Saving | ~2.5 hours/week ≈ 130 hours/year |

*Simulated demo estimate against the synthetic data in this repository. Not a
measured result and not a claim of real-world deployment (Section 19).*

## Features

- **One ranked list** of everything needing attention across four projects
- **Every item links back to its source** — the project that owns it, at the
  specific task, workflow or incident where possible
- **Source health strip**: whether each of the four answered, and what it said
- **Daily Ops Brief** — the one AI feature, one request, behind a button
- **Staleness detection** — "3 sources have changed since this brief was
  written", so a stored paragraph never poses as the current situation
- **Degrades honestly** — a failed source is named with its reason and the
  other three still produce a brief

## Architecture

```
Project 5  Tracker    ─┐   list_projects / list_item_of
Project 4  Builder    ─┤   list_workflows / issues_for / execution status
Project 6  Travel Ops ─┼─► signals.gather()  ─►  rank()  ─►  the page
Project 3  Dashboard  ─┘   analyse(load_sample(…))            │
                                                              └─► AI: the brief
```

### It aggregates; it does not recompute

This is the constraint Section 17 imposes, and it is the whole design. Every
collector calls the owning project's own read functions:

| Signal | Where the answer comes from |
|---|---|
| which tasks are overdue or blocked | Project 5's `list_item_of` |
| whether a project is RED, and why | Project 5's stored assessment, reasoning included |
| which runs are paused for approval | Project 4's execution status, set by the engine |
| which workflows cannot run | Project 4's `issues_for` |
| how severe an incident is | Project 6's stored assessment |
| how many bookings it affects | Project 6's deterministic lookup |
| what counts as an anomaly | Project 3, via the analytics service |

Where a source already phrases a fact, **that phrasing is reused verbatim**.
`Trend.describe()` and `Anomaly.describe()` are printed exactly as they come
back, so the sentence describing an anomaly is written once, in the service
that detects it. Change the wording there and it changes here, because there is
no second copy.

Two tests enforce this against the source itself: one asserts the collectors
contain no date arithmetic, no z-score thresholds and no task-status rules —
those belong to Projects 5, 6 and 3 — and one asserts the `describe()` calls
are still what produce the anomaly text.

### It stores almost nothing

One table, `ops_briefs`, holding the narrative the model wrote, the actions it
recommended, and the per-source signal counts at the time. Nothing about tasks,
workflows, incidents or metrics is copied here; all of it is re-read on every
request.

The stored counts earn their place. Comparing them against a fresh gather is
what lets the page say *"3 sources have changed since this brief was written"*.
A stored summary that cannot tell you it is stale is worse than no stored
summary at all.

### One source down does not take the page down

Each collector runs inside its own guard. A source that raises is reported as
unavailable **with the reason**, and the brief is produced from the rest. An
aggregator that goes blank because one of four inputs failed is worse than
useless: it hides the three that were working.

The reason is carried through rather than swallowed, because "unavailable"
alone gives an operator nothing to act on. Four parametrised tests break each
source in turn and assert the other three still report; a fifth breaks all four
and asserts the page still renders.

A brief generated while a source was down records which one, so it cannot later
be mistaken for a complete picture — and the prompt is told, so the model says
the picture is incomplete rather than writing a confidently whole-sounding
paragraph over three-quarters of the data.

### Ranking is computed, not asked for

`signals.rank` orders by a severity weight plus a magnitude bump. A model
deciding which of two problems matters more would be a judgement nobody could
check, and it would cost a request on every page load. The weights are crude on
purpose — they only have to put the urgent things near the top.

## AI Usage

One call. One button. One request.

| Call | Output | Constraint |
|---|---|---|
| Daily Ops Brief | a morning paragraph plus up to five actions | actions must cite a real signal id; invented ids have the reference dropped |

Opening the page costs nothing — no model is called by `GET /api/command-center`,
which is what makes it safe as the first page of the day. A test asserts three
page loads spend zero requests.

The model is told every figure is given and may not be re-derived. It is
interpreting a situation, not measuring one.

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL · the shared AI layer · Next.js,
TypeScript, Tailwind

## Setup

Nothing project-specific; installed via `requirements.txt`. One table,
`ops_briefs`, created by `create_all()`.

## Environment Variables

None of its own.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/command-center**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/command-center**

## Example

With the seeded data, the page ranks a paused workflow run and a RED project
above a 20% trend movement, and the brief reads:

> *"Two approvals are sitting unactioned — a workflow run paused mid-execution
> and drafted agency communications on the BOM-GOI delay — and neither moves
> until someone decides. The Refund turnaround programme is RED with two
> overdue tasks against a target nine days out."*

Every item under it carries an **Open in Project Tracker →** style link back to
the page that owns it.

## Limitations

- **Dashboard signals come from a bundled dataset.** The Operations Dashboard
  analyses an uploaded file and persists nothing, so there is no live KPI state
  to aggregate. The page names the dataset it read. Giving Project 3 a
  persistence layer purely so Project 9 could read it would be the duplication
  Section 17 forbids.
- **Project 8 is not built**, so there are no inbox signals yet. Section 17
  lists them; when the Operations Inbox ships it becomes a fifth collector and
  nothing else changes.
- **The brief is a model's opinion** of signals it did not produce. It is shown
  next to those signals so a reader can check it.
- **Ranking weights are crude.** They separate critical from noise; they are not
  a scheduling algorithm.
- **No per-signal dismissal or snoozing.** Everything is derived from source
  state, so a signal disappears when the underlying thing is fixed — which is
  the correct behaviour for an aggregator, but means you cannot silence one.
- **All data is synthetic.**

## Security

No secrets of its own. It performs no writes to any source project — every
collector calls read functions only, and the single table it owns holds nothing
but its own generated text. A compromised brief cannot alter a task, approve a
workflow, or close an incident, because this project has no code path that does
any of those things.

## Responsible AI

The model summarises; it never acts and never measures. Every figure in the
brief was collected before it was called, and the signals it summarises are
rendered on the same page so the paragraph can be checked against them.

An action citing a signal that does not exist has the reference stripped rather
than rendered as a working link to nothing. A brief written while a source was
unavailable records that fact and displays it, because a summary that looks
complete when it is not is the most damaging thing this page could produce.

## Future Improvements

- Add the Operations Inbox (Project 8) as a fifth collector once it ships
- A dated history of briefs, so "what did we say last Monday" is answerable
- Per-source refresh, so a slow source does not delay the whole page
