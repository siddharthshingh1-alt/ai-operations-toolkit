"use server";

import { revalidatePath } from "next/cache";
import type { AssessResponse, CommunicationView, IncidentDetail } from "@aiops/types";
import {
  assessIncident,
  decideCommunication,
  reportIncident,
  TravelApiError,
} from "@/lib/travel-api";

/**
 * Server actions for Travel Operations.
 *
 * `decideAction` is the only action in this toolkit that can cause a message to
 * be recorded as communicated to a partner. It requires an approver's name and
 * refuses without one — the same requirement the API and the email adapter each
 * enforce independently.
 */

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code: string };

function toError(error: unknown): { ok: false; error: string; code: string } {
  if (error instanceof TravelApiError) {
    return { ok: false, error: error.message, code: error.code };
  }
  return {
    ok: false,
    error: "Something went wrong. Please try again.",
    code: "unknown",
  };
}

export async function assessAction(
  incidentId: string,
): Promise<ActionResult<AssessResponse>> {
  try {
    const data = await assessIncident(incidentId);
    revalidatePath(`/travel-ops/${incidentId}`);
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function decideAction(
  communicationId: string,
  incidentId: string,
  approved: boolean,
  approvedBy: string,
  note?: string,
): Promise<ActionResult<CommunicationView>> {
  const approver = approvedBy.trim();
  if (approver.length < 2) {
    // Checked here as well as server-side, so the UI can say what is wrong
    // rather than surfacing a validation error from the API.
    return {
      ok: false,
      error: "Enter your name before approving or rejecting — a decision has to be attributable.",
      code: "approver_required",
    };
  }

  try {
    const data = await decideCommunication(communicationId, {
      approved,
      approved_by: approver,
      note,
    });
    revalidatePath(`/travel-ops/${incidentId}`);
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}

export async function reportAction(
  formData: FormData,
): Promise<ActionResult<IncidentDetail>> {
  const title = String(formData.get("title") ?? "").trim();
  if (title.length < 3) {
    return { ok: false, error: "Give the incident a title.", code: "title_required" };
  }

  const occurredAt = String(formData.get("occurred_at") ?? "").trim();

  try {
    const data = await reportIncident({
      kind: String(formData.get("kind") ?? "flight_delay"),
      title,
      description: String(formData.get("description") ?? "").trim(),
      route: String(formData.get("route") ?? "").trim() || null,
      supplier: String(formData.get("supplier") ?? "").trim() || null,
      occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null,
    });
    revalidatePath("/travel-ops");
    return { ok: true, data };
  } catch (error) {
    return toError(error);
  }
}
