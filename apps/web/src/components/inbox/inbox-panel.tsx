"use client";

import { useState } from "react";
import { Badge, Card, CardHeader } from "@aiops/ui";
import type {
  InboxAccuracy,
  InboxCounts,
  InboxItem,
  InboxThreadResponse,
  TrackerUsageInfo,
  TriageView,
} from "@aiops/types";
import {
  decideReplyAction,
  draftReplyAction,
  getThreadAction,
  triageThreadAction,
} from "@/app/inbox/actions";

/**
 * The Operations Inbox.
 *
 * The list on the left is entirely computed — who wrote, when, whether it has
 * been answered. Opening a message costs nothing. The two buttons on the right
 * are the only things that spend a request, and the approval box beneath them
 * is the only route to a send.
 */

function urgencyTone(urgency: string | null): "danger" | "warning" | "info" | "neutral" {
  if (urgency === "critical") return "danger";
  if (urgency === "high") return "warning";
  if (urgency === "normal") return "info";
  return "neutral";
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-slate-200 px-3 py-2 dark:border-slate-800">
      <div className="text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-100">
        {value}
      </div>
      <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

function TriageDetail({ triage }: { triage: TriageView }) {
  return (
    <div className="space-y-3 rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2">
        {triage.category ? <Badge tone="info">{triage.category}</Badge> : null}
        {triage.urgency ? (
          <Badge tone={urgencyTone(triage.urgency)}>{triage.urgency}</Badge>
        ) : null}
        {triage.agreed_with_seed !== null ? (
          <Badge tone={triage.agreed_with_seed ? "success" : "warning"}>
            {triage.agreed_with_seed ? "matched the seeded label" : "differed from the seeded label"}
          </Badge>
        ) : null}
      </div>

      {triage.reasoning ? (
        <div>
          <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300">Why</h4>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{triage.reasoning}</p>
        </div>
      ) : null}

      {triage.summary ? (
        <div>
          <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300">
            What it asks for
          </h4>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{triage.summary}</p>
        </div>
      ) : null}

      {triage.tasks.length > 0 ? (
        <div>
          <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300">
            Extracted tasks
          </h4>
          <ul className="mt-1 space-y-1">
            {triage.tasks.map((task, index) => (
              <li key={index} className="text-sm text-slate-600 dark:text-slate-400">
                {task.title}
                {task.owner_hint ? (
                  <span className="text-xs text-slate-400"> — {task.owner_hint}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {triage.follow_up ? (
        <div>
          <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300">Follow-up</h4>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{triage.follow_up}</p>
        </div>
      ) : null}
    </div>
  );
}

export function InboxPanel({
  items,
  counts,
  accuracy,
  categories,
  unansweredAfterHours,
  initialThread,
}: {
  items: InboxItem[];
  counts: InboxCounts;
  accuracy: InboxAccuracy;
  categories: string[];
  unansweredAfterHours: number;
  initialThread: InboxThreadResponse | null;
}) {
  const [thread, setThread] = useState<InboxThreadResponse | null>(initialThread);
  const [usage, setUsage] = useState<TrackerUsageInfo | null>(null);
  const [approver, setApprover] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function open(threadId: string) {
    if (thread?.thread_id === threadId) return;
    setBusy("open");
    setError(null);
    setMessage(null);
    setUsage(null);
    const result = await getThreadAction(threadId);
    if (result.ok) setThread(result.data);
    else setError(result.error);
    setBusy(null);
  }

  async function run(
    key: string,
    call: (id: string) => Promise<{ ok: boolean } & Record<string, unknown>>,
  ) {
    if (!thread) return;
    setBusy(key);
    setError(null);
    setMessage(null);
    const result = (await call(thread.thread_id)) as
      | { ok: true; data: { thread: InboxThreadResponse; usage: TrackerUsageInfo } }
      | { ok: false; error: string };
    if (result.ok) {
      setThread(result.data.thread);
      setUsage(result.data.usage);
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  async function decide(approved: boolean) {
    if (!thread) return;
    setBusy(approved ? "approve" : "reject");
    setError(null);
    const result = await decideReplyAction(thread.thread_id, approved, approver, note);
    if (result.ok) {
      setThread(result.data);
      setMessage(
        approved
          ? "Approved and recorded. Nothing was transmitted — the adapter logs the send."
          : "Rejected. Nothing was recorded as sent.",
      );
      setNote("");
    } else {
      setError(result.error);
    }
    setBusy(null);
  }

  const triage = thread?.triage ?? null;
  const latest = thread?.emails[thread.emails.length - 1];

  return (
    <div className="space-y-6">
      {error ? (
        <div
          role="alert"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          {message}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Messages" value={counts.total} />
        <Stat label={`Unanswered > ${unansweredAfterHours}h`} value={counts.unanswered} />
        <Stat label="Triaged" value={counts.triaged} />
        <Stat label="Awaiting approval" value={counts.awaiting_approval} />
      </div>

      {accuracy.triaged > 0 ? (
        <Card>
          <div className="px-5 py-3 text-sm text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-slate-100">
              Classification accuracy: {accuracy.agreed} of {accuracy.triaged}
              {accuracy.percent !== null ? ` (${accuracy.percent}%)` : ""}
            </strong>{" "}
            — the model classified from the subject and body alone, and this compares its
            answer with the category the dataset was generated from.{" "}
            <span className="text-slate-400 dark:text-slate-500">
              This measurement exists only because the inbox is synthetic. A real inbox
              has no answer key, and this panel would not exist.
            </span>
          </div>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        {/* ---- the list ------------------------------------------------ */}
        <Card>
          <CardHeader
            title="Messages"
            description="Newest first. Reading costs nothing."
          />
          <ul className="max-h-[36rem] divide-y divide-slate-200 overflow-y-auto dark:divide-slate-800">
            {items.map((item) => (
              <li key={item.email.id}>
                <button
                  type="button"
                  onClick={() => void open(item.email.thread_id)}
                  className={`w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 ${
                    thread?.thread_id === item.email.thread_id
                      ? "bg-slate-50 dark:bg-slate-800/50"
                      : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                      {item.email.subject}
                    </span>
                    {item.triage?.urgency ? (
                      <Badge tone={urgencyTone(item.triage.urgency)}>
                        {item.triage.urgency}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                    <span className="truncate">{item.email.sender}</span>
                    <span>· {Math.round(item.email.age_hours)}h ago</span>
                    {item.message_count > 1 ? <span>· {item.message_count} messages</span> : null}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {item.email.is_unanswered ? <Badge tone="warning">unanswered</Badge> : null}
                    {item.triage?.category ? (
                      <Badge tone="neutral">{item.triage.category}</Badge>
                    ) : null}
                    {item.triage?.draft_status === "draft" ? (
                      <Badge tone="danger">awaiting approval</Badge>
                    ) : null}
                    {item.triage?.draft_status === "approved" ? (
                      <Badge tone="success">replied</Badge>
                    ) : null}
                  </div>
                </button>
              </li>
            ))}
            {items.length === 0 ? (
              <li className="px-4 py-6 text-sm text-slate-500 dark:text-slate-400">
                No messages match this filter.
              </li>
            ) : null}
          </ul>
        </Card>

        {/* ---- the thread ---------------------------------------------- */}
        <div className="space-y-6">
          {thread && latest ? (
            <>
              <Card>
                <CardHeader
                  title={latest.subject}
                  description={`${thread.message_count} message${
                    thread.message_count === 1 ? "" : "s"
                  }${thread.is_long ? " · long enough that the summary is worth more than reading it" : ""}`}
                />
                <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                  {thread.emails.map((email) => (
                    <li key={email.id} className="px-5 py-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                        <span className="font-medium text-slate-700 dark:text-slate-300">
                          {email.sender}
                        </span>
                        <span>{new Date(email.received_at).toLocaleString()}</span>
                        {email.is_unanswered ? <Badge tone="warning">unanswered</Badge> : null}
                        {email.agency_id ? <Badge tone="neutral">{email.agency_id}</Badge> : null}
                      </div>
                      <p className="mt-1.5 text-sm whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                        {email.body}
                      </p>
                    </li>
                  ))}
                </ul>
              </Card>

              <Card>
                <CardHeader
                  title="Ask the AI"
                  description="Each button spends one request. Nothing here runs on its own."
                />
                <div className="space-y-4 px-5 py-4">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => run("triage", triageThreadAction)}
                      disabled={busy !== null}
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                    >
                      {busy === "triage" ? "Reading…" : "Triage · 1 request"}
                    </button>
                    <button
                      type="button"
                      onClick={() => run("draft", draftReplyAction)}
                      disabled={busy !== null}
                      className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {busy === "draft" ? "Writing…" : "Draft a reply · 1 request"}
                    </button>
                  </div>

                  {usage ? (
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      {usage.model} · {usage.input_tokens + usage.output_tokens} tokens ·{" "}
                      {usage.estimated_cost_usd != null
                        ? `$${usage.estimated_cost_usd.toFixed(6)}`
                        : "cost —"}{" "}
                      · {usage.duration_ms}ms
                    </p>
                  ) : null}

                  {triage && triage.category ? <TriageDetail triage={triage} /> : null}

                  {triage?.draft_body ? (
                    <div className="rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300">
                          Drafted reply
                        </h4>
                        <Badge
                          tone={
                            triage.draft_status === "approved"
                              ? "success"
                              : triage.draft_status === "rejected"
                                ? "neutral"
                                : "warning"
                          }
                        >
                          {triage.draft_status}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                        {triage.draft_body}
                      </p>

                      {triage.draft_status === "draft" ? (
                        <div className="mt-3 space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            Nothing is recorded as sent until a person decides, and the
                            decision is stored with their name.
                          </p>
                          <input
                            value={approver}
                            onChange={(event) => setApprover(event.target.value)}
                            placeholder="Your name"
                            className="block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                          />
                          <input
                            value={note}
                            onChange={(event) => setNote(event.target.value)}
                            placeholder="Note (optional, kept if you reject)"
                            className="block w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => decide(true)}
                              disabled={busy !== null}
                              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                            >
                              {busy === "approve" ? "Recording…" : "Approve"}
                            </button>
                            <button
                              type="button"
                              onClick={() => decide(false)}
                              disabled={busy !== null}
                              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                            >
                              {busy === "reject" ? "Recording…" : "Reject"}
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {triage.approved_by ? (
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                          Approved by {triage.approved_by}
                          {triage.approved_at
                            ? ` on ${new Date(triage.approved_at).toLocaleString()}`
                            : ""}
                          . Recorded as {triage.recorded_message_id} — transmitted to nobody.
                        </p>
                      ) : null}
                      {triage.rejection_note ? (
                        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                          Rejected: {triage.rejection_note}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </Card>
            </>
          ) : (
            <Card>
              <p className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
                Select a message on the left.
              </p>
            </Card>
          )}
        </div>
      </div>

      <p className="pb-2 text-xs text-slate-400 dark:text-slate-500">
        Read through the mock email adapter. No real mailbox is connected, and no message
        is ever transmitted — an approved reply is recorded and labelled as such.{" "}
        {categories.length} categories: {categories.join(", ")}.
      </p>
    </div>
  );
}
