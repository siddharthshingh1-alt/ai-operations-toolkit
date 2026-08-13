# Business cases

One document per project, following the Section 5 "Business-first" structure:

```
Problem
Users
Current manual process
Bottleneck
AI opportunity
Workflow
Expected business impact
```

## Status

Empty. Each business case is written when its project is built, alongside the
implementation — not before.

That is deliberate rather than lazy. A business case written in advance is a
guess; written next to a working implementation it can state what the thing
actually does. The intent for each project is summarised in its
`projects/<slug>/README.md`, which is enough to build against.

## The impact rule

Every business case must label its numbers as a **simulated demo estimate**
(CLAUDE.md Section 19):

```
Manual process:     12 hours/week
Automated process:   2 hours/week
Estimated saving:   10 hours/week ≈ 520 hours/year

Simulated demo estimate against synthetic data. Not a measured result and not
a claim of real-world deployment.
```

No document here may claim real users, real deployment, or a measured
real-world saving, because none exists.
