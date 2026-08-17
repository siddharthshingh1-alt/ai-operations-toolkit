"use server";

import { revalidatePath } from "next/cache";
import type { InboxThreadResponse, InboxTriageResponse } from "@aiops/types";
import {
  InboxApiError,
  decideReply,
  draftReply,
  getThread,
  triageThread,
} from "@/lib/inbox-api";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof InboxApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return { ok: false, error: "Something went wrong. Please try again.", code: "unknown" };
}

export async function getThreadAction(
  threadId: string,
): Promise<ActionResult<InboxThreadResponse>> {
  try {
    return { ok: true, data: await getThread(threadId) };
  } catch (error) {
    return toError(error);
  }
}

/** One AI request. */
export async function triageThreadAction(
  threadId: string,
): Promise<ActionResult<InboxTriageResponse>> {
  try {
    const data = await triageThread(threadId);
    revalidatePath("/inbox");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

/** One AI request. The result is a draft and goes nowhere. */
export async function draftReplyAction(
  threadId: string,
): Promise<ActionResult<InboxTriageResponse>> {
  try {
    const data = await draftReply(threadId);
    revalidatePath("/inbox");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

/**
 * Approve or reject a drafted reply.
 *
 * The approver is checked here as well as in the API, so an unnamed approval
 * never leaves the browser — but the API and the adapter beneath it refuse one
 * regardless. That redundancy is deliberate: Section 16's rule is the one in
 * this project worth defending in more than one place.
 */
export async function decideReplyAction(
  threadId: string,
  approved: boolean,
  approvedBy: string,
  note?: string,
): Promise<ActionResult<InboxThreadResponse>> {
  const approver = approvedBy.trim();
  if (approver.length < 2) {
    return {
      ok: false,
      error:
        "Enter your name before approving or rejecting — a decision has to be attributable.",
      code: "approver_required",
    };
  }
  try {
    const data = await decideReply(threadId, {
      approved,
      approved_by: approver,
      note: note?.trim() || null,
    });
    revalidatePath("/inbox");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}
