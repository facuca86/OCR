from __future__ import annotations

from ocr_book.config.schema import ExportFormat
from ocr_book.export.base import Exporter
from ocr_book.export.docx_exporter import DocxExporter
from ocr_book.export.epub_exporter import EpubExporter
from ocr_book.export.html_exporter import HtmlExporter
from ocr_book.export.markdown_exporter import MarkdownExporter
from ocr_book.export.pdf_exporter import PdfExporter
from ocr_book.export.txt_exporter import TxtExporter

_EXPORTERS: dict[ExportFormat, type[Exporter]] = {
    ExportFormat.TXT: TxtExporter,
    ExportFormat.MARKDOWN: MarkdownExporter,
    ExportFormat.HTML: HtmlExporter,
    ExportFormat.DOCX: DocxExporter,
    ExportFormat.EPUB: EpubExporter,
    ExportFormat.PDF: PdfExporter,
}


def get_exporter(fmt: ExportFormat) -> Exporter:
    return _EXPORTERS[fmt]()
