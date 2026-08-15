# AI Operations Dashboard

Project 3 of the AI Operations Toolkit. Includes the merged-in KPI Analyzer
(CLAUDE.md Sections 11 and 18).

## Problem

An operations team runs on exports. Somebody pulls a CSV of last quarter's
bookings, opens it in Excel, sorts a column, eyeballs it, and forms an opinion.
The opinion is usually about the thing that is easiest to see rather than the
thing that matters, and by the time it is written up the export is stale.

The slow part is not the analysis. It is that the analysis has to be redone by
hand for every new file, and that the interpretation lives in one person's head
until they find time to write it down.

## Which JD requirement this proves

> *"Build AI-assisted workflows, SOPs, **dashboards**, trackers, and automations."*
> *"Analyze operational data and identify improvement opportunities."*

Two of the five nouns, and the analysis line.

## Who Uses It

An operations associate or team lead with a data export and a question about it.
No SQL, no notebook, no BI licence.

## Business Impact

| | |
|---|---|
| Manual process | ~4 hours/week building a view of the week's operations by hand |
| With this | ~30 minutes reviewing a generated one |
| Estimated saving | ~3.5 hours/week ≈ 180 hours/year |

*Simulated demo estimate against the synthetic datasets in this repository. Not
a measured result and not a claim of real-world deployment (Section 19).*

## Features

- Analyse a bundled operations dataset in one click, or upload CSV/TSV/Excel
- Automatic column typing — dates, numbers, categories, identifiers, free text
- KPI cards with period-over-period movement
- Trend charts per metric, with statistically flagged points marked
- Anomaly detection (z-score) reported separately from trends
- AI insights in the mandated **Observed / Hypothesis / Recommendation** form
- Token, duration and cost reported for every AI call (Section 3d)

## Architecture

```
Upload or sample
  └─ aiops_docproc.read_table        parse + validate (shared with Project 7)
       └─ aiops_analytics            profile → detect_trend → detect_anomalies
            └─ aiops_dashboard.analysis    KPIs, series, preview   ← NO AI HERE
                 └─ aiops_dashboard.insights   the only AI call    ← AI HERE
```

The boundary in the middle of that diagram is the design. Everything above it
is arithmetic; everything below it is commentary. They are separate endpoints,
separate response types, and separately obtained in the UI.

**Why it matters practically:** the dashboard renders completely with no AI
available at all. When the free-tier quota is spent, a visitor loses the
commentary and keeps every number.

## AI Usage

One call, structured output only.

**The model never sees the data.** It receives the computed findings — a
handful of trend and anomaly sentences — and never a row of the file. It
therefore cannot invent a figure, because it is never in a position to produce
one; it can only restate what was measured. This also keeps the prompt small
enough to be cheap on a metered tier.

The response schema has three required fields per finding:

| Field | Contract |
|---|---|
| `observed` | Restates a supplied finding. A fact. |
| `hypothesis` | A *possible* contributor, phrased as a possibility. |
| `recommendation` | A concrete next step. |

"Never present speculation as fact" (Section 11) is enforced by the shape of
the response rather than by asking the model nicely, and the UI renders the
three with different labels and weights so they cannot be skim-read as one
paragraph.

Insights are generated **on a button press, never on page load** — see
*Limitations*.

## Tech Stack

Python, FastAPI, pandas, Pydantic · Next.js, TypeScript, Tailwind, Recharts

## Setup

Nothing project-specific. Follow the root README; this project is installed by
`-e ./projects/ai-operations-dashboard` in `requirements.txt`.

## Environment Variables

None of its own. It uses the shared `AI_PROVIDER` / key settings and honours
`DEMO_MODE` like every other project.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000** — the dashboard is the home page.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app**

The API sleeps after 15 minutes idle, so the first load can take up to a minute.

## Example

From the bundled `operations_metrics.csv` (90 days of operations):

```
Observed:       Cancellation rate moved from 6.26 to 12.24 (+95.5%) over 91 periods.
Hypothesis:     Possible contributor — the concurrent rise in average ticket
                resolution time, though the cause is not determinable from
                this data alone.
Recommendation: Break cancellations down by route and supplier for the last
                three weeks to see whether the increase is concentrated.
```

The +95.5% is computed by `detect_trend`. The model is given that sentence and
writes the two below it.

## Screenshots

Not committed — see the live demo.

## Limitations

- **Uploaded files are not stored.** Analysis happens in the request and the
  file is discarded. The database is public and shared, so persisting
  strangers' uploads would invite junk for no demo value. Saved dashboards are
  a future improvement, not a silent omission.
- **AI insights are behind a button.** The public deployment runs live on a
  free tier of roughly 20 requests a day, shared across every visitor. A
  dashboard that explained itself on load would spend that budget on people who
  never asked for an explanation. Identical findings reuse a cached answer.
- **Anomaly detection is a z-score test**, which assumes roughly normal
  variation. It will flag a legitimate seasonal peak. That is why flagged
  points are labelled "unusual" rather than "wrong", and why the reader can see
  the whole series around them.
- **Trends compare first and last values** over the ordered period. A metric
  that dips and recovers reads as flat, which is honest but coarse.
- **One chart per metric, one y-axis each.** Deliberate: two metrics of
  different scale sharing an axis is the most common way a chart misleads.

## Security

No secrets of its own. Uploads are validated for type, size (10 MB), row count
(100,000) and column count (200) before parsing, and every rejection returns a
typed error with a user-safe message — never a stack trace (Section 23).
Uploads reach the API through a server action, so the browser never holds a
credential.

## Responsible AI

The model interprets; it does not measure. It is never shown the raw data, it
cannot produce a number, and its speculation is structurally separated from
fact in both the schema and the interface. Where a cause is not determinable
from the data, saying so is a valid answer the prompt explicitly permits.

## Future Improvements

- Save a dashboard and share it by link
- Compare two periods side by side
- Seasonal decomposition, so a recurring peak stops being flagged as an anomaly
- Push the insight layer into the Report Generator (Project 7), which reuses
  this analysis rather than rebuilding it
