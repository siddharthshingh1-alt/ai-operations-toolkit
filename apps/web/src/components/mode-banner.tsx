import type { SystemInfo } from "@aiops/types";
import { Badge } from "@aiops/ui";

/**
 * The always-visible mode indicator.
 *
 * CLAUDE.md Section 3b: "Clearly label which mode is active in the UI at all
 * times. Never blur the two." This component is that guarantee — it renders on
 * every page via the root layout, and it never hides.
 */
export function ModeBanner({ system }: { system: SystemInfo | null }) {
  if (!system) {
    return (
      <Badge tone="danger">
        API unreachable — start the backend with <code>npm run dev:api</code>
      </Badge>
    );
  }

  if (!system.demo_mode) {
    return (
      <Badge tone="info">
        Live AI — calls go to {system.ai_provider} and cost money
      </Badge>
    );
  }

  // Demo Mode with no recordings is a real, reportable state, not a warning to
  // paper over: nothing can run until someone records real outputs once.
  if (system.demo_recordings === 0) {
    return (
      <Badge tone="warning">
        Demo Mode — no recordings yet, run <code>npm run record-demo</code>
      </Badge>
    );
  }

  return (
    <Badge tone="success">
      Demo Mode — replaying {system.demo_recordings} recorded AI{" "}
      {system.demo_recordings === 1 ? "output" : "outputs"}
    </Badge>
  );
}
