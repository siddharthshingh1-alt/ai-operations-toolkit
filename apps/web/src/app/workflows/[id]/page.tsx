import Link from "next/link";
import { notFound } from "next/navigation";
import { tryGetWorkflow, tryListWorkflows } from "@/lib/builder-api";
import { WorkflowEditor } from "@/components/builder/workflow-editor";

export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [detail, list] = await Promise.all([tryGetWorkflow(id), tryListWorkflows()]);

  if (detail === null) notFound();

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <Link
          href="/workflows"
          className="text-sm text-slate-500 underline underline-offset-2 dark:text-slate-400"
        >
          ← Workflows
        </Link>
      </div>

      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          {detail.name}
        </h1>
        {detail.description ? (
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {detail.description}
          </p>
        ) : null}
      </header>

      <WorkflowEditor initial={detail} palette={list?.palette ?? []} />
    </div>
  );
}
