import type {
  AssessResponse,
  CommunicationView,
  IncidentDetail,
  IncidentListResponse,
  PartnerListResponse,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/**
 * Client for the Travel Operations API.
 *
 * Every call runs on the server — from a server component or a server action —
 * so the browser never holds a credential and never talks to the API directly.
 */

export class TravelApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "TravelApiError";
  }
}

/** Long enough for a free-tier cold start plus two live model calls. */
const TIMEOUT_MS = 90_000;

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
    throw new TravelApiError(
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
    throw new TravelApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export function listIncidents(): Promise<IncidentListResponse> {
  return request<IncidentListResponse>("/api/travel/incidents");
}

export function getIncident(id: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/api/travel/incidents/${encodeURIComponent(id)}`);
}

export function assessIncident(id: string): Promise<AssessResponse> {
  return request<AssessResponse>(
    `/api/travel/incidents/${encodeURIComponent(id)}/assess`,
    { method: "POST" },
  );
}

export function decideCommunication(
  communicationId: string,
  body: { approved: boolean; approved_by: string; note?: string },
): Promise<CommunicationView> {
  return request<CommunicationView>(
    `/api/travel/communications/${encodeURIComponent(communicationId)}/decision`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function reportIncident(body: {
  kind: string;
  title: string;
  description?: string;
  route?: string | null;
  supplier?: string | null;
  occurred_at?: string | null;
}): Promise<IncidentDetail> {
  return request<IncidentDetail>("/api/travel/incidents", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listPartners(): Promise<PartnerListResponse> {
  return request<PartnerListResponse>("/api/travel/partners");
}

export async function tryListIncidents(): Promise<IncidentListResponse | null> {
  try {
    return await listIncidents();
  } catch {
    return null;
  }
}

export async function tryGetIncident(id: string): Promise<IncidentDetail | null> {
  try {
    return await getIncident(id);
  } catch {
    return null;
  }
}

export async function tryListPartners(): Promise<PartnerListResponse | null> {
  try {
    return await listPartners();
  } catch {
    return null;
  }
}
