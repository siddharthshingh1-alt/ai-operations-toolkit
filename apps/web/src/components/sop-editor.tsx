"use client";

import { useState } from "react";
import type { SopContent, SopMetadata, SopStatus, UsageInfo } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";

/**
 * The review-and-edit step.
 *
 * CLAUDE.md Section 9 says "allow editing before saving", and Section 5 makes
 * human-in-the-loop a design principle. Nothing reaches the database without
 * passing through this component — the AI drafts, a person approves.
 */

const STATUSES: SopStatus[] = ["draft", "active", "under_review", "retired"];

/** Edit a list of plain strings, one per line. */
function ListField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
        {label}
        <span className="ml-2 font-normal normal-case opacity-70">one per line</span>
      </span>
      <textarea
        rows={Math.min(Math.max(value.length + 1, 3), 12)}
        value={value.join("\n")}
        placeholder={placeholder}
        onChange={(e) =>
          onChange(e.target.value.split("\n").filter((line) => line.trim() !== ""))
        }
        className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-700 dark:bg-slate-950"
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
        {label}
      </span>
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
      />
    </label>
  );
}

export function SopEditor({
  initialContent,
  initialMetadata,
  usage,
  saveLabel,
  onSave,
}: {
  initialContent: SopContent;
  initialMetadata?: Partial<SopMetadata>;
  usage?: UsageInfo;
  saveLabel: string;
  onSave: (input: {
    content: SopContent;
    metadata: Partial<SopMetadata>;
    change_note: string;
  }) => Promise<{ ok: boolean; error?: string }>;
}) {
  const [content, setContent] = useState<SopContent>(initialContent);
  const [owner, setOwner] = useState(initialMetadata?.owner ?? "");
  const [department, setDepartment] = useState(initialMetadata?.department ?? "");
  const [status, setStatus] = useState<SopStatus>(initialMetadata?.status ?? "draft");
  const [effectiveDate, setEffectiveDate] = useState(initialMetadata?.effective_date ?? "");
  const [reviewDate, setReviewDate] = useState(initialMetadata?.review_date ?? "");
  const [changeNote, setChangeNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patch<K extends keyof SopContent>(key: K, value: SopContent[K]) {
    setContent((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    if (!content.title.trim()) {
      setError("Give the SOP a title before saving.");
      return;
    }
    setBusy(true);
    setError(null);

    const result = await onSave({
      content,
      metadata: {
        owner,
        department,
        status,
        effective_date: effectiveDate || null,
        review_date: reviewDate || null,
      },
      change_note: changeNote,
    });

    if (!result.ok) {
      setError(result.error ?? "Could not save.");
      setBusy(false);
    }
    // On success the caller navigates away, so `busy` stays true deliberately —
    // it prevents a second submission during the redirect.
  }

  return (
    <div className="space-y-5">
      {usage ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          <Badge tone={usage.from_demo_cache ? "success" : "info"}>
            {usage.from_demo_cache ? "Replayed recording" : "Live AI"}
          </Badge>
          <span>{usage.model}</span>
          <span>·</span>
          <span>
            {usage.input_tokens.toLocaleString()} in /{" "}
            {usage.output_tokens.toLocaleString()} out tokens
          </span>
          <span>·</span>
          <span>{(usage.duration_ms / 1000).toFixed(1)}s</span>
          <span>·</span>
          <span>
            {usage.estimated_cost_usd !== null
              ? `$${usage.estimated_cost_usd.toFixed(5)}`
              : "cost not priced for this model"}
          </span>
        </div>
      ) : null}

      <Card>
        <CardHeader
          title="Review before saving"
          description="The AI drafted this. Nothing is stored until you save it."
        />
        <div className="space-y-4 px-5 py-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
              Title
            </span>
            <input
              type="text"
              value={content.title}
              onChange={(e) => patch("title", e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-medium dark:border-slate-700 dark:bg-slate-950"
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                Owner
              </span>
              <input
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="Who maintains this SOP"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                Department
              </span>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                Status
              </span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as SopStatus)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  Effective
                </span>
                <input
                  type="date"
                  value={effectiveDate ?? ""}
                  onChange={(e) => setEffectiveDate(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  Review by
                </span>
                <input
                  type="date"
                  value={reviewDate ?? ""}
                  onChange={(e) => setReviewDate(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
            </div>
          </div>

          <TextField label="Purpose" value={content.purpose} onChange={(v) => patch("purpose", v)} />
          <TextField label="Scope" value={content.scope} onChange={(v) => patch("scope", v)} />

          <ListField
            label="Prerequisites"
            value={content.prerequisites}
            onChange={(v) => patch("prerequisites", v)}
          />
          <ListField label="Roles" value={content.roles} onChange={(v) => patch("roles", v)} />

          <div>
            <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
              Procedure
            </span>
            <div className="space-y-2">
              {content.procedure.map((step, index) => (
                <div
                  key={index}
                  className="flex gap-2 rounded-md border border-slate-200 p-2 dark:border-slate-800"
                >
                  <span className="mt-2 w-6 shrink-0 text-center text-sm text-slate-400 tabular-nums">
                    {step.number}
                  </span>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <textarea
                      rows={2}
                      value={step.instruction}
                      onChange={(e) => {
                        const next = [...content.procedure];
                        next[index] = { ...step, instruction: e.target.value };
                        patch("procedure", next);
                      }}
                      className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        value={step.responsible}
                        placeholder="Responsible"
                        onChange={(e) => {
                          const next = [...content.procedure];
                          next[index] = { ...step, responsible: e.target.value };
                          patch("procedure", next);
                        }}
                        className="w-full rounded border border-slate-200 px-2 py-1 text-xs dark:border-slate-800 dark:bg-slate-950"
                      />
                      <input
                        type="text"
                        value={step.expected_result}
                        placeholder="Expected result"
                        onChange={(e) => {
                          const next = [...content.procedure];
                          next[index] = { ...step, expected_result: e.target.value };
                          patch("procedure", next);
                        }}
                        className="w-full rounded border border-slate-200 px-2 py-1 text-xs dark:border-slate-800 dark:bg-slate-950"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      patch(
                        "procedure",
                        content.procedure
                          .filter((_, i) => i !== index)
                          .map((s, i) => ({ ...s, number: i + 1 })),
                      )
                    }
                    className="self-start rounded px-2 py-1 text-xs text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
                    aria-label={`Remove step ${step.number}`}
                  >
                    remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  patch("procedure", [
                    ...content.procedure,
                    {
                      number: content.procedure.length + 1,
                      instruction: "",
                      responsible: "",
                      expected_result: "",
                    },
                  ])
                }
                className="rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-sm text-slate-500 hover:border-slate-400 dark:border-slate-700"
              >
                + Add step
              </button>
            </div>
          </div>

          <ListField
            label="Checklist"
            value={content.checklist}
            onChange={(v) => patch("checklist", v)}
          />
          <ListField
            label="Improvement suggestions"
            value={content.improvement_suggestions}
            onChange={(v) => patch("improvement_suggestions", v)}
          />

          <p className="text-xs text-slate-400 dark:text-slate-500">
            Decision points, exceptions, escalation rules, KPIs, and risks were
            generated and are saved with the SOP. They are shown in full on the
            SOP page and in exports.
          </p>
        </div>
      </Card>

      <Card>
        <div className="space-y-3 px-5 py-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
              What changed?
              <span className="ml-2 font-normal normal-case opacity-70">
                shown in the version history
              </span>
            </span>
            <input
              type="text"
              value={changeNote}
              onChange={(e) => setChangeNote(e.target.value)}
              placeholder="e.g. Added supplier-unreachable exception"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            />
          </label>

          {error ? (
            <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              {error}
            </p>
          ) : null}

          <button
            type="button"
            onClick={save}
            disabled={busy}
            className="rounded-md bg-teal-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-teal-800 disabled:bg-slate-300 dark:disabled:bg-slate-700"
          >
            {busy ? "Saving…" : saveLabel}
          </button>
        </div>
      </Card>
    </div>
  );
}
