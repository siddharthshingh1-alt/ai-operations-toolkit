# AI Travel Operations

Project 6 of the AI Operations Toolkit, and the flagship. Includes the
folded-in agent/partner relationship module (CLAUDE.md Sections 14 and 18).

## Problem

A flight is delayed. Somewhere in the booking system are the agencies whose
clients are on it, and none of them know yet.

Finding them is a spreadsheet job. Deciding how bad it is depends on who is
asked. Writing to each agency is twenty minutes of careful typing, repeated per
agency, under time pressure, by someone who is also handling the next incident.
The work is not hard — it is repetitive, and it happens exactly when there is
no time for it.

## Which JD requirement this proves

Identifying operational bottlenecks and solving them with AI; building
AI-assisted workflows and automations; collaborating cross-functionally to
drive execution.

And more directly than any other project here: it is a working simulation of
**the target domain's actual business** — B2B travel, agencies as customers,
on-ground incident handling.

## Who Uses It

An operations associate handling live disruption, and the team lead who
approves what goes out.

## Business Impact

| | |
|---|---|
| Manual process | ~45 min per incident: find affected bookings, judge it, write to each agency |
| With this | ~8 min: read the lookup, read the assessment, approve or reject each draft |
| At ~12 incidents/week | ~7.5 hours/week ≈ 390 hours/year |

*Simulated demo estimate against the synthetic datasets in this repository. Not
a measured result and not a claim of real-world deployment (Section 19).*

## Features

- Incident console, seeded from delays already present in the booking data
- Report an incident — the affected-booking lookup runs immediately, no AI
- AI severity assessment with stated reasoning, traveller impact, recommended action
- AI-drafted communication per affected agency, in B2B register
- **Approve / reject per message**, with the approver's name and time recorded
- Full execution log per incident: every step, its duration, and where a human intervened
- Agency partner view: volume, value, delays, open tickets, what is owed to whom

## Architecture

```
Incident reported
  └─ find affected bookings         BookingProvider — deterministic, no AI
       └─ AI: assess severity       structured output, reasoning required
            └─ AI: draft messages   one per affected agency
                 └─ ⏸ HUMAN APPROVAL     the workflow engine stops here
                      └─ record            only reachable via resume()
```

Built on the shared workflow engine (Section 7) rather than as procedural code,
because that is what makes the pause structural rather than conventional.

### Human-in-the-loop, enforced twice

This is the part worth reading the code for. Two independent mechanisms, either
of which alone would be sufficient:

1. **The graph stops.** `WorkflowEngine` halts at the `HUMAN_APPROVAL` node and
   returns. Nothing downstream executes. The only way past it is
   `engine.resume()`, which requires an approver. `approval_is_reachable_only_after()`
   asserts the recording node's position, and a test calls it — rewire the
   graph to bypass approval and the suite fails.
2. **The send refuses.** `EmailProvider.send_message()` takes `approved_by` as a
   required argument and rejects an empty one. An unapproved send cannot be
   *expressed*, let alone executed.

A third, weaker guard sits in the recording handler itself, which checks the
approval context rather than trusting its position in the graph.

## AI Usage

Two structured calls per incident, both on demand:

| Call | Output | Constraint |
|---|---|---|
| Assess | severity, reasoning, traveller impact, recommended action | reasoning is a required field — a bare label is an invalid response |
| Draft | one message per affected agency | must use the agency's own `agent_id`; drafts for unaffected agencies are dropped |

**The model never counts anything.** Booking counts, values, agency names and
departure times are computed before it is called and passed in as stated facts.
It cannot invent a booking reference because it is never asked to produce one.

Both calls happen when someone presses *Assess and draft* — never on page load.
On a free tier of roughly twenty requests a day, a console that assessed every
incident automatically would spend the budget before anyone read a word.

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL · the shared workflow engine and adapter
layer · Next.js, TypeScript, Tailwind

## Setup

Nothing project-specific; installed via `requirements.txt`. Two tables,
`travel_incidents` and `travel_communications`, are created by `create_all()`.

## Environment Variables

None of its own.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/travel-ops**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/travel-ops**

## Example

An incident seeded from the booking data — two bookings on BOM-GOI, ₹98,615:

> **Severity: medium** — *"This incident is classified as medium severity
> because it impacts 2 bookings with a total value of INR 98,615. The soonest
> departure is 34.0 hours away, which provides a comfortable window for
> intervention before the travellers reach the airport."*

Every figure in that sentence was computed before the model saw it. The drafts
that follow address Harbour Line Travel and Kaveri Tours & Travel by name,
quote booking references `BK-00845` and `BK-00438`, and sit as **drafts** until
someone approves them. The execution log for the approved incident ends:

```
Operations approval           succeeded   {approved: true, approved_by: "Anita Rao"}
Record approved communication succeeded   {recorded: 2, transmitted: 0}
```

## Screenshots

Not committed — see the live demo.

## Limitations

- **Nothing is ever sent.** The email adapter records an approved message and
  transmits nothing. Real delivery is a documented future improvement
  (Section 3c), not a missing piece pretending to be finished.
- **No airline, GDS or payment system is connected, and none ever will be.**
  `BookingProvider` is read-only by construction — it has no method that creates
  or charges anything, and a test asserts none has appeared.
- **Drafts are capped at six agencies per incident.** A wider incident is
  assessed in full, but only the six largest exposures get drafts.
- **Severity is a model's opinion.** It is shown as one, with its reasoning
  attached, next to the numbers it was given so a reader can disagree.
- **Approval is per message, recording is per incident.** A message is
  `approved` the moment you decide; the recording step runs once every draft on
  that incident has been decided, so `recorded_message_id` fills in then. The
  status says `approved`, not `recorded`, precisely so it is not claiming
  something that has not happened yet.
- **All data is synthetic.** No real agency, traveller or booking exists here.

## Security

No secrets of its own. Approval requires a named approver at three layers —
the UI, the API schema, and the adapter — and an anonymous decision is rejected
at each. Nothing user-supplied reaches a booking system, because there is no
path to one.

## Responsible AI

The model judges and drafts; it never acts. High-risk actions — anything a
partner would see — require a human decision that is recorded with a name and a
timestamp. Severity always ships with reasoning, so the judgement can be
argued with rather than deferred to. Where the model addressed an agency not
actually affected, the draft is dropped rather than shown, because a confident
message to the wrong partner is worse than no message at all.

## Future Improvements

- Real email delivery behind the existing adapter seam, once there is a real inbox
- Bulk approve for low-severity incidents, with the same audit trail
- Feed incidents into the Ops Command Center (Project 9) rather than duplicating them
- Agency-specific tone learned from prior approved messages
