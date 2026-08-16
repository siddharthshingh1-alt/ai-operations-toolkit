"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { WorkflowDefinition, WorkflowNodeDefinition } from "@aiops/types";

/**
 * Renders a workflow definition with React Flow.
 *
 * **Positions are computed from the graph, not dragged and stored.** The
 * engine's `WorkflowNode` has no coordinates, and inventing a place to keep
 * them would mean this project maintaining state the engine does not know
 * about — a canvas that could disagree with the workflow it draws. Laying the
 * graph out from its own links means the picture is always a true rendering of
 * what will run, and there is no position state to corrupt or migrate.
 *
 * Editing therefore happens in the side panel rather than by dragging. That is
 * the deliberate trade: a click-to-connect editor that is always correct beats
 * a drag-and-drop one that is usually correct.
 */

const TYPE_STYLES: Record<string, { ring: string; dot: string; kind: string }> = {
  trigger: { ring: "ring-slate-300 dark:ring-slate-600", dot: "bg-slate-400", kind: "Trigger" },
  ai_classification: { ring: "ring-sky-300 dark:ring-sky-700", dot: "bg-sky-500", kind: "AI" },
  ai_extraction: { ring: "ring-sky-300 dark:ring-sky-700", dot: "bg-sky-500", kind: "AI" },
  ai_summarization: { ring: "ring-sky-300 dark:ring-sky-700", dot: "bg-sky-500", kind: "AI" },
  ai_generation: { ring: "ring-sky-300 dark:ring-sky-700", dot: "bg-sky-500", kind: "AI" },
  condition: { ring: "ring-violet-300 dark:ring-violet-700", dot: "bg-violet-500", kind: "Branch" },
  transform: { ring: "ring-slate-300 dark:ring-slate-600", dot: "bg-slate-400", kind: "Logic" },
  human_approval: { ring: "ring-amber-400 dark:ring-amber-600", dot: "bg-amber-500", kind: "Human" },
  email: { ring: "ring-rose-300 dark:ring-rose-700", dot: "bg-rose-500", kind: "Action" },
  notification: { ring: "ring-slate-300 dark:ring-slate-600", dot: "bg-slate-400", kind: "Action" },
  webhook: { ring: "ring-rose-300 dark:ring-rose-700", dot: "bg-rose-500", kind: "Action" },
  database: { ring: "ring-rose-300 dark:ring-rose-700", dot: "bg-rose-500", kind: "Action" },
};

type StepData = {
  label: string;
  kind: string;
  ring: string;
  dot: string;
  selected: boolean;
  issue: boolean;
  status?: string;
};

function StepNode({ data }: NodeProps) {
  const step = data as StepData;
  return (
    <div
      className={[
        "min-w-44 rounded-lg bg-white px-3 py-2 shadow-sm ring-2 dark:bg-slate-900",
        step.ring,
        step.selected ? "outline outline-2 outline-offset-2 outline-slate-900 dark:outline-slate-100" : "",
        step.issue ? "ring-amber-500" : "",
      ].join(" ")}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${step.dot}`} />
        <span className="text-[10px] tracking-wide text-slate-400 uppercase">
          {step.kind}
        </span>
        {step.status ? (
          <span className="ml-auto text-[10px] text-slate-500 dark:text-slate-400">
            {step.status.replace(/_/g, " ")}
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
        {step.label}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
}

const NODE_TYPES = { step: StepNode };

/** Depth-first placement: one row per step, branches offset sideways. */
function layout(definition: WorkflowDefinition): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const byId = new Map(definition.nodes.map((node) => [node.id, node]));

  let row = 0;
  const seen = new Set<string>();

  function place(id: string | null, column: number): void {
    if (!id || seen.has(id)) return;
    const node = byId.get(id);
    if (!node) return;

    seen.add(id);
    positions.set(id, { x: column * 260, y: row * 120 });
    row += 1;

    place(node.next_id, column);
    // A false branch sits one column to the right, so the two paths are
    // visibly different rather than overlapping.
    place(node.next_id_if_false, column + 1);
  }

  place(definition.start_node_id, 0);

  // Anything unreachable is still drawn — a step you added but have not
  // connected yet is exactly the thing you need to see.
  for (const node of definition.nodes) {
    if (!positions.has(node.id)) {
      positions.set(node.id, { x: -280, y: row * 120 });
      row += 1;
    }
  }
  return positions;
}

export function WorkflowCanvas({
  definition,
  selectedId,
  issueNodeIds,
  nodeStatuses,
  onSelect,
}: {
  definition: WorkflowDefinition;
  selectedId: string | null;
  issueNodeIds: Set<string>;
  nodeStatuses?: Record<string, string>;
  onSelect: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const positions = layout(definition);

    const flowNodes: Node[] = definition.nodes.map((node: WorkflowNodeDefinition) => {
      const style = TYPE_STYLES[node.type] ?? TYPE_STYLES.transform;
      return {
        id: node.id,
        type: "step",
        position: positions.get(node.id) ?? { x: 0, y: 0 },
        data: {
          label: node.label,
          kind: style.kind,
          ring: style.ring,
          dot: style.dot,
          selected: node.id === selectedId,
          issue: issueNodeIds.has(node.id),
          status: nodeStatuses?.[node.id],
        } satisfies StepData,
      };
    });

    const flowEdges: Edge[] = [];
    for (const node of definition.nodes) {
      if (node.next_id) {
        flowEdges.push({
          id: `${node.id}->${node.next_id}`,
          source: node.id,
          target: node.next_id,
          label: node.type === "condition" ? "true" : undefined,
          animated: false,
        });
      }
      if (node.next_id_if_false) {
        flowEdges.push({
          id: `${node.id}-false->${node.next_id_if_false}`,
          source: node.id,
          target: node.next_id_if_false,
          label: "false",
          style: { strokeDasharray: "4 4" },
        });
      }
    }
    return { nodes: flowNodes, edges: flowEdges };
  }, [definition, selectedId, issueNodeIds, nodeStatuses]);

  return (
    <div className="h-[480px] w-full rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodeClick={(_event, node) => onSelect(node.id)}
        fitView
        // Editing happens in the side panel, so the canvas is for reading and
        // navigating. Dragging a node would imply a position that is not stored.
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
        proOptions={{ hideAttribution: false }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
