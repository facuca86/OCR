"""Detección automática del idioma de origen antes de traducir."""

from __future__ import annotations

import logging

from langdetect import DetectorFactory, LangDetectException, detect

from ocr_book.reconstruction.document_model import Document

logger = logging.getLogger(__name__)

# langdetect no es determinista por defecto (usa un generador aleatorio
# internamente); fijar la semilla hace que el mismo texto siempre dé el
# mismo idioma, importante para que el pipeline sea reproducible.
DetectorFactory.seed = 0


def detect_document_language(document: Document, default: str = "en") -> str:
    sample = " ".join(block.text for block in document.blocks if block.text.strip())[:4000]
    if not sample.strip():
        return default
    try:
        return detect(sample)
    except LangDetectException:
        logger.warning("No se pudo detectar el idioma del documento; se usa '%s' por defecto.", default)
        return default
