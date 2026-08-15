import Link from "next/link";
import { notFound } from "next/navigation";
import { Card } from "@aiops/ui";
import { tryGetIncident } from "@/lib/travel-api";
import { IncidentPanel } from "@/components/travel/incident-panel";

export default async function IncidentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const incident = await tryGetIncident(id);

  if (incident === null) {
    // Either the incident does not exist or the API is unreachable. The list
    // page reports an unreachable API; from here, "not found" is the useful
    // answer rather than a spinner.
    notFound();
  }

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
          {incident.title}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {incident.kind.replace(/_/g, " ")}
          {incident.route ? ` · ${incident.route}` : ""}
          {incident.supplier ? ` · ${incident.supplier}` : ""}
        </p>
        {incident.description ? (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            {incident.description}
          </p>
        ) : null}
      </header>

      <Card className="border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-600 shadow-none dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-400">
        Synthetic data. No airline, GDS or payment system is connected, and no
        email is transmitted — an approved message is recorded and labelled.
      </Card>

      <IncidentPanel initial={incident} />
    </div>
  );
}
