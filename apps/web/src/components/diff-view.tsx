import Link from "next/link";
import type { FieldDiff, SopDiff } from "@aiops/types";
import { Card, CardHeader } from "@aiops/ui";

/**
 * Renders a version comparison.
 *
 * All the diff logic lives server-side in `aiops_sop.diffing` — this component
 * only paints what it is given, so the browser and any export share exactly
 * one definition of "what changed".
 */

function countLines(field: FieldDiff, kind: "added" | "removed"): number {
  return field.lines.filter((l) => l.kind === kind).length;
}

export function DiffView({ diff, sopId }: { diff: SopDiff; sopId: string }) {
  const changed = diff.fields.filter((f) => f.kind !== "unchanged");

  const added = changed.reduce((n, f) => n + countLines(f, "added"), 0);
  const removed = changed.reduce((n, f) => n + countLines(f, "removed"), 0);

  return (
    <Card>
      <CardHeader
        title={`Changes from version ${diff.from_version} to ${diff.to_version}`}
        description={
          changed.length === 0
            ? "These two versions are identical."
            : `${changed.length} section${changed.length === 1 ? "" : "s"} changed · ${added} line${added === 1 ? "" : "s"} added, ${removed} removed`
        }
        action={
          <Link
            href={`/documents/${sopId}`}
            className="text-sm text-slate-500 hover:underline dark:text-slate-400"
          >
            Close
          </Link>
        }
      />

      {changed.length === 0 ? null : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {changed.map((field) => (
            <div key={field.field} className="px-5 py-3">
              <h4 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
                {field.label}
                <span className="ml-2 font-normal text-slate-400">
                  {field.kind === "added"
                    ? "section added"
                    : field.kind === "removed"
                      ? "section removed"
                      : `+${countLines(field, "added")} / −${countLines(field, "removed")}`}
                </span>
              </h4>

              <div className="overflow-x-auto rounded-md border border-slate-200 dark:border-slate-800">
                <table className="w-full border-collapse font-mono text-xs">
                  <tbody>
                    {field.lines.map((line, i) => {
                      const style =
                        line.kind === "added"
                          ? "bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
                          : line.kind === "removed"
                            ? "bg-rose-50 text-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
                            : "text-slate-500 dark:text-slate-400";
                      const marker =
                        line.kind === "added" ? "+" : line.kind === "removed" ? "−" : " ";

                      return (
                        <tr key={i} className={style}>
                          <td className="w-6 border-r border-slate-200 px-2 py-1 text-center align-top select-none dark:border-slate-800">
                            {marker}
                          </td>
                          <td className="px-3 py-1 break-words whitespace-pre-wrap">
                            {line.text}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
