"use client";

import { useRouter } from "next/navigation";
import type { SopContent, SopMetadata } from "@aiops/types";
import { saveVersionAction } from "@/app/documents/actions";
import { SopEditor } from "@/components/sop-editor";

/**
 * Client wrapper around the shared editor for the edit-an-existing-SOP flow.
 *
 * Uses the same `SopEditor` as the create flow, so the review experience is
 * identical whether the content came from the AI or from a previous version.
 */
export function EditSopForm({
  id,
  content,
  metadata,
  nextVersion,
}: {
  id: string;
  content: SopContent;
  metadata: SopMetadata;
  nextVersion: number;
}) {
  const router = useRouter();

  return (
    <SopEditor
      initialContent={content}
      initialMetadata={metadata}
      saveLabel={`Save as version ${nextVersion}`}
      onSave={async (input) => {
        const result = await saveVersionAction(id, input);
        if (result.ok) {
          // Land on the diff against the previous version, so the first thing
          // the user sees is exactly what their edit changed.
          router.push(
            `/documents/${id}?from=${nextVersion - 1}&to=${result.data.version}`,
          );
          return { ok: true };
        }
        return { ok: false, error: result.error };
      }}
    />
  );
}
