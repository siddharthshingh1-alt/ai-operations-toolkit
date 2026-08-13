"""Document export, built once and shared.

CLAUDE.md Section 3 calls out that PDF generation was previously required by
three separate projects and specified by none. It lives here, and the SOP
Generator (Project 1) and Report Generator (Project 7) both consume it.

Markdown and HTML always work. PDF needs WeasyPrint, which depends on native
GTK/Pango libraries — so it is imported lazily and, when unavailable, raises an
error that tells you exactly what to install rather than crashing on import.
"""

from __future__ import annotations

import html
from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, Field

from aiops_utils import ConfigurationError, ValidationError


class ExportFormat(StrEnum):
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"


class DocumentSection(BaseModel):
    """One titled section of a generated document."""

    heading: str
    body: str = ""
    #: Rendered as a bulleted list beneath the body.
    bullets: list[str] = Field(default_factory=list)


class Document(BaseModel):
    """A structured document, independent of output format.

    Generators build one of these; exporters turn it into bytes. Adding a
    fourth output format means adding one exporter, not touching any project.
    """

    title: str
    subtitle: str | None = None
    sections: list[DocumentSection] = Field(default_factory=list)
    #: Rendered as a key/value block under the title (owner, version, dates).
    metadata: dict[str, str] = Field(default_factory=dict)
    footer: str | None = None


class Exporter(ABC):
    """Turns a `Document` into bytes."""

    format: ExportFormat
    media_type: str
    extension: str

    @abstractmethod
    def render(self, document: Document) -> bytes:
        """Render the document."""


class MarkdownExporter(Exporter):
    """Markdown output. No dependencies, always available."""

    format = ExportFormat.MARKDOWN
    media_type = "text/markdown; charset=utf-8"
    extension = "md"

    def render(self, document: Document) -> bytes:
        lines: list[str] = [f"# {document.title}", ""]
        if document.subtitle:
            lines += [f"_{document.subtitle}_", ""]

        if document.metadata:
            lines += [f"- **{key}:** {value}" for key, value in document.metadata.items()]
            lines.append("")

        for section in document.sections:
            lines += [f"## {section.heading}", ""]
            if section.body:
                lines += [section.body, ""]
            if section.bullets:
                lines += [f"- {bullet}" for bullet in section.bullets]
                lines.append("")

        if document.footer:
            lines += ["---", "", document.footer, ""]

        return "\n".join(lines).encode("utf-8")


class HtmlExporter(Exporter):
    """Self-contained HTML. Also the input WeasyPrint turns into a PDF."""

    format = ExportFormat.HTML
    media_type = "text/html; charset=utf-8"
    extension = "html"

    #: Print-friendly and deliberately plain — this is an internal operations
    #: document, not a marketing page (CLAUDE.md Section 21).
    _CSS = """
    @page { size: A4; margin: 20mm; }
    body { font-family: -apple-system, Segoe UI, Roboto, sans-serif;
           font-size: 11pt; line-height: 1.55; color: #1a1a1a; }
    h1 { font-size: 20pt; margin-bottom: 4px; }
    h2 { font-size: 13pt; margin-top: 22px; border-bottom: 1px solid #ddd;
         padding-bottom: 4px; }
    .subtitle { color: #555; font-style: italic; margin-top: 0; }
    .metadata { background: #f6f6f6; padding: 10px 14px; border-radius: 4px;
                margin: 16px 0; font-size: 10pt; }
    .metadata div { margin: 2px 0; }
    footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid #ddd;
             color: #666; font-size: 9pt; }
    """

    def render(self, document: Document) -> bytes:
        return self.render_html(document).encode("utf-8")

    def render_html(self, document: Document) -> str:
        """Render to an HTML string. Every value is escaped."""
        esc = html.escape
        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>{esc(document.title)}</title>",
            f"<style>{self._CSS}</style>",
            "</head><body>",
            f"<h1>{esc(document.title)}</h1>",
        ]
        if document.subtitle:
            parts.append(f'<p class="subtitle">{esc(document.subtitle)}</p>')

        if document.metadata:
            parts.append('<div class="metadata">')
            parts += [
                f"<div><strong>{esc(key)}:</strong> {esc(value)}</div>"
                for key, value in document.metadata.items()
            ]
            parts.append("</div>")

        for section in document.sections:
            parts.append(f"<h2>{esc(section.heading)}</h2>")
            if section.body:
                parts.append(f"<p>{esc(section.body)}</p>")
            if section.bullets:
                parts.append("<ul>")
                parts += [f"<li>{esc(bullet)}</li>" for bullet in section.bullets]
                parts.append("</ul>")

        if document.footer:
            parts.append(f"<footer>{esc(document.footer)}</footer>")

        parts.append("</body></html>")
        return "\n".join(parts)


class PdfExporter(Exporter):
    """PDF via WeasyPrint, rendered from the same HTML as `HtmlExporter`."""

    format = ExportFormat.PDF
    media_type = "application/pdf"
    extension = "pdf"

    @staticmethod
    def is_available() -> bool:
        """True when WeasyPrint and its native libraries can be loaded.

        Checked by the /health endpoint so the limitation is visible rather
        than discovered when a user clicks Export.
        """
        try:
            import weasyprint  # noqa: F401
        except (ImportError, OSError):
            # OSError, not just ImportError: WeasyPrint imports fine but raises
            # OSError when the GTK/Pango shared libraries are missing.
            return False
        return True

    def render(self, document: Document) -> bytes:
        try:
            from weasyprint import HTML
        except (ImportError, OSError) as exc:
            raise ConfigurationError(
                "PDF export needs WeasyPrint and its native GTK libraries.\n"
                "  Windows: install the GTK3 runtime, then "
                "'pip install .[pdf]' in services/document-processing\n"
                "  macOS:   brew install pango gdk-pixbuf libffi\n"
                "  Linux:   apt install libpango-1.0-0 libpangoft2-1.0-0\n"
                "Markdown and HTML export work without it.",
                user_message=(
                    "PDF export is not available on this server. "
                    "Markdown and HTML downloads still work."
                ),
            ) from exc

        markup = HtmlExporter().render_html(document)
        return HTML(string=markup).write_pdf()


_EXPORTERS: dict[ExportFormat, type[Exporter]] = {
    ExportFormat.MARKDOWN: MarkdownExporter,
    ExportFormat.HTML: HtmlExporter,
    ExportFormat.PDF: PdfExporter,
}


def get_exporter(fmt: ExportFormat | str) -> Exporter:
    """Return the exporter for a format."""
    try:
        return _EXPORTERS[ExportFormat(fmt)]()
    except ValueError as exc:
        raise ValidationError(
            f"Unsupported export format {fmt!r}. "
            f"Expected one of: {', '.join(f.value for f in ExportFormat)}."
        ) from exc


def available_formats() -> list[ExportFormat]:
    """Formats this deployment can actually produce right now."""
    formats = [ExportFormat.MARKDOWN, ExportFormat.HTML]
    if PdfExporter.is_available():
        formats.append(ExportFormat.PDF)
    return formats
