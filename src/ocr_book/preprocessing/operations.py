"""Operaciones de preprocesamiento de imagen, cada una `ndarray -> ndarray`.

Se mantienen como funciones puras (sin estado) para que `PreprocessingPipeline`
pueda componerlas libremente según la configuración del usuario.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

logger = logging.getLogger(__name__)

_ROTATE_MAP = {
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def cap_max_dimension(image: np.ndarray, max_dimension_px: int) -> np.ndarray:
    """Reduce la imagen si su lado mayor supera `max_dimension_px`,
    manteniendo la relación de aspecto. Es una salvaguarda de rendimiento:
    un escaneo a una resolución inusualmente alta no debería multiplicar
    el tiempo de proceso de forma desproporcionada respecto a la mejora de
    calidad que aporta (los pasos siguientes, sobre todo el filtrado de
    ruido, escalan con el número de píxeles)."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dimension_px:
        return image
    scale = max_dimension_px / longest
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def correct_orientation(image: np.ndarray) -> np.ndarray:
    """Detecta si la página está rotada 90/180/270 grados (por ejemplo, un
    escaneo apaisado) usando el clasificador OSD de Tesseract y la endereza."""
    gray = to_gray(image)
    try:
        osd = pytesseract.image_to_osd(gray, output_type=Output.DICT)
    except pytesseract.TesseractError as exc:
        logger.debug("OSD no pudo determinar la orientación: %s", exc)
        return image

    rotate = int(osd.get("rotate", 0)) % 360
    cv2_code = _ROTATE_MAP.get(rotate)
    if cv2_code is None:
        return image
    return cv2.rotate(image, cv2_code)


def rotate_image(image: np.ndarray, angle_degrees: float) -> np.ndarray:
    """Rota la imagen `angle_degrees` (positivo = sentido antihorario)
    conservando el lienzo completo (sin recortar esquinas) y rellenando en
    blanco los bordes nuevos."""
    if abs(angle_degrees) < 0.05:
        return image
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)

    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += (new_w / 2) - center[0]
    matrix[1, 2] += (new_h / 2) - center[1]

    border_value = (255, 255, 255) if image.ndim == 3 else 255
    return cv2.warpAffine(
        image, matrix, (new_w, new_h), flags=cv2.INTER_CUBIC, borderValue=border_value
    )


def deskew(image: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Estima la inclinación fina del texto (a diferencia de
    `correct_orientation`, que solo corrige múltiplos de 90°) mediante el
    rectángulo de área mínima que envuelve los píxeles de tinta."""
    gray = to_gray(image)
    _, thresh = cv2.threshold(255 - gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) > max_angle:
        return image
    return rotate_image(image, -angle)


def denoise(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 21)
    return cv2.fastNlMeansDenoising(image, None, 6, 7, 21)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE sobre el canal de luminancia: mejora el contraste local sin
    sobre-saturar zonas ya claras, a diferencia de una ecualización global."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    if image.ndim == 2:
        return clahe.apply(image)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    luminance, a, b = cv2.split(lab)
    luminance = clahe.apply(luminance)
    merged = cv2.merge((luminance, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def remove_black_borders(
    image: np.ndarray, max_border_fraction: float = 0.15, dark_threshold: float = 50.0
) -> np.ndarray:
    """Recorta el marco negro típico de los escáneres de sobremesa: filas y
    columnas casi completamente oscuras pegadas al borde de la imagen."""
    gray = to_gray(image)
    h, w = gray.shape

    top, bottom, left, right = 0, h, 0, w
    max_top = int(h * max_border_fraction)
    while top < max_top and gray[top, :].mean() < dark_threshold:
        top += 1

    min_bottom = h - int(h * max_border_fraction)
    while bottom > min_bottom and gray[bottom - 1, :].mean() < dark_threshold:
        bottom -= 1

    max_left = int(w * max_border_fraction)
    while left < max_left and gray[:, left].mean() < dark_threshold:
        left += 1

    min_right = w - int(w * max_border_fraction)
    while right > min_right and gray[:, right - 1].mean() < dark_threshold:
        right -= 1

    if bottom <= top or right <= left:
        return image
    return image[top:bottom, left:right]


def crop_margins(image: np.ndarray, padding_fraction: float = 0.02) -> np.ndarray:
    """Recorta el margen de papel en blanco sobrante alrededor del
    contenido real, dejando un pequeño respiro (`padding_fraction`)."""
    gray = to_gray(image)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return image

    x, y, w, h = cv2.boundingRect(coords)
    pad_x = int(image.shape[1] * padding_fraction)
    pad_y = int(image.shape[0] * padding_fraction)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(image.shape[1], x + w + pad_x)
    y1 = min(image.shape[0], y + h + pad_y)
    if x1 <= x0 or y1 <= y0:
        return image
    return image[y0:y1, x0:x1]


def _sauvola_threshold(gray: np.ndarray, window: int = 25, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """Binarización de Sauvola, implementada sin dependencias extra:
    mejor que Otsu en páginas con iluminación desigual o manchas."""
    gray_f = gray.astype(np.float64)
    mean = cv2.boxFilter(gray_f, ddepth=-1, ksize=(window, window))
    mean_sq = cv2.boxFilter(gray_f * gray_f, ddepth=-1, ksize=(window, window))
    variance = np.maximum(mean_sq - mean * mean, 0)
    std = np.sqrt(variance)
    threshold = mean * (1 + k * ((std / r) - 1))
    return np.where(gray_f > threshold, 255, 0).astype(np.uint8)


def binarize(image: np.ndarray, method: str = "adaptive_gaussian") -> np.ndarray:
    gray = to_gray(image)
    if method == "none":
        return image
    if method == "otsu":
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return out
    if method == "adaptive_gaussian":
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )
    if method == "sauvola":
        return _sauvola_threshold(gray)
    raise ValueError(f"Método de binarización desconocido: {method}")
