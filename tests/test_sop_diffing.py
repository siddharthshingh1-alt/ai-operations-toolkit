"""Version diffing tests (CLAUDE.md Section 9).

The spec asks for real diffing "not just a flat list of snapshots", so these
check that a change is located to the right section and the right lines.
"""

from __future__ import annotations

import pytest
from aiops_sop.diffing import ChangeKind, diff_sop_content
from aiops_sop.schema import EscalationRule, ProcedureStep, SopContent

from aiops_utils import ValidationError


def _sop(**overrides: object) -> SopContent:
    base = {
        "title": "Flight Delay Handling",
        "purpose": "Notify agents when a flight is delayed.",
        "scope": "All flights delayed over 3 hours.",
        "prerequisites": ["Access to the booking system"],
        "roles": ["Operations Associate"],
        "procedure": [
            ProcedureStep(number=1, instruction="Confirm the delay with the airline."),
            ProcedureStep(number=2, instruction="Find affected bookings."),
        ],
        "checklist": ["Agent notified"],
    }
    return SopContent(**{**base, **overrides})


def test_identical_versions_report_no_changes() -> None:
    diff = diff_sop_content(_sop(), _sop(), from_version=1, to_version=2)
    assert not diff.has_changes
    assert diff.summary == "No changes between these versions."


def test_edited_step_is_located_to_the_procedure_section() -> None:
    changed = _sop(
        procedure=[
            ProcedureStep(number=1, instruction="Confirm the delay with the airline trade desk."),
            ProcedureStep(number=2, instruction="Find affected bookings."),
        ]
    )
    diff = diff_sop_content(_sop(), changed, from_version=1, to_version=2)

    assert [f.field for f in diff.changed_fields] == ["procedure"]
    procedure = next(f for f in diff.fields if f.field == "procedure")
    assert procedure.added_count == 1
    assert procedure.removed_count == 1


def test_appended_checklist_item_is_an_addition_only() -> None:
    diff = diff_sop_content(
        _sop(),
        _sop(checklist=["Agent notified", "Rebooking offered"]),
        from_version=1,
        to_version=2,
    )
    checklist = next(f for f in diff.fields if f.field == "checklist")
    assert checklist.added_count == 1
    assert checklist.removed_count == 0


def test_newly_populated_section_is_marked_added() -> None:
    diff = diff_sop_content(
        _sop(),
        _sop(
            escalation_rules=[
                EscalationRule(trigger="No airline reply", escalate_to="Duty Manager")
            ]
        ),
        from_version=1,
        to_version=2,
    )
    escalation = next(f for f in diff.fields if f.field == "escalation_rules")
    assert escalation.kind is ChangeKind.ADDED


def test_emptied_section_is_marked_removed() -> None:
    diff = diff_sop_content(_sop(), _sop(prerequisites=[]), from_version=1, to_version=2)
    prerequisites = next(f for f in diff.fields if f.field == "prerequisites")
    assert prerequisites.kind is ChangeKind.REMOVED


def test_unchanged_lines_are_kept_for_context() -> None:
    """A diff with no surrounding context is hard to read."""
    changed = _sop(
        procedure=[
            ProcedureStep(number=1, instruction="Confirm the delay with the airline."),
            ProcedureStep(number=2, instruction="Find every affected booking."),
        ]
    )
    procedure = next(f for f in diff_sop_content(_sop(), changed).fields if f.field == "procedure")
    assert any(line.kind is ChangeKind.UNCHANGED for line in procedure.lines)


def test_summary_counts_sections_and_lines() -> None:
    changed = _sop(
        checklist=["Agent notified", "Rebooking offered"],
        roles=["Operations Associate", "Duty Manager"],
    )
    diff = diff_sop_content(_sop(), changed, from_version=1, to_version=2)
    assert "2 sections changed" in diff.summary
    assert "+2" in diff.summary


def test_structured_item_change_shows_as_a_line_change() -> None:
    """Changing one attribute of an escalation rule must be visible."""
    old = _sop(escalation_rules=[EscalationRule(trigger="No reply", escalate_to="Duty Manager")])
    new = _sop(
        escalation_rules=[EscalationRule(trigger="No reply", escalate_to="Head of Operations")]
    )
    escalation = next(f for f in diff_sop_content(old, new).fields if f.field == "escalation_rules")
    assert escalation.kind is ChangeKind.MODIFIED
    assert any("Head of Operations" in line.text for line in escalation.lines)


def test_procedure_steps_are_renumbered_on_load() -> None:
    """A model that skips or repeats numbers must not corrupt the sequence."""
    content = SopContent(
        title="T",
        purpose="P",
        scope="S",
        procedure=[
            ProcedureStep(number=5, instruction="First"),
            ProcedureStep(number=5, instruction="Second"),
            ProcedureStep(number=9, instruction="Third"),
        ],
    )
    assert [s.number for s in content.procedure] == [1, 2, 3]


def test_comparing_a_version_with_itself_is_rejected() -> None:
    from aiops_sop import service

    with pytest.raises(ValidationError, match="two different versions"):
        service.diff_versions(None, "sop_x", 2, 2)  # type: ignore[arg-type]
