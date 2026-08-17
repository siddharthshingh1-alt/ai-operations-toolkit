import type {
  TrackedProjectDetail,
  TrackerAssessResponse,
  TrackerProjectListResponse,
  WeeklyReportContent,
  WeeklyReportResponse,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/** Client for the Project Tracker API. Every call runs server-side. */

export class TrackerApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "TrackerApiError";
  }
}

/** Long enough for a free-tier cold start plus one AI call. */
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
    throw new TrackerApiError(
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
    throw new TrackerApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function listProjects(): Promise<TrackerProjectListResponse> {
  return request<TrackerProjectListResponse>("/api/tracker/projects");
}

export function getProject(id: string): Promise<TrackedProjectDetail> {
  return request<TrackedProjectDetail>(`/api/tracker/projects/${encodeURIComponent(id)}`);
}

export function createProject(body: {
  name: string;
  description?: string;
  owner?: string;
  target_date?: string | null;
  risks?: string[];
}): Promise<TrackedProjectDetail> {
  return request<TrackedProjectDetail>("/api/tracker/projects", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteProject(id: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/tracker/projects/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export function createTask(
  projectId: string,
  body: Record<string, unknown>,
): Promise<TrackedProjectDetail> {
  return request<TrackedProjectDetail>(
    `/api/tracker/projects/${encodeURIComponent(projectId)}/tasks`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function updateTask(
  taskId: string,
  body: Record<string, unknown>,
): Promise<TrackedProjectDetail> {
  return request<TrackedProjectDetail>(`/api/tracker/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteTask(taskId: string): Promise<TrackedProjectDetail> {
  return request<TrackedProjectDetail>(`/api/tracker/tasks/${encodeURIComponent(taskId)}`, {
    method: "DELETE",
  });
}

/* ---- the AI. One request each, one button each. ------------------------- */

export function assessHealth(projectId: string): Promise<TrackerAssessResponse> {
  return request<TrackerAssessResponse>(
    `/api/tracker/projects/${encodeURIComponent(projectId)}/assess`,
    { method: "POST" },
  );
}

export function suggestNextActions(projectId: string): Promise<TrackerAssessResponse> {
  return request<TrackerAssessResponse>(
    `/api/tracker/projects/${encodeURIComponent(projectId)}/next-actions`,
    { method: "POST" },
  );
}

export function summarizeProject(projectId: string): Promise<TrackerAssessResponse> {
  return request<TrackerAssessResponse>(
    `/api/tracker/projects/${encodeURIComponent(projectId)}/summarize`,
    { method: "POST" },
  );
}

export function generateWeeklyReport(): Promise<WeeklyReportResponse> {
  return request<WeeklyReportResponse>("/api/tracker/report/weekly", { method: "POST" });
}

/**
 * Render an already-generated report.
 *
 * Returns bytes rather than JSON, and deliberately re-posts the content the
 * page is showing: exporting must not spend an AI request, and must not
 * produce a second, differently-worded document.
 */
export async function exportWeeklyReport(
  content: WeeklyReportContent,
  format: "markdown" | "html" | "pdf",
): Promise<{ base64: string; contentType: string; filename: string }> {
  const response = await fetch(
    `${API_URL}/api/tracker/report/weekly/export?format=${format}`,
    {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { "content-type": "application/json" },
      body: JSON.stringify(content),
    },
  );
  if (!response.ok) {
    throw new TrackerApiError("export_failed", "Could not render the report.", response.status);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  return {
    base64: buffer.toString("base64"),
    contentType: response.headers.get("content-type") ?? "application/octet-stream",
    filename: match?.[1] ?? `weekly-status-report.${format}`,
  };
}

export async function tryListProjects(): Promise<TrackerProjectListResponse | null> {
  try {
    return await listProjects();
  } catch {
    return null;
  }
}

export async function tryGetProject(id: string): Promise<TrackedProjectDetail | null> {
  try {
    return await getProject(id);
  } catch {
    return null;
  }
}
