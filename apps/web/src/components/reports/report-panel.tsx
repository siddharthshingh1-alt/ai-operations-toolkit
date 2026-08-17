"use client";

import { useState } from "react";
import { Badge, Card, CardHeader } from "@aiops/ui";
import type {
  MetricChangeView,
  ReportFacts,
  ReportFactsResponse,
  ReportNarrative,
  ReportPeriod,
  ReportSampleOption,
  TrackerUsageInfo,
} from "@aiops/types";
import {
  exportReportAction,
  generateNarrativeAction,
  reportFromSampleAction,
  reportFromUploadAction,
} from "@/app/reports/actions";

/**
 * The Report Generator's interface.
 *
 * The order on screen is the order of the argument: the computed figures come
 * first and arrive free, and the narrative sits underneath as something a
 * person chose to spend a request on. A reader can therefore check every
 * sentence the model wrote against the table above it without scrolling past
 * the prose to find the evidence.
 */

const PERIODS: { value: ReportPeriod; label: string; hint: string }[] = [
  { value: "daily", label: "Daily", hint: "the last day in the data, against the one before" },
  { value: "weekly", label: "Weekly", hint: "the last 7 days, against the 7 before" },
  { value: "monthly", label: "Monthly", hint: "the last 30 days, against the 30 before" },
];

function changeTone(change: MetricChangeView): "neutral" | "info" | "warning" {
  if (change.change_pct === null) return "neutral";
  if (Math.abs(change.change_pct) >= 25) return "warning";
  return "info";
}

function ChangeCell({ change }: { change: MetricChangeView }) {
  if (change.change_pct === null) {
    return (
      <span className="text-xs text-slate-400 dark:text-slate-500">
        {change.previous === null ? "no previous period" : "not comparable"}
      </span>
    );
  }
  const arrow = change.direction === "up" ? "▲" : change.direction === "down" ? "▼" : "—";
  return (
    <Badge tone={changeTone(change)}>
      {arrow} {change.change_pct > 0 ? "+" : ""}
      {change.change_pct}%
    </Badge>
  );
}

export function ReportPanel({
  samples,
  initial,
}: {
  samples: ReportSampleOption[];
  initial: ReportFactsResponse | null;
}) {
  const [facts, setFacts] = useState<ReportFacts | null>(initial?.facts ?? null);
  const [narrative, setNarrative] = useState<ReportNarrative | null>(null);
  const [usage, setUsage] = useState<TrackerUsageInfo | null>(null);
  const [dataset, setDataset] = useState(samples[0]?.key ?? "");
  const [period, setPeriod] = useState<ReportPeriod>("weekly");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Any change of dataset or period invalidates the prose written about the old one. */
  function reset() {
    setNarrative(null);
    setUsage(null);
  }

  async function compute(nextDataset: string, nextPeriod: ReportPeriod) {
    setBusy("compute");
    setError(null);
    reset();
    const result = await reportFromSampleAction(nextDataset, nextPeriod);
    if (result.ok) setFacts(result.data.facts);
    else setError(result.error);
    setBusy(null);
  }

  async function upload(formData: FormData) {
    setBusy("upload");
    setError(null);
    reset();
    formData.set("period", period);
    const result = await reportFromUploadAction(formData);
    if (result.ok) setFacts(result.data.facts);
    else setError(result.error);
    setBusy(null);
  }

  async function write() {
    if (!facts) return;
    setBusy("narrative");
    setError(null);
    const result = await generateNarrativeAction(facts);
    if (result.ok) {
      setNarrative(result.data.narrative);
      setUsage(result.data.usage);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  async function download(format: "markdown" | "html" | "pdf") {
    if (!facts) return;
    setBusy(`export-${format}`);
    setError(null);
    const result = await exportReportAction(facts, narrative, format);
    if (result.ok) {
      const bytes = Uint8Array.from(atob(result.data.base64), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: result.data.contentType }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  return (
    <div className="space-y-6">
      {error ? (
        <div
          role="alert"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          {error}
        </div>
      ) : null}

      {/* ---- what to report on --------------------------------------- */}
      <Card>
        <CardHeader
          title="Report on"
          description="Computing the report costs nothing — no AI is called until you ask for the narrative."
        />
        <div className="space-y-4 px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-slate-700 dark:text-slate-300">Dataset</span>
              <select
                value={dataset}
                disabled={busy !== null}
                onChange={(event) => {
                  setDataset(event.target.value);
                  void compute(event.target.value, period);
                }}
                className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
              >
                {samples.map((sample) => (
                  <option key={sample.key} value={sample.key}>
                    {sample.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-slate-700 dark:text-slate-300">Period</span>
              <select
                value={period}
                disabled={busy !== null}
                onChange={(event) => {
                  const next = event.target.value as ReportPeriod;
                  setPeriod(next);
                  void compute(dataset, next);
                }}
                className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
              >
                {PERIODS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label} — {option.hint}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <form action={upload} className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
            <span className="text-sm text-slate-600 dark:text-slate-400">
              Or report on your own file:
            </span>
            <input
              type="file"
              name="file"
              accept=".csv,.tsv,.xlsx,.xls"
              className="text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm dark:text-slate-400 dark:file:bg-slate-800 dark:file:text-slate-200"
            />
            <button
              type="submit"
              disabled={busy !== null}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {busy === "upload" ? "Reading…" : "Report on this file"}
            </button>
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Nothing is stored — the export is the copy you keep.
            </span>
          </form>
        </div>
      </Card>

      {facts ? (
        <>
          {/* ---- the computed report ------------------------------- */}
          <Card>
            <CardHeader
              title={`${facts.period_label} report — ${facts.dataset_label}`}
              description={
                facts.whole_dataset
                  ? "This dataset has no date column, so the report covers the whole file."
                  : `${facts.current.description} · compared with ${facts.previous.description}`
              }
              action={
                <div className="flex gap-1.5">
                  {(["pdf", "markdown", "html"] as const).map((format) => (
                    <button
                      key={format}
                      type="button"
                      onClick={() => download(format)}
                      disabled={busy !== null}
                      className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {busy === `export-${format}` ? "…" : format.toUpperCase()}
                    </button>
                  ))}
                </div>
              }
            />
            <div className="px-5 py-4">
              {facts.kpis.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
                        <th className="pb-2 font-medium">Metric</th>
                        <th className="pb-2 text-right font-medium">This period</th>
                        <th className="pb-2 text-right font-medium">Previous</th>
                        <th className="pb-2 text-right font-medium">Change</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {facts.kpis.map((kpi) => (
                        <tr key={kpi.label}>
                          <td className="py-2 text-slate-900 dark:text-slate-100">{kpi.label}</td>
                          <td className="py-2 text-right tabular-nums text-slate-900 dark:text-slate-100">
                            {kpi.current.toLocaleString(undefined, {
                              maximumFractionDigits: 2,
                            })}
                            {kpi.unit}
                          </td>
                          <td className="py-2 text-right tabular-nums text-slate-500 dark:text-slate-400">
                            {kpi.previous === null
                              ? "—"
                              : `${kpi.previous.toLocaleString(undefined, {
                                  maximumFractionDigits: 2,
                                })}${kpi.unit}`}
                          </td>
                          <td className="py-2 text-right">
                            <ChangeCell change={kpi} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  No numeric metrics were computable for this period
                  {facts.current.row_count === 0 ? " — it contains no rows" : ""}.
                </p>
              )}
              <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Every figure above was computed from the data by the same analysis the
                Dashboard runs. No AI produced any of them.
              </p>
            </div>
          </Card>

          {/* ---- trends and anomalies ------------------------------ */}
          {facts.findings.length > 0 ? (
            <Card>
              <CardHeader
                title="Trends and anomalies"
                description="Detected by the shared analytics service, in its own words."
              />
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {facts.findings.map((finding, index) => (
                  <li key={`${finding.kind}-${finding.column}-${index}`} className="px-5 py-3">
                    <Badge tone={finding.kind === "anomaly" ? "warning" : "info"}>
                      {finding.kind}
                    </Badge>{" "}
                    <span className="text-sm text-slate-700 dark:text-slate-300">
                      {finding.statement}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {/* ---- the narrative ------------------------------------- */}
          <Card>
            <CardHeader
              title="Narrative"
              description="Executive summary, recommendations and action items. One AI request."
              action={
                <button
                  type="button"
                  onClick={write}
                  disabled={busy !== null}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                >
                  {busy === "narrative"
                    ? "Writing…"
                    : narrative
                      ? "Rewrite · 1 request"
                      : "Write it · 1 request"}
                </button>
              }
            />
            <div className="space-y-4 px-5 py-4">
              {narrative ? (
                <>
                  <div>
                    <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                      Executive summary
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                      {narrative.executive_summary}
                    </p>
                  </div>

                  {narrative.recommendations.length > 0 ? (
                    <div>
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Recommendations
                      </h3>
                      <ul className="mt-1 list-disc pl-5 text-sm text-slate-600 dark:text-slate-400">
                        {narrative.recommendations.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {narrative.action_items.length > 0 ? (
                    <div>
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Action items
                      </h3>
                      <ul className="mt-2 space-y-1.5">
                        {narrative.action_items.map((item, index) => (
                          <li key={index} className="text-sm text-slate-700 dark:text-slate-300">
                            {item.action}
                            {item.owner_hint ? (
                              <span className="text-xs text-slate-500 dark:text-slate-400">
                                {" "}
                                — {item.owner_hint}
                              </span>
                            ) : null}
                            {item.metric ? <Badge tone="info">{item.metric}</Badge> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {usage ? (
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      {usage.model} · {usage.input_tokens + usage.output_tokens} tokens ·{" "}
                      {usage.estimated_cost_usd != null
                        ? `$${usage.estimated_cost_usd.toFixed(6)}`
                        : "cost —"}{" "}
                      · {usage.duration_ms}ms
                    </p>
                  ) : null}
                </>
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Not written yet. The figures above are complete without it — the
                  narrative turns them into something you would circulate. You can
                  export the report either way.
                </p>
              )}
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
