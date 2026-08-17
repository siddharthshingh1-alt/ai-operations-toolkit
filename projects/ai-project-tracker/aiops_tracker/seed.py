"""Starting projects, so a first visitor does not meet an empty tracker.

Three projects, chosen to exercise the three health outcomes without the seed
ever *asserting* a health — that judgement is the model's, and seeding a label
would be exactly the fake functionality Section 2 bans. What the seed does is
create data whose computed facts genuinely differ: one project clean, one with
overdue and blocked work, one with a passed target date.

Dates are relative to the day the seed runs, so the demo never rots into a
tracker where everything is two years overdue.

All content is synthetic and set in the same travel-operations world as the
rest of the toolkit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from aiops_tracker.models import Priority, ProjectState, TaskStatus, TrackedProject, TrackedTask


def _mk_task(
    project_id: str,
    title: str,
    owner: str,
    status: TaskStatus,
    priority: Priority,
    due_offset_days: int | None,
    position: int,
    *,
    blocker_note: str | None = None,
) -> TrackedTask:
    today = datetime.now(UTC).date()
    return TrackedTask(
        project_id=project_id,
        title=title,
        owner=owner,
        due_date=(today + timedelta(days=due_offset_days)) if due_offset_days is not None else None,
        status=status.value,
        priority=priority.value,
        blocker_note=blocker_note if status == TaskStatus.BLOCKED else None,
        position=position,
    )


def seed_projects(db: Session) -> int:
    """Create the demo projects. Returns how many were created."""
    today = datetime.now(UTC).date()

    # ---- 1. running cleanly ------------------------------------------------
    onboarding = TrackedProject(
        name="Agency onboarding revamp",
        description=(
            "Cut the time to onboard a new travel agency from nine days to three "
            "by standardising document collection and credit checks."
        ),
        owner="Anita Rao",
        state=ProjectState.ACTIVE.value,
        target_date=today + timedelta(days=24),
        risks=["Finance sign-off on credit limits is a single point of dependency."],
    )
    db.add(onboarding)
    db.flush()
    db.add_all(
        [
            _mk_task(
                onboarding.id,
                "Map the current onboarding steps",
                "Anita Rao",
                TaskStatus.DONE,
                Priority.MEDIUM,
                -12,
                0,
            ),
            _mk_task(
                onboarding.id,
                "Draft the standard document checklist",
                "Deepak Nair",
                TaskStatus.DONE,
                Priority.HIGH,
                -5,
                1,
            ),
            _mk_task(
                onboarding.id,
                "Automate the credit-check request",
                "Sana Qureshi",
                TaskStatus.IN_PROGRESS,
                Priority.HIGH,
                6,
                2,
            ),
            _mk_task(
                onboarding.id,
                "Write the agency-facing SOP",
                "Anita Rao",
                TaskStatus.TODO,
                Priority.MEDIUM,
                15,
                3,
            ),
        ]
    )

    # ---- 2. overdue and blocked work ---------------------------------------
    refunds = TrackedProject(
        name="Refund turnaround programme",
        description=(
            "Bring refund turnaround under five working days. Blocked on the "
            "payments vendor's sandbox access."
        ),
        owner="Vikas Menon",
        state=ProjectState.ACTIVE.value,
        target_date=today + timedelta(days=9),
        risks=[
            "The payments vendor has missed two access deadlines already.",
            "Peak season starts in six weeks and will double refund volume.",
        ],
    )
    db.add(refunds)
    db.flush()
    integration = _mk_task(
        refunds.id,
        "Integrate the vendor refund API",
        "Sana Qureshi",
        TaskStatus.BLOCKED,
        Priority.URGENT,
        -8,
        1,
        blocker_note="Vendor has not issued sandbox credentials; chased three times.",
    )
    db.add_all(
        [
            _mk_task(
                refunds.id,
                "Measure the current refund turnaround",
                "Vikas Menon",
                TaskStatus.DONE,
                Priority.MEDIUM,
                -20,
                0,
            ),
            integration,
            _mk_task(
                refunds.id,
                "Draft agent-facing refund status emails",
                "Deepak Nair",
                TaskStatus.TODO,
                Priority.HIGH,
                -3,
                2,
            ),
        ]
    )
    db.flush()
    # This one cannot start until the integration lands — a real dependency,
    # so the tracker can show work that is stuck without being marked blocked.
    db.add(
        TrackedTask(
            project_id=refunds.id,
            title="Run the refund pilot with three agencies",
            owner="",
            due_date=today + timedelta(days=7),
            status=TaskStatus.TODO.value,
            priority=Priority.HIGH.value,
            depends_on_id=integration.id,
            position=3,
        )
    )

    # ---- 3. target already passed ------------------------------------------
    visibility = TrackedProject(
        name="Supplier delay visibility",
        description=(
            "Surface supplier delay patterns to the operations desk so repeat "
            "offenders are visible before a season, not after it."
        ),
        owner="Deepak Nair",
        state=ProjectState.ACTIVE.value,
        target_date=today - timedelta(days=4),
        risks=["No agreed data feed from two of the five suppliers."],
    )
    db.add(visibility)
    db.flush()
    db.add_all(
        [
            _mk_task(
                visibility.id,
                "Agree the delay metric with operations",
                "Deepak Nair",
                TaskStatus.DONE,
                Priority.MEDIUM,
                -30,
                0,
            ),
            _mk_task(
                visibility.id,
                "Build the supplier delay view",
                "Sana Qureshi",
                TaskStatus.IN_PROGRESS,
                Priority.HIGH,
                -6,
                1,
            ),
            _mk_task(
                visibility.id,
                "Agree a data feed with the last two suppliers",
                "",
                TaskStatus.BLOCKED,
                Priority.URGENT,
                -14,
                2,
                blocker_note="Waiting on commercial terms from procurement.",
            ),
        ]
    )

    return 3
