"""Interfaz común de motor de traducción.

La traducción se hace a nivel de `Document`, nunca a nivel de línea de
OCR: así un párrafo de entrada produce un párrafo de salida y un título
sigue siendo un título, en vez de romper la estructura del libro."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ocr_book.reconstruction.document_model import Document


class TranslationEngine(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def translate(self, document: Document, target_language: str, source_language: str | None = None) -> Document:
        """Devuelve un nuevo `Document` con el mismo número y tipo de
        bloques que el original, pero con el texto traducido."""
