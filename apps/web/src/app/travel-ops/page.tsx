import Link from "next/link";
import type { IncidentSummary, Severity } from "@aiops/types";
import { Badge, Card, CardHeader, EmptyState } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryListIncidents, tryListPartners } from "@/lib/travel-api";
import { ReportIncidentForm } from "@/components/travel/report-incident-form";

export const metadata = { title: "Travel Ops — AI Operations Toolkit" };

function severityTone(severity: Severity | null) {
  if (severity === "critical" || severity === "high") return "danger" as const;
  if (severity === "medium") return "warning" as const;
  if (severity === "low") return "neutral" as const;
  return "neutral" as const;
}

function inr(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)} L`;
  return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function IncidentRow({ incident }: { incident: IncidentSummary }) {
  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link
            href={`/travel-ops/${incident.id}`}
            className="text-sm font-medium text-slate-900 underline-offset-2 hover:underline dark:text-slate-100"
          >
            {incident.title}
          </Link>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {incident.kind.replace(/_/g, " ")}
            {incident.route ? ` · ${incident.route}` : ""}
            {incident.supplier ? ` · ${incident.supplier}` : ""}
          </p>
          <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">
            <strong className="tabular-nums">{incident.affected_count}</strong> booking
            {incident.affected_count === 1 ? "" : "s"} affected ·{" "}
            <span className="tabular-nums">{inr(incident.affected_value_inr)}</span> at risk
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {incident.severity ? (
            <Badge tone={severityTone(incident.severity)}>{incident.severity}</Badge>
          ) : (
            <Badge tone="neutral">not assessed</Badge>
          )}
          {incident.awaiting_approval_count > 0 ? (
            <span className="text-xs text-amber-700 dark:text-amber-500">
              {incident.awaiting_approval_count} awaiting approval
            </span>
          ) : null}
        </div>
      </div>
    </li>
  );
}

export default async function TravelOpsPage() {
  const [list, partnerList] = await Promise.all([
    tryListIncidents(),
    tryListPartners(),
  ]);

  if (list === null) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Travel operations
          </h1>
        </header>
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
      </div>
    );
  }

  const incidents = list.incidents;
  const awaiting = incidents.reduce((n, i) => n + i.awaiting_approval_count, 0);
  const partners = partnerList?.partners ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Travel operations
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Incidents affecting travel-agency bookings. The AI assesses and drafts;
          nothing reaches a partner until a person approves it.
        </p>
      </header>

      <div className="rounded-lg border border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
        <strong className="text-slate-800 dark:text-slate-200">Simulation.</strong>{" "}
        All bookings, agencies and travellers here are synthetic. No airline,
        GDS or payment system is connected, and no email is ever transmitted —
        an approved message is recorded and labelled as such.
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Incidents", String(incidents.length)],
          [
            "Bookings affected",
            String(incidents.reduce((n, i) => n + i.affected_count, 0)),
          ],
          ["Awaiting approval", String(awaiting)],
          ["Agency partners", String(partners.length)],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900"
          >
            <p className="text-xs tracking-wide text-slate-500 uppercase dark:text-slate-400">
              {label}
            </p>
            <p className="mt-1 text-xl font-semibold text-slate-900 tabular-nums dark:text-slate-100">
              {value}
            </p>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader
          title="Open incidents"
          description={
            list.seeded > 0
              ? `${list.seeded} incident(s) seeded from delays already present in the booking data.`
              : "Newest first. Open one to assess it and draft agency communications."
          }
          action={
            <Link
              href="/travel-ops/partners"
              className="text-sm text-slate-600 underline underline-offset-2 dark:text-slate-400"
            >
              Agency partners →
            </Link>
          }
        />
        {incidents.length === 0 ? (
          <div className="px-5 py-8">
            <EmptyState
              title="No incidents"
              description="Report one below to see the workflow run."
            />
          </div>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {incidents.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} />
            ))}
          </ul>
        )}
      </Card>

      <ReportIncidentForm />
    </div>
  );
}
