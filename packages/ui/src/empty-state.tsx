import type { ReactNode } from "react";

/**
 * Shown where a feature will live but does not yet.
 *
 * Deliberately explicit about *when* the feature arrives rather than showing a
 * fake chart or a spinner that never resolves. An honest placeholder is better
 * than a screen that pretends to work (CLAUDE.md Section 2).
 */
export function EmptyState({
  title,
  description,
  phase,
  action,
}: {
  title: string;
  description: string;
  phase?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 px-6 py-14 text-center dark:border-slate-700">
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h3>
      <p className="mt-1.5 max-w-md text-sm text-slate-500 dark:text-slate-400">
        {description}
      </p>
      {phase ? (
        <p className="mt-3 text-xs font-medium tracking-wide text-slate-400 uppercase dark:text-slate-500">
          {phase}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
