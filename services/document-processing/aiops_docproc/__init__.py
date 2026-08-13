"""Shared document processing.

Phase 0 ships export (Markdown / HTML / PDF). Text *extraction* from uploaded
PDFs and Word files (PyMuPDF, python-docx) lands with Project 1, which is the
first project that needs it — see docs/decisions/0004.
"""

from aiops_docproc.export import (
    Document,
    DocumentSection,
    Exporter,
    ExportFormat,
    HtmlExporter,
    MarkdownExporter,
    PdfExporter,
    available_formats,
    get_exporter,
)

__all__ = [
    "Document",
    "DocumentSection",
    "ExportFormat",
    "Exporter",
    "HtmlExporter",
    "MarkdownExporter",
    "PdfExporter",
    "available_formats",
    "get_exporter",
]
