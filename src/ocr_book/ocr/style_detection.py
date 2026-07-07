"""Detección heurística de negrita/cursiva por análisis de trazo.

Tesseract no expone de forma fiable el estilo tipográfico de cada palabra,
así que se estima a partir de la propia imagen:

- **Negrita**: el grosor medio del trazo (vía transformada de distancia
  sobre la máscara binaria de tinta) normalizado por la altura de la
  palabra, comparado contra la mediana del bloque. Un trazo
  proporcionalmente más grueso que el resto del párrafo sugiere negrita.
- **Cursiva**: se separa la palabra en componentes conexas (aprox. un
  trazo/letra cada una) y se calcula la cizalladura de cada componente con
  sus momentos de segundo orden (`mu11`/`mu02`). Usar la componente
  individual en vez de la palabra completa evita que el hueco entre
  letras y las ascendentes/descendentes distintas contaminen la medida.
  Se toma la mediana de las componentes de la palabra (robusta a letras
  redondas como "o", que no aportan señal de inclinación) y solo se marca
  cursiva si supera un umbral calibrado empíricamente contra tipos
  regulares y cursivos reales (ver `tests/test_style_detection.py`).

Es una heurística, no un clasificador entrenado: prioriza no dar falsos
positivos masivos (umbral conservador) sobre detectar el 100% de los casos.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

_ITALIC_SHEAR_THRESHOLD_DEG = -7.5
_ITALIC_MIN_COMPONENTS = 3
_ITALIC_MIN_COMPONENT_AREA = 15
_ITALIC_MIN_COMPONENT_HEIGHT_FRACTION = 0.35
_BOLD_RATIO_THRESHOLD = 1.25


def _binary_mask(gray_crop: np.ndarray) -> np.ndarray:
    if gray_crop.size == 0:
        return gray_crop
    _, mask = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return mask


def stroke_width_px(gray_crop: np.ndarray) -> float:
    """Grosor medio del trazo en píxeles (vía distance transform), sin
    normalizar por la altura del recorte.

    Deliberadamente NO se divide por la altura de la palabra: dos palabras
    del mismo tamaño de fuente pueden tener bounding boxes de alturas muy
    distintas según lleven ascendentes/descendentes ("ex" vs "commodo"),
    lo que sesgaría el grosor normalizado y produciría falsos positivos de
    negrita en palabras cortas sin astas. Al comparar el valor en píxeles
    directamente contra la mediana del bloque (mismo tamaño de fuente para
    todo el bloque), la comparación es válida sin ese sesgo.
    """
    mask = _binary_mask(gray_crop)
    ink_pixels = mask > 0
    if ink_pixels.sum() < 8:
        return 0.0
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    mean_half_width = dist[ink_pixels].mean()
    return mean_half_width * 2


def _component_shear_angles(mask: np.ndarray) -> list[float]:
    """Ángulo de cizalladura (grados) de cada componente conexa lo bastante
    grande/alta como para ser una letra o trazo real, no ruido."""
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    h_total = mask.shape[0] or 1
    angles: list[float] = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        if area < _ITALIC_MIN_COMPONENT_AREA or height < h_total * _ITALIC_MIN_COMPONENT_HEIGHT_FRACTION:
            continue
        comp_mask = (labels == i).astype(np.uint8) * 255
        moments = cv2.moments(comp_mask, binaryImage=True)
        if moments["mu02"] <= 1e-3:
            continue
        shear = moments["mu11"] / moments["mu02"]
        angles.append(math.degrees(math.atan(shear)))
    return angles


def detect_style(gray_crop: np.ndarray) -> tuple[bool, float]:
    """Devuelve (es_cursiva, grosor_de_trazo_en_px). La negrita se decide
    fuera de esta función comparando el grosor contra la mediana del
    bloque (requiere contexto de todas las palabras del bloque, que el
    llamador ya tiene)."""
    mask = _binary_mask(gray_crop)
    width_px = stroke_width_px(gray_crop)

    angles = _component_shear_angles(mask)
    if len(angles) < _ITALIC_MIN_COMPONENTS:
        is_italic = False
    else:
        is_italic = float(np.median(angles)) <= _ITALIC_SHEAR_THRESHOLD_DEG

    return is_italic, width_px


def is_bold(stroke_width: float, block_median_stroke_width: float) -> bool:
    if block_median_stroke_width <= 1e-6 or stroke_width <= 0:
        return False
    return (stroke_width / block_median_stroke_width) >= _BOLD_RATIO_THRESHOLD
