import Link from "next/link";
import { Badge, Card, CardHeader, EmptyState } from "@aiops/ui";
import type { BadgeTone } from "@aiops/ui";
import type { SopStatus } from "@aiops/types";
import { AskPanel } from "@/components/ask-panel";
import { tryListSops } from "@/lib/sop-api";

export const metadata = { title: "Documents — AI Operations Toolkit" };

const STATUS_TONE: Record<SopStatus, BadgeTone> = {
  draft: "neutral",
  active: "success",
  under_review: "warning",
  retired: "danger",
};

export default async function DocumentsPage() {
  const sops = await tryListSops();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Documents
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Standard operating procedures — generated, versioned, and searchable.
          </p>
        </div>
        <Link
          href="/documents/new"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          New SOP
        </Link>
      </header>

      {sops === null ? (
        <Card>
          <div className="px-5 py-8 text-center text-sm text-slate-600 dark:text-slate-400">
            <p className="font-medium text-slate-900 dark:text-slate-100">
              Could not reach the API
            </p>
            <p className="mt-1">
              Start it with{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                npm run dev
              </code>
              .
            </p>
          </div>
        </Card>
      ) : (
        <>
          <AskPanel sopCount={sops.length} />

          <Card>
            <CardHeader
              title="SOP library"
              description={
                sops.length === 0
                  ? "Nothing here yet."
                  : `${sops.length} SOP${sops.length === 1 ? "" : "s"}.`
              }
            />

            {sops.length === 0 ? (
              <div className="p-5">
                <EmptyState
                  title="No SOPs yet"
                  description="Describe a process in your own words and the AI will draft a full standard operating procedure for you to review and edit."
                  action={
                    <Link
                      href="/documents/new"
                      className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900"
                    >
                      Create your first SOP
                    </Link>
                  }
                />
              </div>
            ) : (
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {sops.map((sop) => (
                  <li key={sop.id}>
                    <Link
                      href={`/documents/${sop.id}`}
                      className="flex flex-wrap items-start justify-between gap-3 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
                          {sop.title}
                        </h3>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {sop.owner || "No owner"}
                          {sop.department ? ` · ${sop.department}` : ""}
                          {" · "}version {sop.current_version}
                          {sop.review_date ? ` · review by ${sop.review_date}` : ""}
                        </p>
                      </div>
                      <Badge tone={STATUS_TONE[sop.status] ?? "neutral"}>
                        {sop.status.replace("_", " ")}
                      </Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
