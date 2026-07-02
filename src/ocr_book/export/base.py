"""Interfaz común de exportador."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.reconstruction.document_model import Document


class Exporter(ABC):
    extension: str = ""

    @abstractmethod
    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        """Escribe el documento en `output_path` y devuelve la ruta final."""
