"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Card, CardHeader } from "@aiops/ui";
import { reportAction } from "@/app/travel-ops/actions";

const KINDS = [
  ["flight_delay", "Flight delay"],
  ["flight_cancellation", "Flight cancellation"],
  ["hotel_overbooking", "Hotel overbooking"],
  ["schedule_change", "Schedule change"],
  ["other", "Other"],
] as const;

/**
 * Report an incident.
 *
 * Reporting runs the affected-booking lookup and costs no AI request, so the
 * console stays useful when the day's model budget is spent.
 */
export function ReportIncidentForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(formData: FormData) {
    setError(null);
    startTransition(async () => {
      const result = await reportAction(formData);
      if (result.ok) router.push(`/travel-ops/${result.data.id}`);
      else setError(result.error);
    });
  }

  return (
    <Card>
      <CardHeader
        title="Report an incident"
        description="Finds the affected bookings immediately. No AI is used until you ask for it."
      />
      <form action={submit} className="space-y-4 px-5 py-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-slate-700 dark:text-slate-300">Type</span>
            <select
              name="kind"
              defaultValue="flight_delay"
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              {KINDS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-slate-700 dark:text-slate-300">
              Route <span className="text-slate-400">(e.g. DEL-DXB)</span>
            </span>
            <input
              name="route"
              placeholder="DEL-DXB"
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="text-slate-700 dark:text-slate-300">Title</span>
          <input
            name="title"
            required
            placeholder="DEL-DXB delayed by six hours"
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-slate-700 dark:text-slate-300">
              Supplier <span className="text-slate-400">(optional)</span>
            </span>
            <input
              name="supplier"
              placeholder="Air India"
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
          </label>

          <label className="block text-sm">
            <span className="text-slate-700 dark:text-slate-300">
              Departure date affected
            </span>
            <input
              type="date"
              name="occurred_at"
              className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="text-slate-700 dark:text-slate-300">
            What happened <span className="text-slate-400">(optional)</span>
          </span>
          <textarea
            name="description"
            rows={3}
            placeholder="Aircraft technical issue; revised departure not yet confirmed."
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </label>

        {error ? (
          <div
            role="alert"
            className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
          >
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          {pending ? "Finding affected bookings…" : "Report incident"}
        </button>
      </form>
    </Card>
  );
}
