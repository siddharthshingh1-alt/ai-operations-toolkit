"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge, Card, CardHeader } from "@aiops/ui";
import type { BriefView, SignalView, TrackerUsageInfo } from "@aiops/types";
import { generateBriefAction } from "@/app/command-center/actions";

/**
 * The Ops Brief: the one thing on this page that costs an AI request.
 *
 * The signals it summarises are rendered by the server component above it and
 * are free. This is separated out so pressing the button re-renders only the
 * narrative, and so the cost sits visibly next to the thing that spends it.
 */
export function BriefPanel({
  initialBrief,
  signals,
}: {
  initialBrief: BriefView | null;
  signals: SignalView[];
}) {
  const [brief, setBrief] = useState(initialBrief);
  const [usage, setUsage] = useState<TrackerUsageInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const byId = new Map(signals.map((s) => [s.id, s]));

  async function generate() {
    setBusy(true);
    setError(null);
    const result = await generateBriefAction();
    if (result.ok) {
      setBrief(result.data.brief);
      setUsage(result.data.usage);
    } else {
      setError(result.error);
    }
    setBusy(false);
  }

  return (
    <Card>
      <CardHeader
        title="Daily Ops Brief"
        description="Written by the AI over the signals below. One request."
        action={
          <button
            type="button"
            onClick={generate}
            disabled={busy}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            {busy ? "Writing…" : brief ? "Regenerate · 1 request" : "Generate · 1 request"}
          </button>
        }
      />
      <div className="space-y-4 px-5 py-4">
        {error ? (
          <div
            role="alert"
            className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
          >
            {error}
          </div>
        ) : null}

        {brief ? (
          <>
            {brief.changed_since > 0 ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                <strong>{brief.changed_since}</strong> source
                {brief.changed_since === 1 ? " has" : "s have"} changed since this brief
                was written. The signals below are current; this paragraph is not.
              </div>
            ) : null}

            {brief.unavailable_sources.length > 0 ? (
              <div className="rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200">
                Written while {brief.unavailable_sources.join(", ")} could not be
                reached, so it describes an incomplete picture.
              </div>
            ) : null}

            <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">
              {brief.summary}
            </p>

            {brief.actions.length > 0 ? (
              <div>
                <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Recommended today
                </h3>
                <ol className="mt-2 space-y-1.5">
                  {brief.actions.map((action, index) => {
                    const signal = action.signal_id ? byId.get(action.signal_id) : undefined;
                    return (
                      <li key={index} className="text-sm text-slate-700 dark:text-slate-300">
                        {action.action}{" "}
                        {signal ? (
                          <Link
                            href={signal.link}
                            className="text-xs underline underline-offset-2 text-slate-500 dark:text-slate-400"
                          >
                            → {signal.source_label}
                          </Link>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              </div>
            ) : null}

            <p className="text-xs text-slate-400 dark:text-slate-500">
              Generated {new Date(brief.generated_at).toLocaleString()}
              {usage
                ? ` · ${usage.model} · ${usage.input_tokens + usage.output_tokens} tokens · ${
                    usage.estimated_cost_usd != null
                      ? `$${usage.estimated_cost_usd.toFixed(6)}`
                      : "cost —"
                  }`
                : ""}
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Not written yet. Everything below was gathered without any AI — the brief
            turns it into the paragraph you would read at 9am. <Badge tone="info">1 request</Badge>
          </p>
        )}
      </div>
    </Card>
  );
}
