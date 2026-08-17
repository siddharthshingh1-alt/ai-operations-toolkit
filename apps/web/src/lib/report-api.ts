import type {
  ReportFacts,
  ReportFactsResponse,
  ReportNarrative,
  ReportNarrativeResponse,
  ReportPeriod,
  ReportSampleOption,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/** Client for the Report Generator API. Every call runs server-side. */

export class ReportApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ReportApiError";
  }
}

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
    throw new ReportApiError(
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
    throw new ReportApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function listSamples(): Promise<ReportSampleOption[]> {
  return request<ReportSampleOption[]>("/api/reports/samples");
}

/** Compute a report. No AI request is spent. */
export function reportFromSample(
  key: string,
  period: ReportPeriod,
): Promise<ReportFactsResponse> {
  return request<ReportFactsResponse>(
    `/api/reports/samples/${encodeURIComponent(key)}?period=${period}`,
  );
}

export async function reportFromUpload(
  file: File,
  period: ReportPeriod,
): Promise<ReportFactsResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<ReportFactsResponse>(`/api/reports/analyse?period=${period}`, {
    method: "POST",
    body: form,
  });
}

/** The single AI request: executive summary, recommendations, action items. */
export function generateNarrative(facts: ReportFacts): Promise<ReportNarrativeResponse> {
  return request<ReportNarrativeResponse>("/api/reports/narrative", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ facts }),
  });
}

/**
 * Render the report for download. Spends no AI request.
 *
 * Bytes come back base64-encoded because a server action can only return
 * serialisable values; the client turns it into a blob.
 */
export async function exportReport(
  facts: ReportFacts,
  narrative: ReportNarrative | null,
  format: "markdown" | "html" | "pdf",
): Promise<{ base64: string; contentType: string; filename: string }> {
  const response = await fetch(`${API_URL}/api/reports/export?format=${format}`, {
    method: "POST",
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ facts, narrative }),
  });
  if (!response.ok) {
    let message = "Could not render the report.";
    try {
      const body = await response.json();
      message = body.message ?? message;
    } catch {
      /* keep the fallback */
    }
    throw new ReportApiError("export_failed", message, response.status);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  return {
    base64: buffer.toString("base64"),
    contentType: response.headers.get("content-type") ?? "application/octet-stream",
    filename: match?.[1] ?? `report.${format}`,
  };
}

export async function tryListSamples(): Promise<ReportSampleOption[] | null> {
  try {
    return await listSamples();
  } catch {
    return null;
  }
}

export async function tryReportFromSample(
  key: string,
  period: ReportPeriod,
): Promise<ReportFactsResponse | null> {
  try {
    return await reportFromSample(key, period);
  } catch {
    return null;
  }
}
