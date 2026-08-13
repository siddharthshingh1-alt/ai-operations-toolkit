import { cn } from "./cn";

/**
 * A small coloured dot with an accessible label.
 *
 * The label is not decorative: colour alone must never be the only carrier of
 * meaning (CLAUDE.md Section 21 requires the UI to be accessible).
 */
export function StatusDot({
  tone,
  label,
}: {
  tone: "ok" | "warning" | "danger" | "idle";
  label: string;
}) {
  const colour = {
    ok: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-rose-500",
    idle: "bg-slate-300 dark:bg-slate-600",
  }[tone];

  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cn("size-2 rounded-full", colour)}
        aria-hidden="true"
      />
      <span className="text-sm text-slate-700 dark:text-slate-300">{label}</span>
    </span>
  );
}
