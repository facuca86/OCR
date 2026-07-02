"""Pruebas de los exportadores contra un `Document` construido a mano
(rápidas, sin pasar por OCR): cada formato debe producir un archivo
válido con el contenido esperado y sin duplicar el título."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocr_book.config.schema import ExportConfig, ExportFormat
from ocr_book.export import get_exporter
from ocr_book.export.markdown_exporter import document_to_markdown
from ocr_book.export.txt_exporter import document_to_text
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun


def _sample_document() -> Document:
    document = Document(title="Mi Libro", source_language="es")
    document.add(Block(type=BlockType.TITLE, runs=[TextRun("Mi Libro")]))
    document.add(
        Block(
            type=BlockType.PARAGRAPH,
            runs=[TextRun("Texto normal y "), TextRun("texto en negrita", bold=True), TextRun(".")],
        )
    )
    document.add(Block(type=BlockType.QUOTE, runs=[TextRun("Una cita memorable.")]))
    document.add(Block(type=BlockType.LIST_ITEM, runs=[TextRun("Primer elemento")], list_ordered=False))
    document.add(Block(type=BlockType.LIST_ITEM, runs=[TextRun("Segundo elemento")], list_ordered=False))
    document.add(
        Block(type=BlockType.FOOTNOTE, runs=[TextRun("Texto de la nota.")], footnote_marker="1")
    )
    return document


def test_markdown_export_has_no_duplicated_title() -> None:
    markdown = document_to_markdown(_sample_document())
    assert markdown.count("# Mi Libro") == 1
    assert "**texto en negrita**" in markdown
    assert "> Una cita memorable." in markdown
    assert "- Primer elemento" in markdown
    assert "- Segundo elemento" in markdown
    assert "[^1]: Texto de la nota." in markdown


def test_txt_export_renders_all_block_types() -> None:
    text = document_to_text(_sample_document())
    assert "MI LIBRO" in text
    assert "Una cita memorable." in text
    assert "- Primer elemento" in text
    assert "[1] Texto de la nota." in text


@pytest.mark.parametrize(
    "fmt",
    [ExportFormat.TXT, ExportFormat.MARKDOWN, ExportFormat.HTML, ExportFormat.DOCX, ExportFormat.EPUB],
)
def test_exporters_produce_a_nonempty_file(tmp_path: Path, fmt: ExportFormat) -> None:
    exporter = get_exporter(fmt)
    output = exporter.export(_sample_document(), tmp_path / "book", ExportConfig())
    assert output.exists()
    assert output.suffix == exporter.extension
    assert output.stat().st_size > 0


def test_pdf_exporter_produces_a_nonempty_file(tmp_path: Path) -> None:
    pytest.importorskip("weasyprint")
    exporter = get_exporter(ExportFormat.PDF)
    output = exporter.export(_sample_document(), tmp_path / "book", ExportConfig())
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")


def test_html_export_escapes_and_styles_runs(tmp_path: Path) -> None:
    exporter = get_exporter(ExportFormat.HTML)
    document = Document()
    document.add(Block(type=BlockType.PARAGRAPH, runs=[TextRun("<script>alert(1)</script>")]))
    output = exporter.export(document, tmp_path / "escape_test", ExportConfig())
    html_content = output.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html_content
    assert "&lt;script&gt;" in html_content
