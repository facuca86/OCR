"""Pruebas del orquestador: el atajo de texto nativo (sin OCR) y la
utilidad de división en párrafos que usa, más una prueba de extremo a
extremo real contra el PDF escaneado sintético, verificando que ya no
existe la regresión de rendimiento por sobre-suscripción de hilos /
deadlock de fork descubierta durante el desarrollo (debe terminar en un
tiempo acotado, no colgarse)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import fitz
import pytest

from ocr_book.config import AppConfig
from ocr_book.config.schema import ExportFormat
from ocr_book.pipeline.orchestrator import PipelineOrchestrator, _split_blank_line_paragraphs
from ocr_book.reconstruction.document_model import BlockType


def test_split_blank_line_paragraphs_keeps_real_breaks_and_joins_wrapped_lines() -> None:
    text = "Primera linea del parrafo uno\nsegunda linea del mismo parrafo.\n\nParrafo nuevo aqui."
    paragraphs = _split_blank_line_paragraphs(text)
    assert paragraphs == [
        "Primera linea del parrafo uno segunda linea del mismo parrafo.",
        "Parrafo nuevo aqui.",
    ]


def test_split_blank_line_paragraphs_ignores_empty_chunks() -> None:
    assert _split_blank_line_paragraphs("\n\n\n") == []
    assert _split_blank_line_paragraphs("") == []


def test_text_layer_pdf_skips_ocr_and_preserves_paragraph_breaks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "native.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(72, 72, 500, 300),
        "Primer parrafo con texto nativo seleccionable.\n\nSegundo parrafo, tambien nativo.",
        fontsize=11,
    )
    doc.save(pdf_path)
    doc.close()

    config = AppConfig()
    orchestrator = PipelineOrchestrator(config)
    document = orchestrator.process_document(pdf_path)

    paragraphs = [b for b in document.blocks if b.type == BlockType.PARAGRAPH]
    assert len(paragraphs) == 2
    assert "Primer parrafo" in paragraphs[0].text
    assert "Segundo parrafo" in paragraphs[1].text


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requiere el binario 'tesseract'")
def test_process_and_export_scanned_pdf_completes_within_a_bounded_time(
    tmp_path: Path, single_column_pdf: Path
) -> None:
    """Regresión: antes del fix de multiprocessing (spawn + un solo hilo
    por worker), este mismo caso podía colgarse varios minutos por un
    deadlock de fork combinado con sobre-suscripción de hilos entre
    OpenCV/Tesseract y el pool de procesos."""
    config = AppConfig()
    config.export.formats = [ExportFormat.MARKDOWN]
    config.performance.max_workers = 2

    orchestrator = PipelineOrchestrator(config)
    start = time.monotonic()
    outputs = orchestrator.process_and_export(single_column_pdf, tmp_path / "libro")
    elapsed = time.monotonic() - start

    assert elapsed < 90, f"el pipeline tardó {elapsed:.1f}s, se esperaba que terminara en <90s"
    assert len(outputs) == 1
    assert outputs[0].exists()
    content = outputs[0].read_text(encoding="utf-8")
    assert "comienzo" in content.lower()
    assert "desarrollo" in content.lower()
