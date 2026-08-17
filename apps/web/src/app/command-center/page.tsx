import Link from "next/link";
import type { SignalSeverity } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryGetOverview } from "@/lib/command-api";
import { BriefPanel } from "@/components/command/brief-panel";

export const metadata = { title: "Command Center — AI Operations Toolkit" };

/**
 * Project 9 — AI Ops Command Center (CLAUDE.md Section 17).
 *
 * Everything on this page came from somewhere else. Nothing here is measured,
 * decided or stored by this project — the signals are re-read from Projects 3,
 * 4, 5 and 6 on every load, and each one links back to whichever of them owns
 * it. The only thing this project produces is the brief.
 *
 * Rendering costs no AI request, which is what makes it safe as the first page
 * someone opens each morning.
 */

const SEVERITY_TONE: Record<SignalSeverity, "danger" | "warning" | "info"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

export default async function Page() {
  const overview = await tryGetOverview();

  if (overview === null) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Ops Command Center
          </h1>
        </header>
        <Card>
          <div className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
            <p>
              Could not reach the API at{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                {API_URL}
              </code>
              .
            </p>
            <p className="mt-2">
              If this is the deployed site it may be waking from idle — reload in a
              moment.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  const down = overview.sources.filter((s) => !s.available);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Ops Command Center
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Everything needing attention across the toolkit, in one place. Every item
          below was produced by another project and links back to it — this page
          measures nothing of its own.
        </p>
      </header>

      {/* ---- source health ------------------------------------------------ */}
      <Card>
        <CardHeader
          title="Sources"
          description="Read fresh on every load. A source that fails is named, not hidden."
        />
        <div className="grid gap-px bg-slate-200 sm:grid-cols-2 lg:grid-cols-4 dark:bg-slate-800">
          {overview.sources.map((source) => (
            <div key={source.source} className="bg-white px-4 py-3 dark:bg-slate-900">
              <div className="flex items-center justify-between gap-2">
                <Link
                  href={source.link}
                  className="text-sm font-medium text-slate-900 underline underline-offset-2 dark:text-slate-100"
                >
                  {source.label}
                </Link>
                <Badge tone={source.available ? "success" : "danger"}>
                  {source.available ? `${source.signal_count}` : "unavailable"}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {source.detail}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {down.length > 0 ? (
        <div
          role="alert"
          className="rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200"
        >
          {down.length} of {overview.sources.length} sources could not be reached, so
          this picture is incomplete. Everything from the other sources is still shown.
        </div>
      ) : null}

      {/* ---- the brief ---------------------------------------------------- */}
      <BriefPanel initialBrief={overview.brief} signals={overview.signals} />

      {/* ---- the signals -------------------------------------------------- */}
      <Card>
        <CardHeader
          title="Needs attention"
          description="Ranked in code, not by a model. Most urgent first."
          action={
            <div className="flex gap-1.5">
              {overview.critical_count > 0 ? (
                <Badge tone="danger">{overview.critical_count} critical</Badge>
              ) : null}
              {overview.warning_count > 0 ? (
                <Badge tone="warning">{overview.warning_count} warning</Badge>
              ) : null}
              {overview.info_count > 0 ? (
                <Badge tone="info">{overview.info_count} info</Badge>
              ) : null}
            </div>
          }
        />
        {overview.signals.length > 0 ? (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {overview.signals.map((signal) => (
              <li key={signal.id} className="px-5 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={SEVERITY_TONE[signal.severity]}>{signal.severity}</Badge>
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {signal.title}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                  {signal.detail}
                </p>
                <Link
                  href={signal.link}
                  className="mt-1 inline-block text-xs text-slate-500 underline underline-offset-2 dark:text-slate-400"
                >
                  Open in {signal.source_label} →
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-5 py-4 text-sm text-slate-500 dark:text-slate-400">
            Nothing is currently flagged. Every source answered and none of them
            reported anything needing attention.
          </p>
        )}
      </Card>

      <p className="pb-2 text-xs text-slate-400 dark:text-slate-500">
        Collected {new Date(overview.collected_at).toLocaleString()}. Dashboard
        signals come from the bundled <code>{overview.dashboard_dataset}</code>{" "}
        dataset — the Operations Dashboard analyses an uploaded file and stores
        nothing, so there is no live KPI state to aggregate.
      </p>
    </div>
  );
}
