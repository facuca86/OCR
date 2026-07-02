"""Motor OCR opcional alternativo: EasyOCR (PyTorch).

Igual que PaddleOCR, EasyOCR devuelve detecciones por línea/frase, no una
jerarquía completa; se modela igual que en `paddleocr_engine.py`.
"""

from __future__ import annotations

import logging

import numpy as np

from ocr_book.config.schema import OcrConfig
from ocr_book.ocr.base import OcrEngine
from ocr_book.ocr.language_codes import to_easyocr_langs
from ocr_book.ocr.models import OcrResult, OcrWord
from ocr_book.utils.errors import EngineNotAvailableError

logger = logging.getLogger(__name__)


class EasyOcrEngine(OcrEngine):
    name = "easyocr"

    def __init__(self) -> None:
        self._reader_cache: dict[tuple[tuple[str, ...], bool], object] = {}

    def is_available(self) -> bool:
        try:
            import easyocr  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_reader(self, langs: list[str], use_gpu: bool):
        key = (tuple(langs), use_gpu)
        if key not in self._reader_cache:
            import easyocr

            self._reader_cache[key] = easyocr.Reader(langs, gpu=use_gpu, verbose=False)
        return self._reader_cache[key]

    def recognize(self, image: np.ndarray, config: OcrConfig) -> OcrResult:
        if not self.is_available():
            raise EngineNotAvailableError(
                "EasyOCR no está instalado. Instala el extra: pip install "
                "'ocr-book[easyocr]' o 'easyocr'."
            )

        langs = to_easyocr_langs(config.languages)
        reader = self._get_reader(langs, config.use_gpu)
        detections = reader.readtext(image)

        words: list[OcrWord] = []
        for line_num, (box_points, text, conf) in enumerate(detections):
            text = text.strip()
            confidence = float(conf) * 100.0
            if not text or confidence < config.min_confidence:
                continue
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            left, top = int(min(xs)), int(min(ys))
            width, height = int(max(xs) - min(xs)), int(max(ys) - min(ys))
            words.append(
                OcrWord(
                    text=text,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    confidence=confidence,
                    block_num=0,
                    par_num=0,
                    line_num=line_num,
                    word_num=0,
                )
            )

        return OcrResult(
            words=words, width=image.shape[1], height=image.shape[0], languages=config.languages
        )
