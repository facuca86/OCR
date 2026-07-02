"""Detección de columnas por proyección de cobertura horizontal.

Hay dos formas de obtener la "cobertura" que se proyecta sobre el eje X:

- **Desde píxeles de tinta** (`detect_column_ranges_from_image`): se usa
  *antes* de pasar la página al motor OCR. Es la forma robusta y la que se
  usa por defecto, porque motores como Tesseract, al segmentar
  automáticamente una página con columnas muy próximas entre sí, a veces
  fusionan ambas columnas en un único bloque y mezclan palabras de una y
  otra dentro de la misma línea — a esa altura ya no hay forma de separar
  limpiamente el texto. Detectar las columnas en la imagen y pasarle a
  cada motor OCR un recorte por columna evita el problema de raíz.
- **Desde cajas de palabras ya reconocidas** (`detect_column_ranges`): se
  mantiene como utilidad para motores que no exponen una jerarquía de
  bloques (PaddleOCR, EasyOCR) y como respaldo general.
"""

from __future__ import annotations

import cv2
import numpy as np


def _ranges_from_coverage(
    coverage: np.ndarray,
    region_left: int,
    max_columns: int,
    min_gap_fraction: float,
    min_column_fraction: float,
) -> list[tuple[int, int]]:
    width = coverage.shape[0]
    fallback = [(region_left, region_left + width)]
    if width <= 0:
        return fallback

    runs: list[list[int]] = []
    in_run = False
    run_start = 0
    for i in range(width + 1):
        covered = bool(coverage[i]) if i < width else False
        if covered and not in_run:
            in_run, run_start = True, i
        elif not covered and in_run:
            in_run = False
            runs.append([run_start, i])

    min_gap_px = max(1, int(width * min_gap_fraction))
    merged: list[list[int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < min_gap_px:
            merged[-1][1] = run[1]
        else:
            merged.append(run)

    min_col_px = max(1, int(width * min_column_fraction))
    merged = [m for m in merged if m[1] - m[0] >= min_col_px]

    if not merged or len(merged) > max_columns:
        return fallback

    return [(region_left + m[0], region_left + m[1]) for m in merged]


def detect_column_ranges(
    bboxes: list[tuple[int, int, int, int]],
    region_left: int,
    region_right: int,
    max_columns: int = 4,
    min_gap_fraction: float = 0.015,
    min_column_fraction: float = 0.05,
) -> list[tuple[int, int]]:
    """Detecta columnas a partir de las cajas de bloques de texto ya
    reconocidos. Ver el aviso en el docstring del módulo: úsese solo con
    motores que ya devuelven bloques limpiamente separados por columna."""
    width = region_right - region_left
    if width <= 0 or not bboxes:
        return [(region_left, region_right)]

    coverage = np.zeros(width, dtype=bool)
    for left, _top, right, _bottom in bboxes:
        l0 = max(0, left - region_left)
        r0 = min(width, right - region_left)
        if r0 > l0:
            coverage[l0:r0] = True

    return _ranges_from_coverage(coverage, region_left, max_columns, min_gap_fraction, min_column_fraction)


def detect_column_ranges_from_image(
    gray_or_binary: np.ndarray,
    max_columns: int = 4,
    min_gap_fraction: float = 0.02,
    min_column_fraction: float = 0.08,
    min_ink_row_fraction: float = 0.001,
) -> list[tuple[int, int]]:
    """Detecta columnas proyectando los píxeles de tinta de toda la página
    sobre el eje X, antes de ejecutar el OCR. Una columna del eje X se
    considera "cubierta" si al menos `min_ink_row_fraction` de los píxeles
    de esa columna (a lo alto de toda la página) son tinta: eso ignora
    ruido puntual sin exigir que la columna esté "llena"."""
    if gray_or_binary.ndim == 3:
        gray = cv2.cvtColor(gray_or_binary, cv2.COLOR_BGR2GRAY)
    else:
        gray = gray_or_binary

    # THRESH_OTSU con una imagen ya binarizada (solo 0/255) sigue
    # funcionando correctamente: el histograma bimodal hace que el umbral
    # elegido caiga justo en medio.
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    height = mask.shape[0] or 1
    ink_per_column = (mask > 0).sum(axis=0)
    coverage = ink_per_column >= max(1, int(height * min_ink_row_fraction))

    return _ranges_from_coverage(coverage, 0, max_columns, min_gap_fraction, min_column_fraction)


def assign_column_index(
    bbox: tuple[int, int, int, int], column_ranges: list[tuple[int, int]], spanning_fraction: float = 0.7
) -> int:
    """-1 si el bloque cubre casi todo el ancho de la región (un título o
    encabezado de sección que atraviesa varias columnas); en otro caso, el
    índice de la columna cuyo rango contiene el centro del bloque."""
    left, _top, right, _bottom = bbox
    total_width = column_ranges[-1][1] - column_ranges[0][0] if column_ranges else 1
    if total_width > 0 and (right - left) >= spanning_fraction * total_width and len(column_ranges) > 1:
        return -1

    center_x = (left + right) / 2
    best_index = 0
    best_distance = float("inf")
    for i, (col_left, col_right) in enumerate(column_ranges):
        if col_left <= center_x <= col_right:
            return i
        distance = min(abs(center_x - col_left), abs(center_x - col_right))
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return best_index
