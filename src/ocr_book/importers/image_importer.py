"""Importador de imágenes sueltas (jpg, png, tif, tiff) como página única."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ocr_book.importers.base import Importer, SourceDocument, SourcePage
from ocr_book.utils.errors import UnsupportedFileError

_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


class ImageImporter(Importer):
    """Carga una imagen individual (o un TIFF multipágina) como documento."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in _SUPPORTED_SUFFIXES

    def load(self, path: Path, dpi: int = 300) -> SourceDocument:
        if not self.can_handle(path):
            raise UnsupportedFileError(f"Formato de imagen no soportado: {path.suffix}")

        pages: list[SourcePage] = []
        with Image.open(path) as pil_image:
            frame_count = getattr(pil_image, "n_frames", 1)
            source_dpi = pil_image.info.get("dpi", (dpi, dpi))[0] or dpi

            for i in range(frame_count):
                pil_image.seek(i)
                rgb = pil_image.convert("RGB")
                array = np.array(rgb)
                bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                pages.append(
                    SourcePage(
                        index=i,
                        image=bgr,
                        embedded_text=None,
                        dpi=int(source_dpi),
                        width=bgr.shape[1],
                        height=bgr.shape[0],
                    )
                )

        return SourceDocument(source_path=path, pages=pages, has_text_layer=False)
