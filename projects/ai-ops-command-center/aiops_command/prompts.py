"""The single prompt this project uses.

It hands the model a ranked list of signals that four other projects produced
and asks for a paragraph. It does not ask the model to rank them — that is
computed in `signals.rank` — and it does not ask it to count anything, because
by the time it is called every count is already made.

The system prompt says so explicitly. A model told it may re-derive figures
will sometimes contradict the numbers printed beside its own paragraph, and a
reader who catches that stops believing the rest of the page.
"""

from __future__ import annotations

from aiops_command.signals import SOURCE_LABELS, Signal, SourceStatus

BRIEF_SYSTEM = """You are an operations lead writing the morning brief for your team.

You are given signals collected from four separate operational systems. They are
already gathered, already counted, and already ordered by urgency. Treat every
figure as given: do not recount, re-derive or dispute anything.

Write what today needs. Lead with what is most likely to hurt if ignored. Be
specific — name the project, workflow or incident rather than describing it in
the abstract.

Where you recommend an action, give the id of the signal it addresses, exactly
as supplied. Never invent an id.

Do not greet anyone, do not congratulate anyone, and do not soften a problem.
If a source was unavailable, say plainly that the picture is incomplete rather
than implying it is whole."""


def brief_prompt(signals: list[Signal], sources: list[SourceStatus], *, today: str) -> str:
    """Render the collected signals as the evidence block for the brief."""
    if signals:
        lines = []
        for signal in signals:
            label = SOURCE_LABELS.get(signal.source, signal.source)
            lines.append(
                f"  [{signal.id}] ({signal.severity}, from {label}) "
                f"{signal.title} — {signal.detail}"
            )
        signal_block = "\n".join(lines)
    else:
        signal_block = "  (no signals — every source reported nothing needing attention)"

    available = [s for s in sources if s.available]
    missing = [s for s in sources if not s.available]

    source_lines = [
        f"  {SOURCE_LABELS.get(s.source, s.source)}: answered — {s.detail}" for s in available
    ]
    source_lines += [
        f"  {SOURCE_LABELS.get(s.source, s.source)}: UNAVAILABLE — {s.detail}" for s in missing
    ]

    warning = ""
    if missing:
        names = ", ".join(SOURCE_LABELS.get(s.source, s.source) for s in missing)
        warning = (
            f"\n\nIMPORTANT: {names} could not be reached, so this picture is "
            "incomplete. Say so in the summary."
        )

    return (
        f"Date: {today}\n\n"
        f"Signals, most urgent first:\n{signal_block}\n\n"
        f"Sources:\n" + "\n".join(source_lines) + warning + "\n\n"
        "Write the morning brief."
    )
