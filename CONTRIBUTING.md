# Contributing

This is a personal portfolio project, so it is not looking for outside
contributions. The conventions are recorded here because they are what keep the
codebase coherent as nine projects land on top of it.

## Setup

```bash
# Python
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows
.venv/bin/python     -m pip install -r requirements-dev.txt   # macOS / Linux

# JavaScript
npm install

# Synthetic datasets (needed by tests and the mock adapters)
npm run demo-data
```

## The database, and one thing to get right

**The test suite needs no database.** It uses in-memory SQLite where storage
matters and stubs the AI everywhere, so `pytest` never opens a connection to
whatever `DATABASE_URL` names. You can verify that claim in one command:

```bash
DATABASE_URL="postgresql://nobody:x@does-not-exist.invalid:5432/nope" pytest
```

Everything passes except one assertion about default settings, because nothing
in the suite connects.

**Running the app locally is where care is needed.** If `DATABASE_URL` points at
a deployed database and `DB_AUTO_CREATE` is on, then merely importing the app —
a smoke test, a one-line `create_app()` check — issues `CREATE TABLE` against
it. That happened twice while this repository was being built.

`create_all()` now refuses when the host is not local, so this is prevented
rather than remembered. But the comfortable arrangement is a database of your
own:

```bash
# A local Postgres with pgvector, on port 5432
docker compose up -d db

# Then in .env
DATABASE_URL=postgresql+psycopg://aiops:aiops@localhost:5432/aiops
DB_AUTO_CREATE=true      # safe: it is your database
```

Without Docker, either install PostgreSQL 17 with the pgvector extension, or
leave `DATABASE_URL` empty — most of the toolkit works without a database at
all, and the endpoints that need one return a 503 saying so.

If you deliberately need to create tables on a remote database, set
`DB_ALLOW_REMOTE_SCHEMA=true` for that one command, not in `.env`.

## Before every commit

```bash
npm run verify    # lint + typecheck + test + build, both languages
```

Individual gates:

| Command | What it runs |
|---|---|
| `npm run lint` | ruff + eslint |
| `npm run typecheck` | mypy + tsc |
| `npm test` | pytest |
| `npm run build` | Next.js production build |

CI runs the same set on every push, plus a secret scan.

## Non-negotiables

These come from `CLAUDE.md` and are enforced by tests. Changing one means
changing a test deliberately, which is the point.

1. **No fabricated AI output.** Demo Mode replays recorded real responses. If a
   recording is missing it fails loudly. Never add a code path that generates a
   plausible answer to fill a gap.
2. **No guessed numbers.** An unpriced model reports `None` cost, not an
   estimate. The same principle applies anywhere a figure is displayed.
3. **Human approval is structural.** High-risk actions — sending email, calling
   a webhook, writing to a database — halt the workflow. The approver is a
   required argument, not an optional flag.
4. **Observation and hypothesis stay apart.** Analysis output uses the
   `observed` / `hypothesis` / `recommendation` shape. Never state a cause as
   established.
5. **No secrets anywhere near the client.** Server components only; only
   `Settings.redacted()` crosses an HTTP boundary.
6. **Mock integrations only.** Do not add a real OAuth flow without updating
   `docs/decisions/0003` first.

## Adding a project

Work through one project completely before starting the next (CLAUDE.md
Section 2): build, test, document, deploy, then move on.

1. Add its routers under `apps/api/app/routers/` and mount them in `main.py`.
2. Add its pages under `apps/web/src/app/`.
3. Reuse `packages/ai`, `services/analytics`, and `services/workflow-engine`.
   If you find yourself writing a second AI integration or a second workflow
   engine, stop — that is the thing the shared layer exists to prevent.
4. Fill in `projects/<slug>/README.md` against the Section 26 template.
5. Flip its `status` in `apps/web/src/lib/projects.ts` to `shipped` **only**
   when it genuinely works end to end.

## Commit messages

Conventional commits, describing the change in operational terms:

```
feat: add SOP generation workflow
feat: add travel-ops delay-incident workflow
fix: handle failed AI provider response
docs: record decision on mock-only integrations
```

Do not fabricate commit history.
