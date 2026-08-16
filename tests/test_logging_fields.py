"""Structured-logging fields must not collide with `LogRecord`'s own.

`logger.info(..., extra={...})` does not merge: `Logger.makeRecord` raises
`KeyError` if a key would overwrite an existing `LogRecord` attribute. So
`extra={"created": n}` is not a slightly-wrong label, it is an exception —
raised from the log line, at whatever moment the code path first runs.

That is how it reaches production unseen. The call sites are in seeding
routines, which do nothing on a database that has already been seeded, so the
deployed site is fine until the day it is pointed at a fresh one. Two of these
shipped: `extra={"created": ...}` in the Workflow Builder's and Travel
Operations' seeds, and `extra={"module": ...}` in the schema loader.

A static scan is the right shape here — it covers log lines no test executes,
which is exactly the population the bug hides in.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

#: Every attribute `logging.Logger.makeRecord` sets, plus the two it rejects by
#: name. Taken from a real record rather than hand-copied, so a future Python
#: that adds an attribute (as 3.12 added `taskName`) tightens this test itself.
RESERVED: frozenset[str] = frozenset(
    vars(
        logging.LogRecord(
            name="probe",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )
    )
) | {"message", "asctime"}

SOURCE_ROOTS = ("apps", "packages", "projects", "services")


def _python_files() -> list[Path]:
    repo = Path(__file__).resolve().parents[1]
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        files.extend(
            path
            for path in (repo / root).rglob("*.py")
            if ".venv" not in path.parts and "node_modules" not in path.parts
        )
    return files


def _extra_keys(path: Path) -> list[tuple[str, int]]:
    """Every literal key passed as `extra={...}` to a call in this file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
        return []

    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
                continue
            for key in keyword.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.append((key.value, key.lineno))
    return found


def test_no_log_extra_collides_with_a_reserved_record_attribute() -> None:
    repo = Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(repo)}:{line} extra={{{key!r}: ...}}"
        for path in _python_files()
        for key, line in _extra_keys(path)
        if key in RESERVED
    ]
    assert not offenders, (
        "These log calls raise KeyError instead of logging:\n  "
        + "\n  ".join(offenders)
        + "\nRename the field — 'created' -> 'seeded', 'module' -> 'module_name'."
    )


@pytest.mark.parametrize("key", ["created", "module", "name", "message"])
def test_the_reserved_set_is_not_vacuous(key: str) -> None:
    """Guard the guard: prove these names really do raise."""
    logger = logging.getLogger("aiops.test.reserved")
    logger.setLevel(logging.INFO)
    assert key in RESERVED
    with pytest.raises(KeyError):
        logger.info("probe", extra={key: "x"})
