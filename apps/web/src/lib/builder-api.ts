import type {
  WorkflowDefinition,
  WorkflowDetail,
  WorkflowExecutionDetail,
  WorkflowListResponse,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/** Client for the Workflow Builder API. Every call runs server-side. */

export class BuilderApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "BuilderApiError";
  }
}

/** Long enough for a cold start plus several AI nodes in one run. */
const TIMEOUT_MS = 120_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      ...init,
      headers: { accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new BuilderApiError(
      "unreachable",
      process.env.NODE_ENV === "production"
        ? "Could not reach the API. It may be waking up from idle — retry in a moment."
        : "Could not reach the API. Start it with `npm run dev`.",
      0,
    );
  }

  if (!response.ok) {
    let code = "error";
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      code = body.code ?? code;
      message = body.message ?? message;
    } catch {
      /* keep the fallback */
    }
    throw new BuilderApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function listWorkflows(): Promise<WorkflowListResponse> {
  return request<WorkflowListResponse>("/api/workflows");
}

export function getWorkflow(id: string): Promise<WorkflowDetail> {
  return request<WorkflowDetail>(`/api/workflows/${encodeURIComponent(id)}`);
}

export function createWorkflow(body: {
  name: string;
  description?: string;
}): Promise<WorkflowDetail> {
  return request<WorkflowDetail>("/api/workflows", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function saveWorkflow(
  id: string,
  definition: WorkflowDefinition,
): Promise<WorkflowDetail> {
  return request<WorkflowDetail>(`/api/workflows/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ definition }),
  });
}

export function duplicateWorkflow(id: string): Promise<WorkflowDetail> {
  return request<WorkflowDetail>(
    `/api/workflows/${encodeURIComponent(id)}/duplicate`,
    { method: "POST" },
  );
}

export function deleteWorkflow(id: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/workflows/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function runWorkflow(
  id: string,
  context: Record<string, unknown>,
): Promise<WorkflowExecutionDetail> {
  return request<WorkflowExecutionDetail>(
    `/api/workflows/${encodeURIComponent(id)}/run`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ context }),
    },
  );
}

export function decideExecution(
  executionId: string,
  body: { approved: boolean; approved_by: string },
): Promise<WorkflowExecutionDetail> {
  return request<WorkflowExecutionDetail>(
    `/api/workflows/executions/${encodeURIComponent(executionId)}/decision`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export async function tryListWorkflows(): Promise<WorkflowListResponse | null> {
  try {
    return await listWorkflows();
  } catch {
    return null;
  }
}

export async function tryGetWorkflow(id: string): Promise<WorkflowDetail | null> {
  try {
    return await getWorkflow(id);
  } catch {
    return null;
  }
}
