import { Badge, Card } from "@aiops/ui";
import { projectsByPhase } from "@/lib/projects";

export const metadata = { title: "Projects — AI Operations Toolkit" };

export default function ProjectsPage() {
  const projects = projectsByPhase();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Projects
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Nine projects, each mapped to a requirement from the role this
          portfolio targets. Built strictly one at a time.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {projects.map((project) => (
          <Card key={project.slug} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {project.name}
              </h2>
              <Badge tone={project.status === "shipped" ? "success" : "neutral"}>
                {project.status.replace("_", " ")}
              </Badge>
            </div>

            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              {project.description}
            </p>

            <dl className="mt-4 space-y-1.5 border-t border-slate-100 pt-3 dark:border-slate-800">
              <div className="flex gap-2 text-xs">
                <dt className="shrink-0 text-slate-400 dark:text-slate-500">
                  Proves
                </dt>
                <dd className="text-slate-600 dark:text-slate-400">
                  {project.jdRequirement}
                </dd>
              </div>
              <div className="flex gap-2 text-xs">
                <dt className="shrink-0 text-slate-400 dark:text-slate-500">
                  Build order
                </dt>
                <dd className="text-slate-600 dark:text-slate-400">
                  Phase {project.phase}
                </dd>
              </div>
            </dl>
          </Card>
        ))}
      </div>
    </div>
  );
}
