import { Card } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryListSamples, tryReportFromSample } from "@/lib/report-api";
import { ReportPanel } from "@/components/reports/report-panel";

export const metadata = { title: "Reports — AI Operations Toolkit" };

/**
 * Project 7 — AI Report Generator (CLAUDE.md Section 15).
 *
 * The first report is computed on the server so the page arrives with figures
 * already on it. That costs nothing: KPIs, trends and anomalies come from the
 * same `analyse()` the Operations Dashboard calls, and no model is involved
 * until someone asks for the narrative.
 */
export default async function Page() {
  const samples = await tryListSamples();
  const first = samples?.[0];
  const initial = first ? await tryReportFromSample(first.key, "weekly") : null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Reports
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Daily, weekly and monthly operational reports. Every figure is computed by
          the same analysis the Dashboard runs; the AI writes only the narrative on
          top of it.
        </p>
      </header>

      {samples === null ? (
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
      ) : (
        <ReportPanel samples={samples} initial={initial} />
      )}
    </div>
  );
}
