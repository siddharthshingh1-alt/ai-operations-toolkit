"use server";

import { revalidatePath } from "next/cache";
import type { GenerateBriefResponse } from "@aiops/types";
import { CommandApiError, generateBrief } from "@/lib/command-api";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

/**
 * Write the daily Ops Brief. One AI request.
 *
 * The only action this project has. Everything else on the page is a read, and
 * reads cost nothing — a page meant to be opened every morning cannot spend a
 * request to render.
 */
export async function generateBriefAction(): Promise<ActionResult<GenerateBriefResponse>> {
  try {
    const data = await generateBrief();
    revalidatePath("/command-center");
    return { ok: true, data };
  } catch (error) {
    if (error instanceof CommandApiError) {
      return { ok: false, error: error.message, code: error.code };
    }
    return { ok: false, error: "Something went wrong. Please try again.", code: "unknown" };
  }
}
