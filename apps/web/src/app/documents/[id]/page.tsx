import Link from "next/link";
import { notFound } from "next/navigation";
import type { SopStatus } from "@aiops/types";
import { Badge, Card, CardHeader } from "@aiops/ui";
import type { BadgeTone } from "@aiops/ui";
import { exportUrl, getDiff, getSop } from "@/lib/sop-api";
import { DiffView } from "@/components/diff-view";

const STATUS_TONE: Record<SopStatus, BadgeTone> = {
  draft: "neutral",
  active: "success",
  under_review: "warning",
  retired: "danger",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-slate-100 px-5 py-4 dark:border-slate-800">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-400 uppercase dark:text-slate-500">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400 italic">None recorded.</p>;
  }
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export default async function SopPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ version?: string; from?: string; to?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;

  const version = query.version ? Number(query.version) : undefined;

  let sop;
  try {
    sop = await getSop(id, version);
  } catch {
    notFound();
  }

  // Diff mode: both ?from and ?to present.
  const from = query.from ? Number(query.from) : null;
  const to = query.to ? Number(query.to) : null;
  const diff = from && to && from !== to ? await getDiff(id, from, to).catch(() => null) : null;

  const c = sop.content;
  const isHistorical = sop.version !== sop.versions[0]?.version;

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <Link
          href="/documents"
          className="text-sm text-slate-500 hover:underline dark:text-slate-400"
        >
          ← All documents
        </Link>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            {c.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {sop.metadata.owner || "No owner"}
            {sop.metadata.department ? ` · ${sop.metadata.department}` : ""} · version{" "}
            {sop.version}
            {isHistorical ? " (historical)" : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[sop.metadata.status] ?? "neutral"}>
            {sop.metadata.status.replace("_", " ")}
          </Badge>
          <Link
            href={`/documents/${id}/edit`}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900"
          >
            Edit
          </Link>
        </div>
      </header>

      {isHistorical ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          You are viewing version {sop.version}, not the current one.{" "}
          <Link href={`/documents/${id}`} className="underline">
            View current version
          </Link>
        </div>
      ) : null}

      {diff ? <DiffView diff={diff} sopId={id} /> : null}

      {/* ---- downloads ---- */}
      <Card>
        <div className="flex flex-wrap items-center gap-3 px-5 py-3">
          <span className="text-sm text-slate-500 dark:text-slate-400">Download:</span>
          {(["markdown", "html", "pdf"] as const).map((fmt) => (
            <a
              key={fmt}
              href={exportUrl(id, fmt, sop.version)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {fmt === "markdown" ? "Markdown" : fmt.toUpperCase()}
            </a>
          ))}
          <span className="text-xs text-slate-400">
            PDF needs server-side libraries; Markdown and HTML always work.
          </span>
        </div>
      </Card>

      {/* ---- the SOP itself ---- */}
      <Card>
        <CardHeader title="Standard operating procedure" description={c.purpose} />

        <Section title="Scope">
          <p className="text-sm text-slate-700 dark:text-slate-300">{c.scope}</p>
        </Section>

        <Section title="Prerequisites">
          <Bullets items={c.prerequisites} />
        </Section>

        <Section title="Roles">
          <Bullets items={c.roles} />
        </Section>

        <Section title="Procedure">
          <ol className="space-y-3">
            {c.procedure.map((step) => (
              <li key={step.number} className="flex gap-3">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600 tabular-nums dark:bg-slate-800 dark:text-slate-300">
                  {step.number}
                </span>
                <div className="min-w-0">
                  <p className="text-sm text-slate-800 dark:text-slate-200">
                    {step.instruction}
                  </p>
                  {step.responsible || step.expected_result ? (
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {step.responsible ? `Responsible: ${step.responsible}` : ""}
                      {step.responsible && step.expected_result ? " · " : ""}
                      {step.expected_result ? `Expected: ${step.expected_result}` : ""}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </Section>

        {c.decision_points.length > 0 ? (
          <Section title="Decision points">
            <ul className="space-y-2">
              {c.decision_points.map((d, i) => (
                <li key={i} className="text-sm">
                  <p className="font-medium text-slate-800 dark:text-slate-200">
                    {d.question}
                  </p>
                  <p className="text-slate-600 dark:text-slate-400">
                    Yes → {d.if_yes}
                  </p>
                  <p className="text-slate-600 dark:text-slate-400">No → {d.if_no}</p>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {c.exceptions.length > 0 ? (
          <Section title="Exceptions">
            <ul className="space-y-1.5 text-sm">
              {c.exceptions.map((e, i) => (
                <li key={i}>
                  <span className="text-slate-800 dark:text-slate-200">{e.situation}</span>
                  <span className="text-slate-400"> → </span>
                  <span className="text-slate-600 dark:text-slate-400">{e.action}</span>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {c.escalation_rules.length > 0 ? (
          <Section title="Escalation">
            <ul className="space-y-1.5 text-sm">
              {c.escalation_rules.map((e, i) => (
                <li key={i} className="text-slate-700 dark:text-slate-300">
                  {e.trigger} → <strong>{e.escalate_to}</strong>
                  {e.within ? ` within ${e.within}` : ""}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        <Section title="Checklist">
          <ul className="space-y-1 text-sm">
            {c.checklist.map((item, i) => (
              <li key={i} className="flex gap-2 text-slate-700 dark:text-slate-300">
                <span className="text-slate-300 dark:text-slate-600">☐</span>
                {item}
              </li>
            ))}
          </ul>
        </Section>

        {c.kpis.length > 0 ? (
          <Section title="KPIs">
            <ul className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
              {c.kpis.map((k, i) => (
                <li key={i}>
                  <strong>{k.name}</strong>
                  {k.target ? ` — target ${k.target}` : ""}
                  {k.how_measured ? ` (${k.how_measured})` : ""}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {c.risks.length > 0 ? (
          <Section title="Risks">
            <ul className="space-y-1.5 text-sm">
              {c.risks.map((r, i) => (
                <li key={i}>
                  <Badge
                    tone={
                      r.severity === "high"
                        ? "danger"
                        : r.severity === "low"
                          ? "neutral"
                          : "warning"
                    }
                  >
                    {r.severity}
                  </Badge>{" "}
                  <span className="text-slate-700 dark:text-slate-300">
                    {r.description}
                  </span>
                  {r.mitigation ? (
                    <span className="text-slate-500 dark:text-slate-400">
                      {" "}
                      — {r.mitigation}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {c.improvement_suggestions.length > 0 ? (
          <Section title="Improvement suggestions">
            <Bullets items={c.improvement_suggestions} />
          </Section>
        ) : null}
      </Card>

      {/* ---- version history ---- */}
      <Card>
        <CardHeader
          title="Version history"
          description={
            sop.versions.length > 1
              ? "Pick two versions to see exactly what changed."
              : "Saving an edit creates version 2, which you can then compare against this one."
          }
        />
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {sop.versions.map((v) => (
            <li
              key={v.version}
              className="flex flex-wrap items-center justify-between gap-2 px-5 py-3"
            >
              <div className="min-w-0">
                <p className="text-sm text-slate-800 dark:text-slate-200">
                  <Link
                    href={`/documents/${id}?version=${v.version}`}
                    className="font-medium hover:underline"
                  >
                    Version {v.version}
                  </Link>
                  {" — "}
                  {v.change_note}
                </p>
                <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                  {new Date(v.created_at).toLocaleString()} · {v.created_by}
                  {v.ai_generated ? ` · AI draft (${v.ai_model ?? "unknown"})` : " · human edit"}
                  {v.searchable ? "" : " · not indexed for search"}
                </p>
              </div>
              {v.version > 1 ? (
                <Link
                  href={`/documents/${id}?from=${v.version - 1}&to=${v.version}`}
                  className="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Compare with v{v.version - 1}
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
