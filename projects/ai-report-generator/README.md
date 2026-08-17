# AI Report Generator

Project 7 of the AI Operations Toolkit (CLAUDE.md Section 15).

**Status: shipped.** Live at
**https://ai-operations-toolkit-web.vercel.app/reports**

## Problem

Someone assembles the weekly operations report by hand. They open the same
spreadsheet, recompute the same handful of numbers, remember roughly what last
week's were, and write four paragraphs around them. It takes most of a Friday
afternoon, and the part that took longest — the arithmetic — is the part least
worth a person's time.

The part that *is* worth their time, deciding what the movement means and what
to do about it, gets whatever attention is left at 5pm.

## Which JD requirement this proves

Analysing operational data and identifying improvement opportunities, and
documenting a standardised operational process — the same report, the same
sections, every period, without anyone having to remember the format.

## Who Uses It

An operations lead who has to circulate something on Friday, and the team who
read it on Monday.

## Business Impact

| | |
|---|---|
| Manual process | ~3 hrs/week: recompute the numbers, look up last period, write it up, format it |
| With this | ~20 min: pick the period, read the computed table, generate, edit, export |
| Saving | ~2.6 hours/week ≈ 135 hours/year |

*Simulated demo estimate against the synthetic datasets in this repository. Not
a measured result and not a claim of real-world deployment (Section 19).*

## Features

- **Daily, weekly and monthly** windows over any dataset
- **Period-over-period comparison** — every KPI against the same-length window
  before it
- KPI table, trends and anomalies, all computed
- **AI narrative**: executive summary, recommendations, action items
- Export to **PDF, Markdown and HTML** through the shared exporter
- Bundled datasets, or upload your own CSV/Excel

## Architecture

```
dataset ─► periods.split()        current window + the window before it
             │
             ├─► analyse(current)   ─┐  the Dashboard's own call
             ├─► analyse(previous)  ─┤
             │                       └─► compare()  → the KPI table
             └─────────────────────────► trends + anomalies, verbatim
                                              │
                                              └─► AI: the narrative
                                                       │
                                              shared exporter → PDF/MD/HTML
```

### What is reused, and what is new

Section 15 is explicit: *"reuse the trend/anomaly logic already built for
Project 3 rather than rebuilding it."*

| Piece | Where it comes from |
|---|---|
| KPI values, units, headline selection | `analyse()` — the Operations Dashboard's own call |
| Trend detection | the analytics service, via `analyse()` |
| Anomaly detection | the analytics service, via `analyse()` |
| The wording of a trend or anomaly | `Trend.describe()` / `Anomaly.describe()`, printed verbatim |
| Reading an uploaded CSV/Excel | `aiops_docproc.read_table`, with its existing size and type limits |
| PDF, Markdown, HTML rendering | `aiops_docproc.get_exporter` |

**The only new computation is `periods.py`**: slice a dataset into a window,
slice the window before it, and subtract one set of already-computed KPIs from
the other. That subtraction is what turns *"cancellations were 12.2%"* into
*"cancellations were 12.2%, up 9.8% on the previous week"* — which is the only
reason anyone reads a periodic report rather than a dashboard.

It is not a detector, and two tests hold that line: one asserts the package
contains no `z_score`, `std_dev`, `detect_trend` or `detect_anomalies`, and one
asserts the router contains no private renderer.

### Details in the period logic worth knowing

- **Windows anchor to the latest date in the data, not to today.** A dataset
  whose last row is three weeks old still produces a report about the week it
  covers. Anchoring to `today` would return a confidently empty report for
  every historical file.
- **The windows abut exactly** — no gap, no overlap. A day counted in both
  would corrupt the comparison in a way nobody would notice.
- **A previous value of zero withholds the percentage** rather than reporting
  infinity. The previous value is still shown, so a reader can see 0 → 5.
- **"No comparison available" and "0% change" are different**, and are never
  conflated. One means nothing to compare against; the other means nothing
  moved.
- **A dataset with no date column** reports on the whole file and says so.

## AI Usage

One call, behind one button, labelled with its cost.

| Call | Output | Constraint |
|---|---|---|
| Narrative | executive summary, recommendations, action items | every figure supplied; the model may not re-derive or introduce one |

The prompt carries the observed/hypothesis discipline from Section 11: state
what happened before saying what it might mean, mark a cause as a possibility,
and say the cause is not determinable when it is not. Action items must cite a
metric label that exists in the table; an invented one has the reference
stripped before the report is rendered.

**Computing the report costs nothing.** Selecting a dataset or changing the
period recomputes everything with no model involved, which is what makes it
reasonable to click around before deciding to spend a request.

Changing the dataset or the period **discards the narrative**, because prose
written about last week's figures sitting above this week's table is the exact
failure this project is meant to prevent.

## Tech Stack

Python, FastAPI, pandas · the analytics service, the Operations Dashboard's
analysis, the shared AI layer and document exporter · Next.js, TypeScript,
Tailwind

## Setup

Nothing project-specific; installed via `requirements.txt`. **No database
table** — see Limitations.

## Environment Variables

None of its own.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/reports**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/reports**

## Example

A weekly report on the bundled operations metrics:

Covering the last seven days in the dataset against the seven before them.
The dates move — the synthetic data is regenerated relative to the day it is
built — but the figures are stable, because the generator is seeded:

| Metric | This period | Previous | Change |
|---|---|---|---|
| Cancellation rate | 12.24% | 11.15% | ▲ +9.8% |
| On time departure | 89.37% | 83.58% | ▲ +6.9% |
| Avg resolution hours | 16.95 hrs | 13.74 hrs | ▲ +23.4% |
| Bookings cancelled | 12 | 8 | ▲ +50.0% |
| Bookings created | 72 | 91 | ▼ −20.9% |

Every number in that table was computed before the model was called. The
narrative it then writes refers to those figures and adds nothing numeric.

## Screenshots

Not committed — see the live demo.

## Limitations

- **Nothing is stored.** A report is derived from a dataset and a period, so a
  saved copy would be a stale duplicate of something reproducible. The exported
  document is the artifact. The consequence is real: an *uploaded* file is not
  kept, so regenerating its report means uploading it again.
- **Monthly reports need 60 days of data** to have a full comparison window.
  The bundled dataset has 91 days, so monthly comparisons work but there are
  only three such windows in it. The page states the window it actually used
  rather than implying more.
- **Periods are fixed lengths** — 1, 7 and 30 days — not calendar boundaries. A
  "monthly" report is the last 30 days, not the last calendar month.
- **The narrative is a model's opinion** of computed figures. It sits below the
  table it describes so it can be checked against it.
- **No scheduling.** Reports are generated when someone asks. Emailing one every
  Friday needs the automation layer, not this project.
- **All data is synthetic.**

## Security

No secrets of its own, and no database. Uploads go through the same
`read_table` path as the Dashboard, inheriting its size limit and file-type
validation; an unsupported file is refused before anything parses it. The
export endpoint renders only what it is given and reads nothing from disk.

## Responsible AI

The model writes prose and nothing else. It cannot change a figure, because
every figure is computed before it is called and passed in as given — and the
table it describes is rendered on the same page, above it.

The prompt requires an observation before an interpretation, requires a
suggested cause to be marked as a possibility, and explicitly permits "the
cause is not determinable from this data" as an answer. A report that presents
a guess about *why* a number moved as though it were a finding is the specific
failure that teaches an operations team to stop reading reports.

Action items citing a metric that is not in the table have the citation removed
rather than rendered as a pointer to nothing.

## Future Improvements

- Calendar-aligned periods (last calendar month, ISO weeks)
- Scheduled generation, once an automation layer exists to run it
- Compare against the same period last year, not only the preceding one
