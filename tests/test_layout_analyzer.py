"""Pruebas de extremo a extremo del analizador de layout heurístico contra
PDFs sintéticos generados por `scripts/make_test_pdf.py` y
`scripts/make_multicolumn_test_pdf.py`. Sirven de test de regresión para
los casos límite descubiertos durante el desarrollo: fusión de encabezado
y título, mezcla de columnas por segmentación automática de Tesseract, y
corte de bandas a través de un párrafo normal."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ocr_book.config import AppConfig
from ocr_book.importers import import_file
from ocr_book.layout import RegionType, get_layout_analyzer
from ocr_book.ocr import get_engine, recognize_with_columns
from ocr_book.preprocessing import PreprocessingPipeline

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="requiere el binario 'tesseract'"
)


def _analyze_first_page(pdf_path: Path):
    cfg = AppConfig()
    doc = import_file(pdf_path, dpi=200)
    pipeline = PreprocessingPipeline(cfg.preprocessing)
    engine = get_engine(cfg.ocr)
    analyzer = get_layout_analyzer(cfg.layout)

    image = pipeline.run(doc.pages[0].image)
    ocr_result = recognize_with_columns(engine, image, cfg.ocr, cfg.layout)
    return analyzer.analyze(ocr_result, cfg.layout)


def test_single_column_page_has_clean_title_and_two_paragraphs(single_column_pdf: Path) -> None:
    layout = _analyze_first_page(single_column_pdf)
    regions = layout.regions_in_reading_order()

    body_regions = [r for r in regions if r.type == RegionType.BODY_TEXT]
    title_or_heading = [r for r in regions if r.type in (RegionType.TITLE, RegionType.HEADING)]

    assert len(title_or_heading) == 1
    assert "comienzo" in title_or_heading[0].text.lower()
    # el título no debe fusionarse con el cuerpo del primer párrafo
    assert "lorem ipsum" not in title_or_heading[0].text.lower()

    assert len(body_regions) == 2
    assert "lorem ipsum" in body_regions[0].text.lower()
    assert "duis aute" in body_regions[1].text.lower()


def test_multicolumn_page_separates_header_title_columns_and_footnote(
    multicolumn_pdf: Path,
) -> None:
    layout = _analyze_first_page(multicolumn_pdf)
    regions = layout.regions_in_reading_order()
    by_type = {r.type: r for r in regions if r.type != RegionType.BODY_TEXT}

    assert RegionType.HEADER in by_type
    assert "libro de prueba" in by_type[RegionType.HEADER].text.lower()

    assert RegionType.TITLE in by_type
    assert "columnas" in by_type[RegionType.TITLE].text.lower()

    assert RegionType.FOOTNOTE in by_type
    assert "nota al pie" in by_type[RegionType.FOOTNOTE].text.lower()

    assert RegionType.PAGE_NUMBER in by_type
    assert by_type[RegionType.PAGE_NUMBER].text.strip() == "42"

    body_regions = [r for r in regions if r.type == RegionType.BODY_TEXT]
    columns_used = {r.column_index for r in body_regions}
    assert columns_used == {0, 1}, "el cuerpo debe repartirse en dos columnas distintas"

    col0 = next(r for r in body_regions if r.column_index == 0)
    col1 = next(r for r in body_regions if r.column_index == 1)
    assert "primera columna" in col0.text.lower()
    assert "segunda columna" in col1.text.lower()
    # orden de lectura: toda la columna izquierda antes que la derecha
    assert col0.reading_order < col1.reading_order

    # ninguna columna debe contener texto de la otra (la fusión por PSM
    # automático de Tesseract fue el bug original que motivó este test)
    assert "segunda columna" not in col0.text.lower()
    assert "primera columna" not in col1.text.lower()
