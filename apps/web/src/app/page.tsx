import Link from "next/link";
import { Badge, Card, CardHeader, StatusDot } from "@aiops/ui";
import { API_URL, tryGetReadiness, tryGetSystemInfo } from "@/lib/api";
import { projectsByPhase } from "@/lib/projects";

export default async function DashboardPage() {
  const [system, readiness] = await Promise.all([
    tryGetSystemInfo(),
    tryGetReadiness(),
  ]);

  const projects = projectsByPhase();
  const shipped = projects.filter((p) => p.status === "shipped").length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Foundation is in place. Projects come online one at a time, in the
          build order below.
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

      {/* ---- system status ------------------------------------------------ */}
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
            <div className="text-sm text-slate-600 dark:text-slate-400">
              <p>
                Could not reach the API at{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                  {API_URL}
                </code>
                .
              </p>
              <p className="mt-2">
                Start it with{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                  npm run dev
                </code>
                , which runs the API and this web app together.
              </p>
            </div>
          )}
        </div>
      </Card>

      {/* ---- configuration ------------------------------------------------ */}
      {system ? (
        <Card>
          <CardHeader
            title="Configuration"
            description="Non-secret settings only. API keys are never sent to the browser."
          />
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 px-5 py-4 sm:grid-cols-3">
            {[
              ["AI provider", system.ai_provider],
              ["Auth mode", system.auth_mode],
              ["Database", system.database_configured ? "configured" : "not configured"],
              ["Demo recordings", String(system.demo_recordings)],
              ["Export formats", system.export_formats.join(", ")],
              ["Bring your own key", system.allow_bring_your_own_key ? "allowed" : "off"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs tracking-wide text-slate-400 uppercase dark:text-slate-500">
                  {label}
                </dt>
                <dd className="mt-0.5 text-sm text-slate-800 dark:text-slate-200">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      ) : null}

      {/* ---- build order -------------------------------------------------- */}
      <Card>
        <CardHeader
          title="Projects"
          description={`${shipped} of ${projects.length} shipped. Each is built and tested fully before the next begins.`}
        />
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {projects.map((project) => (
            <li
              key={project.slug}
              className="flex flex-wrap items-start justify-between gap-3 px-5 py-3.5"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 tabular-nums dark:text-slate-500">
                    {String(project.phase).padStart(2, "0")}
                  </span>
                  <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {project.name}
                  </h3>
                </div>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  {project.description}
                </p>
                <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                  Proves: {project.jdRequirement}
                </p>
              </div>
              <Badge tone={project.status === "shipped" ? "success" : "neutral"}>
                {project.status.replace("_", " ")}
              </Badge>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
