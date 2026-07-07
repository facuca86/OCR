"""Importador de archivos PDF (escaneados o con texto nativo)."""

from __future__ import annotations

from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np

from ocr_book.importers.base import Importer, SourceDocument, SourcePage
from ocr_book.importers.detector import document_has_text_layer, page_has_meaningful_text


def _extract_text_with_paragraph_breaks(page: fitz.Page) -> str:
    """`page.get_text("text")` concatena todos los bloques de texto con un
    único salto de línea, perdiendo el espacio en blanco real entre
    párrafos. `get_text("blocks")` sí conserva la segmentación en bloques
    visuales de PyMuPDF; se unen con una línea en blanco para que el
    reconstructor pueda distinguir un párrafo nuevo de un simple ajuste de
    línea, igual que hace con el texto que sale del OCR."""
    blocks = page.get_text("blocks")
    text_blocks = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
    return "\n\n".join(text_blocks)


class PdfImporter(Importer):
    """Abre un PDF, detecta automáticamente si ya tiene texto seleccionable
    y, si no, renderiza cada página como imagen de alta resolución lista
    para el pipeline de OCR."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def load(self, path: Path, dpi: int = 300) -> SourceDocument:
        doc = fitz.open(path)
        try:
            has_text_layer = document_has_text_layer(doc)
            pages: list[SourcePage] = []
            zoom = dpi / 72.0  # PyMuPDF trabaja en puntos (72 dpi por defecto)
            matrix = fitz.Matrix(zoom, zoom)

            for i, page in enumerate(doc):
                embedded_text = None
                image = None

                if has_text_layer and page_has_meaningful_text(page):
                    embedded_text = _extract_text_with_paragraph_breaks(page)
                else:
                    pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
                    arr = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )
                    image = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

                pages.append(
                    SourcePage(
                        index=i,
                        image=image,
                        embedded_text=embedded_text,
                        dpi=dpi,
                        width=image.shape[1] if image is not None else int(page.rect.width * zoom),
                        height=image.shape[0] if image is not None else int(page.rect.height * zoom),
                    )
                )

            return SourceDocument(source_path=path, pages=pages, has_text_layer=has_text_layer)
        finally:
            doc.close()
