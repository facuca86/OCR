"""Compone las operaciones de preprocesamiento según la configuración."""

from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from ocr_book.config.schema import PreprocessingConfig
from ocr_book.preprocessing import operations as ops

logger = logging.getLogger(__name__)

Operation = Callable[[np.ndarray], np.ndarray]


class PreprocessingPipeline:
    """Pipeline configurable de mejora de imagen previa al OCR.

    El orden de las operaciones importa: primero se corrige la orientación
    gruesa (90/180/270°) y la inclinación fina, luego se limpia la imagen
    (ruido, contraste), después se recortan bordes/márgenes (ya con la
    imagen enderezada) y por último se binariza, que es destructivo y debe
    ser el último paso.
    """

    def __init__(self, config: PreprocessingConfig):
        self.config = config
        self._steps: list[tuple[str, Operation]] = self._build_steps()

    def _build_steps(self) -> list[tuple[str, Operation]]:
        cfg = self.config
        # La salvaguarda de tamaño máximo se aplica siempre, incluso con el
        # resto del preprocesamiento desactivado: es una protección de
        # rendimiento, no una mejora de calidad opcional.
        steps: list[tuple[str, Operation]] = [
            ("cap_max_dimension", lambda img: ops.cap_max_dimension(img, cfg.max_dimension_px))
        ]
        if not cfg.enabled:
            return steps

        if cfg.detect_orientation:
            steps.append(("orientation", ops.correct_orientation))
        if cfg.deskew:
            steps.append(("deskew", ops.deskew))
        if cfg.denoise:
            steps.append(("denoise", ops.denoise))
        if cfg.enhance_contrast:
            steps.append(("contrast", ops.enhance_contrast))
        if cfg.remove_borders:
            steps.append(("remove_borders", ops.remove_black_borders))
        if cfg.crop_margins:
            steps.append(("crop_margins", ops.crop_margins))
        if cfg.binarize:
            steps.append(
                ("binarize", lambda img: ops.binarize(img, cfg.binarization_method.value))
            )
        return steps

    def run(self, image: np.ndarray) -> np.ndarray:
        """Aplica cada paso en orden. Si un paso falla, se registra el
        error y se continúa con la imagen previa al paso fallido: es
        preferible una página con menos mejoras que abortar un libro de
        cientos de páginas por una operación que no convergió en una."""
        result = image
        for name, step in self._steps:
            try:
                result = step(result)
            except Exception:
                logger.exception("Falló el paso de preprocesamiento '%s'; se omite.", name)
        return result
