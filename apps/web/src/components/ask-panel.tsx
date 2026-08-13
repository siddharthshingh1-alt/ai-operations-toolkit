"use client";

import { useState } from "react";
import Link from "next/link";
import type { AskResponse } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { askAction } from "@/app/documents/actions";

/**
 * Ask a question across the SOP library.
 *
 * The important behaviour here is the `answered === false` branch: when nothing
 * in the library is relevant, that is displayed as a clear, deliberate "no
 * answer" with the reason — never softened into a vague response that might
 * read as an answer (CLAUDE.md Section 9).
 */
export function AskPanel({ sopCount }: { sopCount: number }) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || busy) return;

    setBusy(true);
    setError(null);
    setResponse(null);

    const result = await askAction(question.trim());
    if (result.ok) setResponse(result.data);
    else setError(result.error);
    setBusy(false);
  }

  return (
    <Card>
      <CardHeader
        title="Ask your SOPs"
        description={
          sopCount === 0
            ? "Once you have saved an SOP, you can ask questions across the library."
            : `Answers are drawn from your ${sopCount} saved SOP${sopCount === 1 ? "" : "s"}, with sources shown.`
        }
      />

      <div className="px-5 py-4">
        <form onSubmit={submit} className="flex flex-wrap gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. How quickly must we contact agents after a delay?"
            disabled={sopCount === 0 || busy}
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:disabled:bg-slate-900"
          />
          <button
            type="submit"
            disabled={sopCount === 0 || busy || !question.trim()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-900 dark:disabled:bg-slate-700"
          >
            {busy ? "Searching…" : "Ask"}
          </button>
        </form>

        {error ? (
          <p className="mt-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
            {error}
          </p>
        ) : null}

        {response ? (
          <div className="mt-4 space-y-3">
            {response.result.answered ? (
              <>
                <p className="text-sm whitespace-pre-wrap text-slate-800 dark:text-slate-200">
                  {response.result.answer}
                </p>

                <div>
                  <p className="mb-1.5 text-xs font-medium tracking-wide text-slate-400 uppercase dark:text-slate-500">
                    Sources
                  </p>
                  <ul className="space-y-1">
                    {response.result.citations.map((c) => (
                      <li key={c.sop_id}>
                        <Link
                          href={`/documents/${c.sop_id}`}
                          className="inline-flex items-center gap-2 text-sm text-teal-700 hover:underline dark:text-teal-400"
                        >
                          {c.title}
                          <Badge tone="neutral">
                            v{c.version} · {Math.round(c.similarity * 100)}% match
                          </Badge>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              // The deliberate refusal path. Styled as information, not failure.
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 dark:border-amber-900 dark:bg-amber-950/30">
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                  No SOP covers this
                </p>
                <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
                  {response.result.answer}
                </p>
              </div>
            )}

            <p className="border-t border-slate-100 pt-2 text-xs text-slate-400 dark:border-slate-800 dark:text-slate-500">
              {response.result.reasoning_summary}
              {response.skipped_ai
                ? " · No AI call was made, so nothing could be invented."
                : ` · ${response.usage.model} · ${response.usage.input_tokens + response.usage.output_tokens} tokens${
                    response.usage.estimated_cost_usd !== null
                      ? ` · $${response.usage.estimated_cost_usd.toFixed(5)}`
                      : ""
                  }`}
            </p>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
