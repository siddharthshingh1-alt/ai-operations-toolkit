import { EmptyState } from "@aiops/ui";

export const metadata = { title: "Documents — AI Operations Toolkit" };

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Documents
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          SOPs and generated documents, with version history and export.
        </p>
      </header>

      <EmptyState
        title="No documents yet"
        description="SOP generation, version diffing, and citation-backed search land first in the build order."
        phase="Arrives with Project 1 — AI SOP Generator"
      />
    </div>
  );
}
