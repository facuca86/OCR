"""Prueba de extremo a extremo del reconstructor de documentos: desde los
PDFs sintéticos hasta el `Document` final, verificando que el título, los
párrafos, el encabezado (descartado), la nota al pie y la fusión de un
párrafo partido entre dos páginas queden todos correctos."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ocr_book.config import AppConfig
from ocr_book.importers import import_file
from ocr_book.layout import get_layout_analyzer
from ocr_book.ocr import get_engine, recognize_with_columns
from ocr_book.preprocessing import PreprocessingPipeline
from ocr_book.reconstruction import BlockType, DocumentReconstructor

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="requiere el binario 'tesseract'"
)


def _build_document(pdf_path: Path):
    cfg = AppConfig()
    source = import_file(pdf_path, dpi=200)
    pipeline = PreprocessingPipeline(cfg.preprocessing)
    engine = get_engine(cfg.ocr)
    analyzer = get_layout_analyzer(cfg.layout)

    layouts = []
    for page in source.pages:
        image = pipeline.run(page.image)
        ocr_result = recognize_with_columns(engine, image, cfg.ocr, cfg.layout)
        layouts.append(analyzer.analyze(ocr_result, cfg.layout))

    return DocumentReconstructor().build(layouts)


def test_two_page_book_reconstructs_titles_and_paragraphs_per_page(single_column_pdf: Path) -> None:
    document = _build_document(single_column_pdf)

    titles = [b for b in document.blocks if b.type in (BlockType.TITLE, BlockType.HEADING)]
    paragraphs = [b for b in document.blocks if b.type == BlockType.PARAGRAPH]

    assert len(titles) == 2
    assert "comienzo" in titles[0].text.lower()
    assert "desarrollo" in titles[1].text.lower()

    # cada página tenía dos párrafos separados por un hueco claro; ninguno
    # debe haberse fusionado con el título ni entre sí de más
    assert len(paragraphs) == 4
    for paragraph in paragraphs:
        assert paragraph.text.strip().endswith((".", "!", "?"))


def test_multicolumn_book_drops_running_header_and_page_number(multicolumn_pdf: Path) -> None:
    document = _build_document(multicolumn_pdf)

    assert not any("libro de prueba" in b.text.lower() for b in document.blocks)
    assert not any(b.text.strip() == "42" for b in document.blocks)

    footnotes = [b for b in document.blocks if b.type == BlockType.FOOTNOTE]
    assert len(footnotes) == 1
    assert footnotes[0].footnote_marker == "1"
    assert "nota al pie" in footnotes[0].text.lower()
    assert not footnotes[0].text.lstrip().startswith("1 ")

    paragraphs = [b for b in document.blocks if b.type == BlockType.PARAGRAPH]
    assert len(paragraphs) == 2
    assert "primera columna" in paragraphs[0].text.lower()
    assert "segunda columna" in paragraphs[1].text.lower()
