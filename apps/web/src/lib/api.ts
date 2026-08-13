import type { ReadinessResponse, SystemInfo } from "@aiops/types";

/**
 * Server-side API client.
 *
 * Every call is made from a React Server Component, so the browser never talks
 * to the backend directly and no API key can reach client-side code
 * (CLAUDE.md Section 24: "no API keys in frontend").
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** How long to wait before treating the backend as unreachable. */
const TIMEOUT_MS = 5_000;

export class ApiUnreachableError extends Error {
  constructor(readonly path: string, readonly cause_: unknown) {
    super(`The API at ${API_URL}${path} did not respond.`);
    this.name = "ApiUnreachableError";
  }
}

async function get<T>(path: string): Promise<T> {
  try {
    const response = await fetch(`${API_URL}${path}`, {
      // Always current: this is status information, so a stale cache would be
      // actively misleading.
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    throw new ApiUnreachableError(path, error);
  }
}

export function getSystemInfo(): Promise<SystemInfo> {
  return get<SystemInfo>("/api/system");
}

export function getReadiness(): Promise<ReadinessResponse> {
  return get<ReadinessResponse>("/health/ready");
}

/**
 * Fetch without throwing, for pages that should still render when the backend
 * is down. A dashboard that shows "API unreachable" is more useful than a
 * 500 page.
 */
export async function tryGetSystemInfo(): Promise<SystemInfo | null> {
  try {
    return await getSystemInfo();
  } catch {
    return null;
  }
}

export async function tryGetReadiness(): Promise<ReadinessResponse | null> {
  try {
    return await getReadiness();
  } catch {
    return null;
  }
}

export { API_URL };
