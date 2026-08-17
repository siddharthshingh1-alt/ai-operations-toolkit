"""Project 5 — AI Project Tracker (CLAUDE.md Section 13).

Projects, tasks, owners, deadlines, dependencies, risks and blockers, with an
AI health assessment that has to explain itself.

The division of labour is the point of this project, and it is the same one
the Dashboard and Travel Operations already use:

    computed in code        asked of the model
    ----------------        ------------------
    which tasks are overdue whether that adds up to GREEN, YELLOW or RED
    which are blocked       why, in terms of those figures
    what waits on what      what to do next
    completion percentage   how to say it in a standup
    days to target          how it reads in a weekly report

`facts.py` produces the left-hand column and nothing in this package asks a
model to reproduce it. `HealthAssessment` makes the right-hand column
accountable: `reasoning` and `contributing_factors` are required fields, so a
bare "RED" is an invalid response rather than an unhelpful one.

All data is synthetic.
"""

from aiops_tracker.facts import (
    MAX_DEPENDENCY_DEPTH,
    blocking_task,
    days_overdue,
    is_overdue,
    project_facts,
    task_views,
)
from aiops_tracker.models import (
    Health,
    Priority,
    ProjectState,
    TaskStatus,
    TrackedProject,
    TrackedTask,
)
from aiops_tracker.router import router
from aiops_tracker.schema import (
    HealthAssessment,
    NextActions,
    ProjectDetail,
    ProjectFacts,
    ProjectSummary,
    SuggestedAction,
    TaskView,
    WeeklyReportContent,
)

__all__ = [
    "MAX_DEPENDENCY_DEPTH",
    "Health",
    "HealthAssessment",
    "NextActions",
    "Priority",
    "ProjectDetail",
    "ProjectFacts",
    "ProjectState",
    "ProjectSummary",
    "SuggestedAction",
    "TaskStatus",
    "TaskView",
    "TrackedProject",
    "TrackedTask",
    "WeeklyReportContent",
    "blocking_task",
    "days_overdue",
    "is_overdue",
    "project_facts",
    "router",
    "task_views",
]
