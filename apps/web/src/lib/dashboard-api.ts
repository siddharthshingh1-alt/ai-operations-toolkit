import type {
  Analysis,
  InsightResponse,
  SampleListResponse,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/**
 * Client for the Operations Dashboard API.
 *
 * Reads run in server components; the upload and insight calls run through
 * server actions. Either way the browser never talks to the API directly, so
 * no key or credential can reach client-side code.
 */

export class DashboardApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "DashboardApiError";
  }
}

/**
 * Long enough to cover a cold start on the free tier the API runs on, which
 * takes 30-60 seconds to wake. Insight generation adds a live model call on
 * top of that.
 */
const TIMEOUT_MS = 60_000;

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
    throw new DashboardApiError(
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
      /* keep the fallback message */
    }
    throw new DashboardApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function listSamples(): Promise<SampleListResponse> {
  return request<SampleListResponse>("/api/dashboard/samples");
}

export function analyseSample(key: string): Promise<Analysis> {
  return request<Analysis>(`/api/dashboard/samples/${encodeURIComponent(key)}`);
}

export function analyseUpload(file: File): Promise<Analysis> {
  const body = new FormData();
  body.append("file", file);
  return request<Analysis>("/api/dashboard/analyse", { method: "POST", body });
}

export function requestInsights(analysis: Analysis): Promise<InsightResponse> {
  return request<InsightResponse>("/api/dashboard/insights", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ analysis }),
  });
}

/** Fetch without throwing, for a page that should still render if the API is down. */
export async function tryAnalyseSample(key: string): Promise<Analysis | null> {
  try {
    return await analyseSample(key);
  } catch {
    return null;
  }
}

export async function tryListSamples(): Promise<SampleListResponse | null> {
  try {
    return await listSamples();
  } catch {
    return null;
  }
}
