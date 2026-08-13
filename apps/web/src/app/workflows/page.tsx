import { EmptyState } from "@aiops/ui";

export const metadata = { title: "Workflows — AI Operations Toolkit" };

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Workflows
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Visual automations built on the shared workflow engine.
        </p>
      </header>

      <EmptyState
        title="No workflows yet"
        description="The engine is built and tested; the visual editor that drives it is the next thing to land here."
        phase="Arrives with Project 4 — AI Workflow Builder"
      />
    </div>
  );
}
