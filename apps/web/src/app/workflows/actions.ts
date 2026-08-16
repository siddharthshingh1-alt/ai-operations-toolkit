"use server";

import { revalidatePath } from "next/cache";
import type {
  WorkflowDefinition,
  WorkflowDetail,
  WorkflowExecutionDetail,
} from "@aiops/types";
import {
  BuilderApiError,
  createWorkflow,
  decideExecution,
  deleteWorkflow,
  duplicateWorkflow,
  runWorkflow,
  saveWorkflow,
} from "@/lib/builder-api";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof BuilderApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return { ok: false, error: "Something went wrong. Please try again.", code: "unknown" };
}

export async function createWorkflowAction(
  formData: FormData,
): Promise<ActionResult<WorkflowDetail>> {
  const name = String(formData.get("name") ?? "").trim();
  if (name.length < 2) {
    return { ok: false, error: "Give the workflow a name.", code: "name_required" };
  }
  try {
    const data = await createWorkflow({
      name,
      description: String(formData.get("description") ?? "").trim(),
    });
    revalidatePath("/workflows");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function saveWorkflowAction(
  id: string,
  definition: WorkflowDefinition,
): Promise<ActionResult<WorkflowDetail>> {
  try {
    const data = await saveWorkflow(id, definition);
    revalidatePath(`/workflows/${id}`);
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function duplicateWorkflowAction(
  id: string,
): Promise<ActionResult<WorkflowDetail>> {
  try {
    const data = await duplicateWorkflow(id);
    revalidatePath("/workflows");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function deleteWorkflowAction(
  id: string,
): Promise<ActionResult<{ status: string }>> {
  try {
    const data = await deleteWorkflow(id);
    revalidatePath("/workflows");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function runWorkflowAction(
  id: string,
  input: string,
): Promise<ActionResult<WorkflowExecutionDetail>> {
  try {
    const data = await runWorkflow(id, { input });
    revalidatePath(`/workflows/${id}`);
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function decideExecutionAction(
  executionId: string,
  workflowId: string,
  approved: boolean,
  approvedBy: string,
): Promise<ActionResult<WorkflowExecutionDetail>> {
  const approver = approvedBy.trim();
  if (approver.length < 2) {
    return {
      ok: false,
      error: "Enter your name before approving or rejecting — a decision has to be attributable.",
      code: "approver_required",
    };
  }
  try {
    const data = await decideExecution(executionId, {
      approved,
      approved_by: approver,
    });
    revalidatePath(`/workflows/${workflowId}`);
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}
