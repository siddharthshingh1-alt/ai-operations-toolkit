"use server";

import { revalidatePath } from "next/cache";
import type { SopContent, SopMetadata } from "@aiops/types";
import {
  askLibrary,
  createSop,
  generateSop,
  saveVersion,
  SopApiError,
} from "@/lib/sop-api";

/**
 * Server actions for the SOP pages.
 *
 * These run on the server, so the browser never holds a database credential or
 * an API key. Each returns a discriminated result rather than throwing, so the
 * UI can show a readable message instead of an error boundary.
 */

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

function toError(error: unknown): { ok: false; error: string } {
  if (error instanceof SopApiError) return { ok: false, error: error.message };
  return { ok: false, error: "Something went wrong. Please try again." };
}

export async function generateAction(input: {
  process_description: string;
  role: string;
  department: string;
  objective: string;
  existing_sop: string;
  document_text: string;
}): Promise<ActionResult<Awaited<ReturnType<typeof generateSop>>>> {
  try {
    const data = await generateSop({
      process_description: input.process_description,
      role: input.role || undefined,
      department: input.department || undefined,
      objective: input.objective || undefined,
      existing_sop: input.existing_sop || null,
      document_text: input.document_text || null,
    });
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function createAction(input: {
  content: SopContent;
  metadata: Partial<SopMetadata>;
  change_note: string;
}): Promise<ActionResult<{ id: string }>> {
  try {
    const saved = await createSop(input);
    revalidatePath("/documents");
    return { ok: true, data: { id: saved.id } };
  } catch (error) {
    return toError(error);
  }
}

export async function saveVersionAction(
  id: string,
  input: {
    content: SopContent;
    metadata: Partial<SopMetadata>;
    change_note: string;
  },
): Promise<ActionResult<{ version: number }>> {
  try {
    const saved = await saveVersion(id, input);
    revalidatePath("/documents");
    revalidatePath(`/documents/${id}`);
    return { ok: true, data: { version: saved.version } };
  } catch (error) {
    return toError(error);
  }
}

export async function askAction(
  question: string,
): Promise<ActionResult<Awaited<ReturnType<typeof askLibrary>>>> {
  try {
    return { ok: true, data: await askLibrary(question) };
  } catch (error) {
    return toError(error);
  }
}
