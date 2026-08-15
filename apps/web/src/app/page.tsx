import Link from "next/link";
import { Badge, Card, CardHeader, StatusDot } from "@aiops/ui";
import { API_URL, tryGetReadiness, tryGetSystemInfo } from "@/lib/api";
import { tryAnalyseSample, tryListSamples } from "@/lib/dashboard-api";
import { DashboardPanel } from "@/components/dashboard/dashboard-panel";

/**
 * Home — Project 3, the AI Operations Dashboard (CLAUDE.md Section 11).
 *
 * The first dataset is analysed on the server so the page arrives with a full
 * dashboard on it rather than an empty file-picker. That first render involves
 * no AI at all: profiling, trends and anomalies are arithmetic, so this page
 * is complete and correct even when the day's AI budget is gone.
 *
 * The build-order project list that used to live here now lives on /projects,
 * which already showed a fuller version of it.
 */

export default async function DashboardPage() {
  const [system, readiness, samples] = await Promise.all([
    tryGetSystemInfo(),
    tryGetReadiness(),
    tryListSamples(),
  ]);

  const available = samples?.samples ?? [];
  const first = available[0]?.key;
  const initialAnalysis = first ? await tryAnalyseSample(first) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Operations dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          KPIs, trends and anomalies from operations data. Every number here is
          computed, not generated — the AI only interprets, and only when asked.
        </p>
      </header>

      {/* First-time orientation. Stated here as well as on the guide because a
          visitor who never opens the guide should still know what they are
          using and what it costs. */}
      {system && !system.demo_mode ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-5 py-4 text-sm dark:border-slate-800 dark:bg-slate-800/40">
          <p className="text-slate-700 dark:text-slate-300">
            <strong>The AI here runs live.</strong> Ask it your own questions —
            nothing is replayed. It runs on free-tier infrastructure with a
            limit of roughly 20 AI requests a day across all visitors, which is
            a deliberate cost choice: if the day&rsquo;s budget runs out the
            site says so plainly rather than pretending otherwise.
          </p>
          <p className="mt-2 text-slate-500 dark:text-slate-400">
            New here?{" "}
            <Link href="/guide" className="underline underline-offset-2">
              Start here
            </Link>{" "}
            — a five-minute walkthrough.
          </p>
        </div>
      ) : null}

      {available.length > 0 || initialAnalysis ? (
        <DashboardPanel
          samples={available}
          initialAnalysis={initialAnalysis}
          initialError={null}
        />
      ) : (
        <Card>
          <CardHeader
            title="Operations data"
            description="The dashboard could not reach the API."
          />
          <div className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
            <p>
              Could not reach the API at{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                {API_URL}
              </code>
              .
            </p>
            <p className="mt-2">
              If this is a deployed site it may be waking from idle — reload in
              a moment. Locally, start it with{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                npm run dev
              </code>
              .
            </p>
          </div>
        </Card>
      )}

      {/* ---- system status strip ------------------------------------------ */}
      <Card>
        <CardHeader
          title="System status"
          description="Live from the API's readiness endpoint."
          action={
            readiness ? (
              <Badge
                tone={
                  readiness.status === "ok"
                    ? "success"
                    : readiness.status === "degraded"
                      ? "warning"
                      : "danger"
                }
              >
                {readiness.status}
              </Badge>
            ) : (
              <Badge tone="danger">unreachable</Badge>
            )
          }
        />

        <div className="px-5 py-4">
          {readiness ? (
            <ul className="space-y-3">
              {readiness.checks.map((check) => (
                <li
                  key={check.name}
                  className="flex flex-wrap items-baseline justify-between gap-2"
                >
                  <StatusDot
                    tone={
                      check.status === "ok"
                        ? "ok"
                        : check.status === "not_configured"
                          ? "idle"
                          : "danger"
                    }
                    label={check.name.replace(/_/g, " ")}
                  />
                  <span className="text-sm text-slate-500 dark:text-slate-400">
                    {check.detail}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              The API did not respond, so no dependency status is available.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
