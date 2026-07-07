"""Heurísticas de clasificación de regiones: encabezado, pie de página,
numeración, notas al pie, títulos y subtítulos.

Todas trabajan sobre posición relativa en la página y tamaño de fuente
relativo (altura de línea), que es la señal disponible sin recurrir a un
modelo de layout entrenado.
"""

from __future__ import annotations

import re

_PAGE_NUMBER_RE = re.compile(r"^[ivxlcdm]{1,7}$|^\d{1,4}$", re.IGNORECASE)

# Públicas: también las usa `ocr/column_ocr.py` para acotar la banda de
# cuerpo antes de dividir en columnas (un número de página u otro elemento
# centrado independiente de las columnas, situado en estas bandas, no debe
# tratarse como si perteneciera a la maquetación a columnas del cuerpo).
HEADER_ZONE_FRACTION = 0.05
FOOTER_ZONE_FRACTION = 0.08
FOOTNOTE_ZONE_FRACTION = 0.28  # banda inferior (excluyendo el pie) donde se buscan notas
_FOOTNOTE_SIZE_RATIO = 0.82
_TITLE_SIZE_RATIO = 1.4
_HEADING_SIZE_RATIO = 1.15
_TITLE_TOP_ZONE_FRACTION = 0.2


def looks_like_page_number(text: str) -> bool:
    stripped = text.strip(" .-—–")
    if not stripped or len(stripped) > 7:
        return False
    return bool(_PAGE_NUMBER_RE.match(stripped))


def is_in_header_zone(y_center: float, page_height: int) -> bool:
    return y_center <= page_height * HEADER_ZONE_FRACTION


def is_in_footer_zone(y_center: float, page_height: int) -> bool:
    return y_center >= page_height * (1 - FOOTER_ZONE_FRACTION)


def is_in_footnote_zone(y_center: float, page_height: int) -> bool:
    footer_start = page_height * (1 - FOOTER_ZONE_FRACTION)
    footnote_start = page_height * (1 - FOOTNOTE_ZONE_FRACTION)
    return footnote_start <= y_center < footer_start


def looks_like_footnote_marker(text: str) -> bool:
    """Una nota al pie suele empezar con su número/símbolo de referencia:
    "1 ...", "1. ...", "* ...", "¹...". No es concluyente por sí solo, se
    usa como señal adicional junto a la posición y el tamaño de fuente."""
    stripped = text.strip()
    return bool(re.match(r"^(\d{1,3}[.\)]?\s|\*\s|[¹²³⁴⁵⁶⁷⁸⁹]\s?)", stripped))


def is_title(mean_line_height: float, body_median_height: float, top_y: float, page_height: int) -> bool:
    if body_median_height <= 0:
        return False
    in_top_zone = top_y <= page_height * _TITLE_TOP_ZONE_FRACTION
    return in_top_zone and mean_line_height >= body_median_height * _TITLE_SIZE_RATIO


def is_heading(mean_line_height: float, body_median_height: float) -> bool:
    if body_median_height <= 0:
        return False
    return mean_line_height >= body_median_height * _HEADING_SIZE_RATIO


def is_footnote_candidate(mean_line_height: float, body_median_height: float) -> bool:
    if body_median_height <= 0:
        return False
    return mean_line_height <= body_median_height * _FOOTNOTE_SIZE_RATIO
