# Deployment

Getting the toolkit onto a public URL, per CLAUDE.md Section 3a: *"a hiring
manager will not clone this repo, install Docker, stand up Postgres, and supply
API keys just to look at it."*

Three pieces, already chosen:

| Piece | Host | Cost |
|---|---|---|
| Web app (Next.js) | **Vercel** | Free |
| API (FastAPI) | **Render** | Free |
| Database | **Supabase** | Free, already running |

---

## Before you start

**Two decisions are already made in configuration, and both matter.**

**1. The public deployment runs in Demo Mode.** `render.yaml` sets
`DEMO_MODE=true`, so the deployed API needs no API key at all. That means:

- there is no key on the server to leak;
- a visitor cannot exhaust your Gemini free-tier quota (20 requests/day);
- every AI output shown is a *real recorded response*, not a simulation.

The three example SOPs and three sample questions work. Free-typed input
returns an honest "no recording for this" — which is the documented trade for
never fabricating output.

**2. You will need the Supabase *session pooler* connection string, not the
direct one.** Your `.env` uses the direct connection, which resolves over IPv6
only. Your home network happens to support IPv6; Render's outbound network
does not. Using the direct string in production produces a service that builds
fine and then cannot reach the database.

---

## Part 1 — Deploy the API to Render

### 1.1 Create the account

Go to **https://render.com** → **Get Started** → **GitHub**. Authorise Render.

When it asks which repositories to grant access to, choose **Only select
repositories** and pick `ai-operations-toolkit`. The repository stays private.

### 1.2 Get the pooler connection string from Supabase

In a second tab, open your Supabase project → **Connect** (top of the page) →
**Connection string** tab.

Look for **Session pooler** (sometimes under a "Type" dropdown). Copy the
**URI**. It looks like:

```
postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Note the host contains `pooler.supabase.com`. If yours says
`db.<something>.supabase.co`, that is the direct connection — keep looking.

Replace `[YOUR-PASSWORD]` with your real database password.

> **If your password contains `#`, `@`, `/`, `?`, or `%`**, it must be
> percent-encoded in a URL. `#` becomes `%23`. (Your local `.env` already has
> this applied.)

Keep this tab open. You will paste this value into Render's dashboard — never
into a chat.

### 1.3 Create the service

In Render: **New +** → **Blueprint** → select `ai-operations-toolkit` →
**Connect**.

Render reads `render.yaml` and proposes one service called `aiops-api`. It will
ask you for the two values marked as secrets:

| Field | What to paste |
|---|---|
| `DATABASE_URL` | The session pooler URI from step 1.2 |
| `CORS_ORIGINS` | `http://localhost:3000` for now — updated in Part 3 |

Click **Apply**.

The first build takes **5–10 minutes**. It installs the Pango system libraries
that PDF export needs, so it is slower than a plain Python deploy.

### 1.4 Check it worked

Render shows a URL like `https://aiops-api.onrender.com`.

Open **`<your-url>/health`**. You should see:

```json
{"status": "ok", "service": "aiops-api", ...}
```

Then open **`<your-url>/health/ready`** and check three things:

- `database` → `ok` — if it says `unavailable`, you used the direct connection
  string, not the pooler
- `ai` → `ok, Demo Mode: replaying 12 recorded outputs`
- `pdf_export` → **`ok, WeasyPrint available`** — this is the one that does not
  work locally

**Write down your API URL.** Part 2 needs it.

---

## Part 2 — Deploy the web app to Vercel

### 2.1 Create the account

Go to **https://vercel.com** → **Sign Up** → **Continue with GitHub**.

### 2.2 Import the repository

**Add New…** → **Project** → find `ai-operations-toolkit` → **Import**.

If it is not listed, click **Adjust GitHub App Permissions** and grant access
to the repository.

### 2.3 Configure — this is the step that matters

| Setting | Value |
|---|---|
| **Framework Preset** | Next.js *(detected automatically)* |
| **Root Directory** | **`apps/web`** ← click Edit and set this |
| Build Command | leave default |
| Install Command | leave default |

Getting Root Directory wrong is the single most common failure: Vercel builds
the repository root, finds no Next.js app, and fails.

Then expand **Environment Variables** and add one:

| Name | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | your Render URL from 1.4, e.g. `https://aiops-api.onrender.com` |

No trailing slash.

Click **Deploy**. Two to four minutes.

---

## Part 3 — Point CORS at the real domain

> **This step is correctness, not repair.** An earlier version of this document
> claimed the site would not work until `CORS_ORIGINS` matched the Vercel
> domain. That is wrong, and worth stating plainly because it sends you
> chasing a fault that is not there.
>
> CORS is a rule browsers apply to requests *the browser itself makes*. This
> app never makes one: every API call runs on Vercel's server inside a React
> Server Component (`apps/web/src/lib/api.ts`), and the export buttons are
> plain download links (`documents/[id]/page.tsx`), which browsers do not
> subject to CORS either. The deployment was verified working with
> `CORS_ORIGINS` still set to `http://localhost:3000`.
>
> Set it correctly anyway: `http://localhost:3000` is simply untrue of a
> production service, and the moment any project in this toolkit calls the API
> from the browser, this becomes load-bearing.

1. Copy your Vercel URL, e.g. `https://ai-operations-toolkit-web.vercel.app`
2. Back in Render → your service → **Environment**
3. Edit `CORS_ORIGINS` to exactly that URL, no trailing slash
4. **Save Changes** — Render redeploys automatically (~5 minutes)

---

## Part 4 — Verify

Open your Vercel URL and click **Documents**.

| Check | Expected |
|---|---|
| Header badge | *"Demo Mode — replaying 12 recorded AI outputs"* |
| SOP library | at least the 3 seeded SOPs (the database is shared and public, so anything created through the live site is also listed) |
| Ask a question | *"What do we do if a hotel overbooks a confirmed room?"* → answer with sources |
| Ask something unrelated | *"How do I fix the office printer?"* → honest "no SOP covers this" |
| Generate | **New SOP** → click an example button → **Generate SOP** |
| **PDF export** | Open any SOP → **PDF** → downloads a real PDF |

That last one is the proof the deployment adds something local development
cannot do.

---

## Known limitations of the free tiers

**Render free services sleep after 15 minutes of inactivity.** The first
request after that takes **30–60 seconds** while the container restarts
(measured: 39s). Everything after is fast.

The web app waits 45 seconds before declaring the API unreachable
(`apps/web/src/lib/api.ts`), so a cold start shows a slow page rather than a
false "API unreachable". That wait is safe because these calls run server-side
on Vercel, whose Hobby plan allows 300s per invocation.

For a hiring manager clicking a link cold, that first load is slow. Options:

- Accept it, and say so next to the link ("first load may take a minute")
- Use a free uptime pinger (UptimeRobot, every 10 minutes) to keep it warm
- Upgrade to Render's paid tier (~$7/month) for no sleeping

**The database is shared and public.** Anyone with the link can create and edit
SOPs. Fine for a portfolio; the seeded SOPs can be restored by re-running
`npm run record-demo`.

---

## If something fails

| Symptom | Cause | Fix |
|---|---|---|
| Render build fails | Usually a missing file in the build context | Read the build log; the failing `COPY` or `pip` line names it |
| `/health/ready` says database `unavailable` | Direct connection string instead of the pooler | Swap to the session pooler URI (step 1.2) |
| `pdf_export` says `not_configured` | Image built without the Pango libraries | Confirm Render used `apps/api/Dockerfile`, not a native Python runtime |
| Vercel build fails | Root Directory not set to `apps/web` | Settings → General → Root Directory |
| Site loads but shows "API unreachable" | `NEXT_PUBLIC_API_URL` wrong or missing, or set for Preview/Development but not **Production** | Vercel → Settings → Environment Variables, then **redeploy** — this value is baked in at build time |
| Every API call 404s | A trailing slash on `NEXT_PUBLIC_API_URL` — the client joins paths directly, so `.../` becomes `//api/system`, which is a different path | Remove the trailing slash and redeploy |
