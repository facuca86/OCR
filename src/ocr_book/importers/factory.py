"""Selecciona el importador adecuado según la extensión del archivo."""

from __future__ import annotations

from pathlib import Path

from ocr_book.importers.base import Importer, SourceDocument
from ocr_book.importers.image_importer import ImageImporter
from ocr_book.importers.pdf_importer import PdfImporter
from ocr_book.utils.errors import UnsupportedFileError

_IMPORTERS: list[Importer] = [PdfImporter(), ImageImporter()]


def get_importer(path: Path) -> Importer:
    for importer in _IMPORTERS:
        if importer.can_handle(path):
            return importer
    raise UnsupportedFileError(f"No hay importador disponible para: {path}")


def import_file(path: str | Path, dpi: int = 300) -> SourceDocument:
    path = Path(path)
    return get_importer(path).load(path, dpi=dpi)
