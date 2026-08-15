"use client";

import { useState, useTransition } from "react";
import type { CommunicationView, IncidentDetail, Severity } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { assessAction, decideAction } from "@/app/travel-ops/actions";

/**
 * One incident: what is affected, what the model thinks, and what a person
 * decides.
 *
 * The layout follows the order of authority. Measured facts first — the
 * bookings and the value at risk, which nothing generated. The assessment
 * second, labelled as a judgement with its reasoning attached. The drafts
 * last, each behind an explicit decision that cannot be made anonymously.
 */

function severityTone(severity: Severity | null) {
  if (severity === "critical" || severity === "high") return "danger" as const;
  if (severity === "medium") return "warning" as const;
  return "neutral" as const;
}

function inr(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)} L`;
  return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function when(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function CommunicationCard({
  communication,
  incidentId,
  approver,
  onApproverMissing,
  onUpdated,
}: {
  communication: CommunicationView;
  incidentId: string;
  approver: string;
  onApproverMissing: (message: string) => void;
  onUpdated: (updated: CommunicationView) => void;
}) {
  const [pending, startTransition] = useTransition();
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);

  const isDraft = communication.status === "draft";

  function decide(approved: boolean) {
    startTransition(async () => {
      const result = await decideAction(
        communication.id,
        incidentId,
        approved,
        approver,
        approved ? undefined : note,
      );
      if (result.ok) onUpdated(result.data);
      else onApproverMissing(result.error);
    });
  }

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
            {communication.agent_name}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            {communication.agent_id} · {communication.booking_ids.length} booking
            {communication.booking_ids.length === 1 ? "" : "s"}
          </p>
        </div>
        {communication.status === "draft" ? (
          <Badge tone="warning">draft — not sent</Badge>
        ) : communication.status === "approved" ? (
          <Badge tone="success">
            {communication.recorded_message_id
              ? "approved · recorded"
              : "approved · recording pending"}
          </Badge>
        ) : (
          <Badge tone="neutral">rejected</Badge>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
          {communication.subject}
        </p>
        <p className="text-sm whitespace-pre-wrap text-slate-600 dark:text-slate-400">
          {communication.body}
        </p>

        {communication.approved_by ? (
          <p className="border-t border-slate-100 pt-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-500">
            {communication.status === "approved" ? "Approved" : "Rejected"} by{" "}
            <strong className="text-slate-700 dark:text-slate-300">
              {communication.approved_by}
            </strong>{" "}
            on {when(communication.approved_at)}
            {communication.rejection_note ? ` — “${communication.rejection_note}”` : ""}
            {communication.recorded_message_id ? (
              <>
                {" "}
                · reference{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5 dark:bg-slate-800">
                  {communication.recorded_message_id}
                </code>{" "}
                <span className="text-slate-400">(recorded, not transmitted)</span>
              </>
            ) : null}
          </p>
        ) : null}

        {isDraft ? (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
            <button
              type="button"
              disabled={pending}
              onClick={() => decide(true)}
              className="rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-60"
            >
              {pending ? "Working…" : "Approve"}
            </button>
            <button
              type="button"
              disabled={pending}
              onClick={() => (showNote ? decide(false) : setShowNote(true))}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {showNote ? "Confirm reject" : "Reject"}
            </button>
            {showNote ? (
              <input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Why are you rejecting it?"
                className="min-w-48 flex-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function IncidentPanel({ initial }: { initial: IncidentDetail }) {
  const [incident, setIncident] = useState(initial);
  const [approver, setApprover] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [usageNote, setUsageNote] = useState<string | null>(null);
  const [assessing, setAssessing] = useState(false);

  async function assess() {
    setAssessing(true);
    setError(null);
    const result = await assessAction(incident.id);
    if (result.ok) {
      setIncident(result.data.incident);
      const usage = result.data.usage;
      setUsageNote(
        `${usage.model} · ${usage.input_tokens.toLocaleString()} in / ${usage.output_tokens.toLocaleString()} out · ${(usage.duration_ms / 1000).toFixed(1)}s` +
          (usage.estimated_cost_usd !== null
            ? ` · ~$${usage.estimated_cost_usd.toFixed(4)}`
            : ""),
      );
    } else {
      setError(result.error);
    }
    setAssessing(false);
  }

  function onUpdated(updated: CommunicationView) {
    setError(null);
    setIncident({
      ...incident,
      communications: incident.communications.map((c) =>
        c.id === updated.id ? updated : c,
      ),
    });
  }

  const drafts = incident.communications.filter((c) => c.status === "draft");

  return (
    <div className="space-y-6">
      {/* ---- measured facts, first ---------------------------------------- */}
      <Card>
        <CardHeader
          title="Affected bookings"
          description="Found by matching route, supplier and date. No model was involved."
          action={
            <Badge tone="neutral">{incident.status.replace(/_/g, " ")}</Badge>
          }
        />
        <div className="grid grid-cols-2 gap-4 border-b border-slate-200 px-5 py-4 sm:grid-cols-4 dark:border-slate-800">
          {[
            ["Bookings", String(incident.affected_count)],
            ["Value at risk", inr(incident.affected_value_inr)],
            [
              "Agencies",
              String(new Set(incident.affected_bookings.map((b) => b.agent_id)).size),
            ],
            ["Reported", when(incident.created_at)],
          ].map(([label, value]) => (
            <div key={label}>
              <p className="text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
                {label}
              </p>
              <p className="mt-0.5 text-sm font-medium text-slate-900 tabular-nums dark:text-slate-100">
                {value}
              </p>
            </div>
          ))}
        </div>

        {incident.affected_bookings.length > 0 ? (
          <div className="max-h-80 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 border-b border-slate-200 bg-white text-xs tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                <tr>
                  {["Booking", "Agency", "Traveller", "Departs", "Value"].map((h) => (
                    <th key={h} className="px-5 py-2 font-medium whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {incident.affected_bookings.map((booking) => (
                  <tr key={booking.id}>
                    <td className="px-5 py-1.5 whitespace-nowrap text-slate-700 dark:text-slate-300">
                      {booking.id}
                    </td>
                    <td className="px-5 py-1.5 whitespace-nowrap text-slate-700 dark:text-slate-300">
                      {booking.agent_name}
                    </td>
                    <td className="px-5 py-1.5 whitespace-nowrap text-slate-600 dark:text-slate-400">
                      {booking.traveller_name}
                    </td>
                    <td className="px-5 py-1.5 whitespace-nowrap text-slate-600 dark:text-slate-400">
                      {when(booking.departure_at)}
                    </td>
                    <td className="px-5 py-1.5 whitespace-nowrap text-slate-700 tabular-nums dark:text-slate-300">
                      {inr(booking.value_inr)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
            No bookings matched this incident. Check the route, supplier and date.
          </p>
        )}
      </Card>

      {/* ---- the model's judgement ---------------------------------------- */}
      <Card>
        <CardHeader
          title="Assessment"
          description="A judgement, not a measurement — shown with the reasoning behind it."
          action={
            <button
              type="button"
              onClick={assess}
              disabled={assessing || incident.affected_count === 0}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {assessing
                ? "Assessing…"
                : incident.severity
                  ? "Re-assess and redraft"
                  : "Assess and draft"}
            </button>
          }
        />
        <div className="space-y-3 px-5 py-4">
          {error ? (
            <div
              role="alert"
              className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
            >
              {error}
            </div>
          ) : null}

          {incident.severity ? (
            <>
              <div className="flex items-center gap-2">
                <Badge tone={severityTone(incident.severity)}>
                  {incident.severity}
                </Badge>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  assigned by the model
                </span>
              </div>
              <div>
                <p className="text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  Why
                </p>
                <p className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">
                  {incident.severity_reasoning}
                </p>
              </div>
              <div>
                <p className="text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  Traveller impact
                </p>
                <p className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">
                  {incident.traveller_impact}
                </p>
              </div>
              <div>
                <p className="text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
                  Recommended action
                </p>
                <p className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">
                  {incident.recommended_action}
                </p>
              </div>
              {usageNote ? (
                <p className="border-t border-slate-200 pt-3 text-xs text-slate-400 dark:border-slate-800 dark:text-slate-500">
                  {usageNote}
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Not assessed yet. Pressing the button spends two AI requests — one to
              judge severity, one to draft the agency messages — and stops before
              anything is sent.
            </p>
          )}
        </div>
      </Card>

      {/* ---- drafts and the human decision --------------------------------- */}
      {incident.communications.length > 0 ? (
        <Card>
          <CardHeader
            title="Agency communications"
            description="Drafted by the model. Nothing here has been sent, and nothing will be without your approval."
            action={
              drafts.length > 0 ? (
                <Badge tone="warning">{drafts.length} awaiting you</Badge>
              ) : (
                <Badge tone="success">all decided</Badge>
              )
            }
          />
          <div className="space-y-4 px-5 py-4">
            <label className="block text-sm">
              <span className="text-slate-700 dark:text-slate-300">
                Your name — required, so the decision is attributable
              </span>
              <input
                value={approver}
                onChange={(event) => setApprover(event.target.value)}
                placeholder="e.g. Anita Rao"
                className="mt-1 block w-full max-w-sm rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
            </label>

            {incident.communications.map((communication) => (
              <CommunicationCard
                key={communication.id}
                communication={communication}
                incidentId={incident.id}
                approver={approver}
                onApproverMissing={setError}
                onUpdated={onUpdated}
              />
            ))}
          </div>
        </Card>
      ) : null}

      {/* ---- the audit trail ------------------------------------------------ */}
      {incident.execution ? (
        <Card>
          <CardHeader
            title="Execution log"
            description="Every step of the workflow, including where it stopped for a person."
          />
          <ol className="divide-y divide-slate-200 dark:divide-slate-800">
            {incident.execution.node_runs.map((run, index) => (
              <li
                key={`${run.node_id}-${index}`}
                className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-2.5"
              >
                <span className="text-sm text-slate-700 dark:text-slate-300">
                  {index + 1}. {run.label}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {run.status.replace(/_/g, " ")}
                  {run.duration_ms ? ` · ${run.duration_ms} ms` : ""}
                  {typeof run.output?.recorded === "number"
                    ? ` · recorded ${run.output.recorded}, transmitted 0`
                    : ""}
                </span>
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}
