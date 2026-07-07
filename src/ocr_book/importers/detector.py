"""Detección de si un PDF ya contiene una capa de texto seleccionable o si
es un escaneo compuesto únicamente por imágenes."""

from __future__ import annotations

import fitz  # PyMuPDF


def page_has_meaningful_text(page: fitz.Page, min_chars: int = 20) -> bool:
    """Una página "tiene texto" si su capa de texto nativa supera un mínimo
    de caracteres no-espacio. Evita falsos positivos por marcas de agua o
    números de página sueltos que a veces sí están embebidos como texto."""
    text = page.get_text("text")
    return len(text.strip().replace("\n", "")) >= min_chars


def document_has_text_layer(doc: fitz.Document, min_fraction: float = 0.6) -> bool:
    """Un PDF se considera "con texto" si al menos `min_fraction` de sus
    páginas tienen una capa de texto significativa. Un umbral por
    proporción (en vez de "todas las páginas") tolera portadas o láminas
    sueltas sin texto dentro de un libro por lo demás digitalizado con OCR
    previo."""
    if doc.page_count == 0:
        return False
    with_text = sum(1 for page in doc if page_has_meaningful_text(page))
    return (with_text / doc.page_count) >= min_fraction
