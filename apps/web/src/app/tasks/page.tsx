import { EmptyState } from "@aiops/ui";

export const metadata = { title: "Tasks — AI Operations Toolkit" };

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Tasks
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Projects, tasks, owners, deadlines, and blockers.
        </p>
      </header>

      <EmptyState
        title="No tasks yet"
        description="Task tracking with an AI health assessment that explains its reasoning."
        phase="Arrives with Project 5 — AI Project Tracker"
      />
    </div>
  );
}
