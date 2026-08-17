import { Card, CardHeader } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryGetProject, tryListProjects } from "@/lib/tracker-api";
import { NewProjectForm } from "@/components/tracker/new-project-form";
import { TrackerPanel } from "@/components/tracker/tracker-panel";

export const metadata = { title: "Tasks — AI Operations Toolkit" };

/**
 * Project 5 — AI Project Tracker (CLAUDE.md Section 13).
 *
 * The list and the first project's detail are fetched on the server so the
 * page arrives populated. No AI call happens here: health, next actions,
 * summaries and the weekly report are all behind buttons, because the public
 * demo runs live on a free tier and a page that assessed every project on
 * every visit would spend the day's budget on nobody's question.
 */
export default async function Page() {
  const list = await tryListProjects();
  const first = list?.projects[0];
  const detail = first ? await tryGetProject(first.id) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Project tracker
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Projects, tasks, owners, deadlines, dependencies, risks and blockers. The
          figures are computed; the health status is the AI&rsquo;s, and it has to say
          why.
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
              If this is the deployed site it may be waking from idle — reload in a
              moment.
            </p>
          </div>
        </Card>
      ) : list.projects.length === 0 ? (
        <Card>
          <CardHeader title="No projects yet" description="Create one to get started." />
          <div className="px-5 py-4">
            <NewProjectForm />
          </div>
        </Card>
      ) : (
        <>
          <TrackerPanel projects={list.projects} initialDetail={detail} />
          <NewProjectForm />
        </>
      )}
    </div>
  );
}
