"""Construye el motor OCR configurado, con caída controlada a Tesseract si
el motor pedido no está instalado (en vez de abortar todo el libro)."""

from __future__ import annotations

import logging

from ocr_book.config.schema import OcrConfig, OcrEngineName
from ocr_book.ocr.base import OcrEngine
from ocr_book.ocr.tesseract_engine import TesseractEngine

logger = logging.getLogger(__name__)

_ENGINE_CLASSES = {
    OcrEngineName.TESSERACT: TesseractEngine,
}


def _lazy_engine_classes() -> dict[OcrEngineName, type[OcrEngine]]:
    # Import perezoso: paddleocr_engine/easyocr_engine no requieren que sus
    # dependencias pesadas estén instaladas solo para *construir* el mapa.
    from ocr_book.ocr.easyocr_engine import EasyOcrEngine
    from ocr_book.ocr.paddleocr_engine import PaddleOcrEngine

    return {
        OcrEngineName.TESSERACT: TesseractEngine,
        OcrEngineName.PADDLEOCR: PaddleOcrEngine,
        OcrEngineName.EASYOCR: EasyOcrEngine,
    }


def get_engine(config: OcrConfig) -> OcrEngine:
    classes = _lazy_engine_classes()
    engine_cls = classes[config.engine]
    engine = engine_cls()

    if not engine.is_available():
        logger.warning(
            "El motor OCR '%s' no está disponible; se usa Tesseract como respaldo.",
            config.engine.value,
        )
        engine = TesseractEngine()

    return engine
