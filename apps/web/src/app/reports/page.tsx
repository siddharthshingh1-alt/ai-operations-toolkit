import { EmptyState } from "@aiops/ui";

export const metadata = { title: "Reports — AI Operations Toolkit" };

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Reports
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Daily, weekly, and monthly operational reports.
        </p>
      </header>

      <EmptyState
        title="No reports yet"
        description="Reporting reuses the dashboard's trend and anomaly analysis rather than rebuilding it."
        phase="Arrives with Project 7 — AI Report Generator"
      />
    </div>
  );
}
