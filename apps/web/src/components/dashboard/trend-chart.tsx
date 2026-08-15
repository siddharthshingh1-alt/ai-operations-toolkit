"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSeries } from "@aiops/types";

/**
 * One metric over the dataset's time axis, with detected anomalies marked.
 *
 * Design decisions worth stating, since a chart is read rather than executed:
 *
 * - **One series per chart, one y-axis.** Two metrics of different scale on
 *   shared axes is the most common way a chart lies; separate charts cost a
 *   little vertical space and no truth.
 * - **Anomalies are a second layer, not a recolouring of the line.** "This
 *   point was flagged by a z-score test" is a different claim from "this is
 *   the value", and the reader is entitled to disagree with the first while
 *   trusting the second.
 * - **Colours come from CSS custom properties**, so the dark palette is a
 *   selected set validated against the dark surface rather than an inversion.
 * - The flagged count is written above the chart, so the marks are never the
 *   only way to know an anomaly exists.
 */
export function TrendChart({ series }: { series: ChartSeries }) {
  const data = series.points.map((point) => ({
    label: point.label,
    value: point.value,
    // Recharts skips null points, so this renders a dot only where flagged.
    anomaly: point.is_anomaly ? point.value : null,
  }));

  const anomalyCount = series.points.filter((point) => point.is_anomaly).length;

  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
          {series.column}
        </h3>
        {anomalyCount > 0 ? (
          <span className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: "var(--chart-anomaly)" }}
            />
            {anomalyCount} unusual point{anomalyCount === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>

      <div className="h-52 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 10, bottom: 0, left: -10 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--chart-grid)"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "var(--chart-axis)" }}
              stroke="var(--chart-grid)"
              minTickGap={44}
              tickMargin={6}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--chart-axis)" }}
              stroke="var(--chart-grid)"
              width={60}
              tickMargin={4}
            />
            <Tooltip
              contentStyle={{
                fontSize: 12,
                borderRadius: 6,
                background: "var(--chart-surface)",
                border: "1px solid var(--chart-grid)",
                color: "var(--foreground)",
              }}
              labelStyle={{ fontWeight: 500, color: "var(--foreground)" }}
              formatter={(value, name) => [
                String(value ?? ""),
                name === "Unusual" ? "Flagged as unusual" : series.column,
              ]}
            />
            <Line
              type="monotone"
              dataKey="value"
              name={series.column}
              stroke="var(--chart-line)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
            {/* Marks only. `strokeWidth={0}` keeps this from drawing a second
                line through the flagged points, which would read as a trend. */}
            <Line
              type="monotone"
              dataKey="anomaly"
              name="Unusual"
              stroke="none"
              strokeWidth={0}
              connectNulls={false}
              isAnimationActive={false}
              dot={{
                r: 5,
                fill: "var(--chart-anomaly)",
                stroke: "var(--chart-surface)",
                strokeWidth: 2,
              }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
