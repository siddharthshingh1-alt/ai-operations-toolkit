"""Starting workflows, so the canvas is never a blank page.

The first of these is the point of the project. It is the *actual* workflow
Project 6 runs in production — imported unchanged, because Project 4 and
Project 6 are two clients of one engine and therefore speak the same type. It
is stored read-only: the builder should be able to prove it can render a real
workflow without offering to break the flagship.

The second is the example CLAUDE.md Section 12 gives, and it is editable.
"""

from __future__ import annotations

from aiops_travelops import incident_workflow

from aiops_workflow import NodeType, Workflow, WorkflowNode


def travel_incident_template() -> Workflow:
    """Project 6's live incident workflow, unmodified."""
    workflow = incident_workflow()
    workflow.description = (
        "The workflow Project 6 runs for real. Shown here to demonstrate that "
        "the builder and the flagship are two clients of one engine — this is "
        "not a copy, it is the same definition. Read-only."
    )
    return workflow


def booking_complaint_template() -> Workflow:
    """CLAUDE.md Section 12's example flow.

    Booking complaint -> classify -> priority -> draft response -> approval ->
    send -> close.
    """
    return Workflow(
        id="wf_booking_complaint",
        name="Booking complaint triage",
        description=(
            "Classify an agent's complaint, draft a reply, and hold it for "
            "approval before anything is recorded as sent."
        ),
        start_node_id="c_trigger",
        nodes=[
            WorkflowNode(
                id="c_trigger",
                type=NodeType.TRIGGER,
                label="Complaint received",
                config={"event": "complaint_received"},
                next_id="c_classify",
            ),
            WorkflowNode(
                id="c_classify",
                type=NodeType.AI_CLASSIFICATION,
                label="Classify the complaint",
                config={
                    "input_field": "input",
                    "categories": [
                        "Flight delay",
                        "Hotel complaint",
                        "Refund request",
                        "Booking change",
                        "Payment issue",
                        "Other",
                    ],
                },
                next_id="c_priority",
            ),
            WorkflowNode(
                id="c_priority",
                type=NodeType.CONDITION,
                label="Is it urgent?",
                # Branches on what the classifier wrote into the context.
                config={
                    "field": "category",
                    "operator": "in",
                    "value": ["Flight delay", "Payment issue"],
                },
                next_id="c_draft",
                next_id_if_false="c_draft",
            ),
            WorkflowNode(
                id="c_draft",
                type=NodeType.AI_GENERATION,
                label="Draft a reply to the agency",
                config={
                    "input_field": "input",
                    "instruction": (
                        "Draft a short, professional reply to the travel agency "
                        "acknowledging their complaint and stating what happens next."
                    ),
                },
                next_id="c_approval",
            ),
            WorkflowNode(
                id="c_approval",
                type=NodeType.HUMAN_APPROVAL,
                label="Operations approval",
                next_id="c_send",
            ),
            WorkflowNode(
                id="c_send",
                type=NodeType.EMAIL,
                label="Record the reply",
                config={"subject": "Re: your booking complaint"},
                next_id=None,
            ),
        ],
    )


#: (workflow, read_only)
TEMPLATES: list[tuple[Workflow, bool]] = []


def all_templates() -> list[tuple[Workflow, bool]]:
    """Built fresh each call so a caller cannot mutate the shared definition."""
    return [
        (travel_incident_template(), True),
        (booking_complaint_template(), False),
    ]
