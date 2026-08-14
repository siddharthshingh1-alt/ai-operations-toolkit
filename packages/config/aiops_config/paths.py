"""Locate repo-relative paths regardless of the current working directory.

The API is started from `apps/api`, tests run from the repo root, and scripts
run from anywhere. Rather than sprinkling `../../..` around the codebase, every
module asks this helper where the repo root is.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# A directory is the repo root if it contains all of these.
_ROOT_MARKERS = ("requirements.txt", "package.json", "pyproject.toml")

#: Explicit override, for deployments where marker-file detection cannot work.
ROOT_ENV_VAR = "AIOPS_REPO_ROOT"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Return the repository root directory.

    Resolution order:

    1. ``AIOPS_REPO_ROOT``, if set and pointing at a real directory.
    2. Walking upwards from this file looking for the marker files.
    3. The current working directory.

    The environment variable exists because step 2 is fragile in a container.
    A production image copies only what it needs — `requirements.txt` but not
    `package.json` — so the marker check fails, resolution falls through to the
    working directory, and every repo-relative path silently points somewhere
    wrong. That is exactly how the deployed API reported zero Demo Mode
    recordings while the files were present in the image the whole time: it was
    looking in `apps/api/data` instead of `/repo/data`.

    Setting it explicitly turns a silent misdirection into a stated fact.
    """
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            return path

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
