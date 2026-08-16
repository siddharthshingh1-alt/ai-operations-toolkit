import Link from "next/link";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryListWorkflows } from "@/lib/builder-api";
import { NewWorkflowForm } from "@/components/builder/new-workflow-form";

export const metadata = { title: "Workflows — AI Operations Toolkit" };

export default async function WorkflowsPage() {
  const list = await tryListWorkflows();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Workflows
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Build a sequence of steps and run it. Execution uses the shared
          workflow engine — this page is an editor for it, not a second one.
        </p>
      </header>

      {list === null ? (
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
              If this is the deployed site it may be waking from idle — reload in
              a moment.
            </p>
          </div>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader
              title="Saved workflows"
              description={
                list.seeded > 0
                  ? `${list.seeded} starting workflow(s) installed.`
                  : "Open one to edit it, or run it."
              }
            />
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {list.workflows.map((workflow) => (
                <li key={workflow.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/workflows/${workflow.id}`}
                        className="text-sm font-medium text-slate-900 underline-offset-2 hover:underline dark:text-slate-100"
                      >
                        {workflow.name}
                      </Link>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                        {workflow.description}
                      </p>
                      <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                        {workflow.node_count} step
                        {workflow.node_count === 1 ? "" : "s"} ·{" "}
                        {workflow.ai_request_estimate} AI request
                        {workflow.ai_request_estimate === 1 ? "" : "s"} per run
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      {workflow.is_read_only ? (
                        <Badge tone="neutral">read-only</Badge>
                      ) : null}
                      {workflow.blocking_issue_count > 0 ? (
                        <Badge tone="danger">
                          {workflow.blocking_issue_count} blocking
                        </Badge>
                      ) : (
                        <Badge tone="success">runnable</Badge>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          <NewWorkflowForm />
        </>
      )}
    </div>
  );
}
