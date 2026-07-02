"""Encuentra puntos de corte horizontales "seguros" para dividir una página
en bandas antes del OCR, basados en huecos de tinta reales, no en un
porcentaje fijo de la altura.

Se usa desde `ocr/column_ocr.py` para acotar la banda de cuerpo (donde sí
tiene sentido buscar columnas) sin arriesgarse a cortar un párrafo normal
por la mitad solo porque cae dentro de una franja porcentual arbitraria:
un libro sin notas al pie puede tener texto de cuerpo hasta casi el borde
inferior de la página, y una franja fija lo partiría en dos innecesariamente.

Un hueco de tinta por sí solo no basta: el espacio entre dos líneas
seguidas de un mismo párrafo también es un hueco. La señal que sí
distingue de forma fiable un salto de sección (encabezado, nota al pie,
pie de página) de un simple salto de línea es el tamaño relativo: en
cualquier página con varias líneas, el hueco entre líneas de un mismo
párrafo es muy uniforme, mientras que el hueco antes/después de un
encabezado o nota al pie es varias veces más ancho. Por eso se calcula
primero el hueco "típico" (el más pequeño de la página, que corresponde al
interlineado normal) y solo se acepta como frontera un hueco notablemente
más ancho que ese valor de referencia.
"""

from __future__ import annotations

import cv2
import numpy as np

_SIGNIFICANCE_MULTIPLIER = 2.5
_MIN_GAP_HEIGHT_FRACTION = 0.003  # ignora ruido de binarización, no interlineados reales
_FALLBACK_MIN_FRACTION = 0.025  # umbral absoluto cuando no hay suficientes huecos para estimar el interlineado


def _binary_mask(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return mask


def _row_gaps(image: np.ndarray, min_gap_height_fraction: float) -> list[tuple[int, int]]:
    if image.shape[0] == 0:
        return []
    mask = _binary_mask(image)
    height, width = mask.shape
    ink_per_row = (mask > 0).sum(axis=1)
    is_blank_row = ink_per_row <= max(1, int(width * 0.001))

    min_gap_px = max(1, int(height * min_gap_height_fraction))
    gaps: list[tuple[int, int]] = []
    run_start: int | None = None
    for i in range(height + 1):
        blank = bool(is_blank_row[i]) if i < height else False
        if blank and run_start is None:
            run_start = i
        elif not blank and run_start is not None:
            if i - run_start >= min_gap_px:
                gaps.append((run_start, i))
            run_start = None
    return gaps


def _typical_line_gap(image: np.ndarray) -> float:
    """El hueco entre líneas más pequeño de la página, usado como unidad
    de referencia del interlineado normal. Se excluyen los márgenes
    superior/inferior de la página, que no son interlineado."""
    height = image.shape[0]
    gaps = _row_gaps(image, _MIN_GAP_HEIGHT_FRACTION)
    internal = [end - start for start, end in gaps if start > 0 and end < height]
    return min(internal) if internal else 0.0


def _significance_threshold(image: np.ndarray) -> float:
    typical_gap = _typical_line_gap(image)
    floor = image.shape[0] * _FALLBACK_MIN_FRACTION
    return max(typical_gap * _SIGNIFICANCE_MULTIPLIER, floor)


def find_header_cut(image: np.ndarray, search_fraction: float = 0.12) -> int:
    """Devuelve la fila donde termina un posible encabezado, o 0 si no hay
    ningún hueco significativamente más ancho que el interlineado normal
    dentro de la zona de búsqueda (lo que indica que el primer contenido
    de la página, sea título o cuerpo, empieza directamente)."""
    height = image.shape[0]
    search_limit = int(height * search_fraction)
    if search_limit <= 0:
        return 0

    threshold = _significance_threshold(image)
    gaps = _row_gaps(image[:search_limit], _MIN_GAP_HEIGHT_FRACTION)
    for gap_start, gap_end in gaps:
        if gap_start <= 0:
            continue  # es el margen superior de la página, no un encabezado
        if gap_end - gap_start >= threshold:
            return (gap_start + gap_end) // 2
    return 0


def find_bottom_cut(image: np.ndarray, search_fraction: float = 0.35) -> int:
    """Devuelve la fila donde empieza una posible banda inferior (nota al
    pie / pie de página / numeración), o la altura total de la imagen si
    no hay ningún hueco significativo: en ese caso el cuerpo de texto
    llega hasta el final de la página y no hace falta aislar nada."""
    height = image.shape[0]
    search_start = int(height * (1 - search_fraction))
    if search_start >= height:
        return height

    threshold = _significance_threshold(image)
    zone = image[search_start:]
    gaps = _row_gaps(zone, _MIN_GAP_HEIGHT_FRACTION)
    for gap_start, gap_end in gaps:
        if gap_end - gap_start >= threshold:
            return search_start + (gap_start + gap_end) // 2
    return height
