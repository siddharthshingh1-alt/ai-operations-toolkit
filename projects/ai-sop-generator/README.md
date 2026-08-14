# AI SOP Generator

Turns messy operational knowledge into standardised, versioned, searchable
standard operating procedures — and answers questions across them with
citations.

**Status: shipped.** Project 1 of 9, built first per CLAUDE.md Section 8.

## Problem

Operational knowledge lives in people's heads and scattered chat threads. When
a flight is delayed at 6am, three people handle it three different ways. New
joiners repeat old mistakes because nobody wrote the process down; when someone
does write it down, it goes stale because rewriting a document is nobody's job.

The cost is not the missing document — it is the inconsistency. Travellers hear
from the airline before their agent hears from operations, because there was no
agreed order of steps.

## Which JD requirement this proves

> **"Document and standardize scalable operational processes."**

Directly. A rough spoken-style description becomes a structured, owned,
versioned, reviewable procedure — which is what standardising a process
actually means in practice.

It also touches **"build AI-assisted SOPs"** from the core responsibility line,
and the folded-in search capability supports **"identify operational
bottlenecks"** by making the question *"do we even have a process for this?"*
answerable in seconds.

## Who Uses It

- **Operations leads** writing and maintaining SOPs.
- **Operations associates** searching them mid-incident, when there is no time
  to read a 12-page document.
- **New joiners**, whose first week is mostly "how do we do this here?"

## Business Impact

```
Writing one SOP by hand:        3.0 hours   (draft, structure, review, format)
With this tool:                 0.5 hours   (describe, review the draft, edit)
Saving per SOP:                 2.5 hours

Finding an answer mid-incident: 8 minutes   (search chat, ask a colleague)
With cited search:              30 seconds

At 2 new SOPs/month + 10 lookups/week:
  ≈ 5 hours/month writing + ≈ 5 hours/month lookups ≈ 120 hours/year
```

**Simulated demo estimate against synthetic data.** Not a measured result, not
a claim of real-world deployment, and there are no real users. The numbers are
plausible desk estimates for illustration only.

## Features

| Feature | Detail |
|---|---|
| **Generate** | A description becomes 13 structured sections: title, purpose, scope, prerequisites, roles, step-by-step procedure, decision points, exceptions, escalation rules, checklist, KPIs, risks, improvement suggestions |
| **Improve an existing SOP** | Paste a current SOP; what is correct and specific is kept, what is vague is fixed |
| **Read a document** | Upload a PDF, Word, or text file as source material |
| **Review before saving** | Every section editable. Nothing is stored until a human saves it |
| **Governance** | Owner, department, status (draft / active / under review / retired), effective date, review date |
| **Versioning** | Every save is a new immutable version with a change note and author |
| **Diffing** | Compare any two versions — section by section, line by line, with added/removed counts |
| **Export** | Markdown, HTML, and PDF |
| **Cited search** | Ask a question across the library; the answer shows which SOPs support it |
| **Honest gaps** | When no SOP is relevant, it says so instead of inventing one |
| **Cost tracking** | Tokens, duration, and estimated cost recorded per AI call |

## Architecture

```
projects/ai-sop-generator/aiops_sop/
  schema.py     The 13-section SOP shape, plus request/response models
  models.py     sops + sop_versions tables, with a pgvector embedding column
  prompts.py    Generation and answering prompts, in one reviewable place
  service.py    Generate, save, version — the AI never writes to the database
  search.py     Retrieval, the relevance floor, and cited answering
  diffing.py    Field-by-field, line-by-line version comparison
  router.py     HTTP layer (thin — all logic lives above)
```

Two tables rather than one. `sops` holds identity and governance; `sop_versions`
holds immutable content snapshots. That split is what makes diffing possible —
old versions are never overwritten, so any two can be compared.

The embedding lives on the *version*, and only the current version of each SOP
is searchable, so a retired procedure can never be returned as if it were live.

## AI Usage

**Generation** — one structured-output call producing the whole SOP, validated
against a Pydantic model. A response that does not fit the shape is a loud
failure, not a silent partial save.

**Search** — the question is embedded, compared against stored SOP embeddings
by cosine similarity in pgvector, and the top matches become the *only* source
material for the answer.

**The no-hallucination guarantee** is enforced two ways:

1. **A relevance floor (55% similarity).** If nothing clears it, the AI is
   never called — there is no source material, so there is no opportunity to
   invent. The response explains it is a gap.
2. **Citations come from retrieval, not from the model.** The model writes
   prose; the source list is built from what was actually retrieved. A model
   that invented a document name in its text still cannot produce a fake link.

Both are covered by tests in `tests/test_sop_search.py`.

## Tech Stack

Python · FastAPI · SQLAlchemy · PostgreSQL 17 + pgvector 0.8 · Pydantic v2 ·
Next.js 16 · TypeScript · Tailwind v4 · Google Gemini (`gemini-3.6-flash` for
writing, `gemini-embedding-001` at 1536 dimensions for search)

The embedding dimension is deliberate: Gemini returns 3072 by default, but
pgvector cannot build an index on vectors wider than 2000.

## Setup

From the repository root:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows
npm install
cp .env.example .env      # then fill in DATABASE_URL and GOOGLE_API_KEY
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL with pgvector. Paste a Supabase/Neon URI as-is; the driver name is added automatically |
| `GOOGLE_API_KEY` | Gemini key, from https://aistudio.google.com/apikey |
| `AI_PROVIDER` / `EMBEDDING_PROVIDER` | `gemini` for both |
| `GEMINI_EMBEDDING_DIMENSIONS` | `1536`. Changing it after SOPs exist requires re-embedding |
| `DEMO_MODE` | `true` replays recordings with no key; `false` calls the API live |
| `AI_MAX_OUTPUT_TOKENS` | `24576`. A full SOP plus Gemini's thinking tokens does not fit in less |

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/documents**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/documents**

No sign-up and no API key: the deployment runs in Demo Mode, replaying 12 real
recorded AI responses. Web app on Vercel, API on Render, Postgres + pgvector on
Supabase.

Worth clicking specifically:

- **PDF export** on any SOP — WeasyPrint's native libraries are present in the
  deployed container but not on a stock Windows machine, so this is the one
  feature the deployment has and local development does not.
- **Ask** *"What do we do if a hotel overbooks a confirmed room?"* — answered
  with the source SOPs shown.
- **Ask** *"How do I fix the office printer?"* — the relevance floor rejects it
  and the AI is never called, so the answer is an honest "no SOP covers this"
  rather than an invention. *(Demo Mode replays recorded outputs, so this
  demonstrates the refusal only once that question's embedding has been
  recorded — otherwise it reports a missing recording instead.)*

> The API sleeps after 15 minutes idle, so the first load can take up to a
> minute while it wakes.

## Example

**Input** — the kind of thing someone types in 30 seconds:

> "When a flight is delayed by more than three hours we need to work out which
> of our travel agents' bookings are affected, check whether any of those
> travellers have onward connections, and contact each agent with the rebooking
> or refund options. At the moment different people do this differently…"

**Output** — a full SOP with a numbered procedure, decision points, escalation
rules with time bounds, exceptions covering supplier non-response and fare-rule
blocks, KPIs, risks, and a checklist.

**Then**, asking *"How quickly must we contact agents after a delay?"* returns
the answer with the SOP that supports it and a match percentage.

**And** asking *"How do I reset the office wifi password?"* returns:

> No SOP in the library covers this. Rather than guess, this is being reported
> as a gap.
> *Searched 3 SOPs; the closest match scored 48%, below the 55% relevance
> threshold.*

## Screenshots

Not yet captured. To be added alongside deployment.

## Limitations

- **Demo Mode is prompt-exact.** A recording replays only for the exact input it
  was recorded for, so Demo Mode offers three preset examples. Free-typed input
  needs a live key. This is a consequence of replaying real outputs rather than
  simulating them, and is the honest trade.
- **PDF export needs server-side libraries.** WeasyPrint's native dependencies
  are absent on stock Windows; Markdown and HTML always work, PDF works on the
  Linux deployment.
- **Cost shows as unpriced for Gemini.** Token counts are tracked, but no
  verified price table entry exists for Gemini models, so estimated cost reports
  as unknown rather than as a guessed number. Add one via `AIOPS_EXTRA_PRICING`.
- **Search covers current versions only.** Deliberate — returning a superseded
  procedure during an incident would be worse than returning nothing.
- **The relevance floor is tuned, not learned.** 55% works well on the seeded
  SOPs; a much larger library may want retuning.
- **No approval workflow.** Status is a field a human sets, not a routed
  review-and-sign-off process.

## Security

- No secrets in the frontend. Every page is a React Server Component and all
  API calls run server-side, so no key or database credential reaches a browser.
- Uploads are size-limited (`MAX_UPLOAD_MB`) and type-checked before parsing.
- The activity log records model, tokens, cost, duration, and approver — but
  never prompt or response bodies (CLAUDE.md Section 22).
- Every SOP body is HTML-escaped on export; a title containing markup cannot
  become live markup in the exported document.

## Responsible AI

- **Human-in-the-loop.** Generation and saving are separate operations.
  `generate_sop()` takes no database session, so it structurally cannot persist
  anything. A test pins that.
- **Explainability.** Answers carry a reasoning summary and per-source match
  percentages, so a reader can judge how well-supported an answer is.
- **Refusal over invention.** Covered above and by tests.
- **Auditability.** Every version records who saved it, when, whether it was AI
  drafted or human edited, and which model was used.

## Future Improvements

- Deploy and add the live URL.
- Review-date reminders — the fields exist, nothing acts on them yet.
- Approval routing before an SOP becomes `active`.
- Restore a previous version as a new version (currently read-only history).
- Re-embed on dimension change, so the setting can be tuned without manual work.
- Prompt-independent Demo Mode via nearest-neighbour recording lookup.
