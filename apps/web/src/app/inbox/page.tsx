import { Card } from "@aiops/ui";
import { API_URL } from "@/lib/api";
import { tryListInbox, tryGetThread } from "@/lib/inbox-api";
import { InboxPanel } from "@/components/inbox/inbox-panel";

export const metadata = { title: "Inbox — AI Operations Toolkit" };

/**
 * Project 8 — AI Operations Inbox (CLAUDE.md Section 16).
 *
 * The list and the opened thread are fetched on the server, and both are free:
 * which messages are unanswered and how their threads group is computed, not
 * generated. Triage and drafting are behind buttons because each spends a
 * request from a daily budget shared by every visitor.
 *
 * `?thread=` and `?unanswered=` are supported so the Ops Command Center can
 * link straight at the thing it is flagging.
 */
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ thread?: string; unanswered?: string; category?: string }>;
}) {
  const params = await searchParams;
  const listing = await tryListInbox({
    category: params.category,
    unansweredOnly: params.unanswered === "1" || params.unanswered === "true",
  });

  const firstThread = listing?.items[0]?.email.thread_id;
  const wanted = params.thread ?? firstThread;
  const thread = wanted ? await tryGetThread(wanted) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Operations inbox
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Booking changes, delay alerts, agency questions, supplier confirmations and
          invoice queries. The AI reads and drafts; nothing is recorded as sent until a
          person approves it.
        </p>
      </header>

      {listing === null ? (
        <Card>
          <div className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
            <p>
              Could not reach the API at{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                {API_URL}
              </code>
              .
            </p>
            <p className="mt-2">
              If this is the deployed site it may be waking from idle — reload in a
              moment.
            </p>
          </div>
        </Card>
      ) : (
        <InboxPanel
          items={listing.items}
          counts={listing.counts}
          accuracy={listing.accuracy}
          categories={listing.categories}
          unansweredAfterHours={listing.unanswered_after_hours}
          initialThread={thread}
        />
      )}
    </div>
  );
}
