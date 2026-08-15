"use client";

import { useState, useTransition } from "react";
import type { Analysis, InsightResponse, SampleDataset } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import {
  analyseSampleAction,
  analyseUploadAction,
  insightsAction,
} from "@/app/dashboard-actions";
import { TrendChart } from "@/components/dashboard/trend-chart";

/**
 * The Operations Dashboard (CLAUDE.md Section 11).
 *
 * The structural rule this component exists to enforce: **measured facts and
 * model commentary are visually separate and separately obtained.** Everything
 * above the insights card is arithmetic, present the moment the page loads and
 * unaffected by whether any AI is available. The insights card is the only
 * thing that costs an API request, and it only asks for one when a person
 * presses the button.
 */

function formatValue(value: number, unit: string): string {
  const rounded =
    Math.abs(value) >= 1000
      ? value.toLocaleString(undefined, { maximumFractionDigits: 0 })
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (unit === "%") return `${rounded}%`;
  if (unit === "₹") return `₹${rounded}`;
  if (unit) return `${rounded} ${unit}`;
  return rounded;
}

function KpiTile({
  label,
  value,
  unit,
  changePct,
}: {
  label: string;
  value: number;
  unit: string;
  changePct: number | null;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
      <p className="truncate text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">
        {formatValue(value, unit)}
      </p>
      {changePct !== null ? (
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {changePct >= 0 ? "+" : ""}
          {changePct.toFixed(1)}% over the period
        </p>
      ) : (
        <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
          no trend computable
        </p>
      )}
    </div>
  );
}

export function DashboardPanel({
  samples,
  initialAnalysis,
  initialError,
}: {
  samples: SampleDataset[];
  initialAnalysis: Analysis | null;
  initialError: string | null;
}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(initialAnalysis);
  const [selected, setSelected] = useState<string>(
    initialAnalysis?.dataset ?? samples[0]?.key ?? "",
  );
  const [error, setError] = useState<string | null>(initialError);
  const [pending, startTransition] = useTransition();

  const [insights, setInsights] = useState<InsightResponse | null>(null);
  const [insightError, setInsightError] = useState<string | null>(null);
  const [insightPending, setInsightPending] = useState(false);

  function pickSample(key: string) {
    setSelected(key);
    setError(null);
    setInsights(null);
    setInsightError(null);
    startTransition(async () => {
      const result = await analyseSampleAction(key);
      if (result.ok) setAnalysis(result.data);
      else {
        setAnalysis(null);
        setError(result.error);
      }
    });
  }

  function upload(formData: FormData) {
    setError(null);
    setInsights(null);
    setInsightError(null);
    startTransition(async () => {
      const result = await analyseUploadAction(formData);
      if (result.ok) {
        setAnalysis(result.data);
        setSelected("");
      } else {
        setAnalysis(null);
        setError(result.error);
      }
    });
  }

  async function explain() {
    if (!analysis) return;
    setInsightPending(true);
    setInsightError(null);
    const result = await insightsAction(analysis);
    if (result.ok) setInsights(result.data);
    else setInsightError(result.error);
    setInsightPending(false);
  }

  return (
    <div className="space-y-6">
      {/* ---- data source ------------------------------------------------- */}
      <Card>
        <CardHeader
          title="Operations data"
          description="Pick a bundled dataset, or upload your own CSV or Excel file."
        />
        <div className="space-y-4 px-5 py-4">
          <div className="flex flex-wrap gap-2">
            {samples.map((sample) => (
              <button
                key={sample.key}
                type="button"
                onClick={() => pickSample(sample.key)}
                disabled={pending}
                title={sample.description}
                className={
                  selected === sample.key
                    ? "rounded-md border border-teal-600 bg-teal-50 px-3 py-1.5 text-sm font-medium text-teal-900 disabled:opacity-60 dark:border-teal-500 dark:bg-teal-950 dark:text-teal-100"
                    : "rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                }
              >
                {sample.name}
                <span className="ml-1.5 text-xs text-slate-400 tabular-nums">
                  {sample.row_count.toLocaleString()}
                </span>
              </button>
            ))}
          </div>

          <form action={upload} className="flex flex-wrap items-center gap-3">
            <input
              type="file"
              name="file"
              accept=".csv,.tsv,.xlsx,.xlsm"
              className="block max-w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-sm file:text-slate-700 hover:file:bg-slate-50 dark:text-slate-400 dark:file:border-slate-700 dark:file:bg-slate-900 dark:file:text-slate-300"
            />
            <button
              type="submit"
              disabled={pending}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {pending ? "Analysing…" : "Analyse file"}
            </button>
            <span className="text-xs text-slate-400 dark:text-slate-500">
              CSV, TSV or Excel · 10 MB max · nothing is stored
            </span>
          </form>

          {error ? (
            <div
              role="alert"
              className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
            >
              {error}
            </div>
          ) : null}
        </div>
      </Card>

      {analysis ? (
        <>
          {/* ---- KPI row ------------------------------------------------- */}
          {analysis.kpis.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {analysis.kpis.map((kpi) => (
                <KpiTile
                  key={kpi.label}
                  label={kpi.label}
                  value={kpi.value}
                  unit={kpi.unit}
                  changePct={kpi.change_pct}
                />
              ))}
            </div>
          ) : (
            <Card>
              <div className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                No numeric columns were found in this file, so there is nothing
                to chart. The table below shows what was read.
              </div>
            </Card>
          )}

          {/* ---- charts -------------------------------------------------- */}
          {analysis.series.length > 0 ? (
            <Card>
              <CardHeader
                title="Trends"
                description={
                  analysis.date_column
                    ? `Ordered by ${analysis.date_column}. Unusual points are flagged by a z-score test, not by a model.`
                    : "No date column was found, so points are in file order."
                }
              />
              <div className="grid gap-6 px-5 py-4 lg:grid-cols-2">
                {analysis.series.map((series) => (
                  <TrendChart key={series.column} series={series} />
                ))}
              </div>
            </Card>
          ) : null}

          {/* ---- insights ------------------------------------------------ */}
          <Card>
            <CardHeader
              title="AI insights"
              description="Interpretation of the findings above. The numbers themselves were computed, not generated."
              action={
                <button
                  type="button"
                  onClick={explain}
                  disabled={insightPending}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                >
                  {insightPending ? "Thinking…" : "Explain these findings"}
                </button>
              }
            />
            <div className="px-5 py-4">
              {insightError ? (
                <div
                  role="alert"
                  className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
                >
                  {insightError}
                </div>
              ) : insights ? (
                <div className="space-y-5">
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    {insights.report.summary}
                  </p>

                  {insights.report.insights.map((insight, index) => (
                    <div
                      key={index}
                      className="space-y-1.5 border-l-2 border-slate-200 pl-4 dark:border-slate-700"
                    >
                      <p className="text-sm">
                        <span className="font-medium text-slate-900 dark:text-slate-100">
                          Observed:{" "}
                        </span>
                        <span className="text-slate-700 dark:text-slate-300">
                          {insight.observed}
                        </span>
                      </p>
                      <p className="text-sm">
                        <span className="font-medium text-amber-800 dark:text-amber-500">
                          Hypothesis:{" "}
                        </span>
                        <span className="text-slate-600 italic dark:text-slate-400">
                          {insight.hypothesis}
                        </span>
                      </p>
                      <p className="text-sm">
                        <span className="font-medium text-teal-800 dark:text-teal-400">
                          Recommendation:{" "}
                        </span>
                        <span className="text-slate-700 dark:text-slate-300">
                          {insight.recommendation}
                        </span>
                      </p>
                    </div>
                  ))}

                  <p className="border-t border-slate-200 pt-3 text-xs text-slate-400 dark:border-slate-800 dark:text-slate-500">
                    {insights.from_cache ? (
                      <>
                        Reused an earlier answer for identical findings — no AI
                        request was spent.
                      </>
                    ) : (
                      <>
                        {insights.model} · {insights.input_tokens.toLocaleString()} in /{" "}
                        {insights.output_tokens.toLocaleString()} out ·{" "}
                        {(insights.duration_ms / 1000).toFixed(1)}s
                        {insights.estimated_cost_usd !== null
                          ? ` · ~$${insights.estimated_cost_usd.toFixed(4)}`
                          : ""}
                      </>
                    )}
                  </p>
                </div>
              ) : (
                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                  <p>
                    Nothing has been generated yet. Press{" "}
                    <strong>Explain these findings</strong> to spend one AI
                    request on interpreting the numbers above.
                  </p>
                  <p className="text-slate-500 dark:text-slate-500">
                    It is a button rather than something that happens on load
                    because the demo runs on a free tier of about 20 requests a
                    day — a dashboard that explained itself to every visitor
                    would spend that on people who never asked.
                  </p>
                </div>
              )}
            </div>
          </Card>

          {/* ---- data table ---------------------------------------------- */}
          <Card>
            <CardHeader
              title="Data"
              description={`First ${analysis.preview_rows.length} of ${analysis.row_count.toLocaleString()} rows, ${analysis.column_count} columns.`}
              action={
                <Badge tone="neutral">{analysis.dataset}</Badge>
              }
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:text-slate-400">
                  <tr>
                    {analysis.preview_columns.map((column) => (
                      <th key={column} className="px-5 py-2 font-medium whitespace-nowrap">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {analysis.preview_rows.map((row, index) => (
                    <tr key={index}>
                      {analysis.preview_columns.map((column) => (
                        <td
                          key={column}
                          className="px-5 py-1.5 whitespace-nowrap text-slate-700 tabular-nums dark:text-slate-300"
                        >
                          {row[column] ?? ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
