"""Prompts for the Project Tracker.

Each prompt hands the model a block of computed facts and asks it to judge
them. None of them ask it to count anything, because by the time it is called
the counting is done — see `facts.py` for why.

The system prompts say so explicitly ("the figures below are computed ... treat
them as given"). That is not politeness: a model told it may recompute will
sometimes disagree with the numbers printed next to its own answer on the same
page, and a reviewer who spots that stops believing either.
"""

from __future__ import annotations

from aiops_tracker.schema import ProjectFacts

ASSESS_SYSTEM = """You are an operations analyst assessing the health of a project.

The figures you are given are computed from the tracker's own data. Treat them
as given: do not recount, re-derive, or dispute them.

Assign one status:
  GREEN  — on track; no intervention needed.
  YELLOW — at risk; will slip without attention, but is recoverable.
  RED    — will miss its target without intervention now.

You must explain the status. State the specific figures that drove it. A status
without reasoning is not an acceptable answer."""

NEXT_ACTIONS_SYSTEM = """You are an operations lead deciding what a team should do next.

Recommend between one and five concrete actions, most urgent first. Each action
must name what to do and why it is the most useful next step. Where an action
concerns a specific task, give that task's id exactly as supplied — do not
invent ids. Prefer unblocking blocked work and recovering overdue work over
starting anything new."""

SUMMARY_SYSTEM = """You are writing a short status paragraph for a team lead to read aloud.

Three to five sentences of plain prose. No bullet points, no headings, no
preamble such as "Here is the summary". Say where the project stands, what is
at risk, and what happens next. Use the figures supplied and do not invent
any."""

REPORT_SYSTEM = """You are writing a weekly operations status report across several projects.

Work only from the figures supplied. Be specific — name projects and tasks
rather than describing them in the abstract. Where nothing of note happened in
a category, return an empty list rather than padding it with filler.

Do not congratulate anyone, and do not soften a slipping project into a
positive. The reader needs to know where to spend Monday."""


def _facts_block(facts: ProjectFacts) -> str:
    """Render computed facts as the evidence block a prompt reasons over."""
    lines = [
        f"Tasks: {facts.task_count} total — {facts.done_count} done, "
        f"{facts.in_progress_count} in progress, {facts.todo_count} to do, "
        f"{facts.blocked_count} blocked",
        f"Completion: {facts.completion_percent}%",
        f"Overdue tasks: {facts.overdue_count}",
    ]
    if facts.overdue_task_titles:
        lines.append("  overdue: " + "; ".join(facts.overdue_task_titles))
    if facts.blocked_task_titles:
        lines.append("  blocked: " + "; ".join(facts.blocked_task_titles))
    if facts.dependency_blocked_titles:
        lines.append(
            "  waiting on an unfinished dependency: " + "; ".join(facts.dependency_blocked_titles)
        )
    if facts.unassigned_count:
        lines.append(f"Tasks with no owner: {facts.unassigned_count}")
    if facts.target_date is not None:
        when = (
            f"{facts.days_to_target} days away"
            if facts.days_to_target is not None and facts.days_to_target >= 0
            else f"{abs(facts.days_to_target or 0)} days PAST"
        )
        lines.append(f"Target date: {facts.target_date.isoformat()} ({when})")
    else:
        lines.append("Target date: none set")
    if facts.risks:
        lines.append("Recorded risks: " + "; ".join(facts.risks))
    return "\n".join(lines)


def assessment_prompt(name: str, description: str, facts: ProjectFacts) -> str:
    return (
        f"Project: {name}\n"
        f"Description: {description or '(none given)'}\n\n"
        f"Computed figures:\n{_facts_block(facts)}\n\n"
        "Assign GREEN, YELLOW or RED, and explain the assignment against these figures."
    )


def next_actions_prompt(
    name: str, facts: ProjectFacts, tasks: list[tuple[str, str, str, str]]
) -> str:
    """`tasks` is (id, title, status, owner) for the open work."""
    if tasks:
        listing = "\n".join(
            f"  {task_id} | {title} | {status} | owner: {owner or 'unassigned'}"
            for task_id, title, status, owner in tasks
        )
    else:
        listing = "  (no open tasks)"
    return (
        f"Project: {name}\n\n"
        f"Computed figures:\n{_facts_block(facts)}\n\n"
        f"Open tasks (id | title | status | owner):\n{listing}\n\n"
        "Recommend what to do next."
    )


def summary_prompt(name: str, facts: ProjectFacts, health: str | None) -> str:
    return (
        f"Project: {name}\n"
        f"Current health status: {health or 'not yet assessed'}\n\n"
        f"Computed figures:\n{_facts_block(facts)}\n\n"
        "Write the status paragraph."
    )


def report_prompt(blocks: list[str], week_ending: str) -> str:
    joined = "\n\n".join(blocks) if blocks else "(no active projects)"
    return (
        f"Week ending {week_ending}.\n\n"
        f"Projects and their computed figures:\n\n{joined}\n\n"
        "Write the weekly status report."
    )


def project_block(name: str, health: str | None, facts: ProjectFacts) -> str:
    """One project's section inside the weekly report prompt."""
    return f"### {name}\nHealth: {health or 'not assessed'}\n{_facts_block(facts)}"
