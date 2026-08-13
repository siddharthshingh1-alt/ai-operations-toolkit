"""The canonical example inputs used for Demo Mode.

Demo Mode replays a recording keyed on the exact prompt, so a reviewer with no
API key can only see AI output for an input that was actually recorded. These
are those inputs — the recorder writes recordings for them, and the UI offers
them as one-click presets so the two always line up.

Keep this list in step with `apps/web/src/lib/sop-examples.ts`.
"""

from __future__ import annotations

from aiops_sop.schema import GenerateSopRequest

EXAMPLES: list[GenerateSopRequest] = [
    GenerateSopRequest(
        process_description=(
            "When a flight is delayed by more than three hours we need to work out "
            "which of our travel agents' bookings are affected, check whether any "
            "of those travellers have onward connections, and contact each agent "
            "with the rebooking or refund options. At the moment different people "
            "do this differently, there is no fixed order, and travellers "
            "sometimes hear from the airline before their agent hears from us."
        ),
        role="Operations Associate",
        department="Flight Operations",
        objective="Contact every affected travel agent within 30 minutes of a confirmed delay",
    ),
    GenerateSopRequest(
        process_description=(
            "A hotel tells us they have overbooked and cannot honour a room we have "
            "already confirmed to a travel agent. We have to find an equivalent or "
            "better property nearby, agree who covers any rate difference, get the "
            "hotel to confirm in writing, and tell the agent before the traveller "
            "arrives at the original hotel. This currently depends on whoever picks "
            "up the email and how well they know the local market."
        ),
        role="Operations Associate",
        department="Hotel Operations",
        objective="Rehouse the traveller and inform the agent before check-in",
    ),
    GenerateSopRequest(
        process_description=(
            "New travel agencies sign up as partners and need to be onboarded: "
            "verify their business registration, set their credit limit and payment "
            "terms, create their portal logins, run a walkthrough of how to book, "
            "and hand them to an account owner. Right now this is tracked in a "
            "spreadsheet, steps get skipped, and agents sometimes get portal access "
            "before their credit terms are agreed."
        ),
        role="Partner Operations Associate",
        department="Agent Partnerships",
        objective="Onboard a new agency in under five working days with nothing skipped",
    ),
]
