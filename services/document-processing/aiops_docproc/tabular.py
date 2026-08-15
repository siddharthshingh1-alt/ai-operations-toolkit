"""Read an uploaded spreadsheet into a dataframe.

Lives here rather than in the Dashboard project because the Report Generator
(Project 7) consumes the same files — CLAUDE.md Section 4 makes document
processing a shared service for exactly this reason.

Everything in this module is about rejecting bad input *clearly*. A dashboard
that renders nothing is a bug report; a dashboard that says "row 14 has 9
values but the header has 8" is a file someone can go and fix. Section 23
requires the difference.
"""

from __future__ import annotations

import io
from enum import StrEnum
from pathlib import Path

import pandas as pd

from aiops_utils import ValidationError, get_logger

logger = get_logger(__name__)


class TableKind(StrEnum):
    CSV = "csv"
    EXCEL = "excel"


_EXTENSIONS: dict[str, TableKind] = {
    ".csv": TableKind.CSV,
    ".tsv": TableKind.CSV,
    ".xlsx": TableKind.EXCEL,
    ".xlsm": TableKind.EXCEL,
}

#: Upload ceiling. Generous for an operations extract, small enough that a
#: mis-click on a database dump fails immediately rather than after a timeout.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

#: Row ceiling. Beyond this the browser, not the analysis, becomes the problem.
MAX_ROWS = 100_000

#: Column ceiling. A file this wide is almost always a misread delimiter.
MAX_COLUMNS = 200


def detect_table_kind(filename: str) -> TableKind:
    """Determine the spreadsheet type from its filename."""
    suffix = Path(filename).suffix.lower()
    kind = _EXTENSIONS.get(suffix)
    if kind is None:
        supported = ", ".join(sorted(_EXTENSIONS))
        raise ValidationError(
            f"{suffix or 'This file type'} is not a supported table. Supported: {supported}.",
            user_message=(
                "That file type cannot be read as a table. Please upload a "
                "CSV or Excel file (.csv, .tsv, .xlsx, .xlsm)."
            ),
        )
    return kind


def _read_csv(data: bytes, *, separator: str | None) -> pd.DataFrame:
    """Decode and parse a delimited text file.

    Encoding is attempted UTF-8 first and Latin-1 second. Latin-1 cannot fail —
    every byte maps to some character — so this never raises for encoding
    reasons. That is deliberate: a spreadsheet exported from Excel on a Windows
    machine is frequently cp1252, and refusing it over one stray character
    would reject files that are otherwise perfectly readable.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        logger.info("upload was not UTF-8, falling back to latin-1")
        text = data.decode("latin-1")

    try:
        return pd.read_csv(
            io.StringIO(text),
            sep=separator,
            engine="python" if separator is None else "c",
            skipinitialspace=True,
        )
    except pd.errors.EmptyDataError as exc:
        raise ValidationError(
            f"The file contains no parsable rows: {exc}",
            user_message="That file appears to be empty. Please upload a file with data in it.",
        ) from exc
    except pd.errors.ParserError as exc:
        # The most common real cause is a ragged file: a row with more values
        # than the header. pandas names the row, so pass that through — it is
        # the one piece of information that makes the file fixable.
        raise ValidationError(
            f"The file could not be parsed: {exc}",
            user_message=(
                "That file could not be read as a table. The rows do not all have "
                f"the same number of columns — {str(exc).split('.')[0].strip()}."
            ),
        ) from exc


def _read_excel(data: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(data))
    except ValueError as exc:
        raise ValidationError(
            f"The workbook could not be read: {exc}",
            user_message=(
                "That workbook could not be read. It may be corrupt, password "
                "protected, or saved in an old .xls format — re-save it as .xlsx."
            ),
        ) from exc
    except Exception as exc:  # noqa: BLE001 — openpyxl raises a broad family
        raise ValidationError(
            f"The workbook could not be read: {exc}",
            user_message=(
                "That workbook could not be read. Please check it opens in Excel, "
                "then re-save it as .xlsx and try again."
            ),
        ) from exc


def read_table(data: bytes, filename: str) -> pd.DataFrame:
    """Parse an uploaded spreadsheet, or raise a `ValidationError` a user can act on.

    Every guard here has a message naming what is wrong and what to do about
    it. None of them show a stack trace (Section 23).
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Upload is {len(data):,} bytes, over the {MAX_UPLOAD_BYTES:,} limit.",
            user_message=(
                f"That file is too large ({len(data) / 1_048_576:.1f} MB). "
                f"The limit is {MAX_UPLOAD_BYTES // 1_048_576} MB — try exporting "
                "a shorter date range."
            ),
        )

    if not data.strip():
        raise ValidationError(
            "Upload is empty.",
            user_message="That file is empty. Please upload a file with data in it.",
        )

    kind = detect_table_kind(filename)
    separator = "\t" if Path(filename).suffix.lower() == ".tsv" else None
    frame = _read_csv(data, separator=separator) if kind is TableKind.CSV else _read_excel(data)

    # A header row with nothing under it parses successfully and then produces
    # an analysis of nothing, which reads as a broken dashboard rather than an
    # unusable file. Name it here instead.
    if frame.empty:
        raise ValidationError(
            f"Parsed {len(frame.columns)} column(s) and no rows.",
            user_message=(
                "That file has column headings but no data rows underneath them. "
                "Please upload a file that contains at least one row."
            ),
        )

    if len(frame) > MAX_ROWS:
        raise ValidationError(
            f"File has {len(frame):,} rows, over the {MAX_ROWS:,} limit.",
            user_message=(
                f"That file has {len(frame):,} rows. The limit is {MAX_ROWS:,} — "
                "please summarise or filter it before uploading."
            ),
        )

    if len(frame.columns) > MAX_COLUMNS:
        raise ValidationError(
            f"File has {len(frame.columns)} columns, over the {MAX_COLUMNS} limit.",
            user_message=(
                f"That file has {len(frame.columns)} columns, which is more than "
                "this dashboard can display. It usually means the delimiter was "
                "misread — check the file is comma-separated."
            ),
        )

    # Unnamed columns come from a trailing comma on every row. Harmless, but
    # they clutter every chart axis and column picker downstream.
    frame = frame.loc[:, ~frame.columns.astype(str).str.match(r"^Unnamed: \d+$")]
    frame.columns = [str(name).strip() for name in frame.columns]

    logger.info(
        "parsed uploaded table",
        extra={"rows": len(frame), "columns": len(frame.columns), "kind": kind.value},
    )
    return frame
