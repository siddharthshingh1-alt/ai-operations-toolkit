# AI Operations Inbox

Project 8 of the AI Operations Toolkit (CLAUDE.md Section 16).

**Status: shipped.** Live at
**https://ai-operations-toolkit-web.vercel.app/inbox**

## Problem

The operations inbox is where the day actually arrives. A booking change from
an agency, a delay alert, a hotel confirming a rate before end of day, an
invoice query, a partner asking about seat limits — all in one list, all
looking identical until someone opens them.

Two things go wrong, and neither is dramatic. The urgent message sits below
four routine ones because it arrived first. And a partner who asked a question
on Thursday is still waiting on Tuesday, because nothing in a mailbox says
"nobody has replied to this".

## Which JD requirement this proves

Building AI-assisted **automations** — the fifth of the role's five nouns — and
identifying an operational bottleneck that is invisible precisely because it
looks like ordinary work.

## Who Uses It

An operations associate working the shared inbox, and whoever approves what
goes back out.

## Business Impact

| | |
|---|---|
| Manual process | ~2.5 hrs/day reading, sorting, and drafting replies across ~40 messages |
| With this | ~50 min: triaged and ordered on arrival, drafts to edit rather than write |
| Saving | ~1.6 hours/day ≈ 400 hours/year |

*Simulated demo estimate against the synthetic dataset in this repository. Not
a measured result and not a claim of real-world deployment (Section 19).*

## Features

- **Classification** into the seven categories, with required reasoning
- **Urgency** judged separately from tone — a politely worded message about
  passengers stranded today outranks an angry one about an invoice
- **Thread summarisation**, in the same call, when a thread is long enough to
  need it
- **Task extraction** — only what the sender actually asked for
- **Drafted replies**, which are drafts and nothing more
- **Suggested follow-up** beyond the reply itself
- **Unanswered detection**, computed
- **Classification accuracy**, measured against the dataset's seeded labels
- Feeds the Ops Command Center as its fifth signal source

## Architecture

```
operations_inbox_emails.csv
  └─ MockEmailProvider          list_emails / get_thread — read only
       ├─ threads.py            computed: unanswered, age, grouping
       └─ AI: triage            category, urgency, reasoning, summary, tasks
            └─ AI: draft reply
                 └─ ⏸ HUMAN APPROVAL      the only path to a send
                      └─ send_reply(approved_by=…)   records, transmits nothing
```

### Nothing is sent without a named person

This is the rule Section 16 exists for, and it is defended at four levels:

1. **The interface.** `EmailProvider.send_reply` takes `approved_by` as a
   required argument. A send with no approver cannot be *expressed*.
2. **The adapter.** It rejects an empty or whitespace approver before doing
   anything.
3. **The service.** Exactly one function reaches `send_reply`, and it passes
   the approver straight from the request. There is no default, no fallback to
   the configured demo user, and no "system".
4. **A test that reads the source**, asserting there is exactly one send call
   and that no code path supplies `approved_by="system"`, `approved_by=None`,
   or the demo user. A future convenience cannot quietly reintroduce an
   unattributed send without failing CI.

Rejecting records the note and nothing else. Redrafting after a decision clears
that decision, because an approval recorded against text that has since been
replaced would be a lie about what was approved.

### The code counts; the model reads

| Computed in `threads.py` | Asked of the model |
|---|---|
| whether a message has been answered | which of the seven categories it is |
| how long it has been waiting | how urgent it is, and why |
| which messages form a thread | what the sender is asking for |
| which agency it came from | what to do about it |

`has_reply` is a boolean and age is a subtraction — a model asked to work those
out would usually be right, and "usually" is the wrong property for the list a
team works through on a Monday.

An email that arrived an hour ago is **not** unanswered, it is new. The
threshold is 48 hours, because a list that flags everything which arrived on
Friday afternoon stops being read by Monday.

### Emails are never stored

They are read through the adapter on every request. The single table holds only
this project's output: the triage, the drafted reply, and the approval record.
A test asserts the table has no `subject`, `body`, `sender` or `received_at`
column, so a future convenience cannot quietly turn this into a mail archive.

### The accuracy panel, and why it is honest

The synthetic dataset carries the category its generator used. **The model
never sees it** — a test asserts the seeded label never appears in the prompt —
and agreement is recorded afterwards as an evaluation signal.

That measurement exists only because the data is seeded. A real inbox has no
answer key, so this panel would not exist, and the UI says exactly that rather
than letting a reviewer infer a capability that would not survive contact with
production.

## AI Usage

Two calls, two buttons, one request each, both labelled with their cost.

| Call | Output | Constraint |
|---|---|---|
| Triage | category, urgency, reasoning, summary, tasks, follow-up | category is a closed enum — an invented one is an invalid response; reasoning is required |
| Draft reply | the reply body | told explicitly it does not know fares, rates, commission or refund timelines, and must say what will be confirmed rather than invent a number |

They are separate calls because they are separate decisions: someone may want
forty messages triaged without forty replies drafted, and each request comes
out of the same daily budget.

**Reading the inbox costs nothing.** A test asserts six page loads spend zero
requests.

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL · the mock `EmailProvider` adapter and
the shared AI layer · Next.js, TypeScript, Tailwind

## Setup

Nothing project-specific. One table, `inbox_triage`, created by `create_all()`.
The dataset comes from `npm run demo-data`.

## Environment Variables

None of its own. `EMAIL_PROVIDER` must stay `mock` — Section 3c makes any other
value a startup error.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/inbox**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/inbox**

## Example

A message from an agency reading *"Our client needs to move BK-00349 to the
following week. Please advise on fare difference and whether the current fare
rules allow a change."*

Triaged, it comes back **Booking Ops / high**, with the reasoning naming the
date change and the fare-rule question, a summary of what is being asked, and
one extracted task — *quote the fare difference* — owned by Booking Ops.

The drafted reply acknowledges both questions and commits to confirming the
fare rather than inventing a number, because the prompt forbids inventing one.
It then sits as a **draft** until someone types their name and approves it, at
which point the adapter records `mock-sent-TH-0014` and transmits nothing.

## Limitations

- **Nothing is ever transmitted.** The adapter records an approved reply and
  sends no mail. Real delivery is a documented future improvement (Section 3c),
  not a missing piece pretending to be finished.
- **No real mailbox, in any version.** No OAuth, no Gmail, no IMAP.
- **Triage is per thread, not bulk.** Forty messages means forty requests,
  which on a twenty-a-day free tier is a real constraint rather than an
  oversight. Bulk triage would need a paid tier to be honest about.
- **The accuracy panel needs seeded data** and would not exist for a real
  inbox.
- **No compose.** This triages what arrives; it does not start conversations.
- **No attachments**, and the dataset has none.
- **All data is synthetic.** No real agency, supplier or person appears in it.

## Security

No secrets of its own. The inbox is read-only through an adapter with no method
that deletes or modifies a message. The single write path requires a named
approver at three layers. No user-supplied text reaches a shell, a file path or
a query, and message bodies are never persisted.

## Responsible AI

The model reads and drafts; it never sends. Every classification carries the
reasoning that produced it, so it can be disagreed with rather than deferred
to. Urgency is explicitly defined as *when a person must act* rather than how
strongly the sender wrote, because a model that rewards shouting will bury the
quiet message about stranded passengers.

The drafting prompt forbids inventing fare differences, rates, commission
figures and refund timelines — the numbers a partner would act on — and
requires saying what will be confirmed instead. Task extraction is told to
return nothing when nothing was asked, rather than inventing a task to look
useful.

The accuracy figure is presented with its own caveat rather than as a general
claim about the model.

## Future Improvements

- Bulk triage of a whole category in one call, once a paid tier makes the
  request budget realistic
- Real delivery behind a Gmail or Microsoft 365 adapter, with the same approval
  gate in front of it
- Reply templates for the recurring categories, so drafting starts from a
  house style rather than from nothing
