"use client";

import { useMemo, useState } from "react";
import type {
  PaletteEntry,
  WorkflowDefinition,
  WorkflowDetail,
  WorkflowExecutionDetail,
  WorkflowNodeDefinition,
} from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import {
  decideExecutionAction,
  runWorkflowAction,
  saveWorkflowAction,
} from "@/app/workflows/actions";
import { WorkflowCanvas } from "@/components/builder/workflow-canvas";

/**
 * The builder around the canvas.
 *
 * All editing is explicit: add a step, then say what it connects to. Nothing
 * here executes a workflow — pressing Run posts the definition to the API,
 * which hands it to the shared engine.
 */

let counter = 0;
function newNodeId(): string {
  counter += 1;
  return `node_${Date.now().toString(36)}_${counter}`;
}

const AI_TYPES = new Set([
  "ai_classification",
  "ai_extraction",
  "ai_summarization",
  "ai_generation",
]);

function blankNode(type: string, label: string): WorkflowNodeDefinition {
  const config: Record<string, unknown> = {};
  if (type === "ai_classification") config.categories = ["Urgent", "Normal"];
  if (type === "ai_extraction") config.fields = ["booking_reference"];
  if (type === "ai_generation") config.instruction = "Draft a reply to the agency.";
  if (type === "condition") config.field = "category";
  if (type === "transform") config.mapping = { copy_of_input: "input" };
  if (AI_TYPES.has(type)) config.input_field = "input";

  return {
    id: newNodeId(),
    type: type as WorkflowNodeDefinition["type"],
    label,
    config,
    next_id: null,
    next_id_if_false: null,
  };
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-slate-700 dark:text-slate-300">{label}</span>
      {children}
      {hint ? (
        <span className="mt-0.5 block text-xs text-slate-400 dark:text-slate-500">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

const INPUT =
  "mt-1 block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900";

export function WorkflowEditor({
  initial,
  palette,
}: {
  initial: WorkflowDetail;
  palette: PaletteEntry[];
}) {
  const [detail, setDetail] = useState(initial);
  const [definition, setDefinition] = useState<WorkflowDefinition>(initial.definition);
  const [selectedId, setSelectedId] = useState<string | null>(
    initial.definition.start_node_id,
  );
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [runInput, setRunInput] = useState(
    "Our client's flight DEL-DXB on 14 March was delayed by six hours and they missed a connection. What can we tell them?",
  );
  const [execution, setExecution] = useState<WorkflowExecutionDetail | null>(null);
  const [approver, setApprover] = useState("");

  // Address the workflow by the row's id, never by `definition.id`. The
  // definition is a document the editor edits; `detail.id` is the resource it
  // is stored under, and it is what the page's own URL uses.
  const workflowId = detail.id;

  const readOnly = detail.is_read_only;
  const selected = definition.nodes.find((node) => node.id === selectedId) ?? null;

  const issueNodeIds = useMemo(
    () => new Set(detail.issues.map((issue) => issue.node_id).filter(Boolean) as string[]),
    [detail.issues],
  );

  const blocking = detail.issues.filter((issue) =>
    ["no_start_node", "start_node_missing", "dangling_next", "unguarded_high_risk", "loop"].includes(
      issue.code,
    ),
  );

  const aiCount = definition.nodes.filter((node) => AI_TYPES.has(node.type)).length;

  const nodeStatuses = useMemo(() => {
    const statuses: Record<string, string> = {};
    for (const run of execution?.execution.node_runs ?? []) {
      statuses[run.node_id] = run.status;
    }
    return statuses;
  }, [execution]);

  function update(next: WorkflowDefinition) {
    setDefinition(next);
    setDirty(true);
    setMessage(null);
  }

  function patchNode(id: string, patch: Partial<WorkflowNodeDefinition>) {
    update({
      ...definition,
      nodes: definition.nodes.map((node) =>
        node.id === id ? { ...node, ...patch } : node,
      ),
    });
  }

  function addNode(entry: PaletteEntry) {
    const node = blankNode(entry.type, entry.label);
    const nodes = [...definition.nodes, node];
    let startId = definition.start_node_id;

    if (!startId) {
      startId = node.id;
    } else if (selected && !selected.next_id) {
      // Chain onto the selected step when it has a free outgoing link, which
      // is what "add the next step" almost always means.
      const index = nodes.findIndex((n) => n.id === selected.id);
      nodes[index] = { ...nodes[index], next_id: node.id };
    }

    update({ ...definition, nodes, start_node_id: startId });
    setSelectedId(node.id);
  }

  function removeNode(id: string) {
    const nodes = definition.nodes
      .filter((node) => node.id !== id)
      .map((node) => ({
        ...node,
        next_id: node.next_id === id ? null : node.next_id,
        next_id_if_false: node.next_id_if_false === id ? null : node.next_id_if_false,
      }));
    update({
      ...definition,
      nodes,
      start_node_id:
        definition.start_node_id === id ? (nodes[0]?.id ?? null) : definition.start_node_id,
    });
    setSelectedId(null);
  }

  async function save() {
    setBusy(true);
    setError(null);
    const result = await saveWorkflowAction(workflowId, definition);
    if (result.ok) {
      setDetail(result.data);
      setDefinition(result.data.definition);
      setDirty(false);
      setMessage("Saved.");
    } else {
      setError(result.error);
    }
    setBusy(false);
  }

  async function run() {
    setBusy(true);
    setError(null);
    setExecution(null);
    const result = await runWorkflowAction(workflowId, runInput);
    if (result.ok) setExecution(result.data);
    else setError(result.error);
    setBusy(false);
  }

  async function decide(approved: boolean) {
    if (!execution) return;
    setBusy(true);
    const result = await decideExecutionAction(
      execution.id,
      workflowId,
      approved,
      approver,
    );
    if (result.ok) {
      setExecution(result.data);
      setError(null);
    } else {
      setError(result.error);
    }
    setBusy(false);
  }

  const awaiting = execution?.status === "awaiting_approval";

  return (
    <div className="space-y-6">
      {/* ---- problems ------------------------------------------------------ */}
      {detail.issues.length > 0 ? (
        <Card>
          <CardHeader
            title="Checks"
            description="Blocking problems must be fixed before this workflow can run."
            action={
              blocking.length > 0 ? (
                <Badge tone="danger">{blocking.length} blocking</Badge>
              ) : (
                <Badge tone="success">runnable</Badge>
              )
            }
          />
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {detail.issues.map((issue, index) => {
              const blocks = blocking.includes(issue);
              return (
                <li key={index} className="flex items-start gap-3 px-5 py-2.5 text-sm">
                  <Badge tone={blocks ? "danger" : "warning"}>
                    {blocks ? "blocks" : "note"}
                  </Badge>
                  <span className="text-slate-700 dark:text-slate-300">
                    {issue.message}
                  </span>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* ---- canvas ------------------------------------------------------ */}
        <div className="space-y-3">
          <WorkflowCanvas
            definition={definition}
            selectedId={selectedId}
            issueNodeIds={issueNodeIds}
            nodeStatuses={nodeStatuses}
            onSelect={setSelectedId}
          />
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Positions are computed from the connections, so the picture always
            matches what will run. Click a step to edit it.
          </p>
        </div>

        {/* ---- side panel --------------------------------------------------- */}
        <div className="space-y-4">
          {!readOnly ? (
            <Card>
              <CardHeader title="Add a step" />
              <div className="flex flex-wrap gap-1.5 px-4 py-3">
                {palette.map((entry) => (
                  <button
                    key={entry.type}
                    type="button"
                    disabled={!entry.available}
                    title={entry.reason ?? undefined}
                    onClick={() => entry.available && addNode(entry)}
                    className={
                      entry.available
                        ? "rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                        : "cursor-not-allowed rounded-md border border-dashed border-slate-300 px-2.5 py-1 text-xs text-slate-400 dark:border-slate-700 dark:text-slate-600"
                    }
                  >
                    {entry.label}
                    {entry.high_risk ? " ⚠" : ""}
                    {!entry.available ? " — unavailable" : ""}
                  </button>
                ))}
              </div>
              <p className="px-4 pb-3 text-xs text-slate-400 dark:text-slate-500">
                ⚠ marks a step that reaches the outside world. One of those
                cannot run unless a Human approval step comes before it.
              </p>
            </Card>
          ) : (
            <Card>
              <div className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                <strong className="text-slate-800 dark:text-slate-200">Read-only.</strong>{" "}
                {detail.description}
              </div>
            </Card>
          )}

          {selected ? (
            <Card>
              <CardHeader
                title="Step"
                action={
                  !readOnly ? (
                    <button
                      type="button"
                      onClick={() => removeNode(selected.id)}
                      className="text-xs text-rose-700 underline underline-offset-2 dark:text-rose-400"
                    >
                      Remove
                    </button>
                  ) : null
                }
              />
              <div className="space-y-3 px-4 py-3">
                <Field label="Name">
                  <input
                    value={selected.label}
                    disabled={readOnly}
                    onChange={(event) =>
                      patchNode(selected.id, { label: event.target.value })
                    }
                    className={INPUT}
                  />
                </Field>

                <Field label="Type">
                  <input value={selected.type} disabled className={INPUT} />
                </Field>

                {selected.type === "ai_classification" ? (
                  <Field
                    label="Categories"
                    hint="One per line. The model must pick one of these."
                  >
                    <textarea
                      rows={4}
                      disabled={readOnly}
                      value={((selected.config.categories as string[]) ?? []).join("\n")}
                      onChange={(event) =>
                        patchNode(selected.id, {
                          config: {
                            ...selected.config,
                            categories: event.target.value
                              .split("\n")
                              .map((line) => line.trim())
                              .filter(Boolean),
                          },
                        })
                      }
                      className={INPUT}
                    />
                  </Field>
                ) : null}

                {selected.type === "ai_generation" ? (
                  <Field label="Instruction" hint="What should it write?">
                    <textarea
                      rows={3}
                      disabled={readOnly}
                      value={String(selected.config.instruction ?? "")}
                      onChange={(event) =>
                        patchNode(selected.id, {
                          config: { ...selected.config, instruction: event.target.value },
                        })
                      }
                      className={INPUT}
                    />
                  </Field>
                ) : null}

                {selected.type === "condition" ? (
                  <Field label="Field to test" hint="A value written by an earlier step.">
                    <input
                      disabled={readOnly}
                      value={String(selected.config.field ?? "")}
                      onChange={(event) =>
                        patchNode(selected.id, {
                          config: { ...selected.config, field: event.target.value },
                        })
                      }
                      className={INPUT}
                    />
                  </Field>
                ) : null}

                <Field label="Next step">
                  <select
                    value={selected.next_id ?? ""}
                    disabled={readOnly}
                    onChange={(event) =>
                      patchNode(selected.id, { next_id: event.target.value || null })
                    }
                    className={INPUT}
                  >
                    <option value="">— end of workflow —</option>
                    {definition.nodes
                      .filter((node) => node.id !== selected.id)
                      .map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.label}
                        </option>
                      ))}
                  </select>
                </Field>

                {selected.type === "condition" ? (
                  <Field label="If false, go to">
                    <select
                      value={selected.next_id_if_false ?? ""}
                      disabled={readOnly}
                      onChange={(event) =>
                        patchNode(selected.id, {
                          next_id_if_false: event.target.value || null,
                        })
                      }
                      className={INPUT}
                    >
                      <option value="">— end of workflow —</option>
                      {definition.nodes
                        .filter((node) => node.id !== selected.id)
                        .map((node) => (
                          <option key={node.id} value={node.id}>
                            {node.label}
                          </option>
                        ))}
                    </select>
                  </Field>
                ) : null}

                {!readOnly ? (
                  <Field label="Starting step">
                    <select
                      value={definition.start_node_id ?? ""}
                      onChange={(event) =>
                        update({ ...definition, start_node_id: event.target.value || null })
                      }
                      className={INPUT}
                    >
                      <option value="">— none —</option>
                      {definition.nodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                ) : null}
              </div>
            </Card>
          ) : null}

          {!readOnly ? (
            <button
              type="button"
              onClick={save}
              disabled={busy || !dirty}
              className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {busy ? "Working…" : dirty ? "Save changes" : "Saved"}
            </button>
          ) : null}
        </div>
      </div>

      {message ? (
        <p className="text-sm text-teal-700 dark:text-teal-400">{message}</p>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          {error}
        </div>
      ) : null}

      {/* ---- run ------------------------------------------------------------ */}
      <Card>
        <CardHeader
          title="Run"
          description="Executed by the shared workflow engine — the same one the Travel Operations project uses."
          action={
            <button
              type="button"
              onClick={run}
              disabled={busy || dirty}
              title={dirty ? "Save your changes first" : undefined}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              {busy
                ? "Running…"
                : `Run — up to ${aiCount} AI request${aiCount === 1 ? "" : "s"}`}
            </button>
          }
        />
        <div className="space-y-3 px-5 py-4">
          <Field label="Input" hint="Steps read this as the field named 'input'.">
            <textarea
              rows={3}
              value={runInput}
              onChange={(event) => setRunInput(event.target.value)}
              className={INPUT}
            />
          </Field>

          {execution ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Badge
                  tone={
                    execution.status === "succeeded"
                      ? "success"
                      : execution.status === "failed"
                        ? "danger"
                        : "warning"
                  }
                >
                  {execution.status.replace(/_/g, " ")}
                </Badge>
                {execution.execution.error ? (
                  <span className="text-sm text-rose-700 dark:text-rose-400">
                    {execution.execution.error}
                  </span>
                ) : null}
              </div>

              <ol className="divide-y divide-slate-200 rounded-md border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
                {execution.execution.node_runs.map((run, index) => (
                  <li
                    key={`${run.node_id}-${index}`}
                    className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-2"
                  >
                    <span className="text-sm text-slate-700 dark:text-slate-300">
                      {index + 1}. {run.label}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {run.status.replace(/_/g, " ")}
                      {run.duration_ms ? ` · ${run.duration_ms} ms` : ""}
                      {typeof (run.output as Record<string, unknown>)?.transmitted === "number"
                        ? " · recorded, transmitted 0"
                        : ""}
                    </span>
                  </li>
                ))}
              </ol>

              {awaiting ? (
                <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-900 dark:bg-amber-950">
                  <p className="text-sm text-amber-900 dark:text-amber-200">
                    This run has stopped at a human approval step. Nothing after it
                    has executed.
                  </p>
                  <input
                    value={approver}
                    onChange={(event) => setApprover(event.target.value)}
                    placeholder="Your name — required"
                    className="block w-full max-w-xs rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm dark:border-amber-800 dark:bg-slate-900"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => decide(true)}
                      disabled={busy}
                      className="rounded-md bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-60"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => decide(false)}
                      disabled={busy}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No run yet. Each AI step spends one request from the shared daily
              free-tier budget, which is why this is a button.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
