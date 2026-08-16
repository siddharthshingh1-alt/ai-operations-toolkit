"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Card, CardHeader } from "@aiops/ui";
import { createWorkflowAction } from "@/app/workflows/actions";

export function NewWorkflowForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(formData: FormData) {
    setError(null);
    startTransition(async () => {
      const result = await createWorkflowAction(formData);
      if (result.ok) router.push(`/workflows/${result.data.id}`);
      else setError(result.error);
    });
  }

  return (
    <Card>
      <CardHeader
        title="New workflow"
        description="Starts empty. Add a Trigger first, then the steps that follow it."
      />
      <form action={submit} className="space-y-3 px-5 py-4">
        <label className="block text-sm">
          <span className="text-slate-700 dark:text-slate-300">Name</span>
          <input
            name="name"
            required
            placeholder="Refund request triage"
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-700 dark:text-slate-300">
            Description <span className="text-slate-400">(optional)</span>
          </span>
          <input
            name="description"
            className="mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          />
        </label>

        {error ? (
          <div
            role="alert"
            className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
          >
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          {pending ? "Creating…" : "Create workflow"}
        </button>
      </form>
    </Card>
  );
}
