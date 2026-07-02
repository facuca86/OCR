"""Motor OCR opcional de alta precisión: PaddleOCR.

Se importa de forma perezosa: si `paddleocr`/`paddlepaddle` no están
instalados, `is_available()` devuelve False y el resto de la aplicación
sigue funcionando con Tesseract, sin que falte el import rompa nada.

PaddleOCR detecta y reconoce por *línea* (no expone una jerarquía
bloque/párrafo/línea/palabra como Tesseract), así que aquí cada línea
detectada se modela como una única "palabra" de texto completo, con
`block_num=0` fijo. El analizador de layout heurístico sigue funcionando
sobre estas cajas de línea, aunque con menos granularidad que con
Tesseract.
"""

from __future__ import annotations

import logging

import numpy as np

from ocr_book.config.schema import OcrConfig
from ocr_book.ocr.base import OcrEngine
from ocr_book.ocr.language_codes import to_paddleocr_lang
from ocr_book.ocr.models import OcrResult, OcrWord
from ocr_book.utils.errors import EngineNotAvailableError

logger = logging.getLogger(__name__)


class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"

    def __init__(self) -> None:
        self._reader_cache: dict[tuple[str, bool], object] = {}

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_reader(self, lang: str, use_gpu: bool):
        key = (lang, use_gpu)
        if key not in self._reader_cache:
            from paddleocr import PaddleOCR

            self._reader_cache[key] = PaddleOCR(
                use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False
            )
        return self._reader_cache[key]

    def recognize(self, image: np.ndarray, config: OcrConfig) -> OcrResult:
        if not self.is_available():
            raise EngineNotAvailableError(
                "PaddleOCR no está instalado. Instala el extra: pip install "
                "'ocr-book[paddleocr]' o 'paddleocr paddlepaddle'."
            )

        lang = to_paddleocr_lang(config.languages)
        reader = self._get_reader(lang, config.use_gpu)
        raw_result = reader.ocr(image, cls=True)

        words: list[OcrWord] = []
        # raw_result: lista (una por imagen) de [ [box_points, (text, conf)], ... ]
        detections = raw_result[0] if raw_result else []
        for line_num, detection in enumerate(detections or []):
            box_points, (text, conf) = detection
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
