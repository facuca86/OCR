from __future__ import annotations

from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.export.base import Exporter
from ocr_book.export.html_builder import document_to_html
from ocr_book.reconstruction.document_model import Document


class HtmlExporter(Exporter):
    extension = ".html"

    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        output_path = output_path.with_suffix(self.extension)
        lang = document.source_language or "es"
        output_path.write_text(document_to_html(document, lang=lang), encoding="utf-8")
        return output_path
