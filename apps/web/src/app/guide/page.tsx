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
 * Starting points for a visitor who does not know the library yet.
 *
 * Not a required list — the deployment runs live AI, so any question works.
 * These are the questions the recorded fallback also covers, so they behave
 * identically in Demo Mode.
 */
const EXAMPLE_QUESTIONS = [
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
          About ten minutes across all four live projects — no sign-up, no API
          key.
        </p>
      </header>

      {/* ---- what this is ------------------------------------------------- */}
      <Card>
        <CardHeader title="What you are looking at" />
        <div className="space-y-3 px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
          <p>
            The <strong>AI Operations Toolkit</strong> is a portfolio built for
            one specific job: an <strong>AI Operations Associate</strong> role at
            a B2B travel-tech company, where travel agencies book flights, hotels
            and holidays and an operations team keeps the on-ground delivery
            working. The role calls for AI-assisted{" "}
            <em>workflows, SOPs, dashboards, trackers and automations</em>, and
            every project here maps to one of those. Anything that could not be
            justified against the role was cut rather than kept for volume.
          </p>
          <p>
            <strong>Four of the nine projects are built and live</strong>, and
            you can click on all four today:
          </p>
          <ul className="ml-1 space-y-1.5">
            <li>
              <Link href="/documents" className="font-medium underline underline-offset-2">
                AI SOP Generator
              </Link>{" "}
              — turns a messy description of how a process works into a
              standardised SOP, and makes the library searchable with the source
              shown next to every answer.
            </li>
            <li>
              <Link href="/" className="font-medium underline underline-offset-2">
                AI Operations Dashboard
              </Link>{" "}
              — upload a spreadsheet and get KPIs, trends and anomalies, with
              what was measured kept separate from what is only a hypothesis.
            </li>
            <li>
              <Link href="/travel-ops" className="font-medium underline underline-offset-2">
                AI Travel Operations
              </Link>{" "}
              — the flagship. A flight is delayed; it finds the affected
              bookings, judges the severity, drafts each agency a message, and
              stops for a human before anything is recorded as sent.
            </li>
            <li>
              <Link href="/workflows" className="font-medium underline underline-offset-2">
                AI Workflow Builder
              </Link>{" "}
              — build a sequence of steps and run it, on the same engine Travel
              Operations runs on, with an approval guard the engine enforces.
            </li>
          </ul>
          <p>
            The remaining five are listed on the{" "}
            <Link href="/projects" className="underline underline-offset-2">Projects</Link>{" "}
            page as not yet built, because they are not yet built.
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
              Live AI — what you are in by default
            </h3>
            <p className="mt-1">
              Ask it anything you like. Your question goes to a real model and
              comes back with a real answer, generated for you, now. Nothing on
              this site is replayed from a script and nothing is hand-written to
              look like AI output.
            </p>
            <p className="mt-2">
              <strong>What this costs, stated plainly:</strong> it runs on a
              free tier, which allows roughly{" "}
              <strong>20 AI requests a day</strong> across everyone using the
              site. That is a deliberate choice rather than an oversight — a
              paid tier would remove the limit, and showing a real system that
              occasionally runs out is more honest than showing a canned one
              that never does. If the day&rsquo;s budget is gone you will get a
              clear message saying so, not a broken page. Try again tomorrow.
            </p>
            <p className="mt-2">
              The AI key lives on the server and is never sent to your browser.
              You are not asked for one, and nothing you type is billed to you.
            </p>
          </div>

          <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
            <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
              Demo Mode — the fallback, and how this is tested
            </h3>
            <p className="mt-1">
              The repository also carries{" "}
              {system && system.demo_recordings > 0 ? (
                <>{system.demo_recordings} recorded AI outputs</>
              ) : (
                <>a set of recorded AI outputs</>
              )}
              : real responses a real model really produced, saved to disk.
              Setting{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                DEMO_MODE=true
              </code>{" "}
              replays those instead of calling the model, which is how local
              development and the automated tests run — no key required and no
              quota spent to run the test suite.
            </p>
            <p className="mt-2">
              It matters that this is a <em>recording</em> and not a
              <em> simulation</em>. Replaying an output a model genuinely
              produced is honest; inventing a plausible-looking one and calling
              it AI output would make every other claim on this site worthless.
              The{" "}
              <Link href="/settings" className="underline underline-offset-2">
                Settings
              </Link>{" "}
              page always shows which mode you are in.
            </p>
          </div>
        </div>
      </Card>

      {/* ---- walkthrough --------------------------------------------------- */}
      <Card>
        <CardHeader
          title="A ten-minute walkthrough"
          description="In order — each step shows something the one before it does not. Steps 1–5 are the SOP Generator; 6, 7 and 8 are the other three live projects."
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
              On the same page, use <strong>Ask</strong>.{" "}
              <strong>Type your own question</strong> — anything the SOP you
              just read would plausibly answer. It goes to a live model, so it
              does not have to be one of ours. If you would rather start from a
              known-good one:
            </p>
            {EXAMPLE_QUESTIONS.map((q) => (
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
              Pick your own unrelated question if you prefer — the behaviour is
              not specific to printers, and the model is answering live, so
              there is nothing prepared here to fall back on.
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

          <Step n={6} title="Analyse a spreadsheet on the Dashboard">
            <p>
              Open the{" "}
              <Link href="/" className="underline underline-offset-2">
                Dashboard
              </Link>{" "}
              and pick a bundled dataset, or upload your own CSV or Excel file.
              KPI cards, trends and anomalies appear immediately —{" "}
              <strong>none of which the AI produced</strong>. Column types,
              rates and outliers are computed in code. The AI is only asked to
              interpret, and only when you press for insights.
            </p>
            <p>
              Read how an insight is worded. An observation and a guess are
              never allowed to blur into one another:{" "}
              <em>observed</em> states a measured fact,{" "}
              <em>hypothesis</em> is labelled as a possible contributor, and a
              recommendation says what to go and check. Presenting a guess as a
              finding is how a dashboard gets someone to act on nothing.
            </p>
          </Step>

          <Step n={7} title="Work a live incident — the flagship">
            <p>
              Open{" "}
              <Link href="/travel-ops" className="underline underline-offset-2">
                Travel Ops
              </Link>{" "}
              and open an incident. The affected bookings are already listed:
              that lookup matches route, supplier and date{" "}
              <strong>with no AI involved</strong>, so the model can never
              invent a booking reference — it is never asked to produce one.
            </p>
            <p>
              Press <strong>Assess and draft</strong>. The AI judges severity{" "}
              <em>and has to show its reasoning</em> — a bare label is a
              rejected response — then writes one message per affected agency.
              Every figure it cites was computed before it was called.
            </p>
            <p>
              Then notice what it will not do: the drafts sit as drafts.
              Approving one records your name and the time. Nothing is ever
              transmitted to anyone, and the execution log shows exactly where
              the human stood in the chain.
            </p>
          </Step>

          <Step n={8} title="Build a workflow, and try to break the guard">
            <p>
              Open{" "}
              <Link href="/workflows" className="underline underline-offset-2">
                Workflows
              </Link>
              . The <em>Travel incident response</em> flow listed there is not a
              picture of the previous step — it is the same definition that step
              actually ran. The builder and the flagship are two clients of one
              engine.
            </p>
            <p>
              Make your own: <strong>New workflow</strong>, then add a Trigger,
              an AI drafting step and an Email step, and save it. Now press{" "}
              <strong>Run</strong>. It refuses — an Email step can be reached
              without a human approving it first, and the engine will not
              execute that graph. Add a <strong>Human approval</strong> step
              before the Email and run it again: it pauses, waits for your
              decision, and only then continues.
            </p>
            <p>
              That refusal is the point of the project. It is enforced by the
              shared engine rather than by the editor being careful, so it holds
              for any workflow anyone builds.
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
              def: "Every AI call logs its model, duration, token count and estimated cost. An operations role that introduces AI without tracking what it spends has moved the problem, not solved it. Running this demo on a free tier with a visible daily ceiling — rather than hiding the cost question behind pre-recorded answers — is the same decision applied to this site.",
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
