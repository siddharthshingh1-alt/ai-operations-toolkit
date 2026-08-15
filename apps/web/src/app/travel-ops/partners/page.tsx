import Link from "next/link";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { tryListPartners } from "@/lib/travel-api";

export const metadata = { title: "Agency partners — AI Operations Toolkit" };

function inr(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)} L`;
  return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

/**
 * The folded-in partner relationship view (CLAUDE.md Sections 14 and 18).
 *
 * Deliberately not a generic CRM. These agencies are already customers, so
 * there is no pipeline to manage — what an operations team needs is volume,
 * what is currently going wrong, and whether anyone is owed a reply. Every
 * number is computed from the booking, ticket and incident data.
 */
export default async function PartnersPage() {
  const list = await tryListPartners();
  const partners = list?.partners ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <Link
          href="/travel-ops"
          className="text-sm text-slate-500 underline underline-offset-2 dark:text-slate-400"
        >
          ← Travel operations
        </Link>
      </div>

      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Agency partners
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          The travel agencies who book through the platform. These are the
          customers — not the travellers.
        </p>
      </header>

      {list === null ? (
        <Card>
          <div className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
            Could not reach the API. If this is the deployed site it may be waking
            from idle — reload in a moment.
          </div>
        </Card>
      ) : (
        <Card>
          <CardHeader
            title={`${partners.length} agencies`}
            description="Ordered by booking value. Follow-ups are derived from open work, not generated."
          />
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {partners.map((partner) => (
              <li key={partner.agent_id} className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {partner.agent_name}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {partner.agent_id}
                    </p>

                    <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
                      {[
                        ["Bookings", String(partner.booking_count)],
                        ["Value", inr(partner.total_value_inr)],
                        ["Delayed", String(partner.delayed)],
                        ["Open tickets", String(partner.open_tickets)],
                      ].map(([label, value]) => (
                        <div key={label}>
                          <dt className="text-xs text-slate-400 dark:text-slate-500">
                            {label}
                          </dt>
                          <dd className="text-sm text-slate-700 tabular-nums dark:text-slate-300">
                            {value}
                          </dd>
                        </div>
                      ))}
                    </dl>

                    {partner.next_follow_up ? (
                      <p className="mt-2 text-sm text-amber-800 dark:text-amber-500">
                        Next follow-up: {partner.next_follow_up}
                      </p>
                    ) : (
                      <p className="mt-2 text-sm text-slate-500 dark:text-slate-500">
                        Nothing outstanding.
                      </p>
                    )}
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    {partner.urgent_tickets > 0 ? (
                      <Badge tone="danger">{partner.urgent_tickets} urgent</Badge>
                    ) : null}
                    {partner.incidents_involved > 0 ? (
                      <Badge tone="neutral">
                        {partner.incidents_involved} incident
                        {partner.incidents_involved === 1 ? "" : "s"}
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
