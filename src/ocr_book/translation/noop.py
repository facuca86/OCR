from __future__ import annotations

from ocr_book.reconstruction.document_model import Document
from ocr_book.translation.base import TranslationEngine


class NoOpTranslator(TranslationEngine):
    """Opción "mantener idioma original": no traduce nada."""

    name = "none"

    def is_available(self) -> bool:
        return True

    def translate(self, document: Document, target_language: str, source_language: str | None = None) -> Document:
        return document
