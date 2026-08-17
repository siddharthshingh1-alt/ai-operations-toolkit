import type {
  InboxListResponse,
  InboxThreadResponse,
  InboxTriageResponse,
} from "@aiops/types";
import { API_URL } from "@/lib/api";

/** Client for the Operations Inbox API. Every call runs server-side. */

export class InboxApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "InboxApiError";
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
    throw new InboxApiError(
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
    throw new InboxApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

/** Reading the inbox is free — no model is called. */
export function listInbox(options?: {
  category?: string;
  unansweredOnly?: boolean;
  limit?: number;
}): Promise<InboxListResponse> {
  const params = new URLSearchParams();
  if (options?.category) params.set("category", options.category);
  if (options?.unansweredOnly) params.set("unanswered_only", "true");
  if (options?.limit) params.set("limit", String(options.limit));
  const query = params.toString();
  return request<InboxListResponse>(`/api/inbox${query ? `?${query}` : ""}`);
}

export function getThread(threadId: string): Promise<InboxThreadResponse> {
  return request<InboxThreadResponse>(
    `/api/inbox/threads/${encodeURIComponent(threadId)}`,
  );
}

/** One AI request: category, urgency, reasoning, summary, tasks, follow-up. */
export function triageThread(threadId: string): Promise<InboxTriageResponse> {
  return request<InboxTriageResponse>(
    `/api/inbox/threads/${encodeURIComponent(threadId)}/triage`,
    { method: "POST" },
  );
}

/** One AI request. The result is a draft and goes nowhere. */
export function draftReply(threadId: string): Promise<InboxTriageResponse> {
  return request<InboxTriageResponse>(
    `/api/inbox/threads/${encodeURIComponent(threadId)}/draft`,
    { method: "POST" },
  );
}

/** The only path that reaches a send, and it needs a name. */
export function decideReply(
  threadId: string,
  body: { approved: boolean; approved_by: string; note?: string | null },
): Promise<InboxThreadResponse> {
  return request<InboxThreadResponse>(
    `/api/inbox/threads/${encodeURIComponent(threadId)}/decision`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export async function tryGetThread(threadId: string): Promise<InboxThreadResponse | null> {
  try {
    return await getThread(threadId);
  } catch {
    return null;
  }
}

export async function tryListInbox(options?: {
  category?: string;
  unansweredOnly?: boolean;
}): Promise<InboxListResponse | null> {
  try {
    return await listInbox(options);
  } catch {
    return null;
  }
}
