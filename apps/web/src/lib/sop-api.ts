import type {
  AskResponse,
  GenerateResponse,
  SopContent,
  SopDetail,
  SopDiff,
  SopMetadata,
  SopSummary,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/**
 * Client for the SOP Generator API.
 *
 * The read functions run in server components; the write functions are called
 * from client components via server actions, so no API key or database
 * credential is ever exposed to the browser.
 */

/** The error shape the API returns (see `apps/api/app/errors.py`). */
export class SopApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "SopApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: { accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new SopApiError(
      "unreachable",
      "Could not reach the API. Start it with `npm run dev`.",
      0,
    );
  }

  if (!response.ok) {
    // The API always returns {code, message}; fall back if something else
    // (a proxy, a crash) produced the response.
    let code = "error";
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      code = body.code ?? code;
      message = body.message ?? message;
    } catch {
      /* keep the fallback message */
    }
    throw new SopApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

// ------------------------------------------------------------------- reading

export function listSops(): Promise<SopSummary[]> {
  return request<SopSummary[]>("/api/sop");
}

export function getSop(id: string, version?: number): Promise<SopDetail> {
  const suffix = version ? `?version=${version}` : "";
  return request<SopDetail>(`/api/sop/${id}${suffix}`);
}

export function getDiff(id: string, from: number, to: number): Promise<SopDiff> {
  return request<SopDiff>(`/api/sop/${id}/diff?from=${from}&to=${to}`);
}

/** Fetch without throwing, for pages that should render even if the API is down. */
export async function tryListSops(): Promise<SopSummary[] | null> {
  try {
    return await listSops();
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------- writing

export function generateSop(input: {
  process_description: string;
  role?: string;
  department?: string;
  objective?: string;
  existing_sop?: string | null;
  document_text?: string | null;
}): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/sop/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function createSop(input: {
  content: SopContent;
  metadata: Partial<SopMetadata>;
  change_note?: string;
}): Promise<SopDetail> {
  return request<SopDetail>("/api/sop", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function saveVersion(
  id: string,
  input: {
    content: SopContent;
    metadata: Partial<SopMetadata>;
    change_note?: string;
  },
): Promise<SopDetail> {
  return request<SopDetail>(`/api/sop/${id}/versions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function askLibrary(question: string): Promise<AskResponse> {
  return request<AskResponse>("/api/sop/search/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, top_k: 4 }),
  });
}

/** URL for downloading an SOP. Used directly as an href. */
export function exportUrl(
  id: string,
  format: "markdown" | "html" | "pdf",
  version?: number,
): string {
  const v = version ? `&version=${version}` : "";
  return `${API_URL}/api/sop/${id}/export?format=${format}${v}`;
}
