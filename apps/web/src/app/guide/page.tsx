import Link from "next/link";
import { Badge, Card, CardHeader } from "@aiops/ui";
import { tryGetSystemInfo } from "@/lib/api";

/**
 * The orientation page for someone who has just opened the deployed site.
 *
 * Written to be read by a hiring manager, not a developer, and to be honest
 * about what Demo Mode cannot do. A demo that quietly hides its limitations
 * teaches a reviewer to distrust everything else on the page — so the
 * constraint is stated plainly, with the reasoning that led to it.
 *
 * The mode facts are read live from the API rather than written into the copy,
 * so this page cannot drift out of date the way prose does.
 */

/**
 * The questions with recorded answers.
 *
 * Source of truth is `scripts/record_demo_outputs.py`; this list is repeated
 * here so a visitor can copy one. If you add a question there, add it here.
 */
const RECORDED_QUESTIONS = [
  "How quickly must we contact agents after a flight delay?",
  "What do we do if a hotel overbooks a confirmed room?",
  "What are the steps to onboard a new travel agency?",
];

function Step({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-4 px-5 py-4">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600 tabular-nums dark:bg-slate-800 dark:text-slate-300">
        {n}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
          {title}
        </h3>
        <div className="mt-1 space-y-2 text-sm text-slate-600 dark:text-slate-400">
          {children}
        </div>
      </div>
    </li>
  );
}

function Quote({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border-l-2 border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
      {children}
    </p>
  );
}

export default async function GuidePage() {
  const system = await tryGetSystemInfo();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          How to use this demo
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          About five minutes, no sign-up, no API key.
        </p>
      </header>

      {/* ---- what this is ------------------------------------------------- */}
      <Card>
        <CardHeader title="What you are looking at" />
        <div className="space-y-3 px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
          <p>
            The <strong>AI Operations Toolkit</strong> is a portfolio built for
            one specific job: an <strong>AI Operations Associate</strong> role at
            a B2B travel-tech company, where travel agents book flights, hotels
            and holidays and an operations team keeps the on-ground delivery
            working. The job description asks for AI-assisted{" "}
            <em>workflows, SOPs, dashboards, trackers and automations</em>, and
            every project here maps to one of those. Anything that could not be
            justified against the role was cut rather than kept for volume.
          </p>
          <p>
            One project is finished so far: the{" "}
            <strong>AI SOP Generator</strong>. It turns a messy description of
            how a process works into a standardised SOP — steps, decision
            points, escalation rules, KPIs — and makes the resulting library
            searchable, with the source SOP shown next to every answer. That is
            the part you can click on today. The remaining projects are listed
            on the <Link href="/" className="underline underline-offset-2">Dashboard</Link>{" "}
            as not yet built, because they are not yet built.
          </p>
          <p>
            All data here is synthetic. No real company, agent or traveller
            appears anywhere in it.
          </p>
        </div>
      </Card>

      {/* ---- the two modes ------------------------------------------------ */}
      <Card>
        <CardHeader
          title="The two modes, and the honest limitation"
          description="Which one you are in right now is read live from the API."
          action={
            system ? (
              <Badge tone={system.demo_mode ? "warning" : "success"}>
                {system.demo_mode ? "Demo Mode" : "Live AI"}
              </Badge>
            ) : null
          }
        />
        <div className="space-y-4 px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
          <div>
            <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
              Demo Mode — what you are in by default
            </h3>
            <p className="mt-1">
              Every AI output you see was <strong>really produced by a real
              model</strong>, once, and saved. Demo Mode replays those
              recordings
              {system ? <> — there are {system.demo_recordings} of them</> : null}
              . It is not a simulation and nothing here was hand-written to look
              like AI output.
            </p>
            <p className="mt-2">
              <strong>The limitation:</strong> a recording exists only for the
              example SOPs and the sample questions below. Type your own
              question and you will get an honest{" "}
              <em>&ldquo;no recording for this&rdquo;</em> rather than an answer.
            </p>
            <p className="mt-2">
              That is a deliberate trade, and the reasoning is the point: this
              site is public, so a live AI key sitting on the server would be a
              key that can leak and a free-tier quota any visitor could exhaust
              in a few minutes. Recording real outputs once removes both risks
              without ever showing you something a model did not actually say.
              The alternative — generating plausible-looking text and calling it
              AI output — would make every other claim on this site worthless.
            </p>
          </div>

          <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
              Running it live — if you want to verify it is real
            </h3>
            <p className="mt-1">
              A reviewer who suspects the whole thing is canned can run it
              against a live model instead: clone the repository, put your own
              provider key in <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">.env</code>,
              set <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">DEMO_MODE=false</code>,
              and every feature runs live on <strong>any</strong> question or
              SOP you like, with nothing replayed. The{" "}
              <Link href="/settings" className="underline underline-offset-2">
                Settings
              </Link>{" "}
              page shows which mode is active.
            </p>
            <p className="mt-2">
              <strong>Being straight about this one:</strong> that currently
              requires running it yourself. Pasting a key into this hosted site
              is not implemented yet — the intended design is that a key you
              supply is used for your session and never stored, and until that
              is actually built, this page will not claim otherwise.
            </p>
          </div>
        </div>
      </Card>

      {/* ---- walkthrough --------------------------------------------------- */}
      <Card>
        <CardHeader
          title="A five-minute walkthrough"
          description="In order — each step shows something the one before it does not."
        />
        <ol className="divide-y divide-slate-200 dark:divide-slate-800">
          <Step n={1} title="Read an SOP first">
            <p>
              Open{" "}
              <Link href="/documents" className="underline underline-offset-2">
                Documents
              </Link>{" "}
              and read one — the hotel overbooking one is a good start. Note
              that it has structure a human would actually use on a shift:
              numbered steps, decision points, escalation rules, KPIs, and named
              role owners. That structure is enforced by the code, not requested
              politely in a prompt.
            </p>
            <p>
              Knowing what is in the library matters for the next two steps.
            </p>
          </Step>

          <Step n={2} title="Ask a question and check the citation">
            <p>
              On the same page, use <strong>Ask</strong>. In Demo Mode, use one
              of the recorded questions:
            </p>
            {RECORDED_QUESTIONS.map((q) => (
              <Quote key={q}>{q}</Quote>
            ))}
            <p>
              The answer arrives with <strong>the SOPs it came from shown
              underneath</strong>. That is the part worth checking: open the
              cited SOP and confirm the answer is actually in it. An answer you
              cannot trace is an answer you cannot act on during an incident.
            </p>
          </Step>

          <Step n={3} title="Now ask something the library does not cover">
            <p>Try:</p>
            <Quote>How do I fix the office printer?</Quote>
            <p>
              No SOP covers office printers, and the honest answer is to say so.
              The system compares your question against the library first and,
              when nothing clears a relevance threshold,{" "}
              <strong>never calls the AI at all</strong> — it reports the gap
              instead. There is no opportunity to invent an answer because no
              answer is ever requested.
            </p>
            <p>
              If you instead see a message about a missing demo recording, that
              is the Demo Mode limitation above showing through rather than the
              refusal behaviour — running it live, as described above,
              demonstrates it properly.
            </p>
          </Step>

          <Step n={4} title="Export a PDF">
            <p>
              Open any SOP and click <strong>PDF</strong>. A real, formatted
              document downloads — the thing an operations team would actually
              print, attach to a ticket, or hand to a new joiner. Markdown and
              HTML are there too.
            </p>
          </Step>

          <Step n={5} title="Edit it, then compare versions">
            <p>
              Edit an SOP and save it. The old version is kept, and the{" "}
              <strong>diff</strong> view shows exactly what changed between any
              two versions, line by line.
            </p>
            <p>
              This is the step that separates a document generator from
              something an operations team can rely on. When an SOP changes, the
              first question anyone asks is <em>what changed, and who changed
              it</em> — a flat list of snapshots cannot answer that.
            </p>
          </Step>
        </ol>
      </Card>

      {/* ---- design principles --------------------------------------------- */}
      <Card>
        <CardHeader
          title="Four decisions behind what you just used"
          description="Each one cost something. That is what makes them decisions."
        />
        <dl className="divide-y divide-slate-200 dark:divide-slate-800">
          {[
            {
              term: "The AI drafts; a human decides",
              def: "Generated SOPs land in an editor, not in the library. Nothing is published, sent, or acted on without someone approving it. For operations work the failure mode is not a bad draft — it is a bad draft nobody read.",
            },
            {
              term: "Refusing to answer is a feature",
              def: "Answers are grounded in retrieved SOPs and cite them. When nothing relevant is found the AI is not called at all. A confident wrong answer during a live booking incident is worse than no answer, because it gets acted on.",
            },
            {
              term: "Cost is measured, not assumed",
              def: "Every AI call logs its model, duration, token count and estimated cost. An operations role that introduces AI without tracking what it spends has moved the problem, not solved it. Recording demo outputs once, instead of paying per visitor, is the same decision applied to this site.",
            },
            {
              term: "Nothing secret reaches your browser",
              def: "API keys stay on the server; the browser is never given one. The database holds only synthetic data, and this public demo needs no key at all — there is nothing here worth stealing, by design rather than by luck.",
            },
          ].map((item) => (
            <div key={item.term} className="px-5 py-4">
              <dt className="text-sm font-medium text-slate-900 dark:text-slate-100">
                {item.term}
              </dt>
              <dd className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                {item.def}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <p className="pb-2 text-xs text-slate-400 dark:text-slate-500">
        The full reasoning — including what was cut from this portfolio and why
        — is in the repository README.
      </p>
    </div>
  );
}
