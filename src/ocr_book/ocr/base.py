"""Interfaz común de motor OCR."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ocr_book.config.schema import OcrConfig
from ocr_book.ocr.models import OcrResult


class OcrEngine(ABC):
    """Cualquier motor OCR (Tesseract, PaddleOCR, EasyOCR, ...) implementa
    esto. `recognize` recibe una imagen ya preprocesada."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Indica si las dependencias del motor están instaladas."""

    @abstractmethod
    def recognize(self, image: np.ndarray, config: OcrConfig) -> OcrResult:
        """Ejecuta el reconocimiento y devuelve palabras con posición y
        confianza, en el modelo de datos común `OcrResult`."""
