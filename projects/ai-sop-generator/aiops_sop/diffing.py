"""Comparing two versions of an SOP.

CLAUDE.md Section 9 asks specifically for "diffing between versions, not just a
flat list of snapshots". So this produces a structured, field-by-field diff:
which sections changed, and within each, which lines were added or removed.

The output is designed to be rendered directly — the UI does no diff logic of
its own.
"""

from __future__ import annotations

import difflib
from enum import StrEnum

from pydantic import BaseModel, Field

from aiops_sop.schema import SopContent


class ChangeKind(StrEnum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class LineChange(BaseModel):
    """One line's fate between two versions."""

    kind: ChangeKind
    text: str


class FieldDiff(BaseModel):
    """How one section of the SOP changed."""

    field: str
    label: str
    kind: ChangeKind
    lines: list[LineChange] = Field(default_factory=list)

    @property
    def added_count(self) -> int:
        return sum(1 for line in self.lines if line.kind is ChangeKind.ADDED)

    @property
    def removed_count(self) -> int:
        return sum(1 for line in self.lines if line.kind is ChangeKind.REMOVED)


class SopDiff(BaseModel):
    """The complete comparison between two versions."""

    from_version: int
    to_version: int
    fields: list[FieldDiff] = Field(default_factory=list)

    @property
    def changed_fields(self) -> list[FieldDiff]:
        return [f for f in self.fields if f.kind is not ChangeKind.UNCHANGED]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)

    @property
    def summary(self) -> str:
        """One line an operator can read, e.g. '3 sections changed, +12 / -4'."""
        changed = self.changed_fields
        if not changed:
            return "No changes between these versions."
        added = sum(f.added_count for f in changed)
        removed = sum(f.removed_count for f in changed)
        section = "section" if len(changed) == 1 else "sections"
        return f"{len(changed)} {section} changed, +{added} / -{removed} lines"


#: Field name -> human label, in the order they appear in the document.
_FIELD_LABELS: list[tuple[str, str]] = [
    ("title", "Title"),
    ("purpose", "Purpose"),
    ("scope", "Scope"),
    ("prerequisites", "Prerequisites"),
    ("roles", "Roles"),
    ("procedure", "Procedure"),
    ("decision_points", "Decision points"),
    ("exceptions", "Exceptions"),
    ("escalation_rules", "Escalation rules"),
    ("checklist", "Checklist"),
    ("kpis", "KPIs"),
    ("risks", "Risks"),
    ("improvement_suggestions", "Improvement suggestions"),
]


def _as_lines(value: object) -> list[str]:
    """Render any SOP field as comparable lines of text."""
    if value is None:
        return []
    if isinstance(value, str):
        return [line for line in value.splitlines() if line.strip()] or (
            [value] if value.strip() else []
        )
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, str):
                if item.strip():
                    lines.append(item)
            elif isinstance(item, BaseModel):
                # Render a structured item as "key: value" pairs on one line so
                # a change to any single attribute shows up as a line change.
                dumped = item.model_dump()
                rendered = " · ".join(
                    f"{key}: {val}" for key, val in dumped.items() if val not in (None, "", [])
                )
                if rendered:
                    lines.append(rendered)
            else:
                lines.append(str(item))
        return lines
    return [str(value)]


def _diff_lines(old: list[str], new: list[str]) -> list[LineChange]:
    """Line-level diff, keeping unchanged lines for context."""
    changes: list[LineChange] = []
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            changes += [LineChange(kind=ChangeKind.UNCHANGED, text=t) for t in old[i1:i2]]
        elif tag == "delete":
            changes += [LineChange(kind=ChangeKind.REMOVED, text=t) for t in old[i1:i2]]
        elif tag == "insert":
            changes += [LineChange(kind=ChangeKind.ADDED, text=t) for t in new[j1:j2]]
        elif tag == "replace":
            # Show removals then additions, which reads naturally in a UI.
            changes += [LineChange(kind=ChangeKind.REMOVED, text=t) for t in old[i1:i2]]
            changes += [LineChange(kind=ChangeKind.ADDED, text=t) for t in new[j1:j2]]

    return changes


def diff_sop_content(
    old: SopContent, new: SopContent, *, from_version: int = 0, to_version: int = 0
) -> SopDiff:
    """Compare two SOP versions field by field."""
    field_diffs: list[FieldDiff] = []

    for field, label in _FIELD_LABELS:
        old_lines = _as_lines(getattr(old, field, None))
        new_lines = _as_lines(getattr(new, field, None))

        if old_lines == new_lines:
            kind = ChangeKind.UNCHANGED
            lines: list[LineChange] = []
        elif not old_lines:
            kind = ChangeKind.ADDED
            lines = [LineChange(kind=ChangeKind.ADDED, text=t) for t in new_lines]
        elif not new_lines:
            kind = ChangeKind.REMOVED
            lines = [LineChange(kind=ChangeKind.REMOVED, text=t) for t in old_lines]
        else:
            kind = ChangeKind.MODIFIED
            lines = _diff_lines(old_lines, new_lines)

        field_diffs.append(FieldDiff(field=field, label=label, kind=kind, lines=lines))

    return SopDiff(from_version=from_version, to_version=to_version, fields=field_diffs)
