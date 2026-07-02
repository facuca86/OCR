"""Interfaz común de analizador de layout."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ocr_book.config.schema import LayoutConfig
from ocr_book.layout.models import PageLayout
from ocr_book.ocr.models import OcrResult


class LayoutAnalyzer(ABC):
    """Recibe el resultado plano del OCR (palabras con posición) y devuelve
    una página estructurada en regiones, ya en orden de lectura."""

    @abstractmethod
    def analyze(self, ocr_result: OcrResult, config: LayoutConfig) -> PageLayout:
        ...
