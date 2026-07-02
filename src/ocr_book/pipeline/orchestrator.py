"""Orquestador: une importación, OCR paralelo por página, reconstrucción,
traducción opcional y exportación en una sola llamada, reportando
progreso y permitiendo cancelación cooperativa desde la GUI o el CLI."""

from __future__ import annotations

import logging
import multiprocessing
import re
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ocr_book.config.schema import AppConfig
from ocr_book.export.factory import get_exporter
from ocr_book.importers.base import SourceDocument
from ocr_book.importers.factory import import_file
from ocr_book.layout.models import PageLayout
from ocr_book.pipeline.page_worker import init_worker, process_page
from ocr_book.pipeline.progress import ProgressCallback, ProgressEvent, noop_progress
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun
from ocr_book.reconstruction.reconstructor import DocumentReconstructor
from ocr_book.translation.factory import get_translation_engine
from ocr_book.translation.language_detection import detect_document_language
from ocr_book.utils.errors import PipelineCancelledError

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Punto de entrada único al motor de conversión. La GUI y el CLI son
    dos interfaces distintas sobre esta misma clase."""

    def __init__(self, config: AppConfig):
        self.config = config

    def process_document(
        self,
        input_path: str | Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Document:
        progress = progress_callback or noop_progress
        input_path = Path(input_path)

        source = import_file(input_path, dpi=self.config.preprocessing.target_dpi)
        progress(ProgressEvent("import", 1, 1, f"{len(source)} página(s) importadas de {input_path.name}"))

        if source.has_text_layer:
            document = self._build_from_text_layer(source, progress)
        else:
            document = self._build_from_ocr(source, progress, cancel_event)

        if self.config.translation.enabled:
            document = self._translate(document, progress)

        return document

    def process_and_export(
        self,
        input_path: str | Path,
        output_basename: str | Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[Path]:
        document = self.process_document(input_path, progress_callback, cancel_event)
        return self.export_document(document, output_basename, progress_callback)

    def export_document(
        self,
        document: Document,
        output_basename: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Path]:
        progress = progress_callback or noop_progress
        output_basename = Path(output_basename)
        output_basename.parent.mkdir(parents=True, exist_ok=True)

        formats = self.config.export.formats
        outputs = []
        for i, fmt in enumerate(formats):
            exporter = get_exporter(fmt)
            path = exporter.export(document, output_basename, self.config.export)
            outputs.append(path)
            progress(ProgressEvent("export", i + 1, len(formats), f"Exportado a {fmt.value}"))
        return outputs

    def _build_from_text_layer(self, source: SourceDocument, progress: ProgressCallback) -> Document:
        """El PDF ya tiene texto seleccionable: se omite todo el pipeline
        de OCR/layout y se reflowea directamente el texto nativo."""
        document = Document()
        total = len(source.pages)
        for i, page in enumerate(source.pages):
            for paragraph_text in _split_blank_line_paragraphs(page.embedded_text or ""):
                document.add(Block(type=BlockType.PARAGRAPH, runs=[TextRun(paragraph_text)], source_page=i))
            progress(ProgressEvent("reconstruction", i + 1, total, f"Página {i + 1}/{total} (texto nativo)"))
        return document

    def _build_from_ocr(
        self,
        source: SourceDocument,
        progress: ProgressCallback,
        cancel_event: threading.Event | None,
    ) -> Document:
        total = len(source.pages)
        max_workers = self.config.performance.max_workers

        # "spawn" en vez del "fork" por defecto en Linux: si el proceso
        # padre ya inicializó hilos internos de OpenCV/NumPy (basta con
        # haber importado ocr_book.importers antes), heredar ese estado al
        # hacer fork() puede dejar mutexes bloqueados para siempre en el
        # hijo. "spawn" arranca cada worker como un intérprete nuevo y
        # limpio; cuesta unos segundos más al iniciar el pool, pero es la
        # única forma robusta de mezclar multiprocessing con estas
        # librerías.
        mp_context = multiprocessing.get_context("spawn")

        layouts_by_index: dict[int, PageLayout] = {}
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=init_worker,
            initargs=(self.config,),
            mp_context=mp_context,
        ) as executor:
            futures = {
                executor.submit(process_page, page.image): page.index
                for page in source.pages
                if page.image is not None
            }
            completed = 0
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    raise PipelineCancelledError("Procesamiento cancelado por el usuario.")

                index = futures[future]
                layouts_by_index[index] = future.result()
                completed += 1
                progress(ProgressEvent("ocr", completed, total, f"Página {index + 1}/{total} procesada"))

        ordered_layouts = [layouts_by_index[i] for i in sorted(layouts_by_index)]
        document = DocumentReconstructor().build(ordered_layouts)
        progress(ProgressEvent("reconstruction", total, total, "Documento reconstruido"))
        return document

    def _translate(self, document: Document, progress: ProgressCallback) -> Document:
        translation_config = self.config.translation
        source_lang = translation_config.source_language or detect_document_language(document)
        engine = get_translation_engine(translation_config)

        progress(
            ProgressEvent(
                "translation",
                0,
                1,
                f"Traduciendo de '{source_lang}' a '{translation_config.target_language}' "
                f"con el motor '{engine.name}'",
            )
        )
        translated = engine.translate(document, translation_config.target_language, source_lang)
        progress(ProgressEvent("translation", 1, 1, "Traducción completa"))
        return translated


def _split_blank_line_paragraphs(text: str) -> list[str]:
    raw_paragraphs = re.split(r"\n\s*\n", text)
    return [" ".join(p.split()) for p in raw_paragraphs if p.strip()]
