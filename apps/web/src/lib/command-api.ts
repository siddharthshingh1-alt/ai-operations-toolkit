import type { CommandCenterResponse, GenerateBriefResponse } from "@aiops/types";
import { API_URL } from "@/lib/api";

/** Client for the Ops Command Center API. Every call runs server-side. */

export class CommandApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "CommandApiError";
  }
}

/**
 * Generous, and for a specific reason.
 *
 * The overview fans out to four sources in one request, and the deployed API
 * sleeps on a free tier. A short timeout here would report the Command Center
 * as broken while it was in fact assembling.
 */
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
    throw new CommandApiError(
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
    throw new CommandApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function getOverview(): Promise<CommandCenterResponse> {
  return request<CommandCenterResponse>("/api/command-center");
}

export function generateBrief(): Promise<GenerateBriefResponse> {
  return request<GenerateBriefResponse>("/api/command-center/brief", { method: "POST" });
}

export async function tryGetOverview(): Promise<CommandCenterResponse | null> {
  try {
    return await getOverview();
  } catch {
    return null;
  }
}
