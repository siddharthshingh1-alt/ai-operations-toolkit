"""Locate repo-relative paths regardless of the current working directory.

The API is started from `apps/api`, tests run from the repo root, and scripts
run from anywhere. Rather than sprinkling `../../..` around the codebase, every
module asks this helper where the repo root is.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# A directory is the repo root if it contains all of these.
_ROOT_MARKERS = ("requirements.txt", "package.json", "pyproject.toml")


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Return the repository root directory.

    Walks upwards from this file until it finds the marker files. Falls back to
    the current working directory if the repo layout is unrecognisable (for
    example when the package is vendored into another project).
    """
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if candidate.is_dir() and all((candidate / marker).exists() for marker in _ROOT_MARKERS):
            return candidate
    return Path.cwd()


def data_dir() -> Path:
    """Directory holding the synthetic demo datasets (CLAUDE.md Section 20)."""
    return repo_root() / "data"


def generated_data_dir() -> Path:
    """Directory for datasets produced by `scripts/generate_demo_data.py`."""
    return data_dir() / "generated"


def demo_cache_dir() -> Path:
    """Directory holding recorded real AI outputs replayed by Demo Mode."""
    return data_dir() / "demo-cache"
