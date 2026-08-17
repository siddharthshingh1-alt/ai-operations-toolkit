"use server";

import { revalidatePath } from "next/cache";
import type {
  TrackedProjectDetail,
  TrackerAssessResponse,
  WeeklyReportContent,
  WeeklyReportResponse,
} from "@aiops/types";
import {
  TrackerApiError,
  assessHealth,
  createProject,
  createTask,
  deleteProject,
  deleteTask,
  exportWeeklyReport,
  generateWeeklyReport,
  getProject,
  suggestNextActions,
  summarizeProject,
  updateTask,
} from "@/lib/tracker-api";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof TrackerApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return { ok: false, error: "Something went wrong. Please try again.", code: "unknown" };
}

export async function getProjectAction(
  id: string,
): Promise<ActionResult<TrackedProjectDetail>> {
  try {
    return { ok: true, data: await getProject(id) };
  } catch (error) {
    return toError(error);
  }
}

export async function createProjectAction(
  formData: FormData,
): Promise<ActionResult<TrackedProjectDetail>> {
  const name = String(formData.get("name") ?? "").trim();
  if (name.length < 2) {
    return { ok: false, error: "Give the project a name.", code: "name_required" };
  }
  const target = String(formData.get("target_date") ?? "").trim();
  const risksRaw = String(formData.get("risks") ?? "").trim();
  try {
    const data = await createProject({
      name,
      description: String(formData.get("description") ?? "").trim(),
      owner: String(formData.get("owner") ?? "").trim(),
      target_date: target || null,
      risks: risksRaw ? risksRaw.split("\n").map((r) => r.trim()).filter(Boolean) : [],
    });
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function deleteProjectAction(
  id: string,
): Promise<ActionResult<{ status: string }>> {
  try {
    const data = await deleteProject(id);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function createTaskAction(
  projectId: string,
  formData: FormData,
): Promise<ActionResult<TrackedProjectDetail>> {
  const title = String(formData.get("title") ?? "").trim();
  if (title.length < 2) {
    return { ok: false, error: "Give the task a title.", code: "title_required" };
  }
  const due = String(formData.get("due_date") ?? "").trim();
  const dependsOn = String(formData.get("depends_on_id") ?? "").trim();
  const status = String(formData.get("status") ?? "todo");
  try {
    const data = await createTask(projectId, {
      title,
      owner: String(formData.get("owner") ?? "").trim(),
      due_date: due || null,
      status,
      priority: String(formData.get("priority") ?? "medium"),
      blocker_note: String(formData.get("blocker_note") ?? "").trim() || null,
      depends_on_id: dependsOn || null,
    });
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function updateTaskAction(
  taskId: string,
  patch: Record<string, unknown>,
): Promise<ActionResult<TrackedProjectDetail>> {
  try {
    const data = await updateTask(taskId, patch);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function deleteTaskAction(
  taskId: string,
): Promise<ActionResult<TrackedProjectDetail>> {
  try {
    const data = await deleteTask(taskId);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

/* ---- the AI. Each of these spends exactly one request. ------------------ */

export async function assessHealthAction(
  projectId: string,
): Promise<ActionResult<TrackerAssessResponse>> {
  try {
    const data = await assessHealth(projectId);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function suggestNextActionsAction(
  projectId: string,
): Promise<ActionResult<TrackerAssessResponse>> {
  try {
    const data = await suggestNextActions(projectId);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function summarizeProjectAction(
  projectId: string,
): Promise<ActionResult<TrackerAssessResponse>> {
  try {
    const data = await summarizeProject(projectId);
    revalidatePath("/tasks");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function generateWeeklyReportAction(): Promise<
  ActionResult<WeeklyReportResponse>
> {
  try {
    return { ok: true, data: await generateWeeklyReport() };
  } catch (error) {
    return toError(error);
  }
}

/**
 * Render the report for download.
 *
 * The bytes come back base64-encoded because a server action can only return
 * serialisable values; the client turns it into a blob. No AI request is
 * spent — the content already on screen is what gets rendered.
 */
export async function exportWeeklyReportAction(
  content: WeeklyReportContent,
  format: "markdown" | "html" | "pdf",
): Promise<ActionResult<{ base64: string; contentType: string; filename: string }>> {
  try {
    return { ok: true, data: await exportWeeklyReport(content, format) };
  } catch (error) {
    return toError(error);
  }
}
