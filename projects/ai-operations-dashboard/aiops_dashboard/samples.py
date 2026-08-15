"""The bundled datasets a visitor can analyse without uploading anything.

A dashboard whose first screen is an empty file-picker asks a reviewer to go
and find a spreadsheet before it will show them anything. These are the
synthetic operations datasets from CLAUDE.md Section 20, already in the image,
so the first screen has a full dashboard on it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aiops_config import generated_data_dir
from aiops_dashboard.models import SampleDataset
from aiops_docproc import read_table
from aiops_utils import NotFoundError, get_logger

logger = get_logger(__name__)

#: key -> (filename, display name, what it is)
_SAMPLES: dict[str, tuple[str, str, str]] = {
    "operations_metrics": (
        "operations_metrics.csv",
        "Daily operations metrics",
        "Ninety days of bookings, cancellations, ticket volume and on-time departures.",
    ),
    "travel_bookings": (
        "travel_bookings.csv",
        "Agent bookings",
        "Individual bookings by travel agent, route, supplier and value.",
    ),
    "support_tickets": (
        "support_tickets.csv",
        "Support tickets",
        "Agent-raised tickets with category, priority and resolution time.",
    ),
    "sales_data": (
        "sales_data.csv",
        "Sales",
        "Revenue by period, product and region.",
    ),
    "employee_tasks": (
        "employee_tasks.csv",
        "Operations tasks",
        "Internal task tracker with owners, deadlines and status.",
    ),
}


def _path_for(key: str) -> Path:
    if key not in _SAMPLES:
        raise NotFoundError(
            f"No sample dataset named {key!r}.",
            user_message="That sample dataset does not exist.",
        )
    return generated_data_dir() / _SAMPLES[key][0]


def load_sample(key: str) -> pd.DataFrame:
    """Read one bundled dataset."""
    path = _path_for(key)
    if not path.is_file():
        # The datasets are generated at build time rather than committed, so a
        # missing file means the generator did not run — say that, rather than
        # letting a FileNotFoundError reach the user as a 500.
        raise NotFoundError(
            f"Sample dataset {key!r} is not present at {path}.",
            user_message=(
                "That sample dataset is not available on this deployment. "
                "It is generated at build time by scripts/generate_demo_data.py."
            ),
        )
    return read_table(path.read_bytes(), path.name)


def available_samples() -> list[SampleDataset]:
    """Every sample present on this deployment, with its row count."""
    found: list[SampleDataset] = []
    for key, (filename, name, description) in _SAMPLES.items():
        path = generated_data_dir() / filename
        if not path.is_file():
            logger.warning("sample dataset missing", extra={"key": key, "path": str(path)})
            continue
        # Counting lines is enough for a menu and avoids parsing five files on
        # every page load.
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            rows = max(sum(1 for _ in handle) - 1, 0)
        found.append(SampleDataset(key=key, name=name, description=description, row_count=rows))
    return found
