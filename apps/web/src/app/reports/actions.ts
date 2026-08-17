"use server";

import type {
  ReportFacts,
  ReportFactsResponse,
  ReportNarrative,
  ReportNarrativeResponse,
  ReportPeriod,
} from "@aiops/types";
import {
  ReportApiError,
  exportReport,
  generateNarrative,
  reportFromSample,
  reportFromUpload,
} from "@/lib/report-api";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof ReportApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return { ok: false, error: "Something went wrong. Please try again.", code: "unknown" };
}

/** Compute a report from a bundled dataset. No AI request. */
export async function reportFromSampleAction(
  key: string,
  period: ReportPeriod,
): Promise<ActionResult<ReportFactsResponse>> {
  try {
    return { ok: true, data: await reportFromSample(key, period) };
  } catch (error) {
    return toError(error);
  }
}

/** Compute a report from an uploaded file. No AI request. */
export async function reportFromUploadAction(
  formData: FormData,
): Promise<ActionResult<ReportFactsResponse>> {
  const file = formData.get("file");
  const period = (String(formData.get("period") ?? "weekly") || "weekly") as ReportPeriod;
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, error: "Choose a CSV or Excel file first.", code: "file_required" };
  }
  try {
    return { ok: true, data: await reportFromUpload(file, period) };
  } catch (error) {
    return toError(error);
  }
}

/** The one AI request on this page. */
export async function generateNarrativeAction(
  facts: ReportFacts,
): Promise<ActionResult<ReportNarrativeResponse>> {
  try {
    return { ok: true, data: await generateNarrative(facts) };
  } catch (error) {
    return toError(error);
  }
}

/** Render for download. Spends nothing. */
export async function exportReportAction(
  facts: ReportFacts,
  narrative: ReportNarrative | null,
  format: "markdown" | "html" | "pdf",
): Promise<ActionResult<{ base64: string; contentType: string; filename: string }>> {
  try {
    return { ok: true, data: await exportReport(facts, narrative, format) };
  } catch (error) {
    return toError(error);
  }
}
