"use server";

import type { Analysis, InsightResponse } from "@aiops/types";
import {
  analyseSample,
  analyseUpload,
  DashboardApiError,
  requestInsights,
} from "@/lib/dashboard-api";

/**
 * Server actions for the dashboard.
 *
 * These run on the server, so an uploaded file never reaches the API from the
 * browser and no credential is exposed. Each returns a discriminated result
 * rather than throwing, so the page can show the API's own message — which for
 * a rejected file is the specific reason it was rejected, and for an exhausted
 * quota is the plain-language explanation rather than a stack trace.
 */

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof DashboardApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return {
    ok: false,
    error: "Something went wrong. Please try again.",
    code: "unknown",
  };
}

export async function analyseSampleAction(
  key: string,
): Promise<ActionResult<Analysis>> {
  try {
    return { ok: true, data: await analyseSample(key) };
  } catch (error) {
    return toError(error);
  }
}

export async function analyseUploadAction(
  formData: FormData,
): Promise<ActionResult<Analysis>> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return {
      ok: false,
      error: "Please choose a file first.",
      code: "no_file",
    };
  }

  try {
    return { ok: true, data: await analyseUpload(file) };
  } catch (error) {
    return toError(error);
  }
}

export async function insightsAction(
  analysis: Analysis,
): Promise<ActionResult<InsightResponse>> {
  try {
    return { ok: true, data: await requestInsights(analysis) };
  } catch (error) {
    return toError(error);
  }
}
