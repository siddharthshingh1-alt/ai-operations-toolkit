# AI Workflow Builder

Project 4 of the AI Operations Toolkit. The visual editor for the shared
workflow engine (CLAUDE.md Sections 7 and 12).

## Problem

Operations processes are sequences: something happens, someone judges it,
someone else writes to a partner, a third person approves it. Those sequences
live in people's heads and in Slack threads, and when a new person joins they
learn them by getting them wrong.

Writing one down as a diagram helps. Writing one down as something that
actually runs helps more.

## Which JD requirement this proves

> *"Build AI-assisted **workflows** … and **automations**."*
> *"Document and standardize scalable operational processes."*

## Who Uses It

An operations associate who wants to encode a repeatable process without
waiting for an engineer.

## Business Impact

| | |
|---|---|
| Manual process | ~3 hrs to specify a process, then engineering time to implement it |
| With this | ~20 min to build and run it directly |
| Estimated saving | Removes the handoff entirely for simple flows |

*Simulated demo estimate. Not a measured result (Section 19).*

## Features

- Canvas rendering of any workflow, laid out from its own connections
- Add steps from a palette; connect them from the step panel
- Configure each step: categories to classify into, an instruction to draft
  from, a field to branch on
- Validation before running: missing start, dangling links, loops, unconfigured
  steps, **and the approval guard below**
- Run it, watch each step's status, duration and AI cost
- Pause at Human approval and approve or reject, by name
- Every run stored as an execution log

## Architecture

**This project contains no engine, and a test asserts that.** Section 7 builds
the engine once in `services/workflow-engine`; Project 4 stores definitions,
renders them, and calls the engine's own `run()` and `resume()`. The test
`test_this_project_contains_no_engine` scans this package's source for the
signs of a second executor — a node-walking loop, a step limit, a status
machine — and fails if one appears.

The definition is stored as one JSON document rather than shredded into node
and edge tables, because `Workflow` is already a validated model owned by the
engine. Reading a row and calling `Workflow.model_validate` returns exactly
what the engine expects.

### The guard this project adds

`HIGH_RISK_NODES` — Email, Webhook, Database — has existed since the engine was
written, described as the set of nodes that "must never run unattended", and
**consulted by nothing**. It was a comment wearing the clothes of a rule.

`WorkflowEngine.run()` now refuses any definition where one of those nodes can
be reached without first passing a `HUMAN_APPROVAL` node, naming the offending
step. A node counts as guarded only if *every* route to it passes an approval —
one unguarded branch is enough to refuse, because the dangerous shape is a
condition where one side is checked and the other is not.

There is deliberately **no argument that turns this off**, and a test asserts
that too: an escape hatch would return the constant to what it was.

### The one-engine proof

The Travel Operations incident workflow — the flagship's real, running
definition — is shipped here as a read-only template. It renders because it is
the same type, not a copy. A test compares it node-for-node against
`incident_workflow()` in Project 6, so the two cannot drift apart silently.

## AI Usage

Four node types call a model, each driven by its own config:

| Node | Does | Constraint |
|---|---|---|
| AI classification | picks one category | must choose from the configured list, never invent one |
| AI extraction | pulls named fields | returns an empty string where a field is absent, never a guess |
| AI summarisation | condenses the input | adds nothing not in the text |
| AI drafting | writes a message | never invents a booking reference, refund, policy or time |

Each node costs one request, and the Run button says how many before you press
it. Nothing runs on page load.

## Tech Stack

Python, FastAPI, SQLAlchemy, PostgreSQL · **React Flow (`@xyflow/react`)**,
Next.js, TypeScript, Tailwind

## Setup

Nothing project-specific. Two tables, `workflows` and `workflow_executions`.

## Environment Variables

None of its own.

## How to Run

```bash
npm run dev
```

Then open **http://localhost:3000/workflows**.

## Live Demo

**https://ai-operations-toolkit-web.vercel.app/workflows**

## Example

Build: *Trigger → AI drafting → Email*. Press Run. It refuses:

> *"'Send it' performs an action that reaches the outside world, and it can be
> reached without a human approving it first. Add a Human approval step before
> it."*

Insert a Human approval step between the two and it runs — pausing at the
approval, with the Email step absent from the log because it has not executed.

## Screenshots

Not committed — see the live demo.

## Limitations

- **Steps are laid out automatically and cannot be dragged.** The engine's node
  model has no coordinates, and inventing somewhere to store them would mean
  this project holding state the engine does not know about — a canvas that
  could disagree with the workflow it draws. Editing happens in the side panel
  instead. A click-to-connect editor that is always correct beats a
  drag-and-drop one that is usually correct.
- **One outgoing connection per step**, two for a Condition. That is the
  engine's model, not a simplification chosen here.
- **Webhook and Database steps appear in the palette but cannot run**, with the
  reason shown. A webhook would call a real address typed into a public form; a
  database node would write to the shared database this demo runs on. Neither
  is faked.
- **No undo, no multi-select, no copy-paste, no workflow versioning.** Normal
  editor features, none of them what this portfolio is being judged on.
- **A run is synchronous.** A long workflow holds the request open; background
  execution is a future improvement.

## Security

Uploads and webhooks do not exist here. The only outward-facing step is Email,
which goes through the mock adapter, requires a named approver, and records
without transmitting. Approval is required by the engine, the API schema and
the adapter independently.

## Responsible AI

Every AI step's output is written into the run log with the model and cost, so
a workflow's behaviour can be audited after the fact. No AI step can trigger an
outward action on its own — the guard makes that a property of the graph rather
than a matter of who built it.

## Future Improvements

- Draggable layout, once there is somewhere honest to store positions
- Background execution for long runs
- Workflow versioning and diffing, reusing Project 1's diff view
- Triggering a workflow from an incident in Project 6 rather than by hand
