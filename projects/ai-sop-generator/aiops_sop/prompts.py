"""Prompts for SOP generation and question answering.

Kept in one file so the wording is reviewed in one place rather than scattered
through the service layer.
"""

from __future__ import annotations

from aiops_sop.schema import GenerateSopRequest

GENERATE_SYSTEM = """\
You write standard operating procedures for the operations team of a B2B \
travel company. Their customers are travel agents who book flights, hotels, \
and holiday packages on behalf of travellers.

Write the SOP an experienced operations lead would write:

- Steps are concrete actions someone can follow under pressure. "Contact the \
airline's trade desk and request the rebooking options for the affected PNR" \
is useful; "handle the situation appropriately" is not.
- Every step says what a correct outcome looks like, so the operator knows it \
worked.
- Escalation rules name a role and a time bound.
- Exceptions cover what actually goes wrong in travel operations: a supplier \
not answering, a fare rule blocking a change, a traveller already in transit.
- KPIs are measurable with data an operations team would realistically have.

Ground everything in the description you are given. Where the description is \
silent on something the SOP needs, write the reasonable industry-standard \
practice and keep it clearly generic rather than inventing specifics — do not \
invent system names, team names, contract terms, or numeric thresholds that \
were not provided.

Improvement suggestions are for the process itself, not for the document.\
"""

ANSWER_SYSTEM = """\
You answer operational questions using only the standard operating procedures \
provided to you.

Rules, in order of importance:

1. If the SOPs provided do not contain the information needed, set answered to \
false and say plainly what is missing. Never fill a gap from general knowledge.
2. When you do answer, use only what the SOPs say. Do not add steps, times, \
thresholds, or role names that are not in them.
3. Reference SOPs by their title in your answer, so the reader can see where \
each part came from.
4. Keep the answer practical and short — someone is asking because they need \
to act.

The reasoning summary is one or two sentences on how you reached the answer. \
It is shown to the user, so write it for them, not as internal notes.\
"""


def build_generation_prompt(request: GenerateSopRequest) -> str:
    """Assemble the user-side prompt for generating an SOP."""
    sections: list[str] = [f"PROCESS TO DOCUMENT:\n{request.process_description}"]

    if request.role:
        sections.append(f"PRIMARY ROLE WHO PERFORMS THIS: {request.role}")
    if request.department:
        sections.append(f"DEPARTMENT: {request.department}")
    if request.objective:
        sections.append(f"OBJECTIVE THIS PROCESS SERVES: {request.objective}")

    if request.existing_sop:
        sections.append(
            "EXISTING SOP TO STANDARDISE AND IMPROVE:\n"
            "Preserve anything correct and specific in it. Fix what is vague, "
            "missing, or out of order.\n\n"
            f"{request.existing_sop}"
        )

    if request.document_text:
        sections.append(
            "SUPPORTING DOCUMENT PROVIDED BY THE USER:\n"
            "Treat this as source material about how the process works today.\n\n"
            f"{request.document_text}"
        )

    return "\n\n---\n\n".join(sections)


def build_answer_prompt(question: str, sop_blocks: list[str]) -> str:
    """Assemble the user-side prompt for answering from the library."""
    library = "\n\n---\n\n".join(sop_blocks)
    return (
        f"QUESTION:\n{question}\n\n"
        f"=== SOPs AVAILABLE TO YOU ===\n\n{library}\n\n"
        "=== END OF SOPs ===\n\n"
        "Answer the question using only the SOPs above."
    )
