"""Exportador a PDF: renderiza el mismo HTML que `HtmlExporter` con
WeasyPrint, que soporta CSS de paginación (tamaño de página, márgenes,
control de saltos), en vez de dibujar con primitivas de bajo nivel. Así se
obtiene un PDF de tipografía moderna y agradable de leer, no una copia
exacta del escaneo."""

from __future__ import annotations

from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.export.base import Exporter
from ocr_book.export.html_builder import document_to_html
from ocr_book.reconstruction.document_model import Document
from ocr_book.utils.errors import EngineNotAvailableError

_PRINT_CSS = """
@page {
    size: A5;
    margin: 2cm 1.8cm;
}
h1 { page-break-before: always; break-before: page; }
h1:first-of-type { page-break-before: avoid; break-before: avoid; }
h2 { break-after: avoid; }
p { orphans: 2; widows: 2; }
"""


class PdfExporter(Exporter):
    extension = ".pdf"

    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise EngineNotAvailableError(
                "El exportador PDF requiere WeasyPrint. Instálalo con: pip install weasyprint"
            ) from exc

        output_path = output_path.with_suffix(self.extension)
        lang = document.source_language or "es"
        html_content = document_to_html(document, lang=lang, extra_css=_PRINT_CSS)
        HTML(string=html_content, base_url=str(output_path.parent)).write_pdf(str(output_path))
        return output_path
