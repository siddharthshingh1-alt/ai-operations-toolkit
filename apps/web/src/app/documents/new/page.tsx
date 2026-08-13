"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { GenerateResponse } from "@aiops/types";
import { Card, CardHeader } from "@aiops/ui";
import { createAction, generateAction } from "@/app/documents/actions";
import { SopEditor } from "@/components/sop-editor";
import { SOP_EXAMPLES } from "@/lib/sop-examples";

/**
 * Two-step flow: describe the process, then review what the AI wrote.
 *
 * Deliberately two steps rather than one. Saving straight from generation
 * would skip the human review that CLAUDE.md Section 5 requires.
 */
export default function NewSopPage() {
  const router = useRouter();
  const [draft, setDraft] = useState<GenerateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    process_description: "",
    role: "",
    department: "",
    objective: "",
    existing_sop: "",
    document_text: "",
  });
  const [showExisting, setShowExisting] = useState(false);

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (form.process_description.trim().length < 20) {
      setError("Describe the process in a bit more detail — at least a sentence or two.");
      return;
    }
    setBusy(true);
    setError(null);

    const result = await generateAction(form);
    if (result.ok) setDraft(result.data);
    else setError(result.error);
    setBusy(false);
  }

  if (draft) {
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <header>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Review your SOP
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Edit anything that is not right, then save. Nothing has been stored yet.
          </p>
        </header>

        <SopEditor
          initialContent={draft.content}
          initialMetadata={{
            department: form.department,
            status: "draft",
          }}
          usage={draft.usage}
          saveLabel="Save SOP"
          onSave={async (input) => {
            const result = await createAction(input);
            if (result.ok) {
              router.push(`/documents/${result.data.id}`);
              return { ok: true };
            }
            return { ok: false, error: result.error };
          }}
        />

        <button
          type="button"
          onClick={() => setDraft(null)}
          className="text-sm text-slate-500 hover:underline dark:text-slate-400"
        >
          ← Start over with a different description
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          New SOP
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Describe the process the way you would explain it to a colleague. The
          AI turns it into a structured procedure for you to review.
        </p>
      </header>

      <Card>
        <CardHeader
          title="Start from an example"
          description="These three have recorded AI outputs, so they work even in Demo Mode with no API key."
        />
        <div className="flex flex-wrap gap-2 px-5 py-4">
          {SOP_EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() =>
                setForm({
                  process_description: example.process_description,
                  role: example.role,
                  department: example.department,
                  objective: example.objective,
                  existing_sop: "",
                  document_text: "",
                })
              }
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:border-teal-600 hover:text-teal-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-teal-500"
            >
              {example.label}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Describe the process" />
        <form onSubmit={generate} className="space-y-4 px-5 py-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
              What happens, and what goes wrong today?
              <span className="ml-2 text-rose-500">required</span>
            </span>
            <textarea
              rows={7}
              value={form.process_description}
              onChange={(e) => set("process_description", e.target.value)}
              placeholder={
                "e.g. When a flight is delayed more than 3 hours we have to work out which agent bookings are affected, check who has a connection, and tell the agents before the airline does. Everyone does it slightly differently and things get missed."
              }
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
            <span className="mt-1 block text-xs text-slate-400">
              {form.process_description.length} characters — more detail gives a better SOP
            </span>
          </label>

          <div className="grid gap-4 sm:grid-cols-3">
            {(
              [
                ["role", "Who does it", "e.g. Operations Associate"],
                ["department", "Department", "e.g. Flight Operations"],
                ["objective", "Objective", "e.g. Contact agents in 30 min"],
              ] as const
            ).map(([key, label, placeholder]) => (
              <label key={key} className="block">
                <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  {label}
                </span>
                <input
                  type="text"
                  value={form[key]}
                  onChange={(e) => set(key, e.target.value)}
                  placeholder={placeholder}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
            ))}
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowExisting((v) => !v)}
              className="text-sm text-slate-500 hover:underline dark:text-slate-400"
            >
              {showExisting ? "−" : "+"} Improve an existing SOP instead
            </button>
            {showExisting ? (
              <textarea
                rows={6}
                value={form.existing_sop}
                onChange={(e) => set("existing_sop", e.target.value)}
                placeholder="Paste your current SOP here. Anything correct and specific will be kept; what is vague or missing gets fixed."
                className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              />
            ) : null}
          </div>

          {error ? (
            <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </p>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-teal-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-teal-800 disabled:bg-slate-300 dark:disabled:bg-slate-700"
            >
              {busy ? "Writing the SOP…" : "Generate SOP"}
            </button>
            <Link
              href="/documents"
              className="text-sm text-slate-500 hover:underline dark:text-slate-400"
            >
              Cancel
            </Link>
          </div>

          {busy ? (
            <p className="text-xs text-slate-400">
              This usually takes 10–30 seconds. The AI is writing the full
              procedure, decision points, exceptions, and KPIs.
            </p>
          ) : null}
        </form>
      </Card>
    </div>
  );
}
