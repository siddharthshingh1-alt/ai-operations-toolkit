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
    // On the deployed URL this is almost always a cold start rather than a
    // fault: the API sleeps after 15 minutes idle and takes about 30 seconds to
    // wake. Telling a visitor to run `npm run dev:api` asks them to start a
    // backend they do not have, on the first screen they ever see, so the
    // developer instruction stays in development where it is the right answer.
    if (process.env.NODE_ENV === "production") {
      return (
        <Badge tone="warning">
          The demo backend is waking up (free tier) — this takes about 30
          seconds, please refresh in a moment
        </Badge>
      );
    }

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
    if (process.env.NODE_ENV === "production") {
      return <Badge tone="warning">Demo Mode — no recorded outputs available</Badge>;
    }

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
