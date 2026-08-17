"use client";

import { useMemo, useState } from "react";
import { Badge, Card, CardHeader } from "@aiops/ui";
import type {
  Health,
  TaskView,
  TrackedProjectDetail,
  TrackedProjectListItem,
  TrackerUsageInfo,
  WeeklyReportResponse,
} from "@aiops/types";
import {
  assessHealthAction,
  createTaskAction,
  deleteTaskAction,
  exportWeeklyReportAction,
  generateWeeklyReportAction,
  getProjectAction,
  suggestNextActionsAction,
  summarizeProjectAction,
  updateTaskAction,
} from "@/app/tasks/actions";

/**
 * The Project Tracker's whole interface.
 *
 * The rule this component exists to make visible: **every number on the left
 * is computed, every sentence on the right is a model's opinion of those
 * numbers.** Overdue counts, blocked counts and dependency state arrive from
 * the API already calculated and are rendered as facts. Health, next actions,
 * the summary and the report are shown next to the figures they were derived
 * from, so a reader can disagree with them.
 *
 * No AI runs on mount. Each of the four buttons spends exactly one request and
 * says so before it is pressed.
 */

const HEALTH_TONE: Record<Health, "success" | "warning" | "danger"> = {
  green: "success",
  yellow: "warning",
  red: "danger",
};

const STATUS_LABEL: Record<string, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2 dark:border-slate-800">
      <div className={`text-lg font-semibold tabular-nums ${tone ?? "text-slate-900 dark:text-slate-100"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

function UsageLine({ usage }: { usage: TrackerUsageInfo | null }) {
  if (!usage) return null;
  const cost =
    usage.estimated_cost_usd != null ? `$${usage.estimated_cost_usd.toFixed(6)}` : "—";
  return (
    <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
      {usage.from_demo_cache ? "Replayed from a recording" : "Live"} · {usage.model} ·{" "}
      {usage.input_tokens + usage.output_tokens} tokens · {cost} · {usage.duration_ms}ms
    </p>
  );
}

function AiButton({
  onClick,
  busy,
  disabled,
  children,
}: {
  onClick: () => void;
  busy: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy || disabled}
      className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
    >
      {busy ? "Working…" : children}
    </button>
  );
}

function TaskRow({
  task,
  onToggle,
  onDelete,
  busy,
}: {
  task: TaskView;
  onToggle: (task: TaskView) => void;
  onDelete: (task: TaskView) => void;
  busy: boolean;
}) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <input
        type="checkbox"
        checked={task.status === "done"}
        onChange={() => onToggle(task)}
        disabled={busy}
        aria-label={`Mark ${task.title} as ${task.status === "done" ? "not done" : "done"}`}
        className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 dark:border-slate-600"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={
              task.status === "done"
                ? "text-sm text-slate-400 line-through dark:text-slate-500"
                : "text-sm text-slate-900 dark:text-slate-100"
            }
          >
            {task.title}
          </span>
          <Badge tone={task.status === "blocked" ? "danger" : "neutral"}>
            {STATUS_LABEL[task.status] ?? task.status}
          </Badge>
          {task.is_overdue ? (
            <Badge tone="danger">
              {task.days_overdue} day{task.days_overdue === 1 ? "" : "s"} overdue
            </Badge>
          ) : null}
          {task.blocked_by ? <Badge tone="warning">waiting on {task.blocked_by}</Badge> : null}
          {task.priority === "urgent" ? <Badge tone="danger">urgent</Badge> : null}
        </div>
        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {task.owner || "unassigned"}
          {task.due_date ? ` · due ${task.due_date}` : " · no due date"}
          {task.depends_on_title ? ` · after “${task.depends_on_title}”` : ""}
        </div>
        {task.blocker_note ? (
          <p className="mt-1 text-xs text-rose-700 dark:text-rose-300">
            Blocked: {task.blocker_note}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => onDelete(task)}
        disabled={busy}
        className="text-xs text-slate-400 underline underline-offset-2 hover:text-rose-600 disabled:opacity-50"
      >
        Remove
      </button>
    </li>
  );
}

export function TrackerPanel({
  projects,
  initialDetail,
}: {
  projects: TrackedProjectListItem[];
  initialDetail: TrackedProjectDetail | null;
}) {
  const [detail, setDetail] = useState<TrackedProjectDetail | null>(initialDetail);
  const [list, setList] = useState(projects);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<TrackerUsageInfo | null>(null);
  const [report, setReport] = useState<WeeklyReportResponse | null>(null);
  const [showAddTask, setShowAddTask] = useState(false);

  const facts = detail?.facts;
  const openTasks = useMemo(
    () => (detail?.tasks ?? []).filter((t) => t.status !== "done"),
    [detail],
  );

  async function pickProject(id: string) {
    if (detail?.id === id) return;
    setError(null);
    setUsage(null);
    setBusy("load");
    const result = await getProjectAction(id);
    if (result.ok) setDetail(result.data);
    else setError(result.error);
    setBusy(null);
  }

  /** Apply a fresh detail payload returned by any action. */
  function applyDetail(next: TrackedProjectDetail) {
    setDetail(next);
    setList((current) =>
      current.map((p) =>
        p.id === next.id
          ? {
              ...p,
              health: next.health,
              health_reasoning: next.health_reasoning,
              task_count: next.facts.task_count,
              done_count: next.facts.done_count,
              overdue_count: next.facts.overdue_count,
              blocked_count: next.facts.blocked_count,
              completion_percent: next.facts.completion_percent,
            }
          : p,
      ),
    );
  }

  async function runAi(
    key: string,
    call: (id: string) => Promise<{ ok: boolean } & Record<string, unknown>>,
  ) {
    if (!detail) return;
    setBusy(key);
    setError(null);
    const result = (await call(detail.id)) as
      | { ok: true; data: { project: TrackedProjectDetail; usage: TrackerUsageInfo } }
      | { ok: false; error: string };
    if (result.ok) {
      applyDetail(result.data.project);
      setUsage(result.data.usage);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  async function toggleTask(task: TaskView) {
    setBusy(task.id);
    setError(null);
    const result = await updateTaskAction(task.id, {
      status: task.status === "done" ? "todo" : "done",
    });
    if (result.ok) applyDetail(result.data);
    else setError(result.error);
    setBusy(null);
  }

  async function removeTask(task: TaskView) {
    setBusy(task.id);
    setError(null);
    const result = await deleteTaskAction(task.id);
    if (result.ok) applyDetail(result.data);
    else setError(result.error);
    setBusy(null);
  }

  async function addTask(formData: FormData) {
    if (!detail) return;
    setBusy("add");
    setError(null);
    const result = await createTaskAction(detail.id, formData);
    if (result.ok) {
      applyDetail(result.data);
      setShowAddTask(false);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  async function makeReport() {
    setBusy("report");
    setError(null);
    const result = await generateWeeklyReportAction();
    if (result.ok) setReport(result.data);
    else setError(result.error);
    setBusy(null);
  }

  async function download(format: "markdown" | "html" | "pdf") {
    if (!report) return;
    setBusy(`export-${format}`);
    const result = await exportWeeklyReportAction(report.content, format);
    if (result.ok) {
      const bytes = Uint8Array.from(atob(result.data.base64), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: result.data.contentType }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  return (
    <div className="space-y-6">
      {error ? (
        <div
          role="alert"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* ---- project list ------------------------------------------- */}
        <Card>
          <CardHeader title="Projects" description="Health is assigned by the AI, on request." />
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {list.map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  onClick={() => void pickProject(project.id)}
                  className={`w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 ${
                    detail?.id === project.id ? "bg-slate-50 dark:bg-slate-800/50" : ""
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                      {project.name}
                    </span>
                    {project.health ? (
                      <Badge tone={HEALTH_TONE[project.health]}>{project.health}</Badge>
                    ) : (
                      <Badge tone="neutral">not assessed</Badge>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {project.done_count}/{project.task_count} done
                    {project.overdue_count > 0 ? ` · ${project.overdue_count} overdue` : ""}
                    {project.blocked_count > 0 ? ` · ${project.blocked_count} blocked` : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        {/* ---- the selected project ------------------------------------ */}
        <div className="space-y-6">
          {detail && facts ? (
            <>
              <Card>
                <CardHeader
                  title={detail.name}
                  description={detail.description || undefined}
                  action={
                    detail.health ? (
                      <Badge tone={HEALTH_TONE[detail.health]}>{detail.health}</Badge>
                    ) : null
                  }
                />
                <div className="space-y-4 px-5 py-4">
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Stat label="Tasks" value={facts.task_count} />
                    <Stat label="Complete" value={`${facts.completion_percent}%`} />
                    <Stat
                      label="Overdue"
                      value={facts.overdue_count}
                      tone={facts.overdue_count > 0 ? "text-rose-600 dark:text-rose-400" : undefined}
                    />
                    <Stat
                      label="Blocked"
                      value={facts.blocked_count}
                      tone={facts.blocked_count > 0 ? "text-amber-600 dark:text-amber-400" : undefined}
                    />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Owner: {detail.owner || "unassigned"}
                    {detail.target_date
                      ? ` · target ${detail.target_date}${
                          facts.days_to_target != null
                            ? facts.days_to_target >= 0
                              ? ` (${facts.days_to_target} days away)`
                              : ` (${Math.abs(facts.days_to_target)} days past)`
                            : ""
                        }`
                      : " · no target date"}
                  </p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    Every figure above is computed from the tasks below. No AI was involved
                    in producing any of them.
                  </p>
                  {detail.risks.length > 0 ? (
                    <div>
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Recorded risks
                      </h3>
                      <ul className="mt-1 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">
                        {detail.risks.map((risk) => (
                          <li key={risk}>{risk}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </Card>

              {/* ---- AI panel ------------------------------------------ */}
              <Card>
                <CardHeader
                  title="Ask the AI"
                  description="Each button spends one AI request. Nothing here runs on its own."
                />
                <div className="space-y-4 px-5 py-4">
                  <div className="flex flex-wrap gap-2">
                    <AiButton busy={busy === "assess"} onClick={() => runAi("assess", assessHealthAction)}>
                      Assess health · 1 request
                    </AiButton>
                    <AiButton
                      busy={busy === "actions"}
                      disabled={openTasks.length === 0}
                      onClick={() => runAi("actions", suggestNextActionsAction)}
                    >
                      Suggest next actions · 1 request
                    </AiButton>
                    <AiButton busy={busy === "summary"} onClick={() => runAi("summary", summarizeProjectAction)}>
                      Summarise · 1 request
                    </AiButton>
                  </div>
                  <UsageLine usage={usage} />

                  {detail.health_reasoning ? (
                    <div className="rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800">
                      <div className="flex items-center gap-2">
                        <Badge tone={detail.health ? HEALTH_TONE[detail.health] : "neutral"}>
                          {detail.health}
                        </Badge>
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          assigned by the model · confidence {detail.health_confidence ?? "—"}
                        </span>
                      </div>
                      <h3 className="mt-2 text-xs font-medium text-slate-700 dark:text-slate-300">
                        Why
                      </h3>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                        {detail.health_reasoning}
                      </p>
                      {detail.health_factors.length > 0 ? (
                        <ul className="mt-2 flex flex-wrap gap-1.5">
                          {detail.health_factors.map((factor) => (
                            <li key={factor}>
                              <Badge tone="info">{factor}</Badge>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}

                  {detail.next_actions.length > 0 ? (
                    <div className="rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800">
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Suggested next actions
                      </h3>
                      <ol className="mt-2 space-y-2">
                        {detail.next_actions.map((action, index) => (
                          <li key={index} className="text-sm">
                            <span className="text-slate-900 dark:text-slate-100">
                              {action.action}
                            </span>
                            <span className="block text-xs text-slate-500 dark:text-slate-400">
                              {action.rationale}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}

                  {detail.summary ? (
                    <div className="rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800">
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Status summary
                      </h3>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                        {detail.summary}
                      </p>
                    </div>
                  ) : null}
                </div>
              </Card>

              {/* ---- tasks --------------------------------------------- */}
              <Card>
                <CardHeader
                  title="Tasks"
                  description="Owners, deadlines, dependencies and blockers."
                  action={
                    <button
                      type="button"
                      onClick={() => setShowAddTask((s) => !s)}
                      className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {showAddTask ? "Cancel" : "Add task"}
                    </button>
                  }
                />
                {showAddTask ? (
                  <form action={addTask} className="space-y-3 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
                    <input
                      name="title"
                      required
                      placeholder="What needs doing?"
                      className="block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                    <div className="grid gap-3 sm:grid-cols-2">
                      <input
                        name="owner"
                        placeholder="Owner"
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                      />
                      <input
                        name="due_date"
                        type="date"
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                      />
                      <select
                        name="status"
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                      >
                        <option value="todo">To do</option>
                        <option value="in_progress">In progress</option>
                        <option value="blocked">Blocked</option>
                        <option value="done">Done</option>
                      </select>
                      <select
                        name="priority"
                        defaultValue="medium"
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="urgent">Urgent</option>
                      </select>
                    </div>
                    <select
                      name="depends_on_id"
                      defaultValue=""
                      className="block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                    >
                      <option value="">No dependency</option>
                      {detail.tasks.map((task) => (
                        <option key={task.id} value={task.id}>
                          Waits for: {task.title}
                        </option>
                      ))}
                    </select>
                    <input
                      name="blocker_note"
                      placeholder="If blocked, why? (only kept while the task is blocked)"
                      className="block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                    <button
                      type="submit"
                      disabled={busy === "add"}
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
                    >
                      {busy === "add" ? "Adding…" : "Add task"}
                    </button>
                  </form>
                ) : null}
                {detail.tasks.length > 0 ? (
                  <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                    {detail.tasks.map((task) => (
                      <TaskRow
                        key={task.id}
                        task={task}
                        busy={busy === task.id}
                        onToggle={toggleTask}
                        onDelete={removeTask}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="px-5 py-4 text-sm text-slate-500 dark:text-slate-400">
                    No tasks yet. Add one to give the health assessment something to judge.
                  </p>
                )}
              </Card>
            </>
          ) : (
            <Card>
              <p className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
                Select a project on the left.
              </p>
            </Card>
          )}

          {/* ---- weekly report --------------------------------------- */}
          <Card>
            <CardHeader
              title="Weekly status report"
              description="One AI request, covering every active project."
              action={
                <AiButton busy={busy === "report"} onClick={makeReport}>
                  Generate · 1 request
                </AiButton>
              }
            />
            {report ? (
              <div className="space-y-4 px-5 py-4">
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Covering {report.project_count} project
                  {report.project_count === 1 ? "" : "s"} · generated{" "}
                  {new Date(report.generated_at).toLocaleString()}
                </p>
                <div>
                  <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                    Executive summary
                  </h3>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    {report.content.executive_summary}
                  </p>
                </div>
                {(
                  [
                    ["Highlights", report.content.highlights],
                    ["Concerns", report.content.concerns],
                    ["Risks", report.content.risks],
                    ["Recommended actions", report.content.recommended_actions],
                  ] as const
                ).map(([heading, items]) =>
                  items.length > 0 ? (
                    <div key={heading}>
                      <h3 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        {heading}
                      </h3>
                      <ul className="mt-1 list-disc pl-5 text-sm text-slate-600 dark:text-slate-400">
                        {items.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null,
                )}
                <UsageLine usage={report.usage} />
                <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    Download (no AI request):
                  </span>
                  {(["pdf", "markdown", "html"] as const).map((format) => (
                    <button
                      key={format}
                      type="button"
                      onClick={() => download(format)}
                      disabled={busy === `export-${format}`}
                      className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {busy === `export-${format}` ? "…" : format.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="px-5 py-4 text-sm text-slate-500 dark:text-slate-400">
                Not generated yet. The report reads the same computed figures shown above
                and turns them into something a lead can circulate.
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
