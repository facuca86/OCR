"""Motor OCR por defecto: Tesseract 5 (LSTM) vía `pytesseract`."""

from __future__ import annotations

import logging
import shutil
import statistics

import numpy as np
import pytesseract
from pytesseract import Output

from ocr_book.config.schema import OcrConfig
from ocr_book.ocr.base import OcrEngine
from ocr_book.ocr.models import OcrResult, OcrWord
from ocr_book.ocr.style_detection import detect_style, is_bold
from ocr_book.preprocessing.operations import to_gray
from ocr_book.utils.errors import EngineNotAvailableError

logger = logging.getLogger(__name__)


class TesseractEngine(OcrEngine):
    name = "tesseract"

    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def recognize(self, image: np.ndarray, config: OcrConfig) -> OcrResult:
        if not self.is_available():
            raise EngineNotAvailableError(
                "El binario 'tesseract' no está instalado o no está en el PATH."
            )

        gray = to_gray(image)
        lang = "+".join(config.languages) if config.languages else "eng"
        tess_config = f"--psm {config.psm} --oem {config.oem}"

        data = pytesseract.image_to_data(
            gray, lang=lang, config=tess_config, output_type=Output.DICT
        )

        words: list[OcrWord] = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            if conf < config.min_confidence:
                continue
            words.append(
                OcrWord(
                    text=text,
                    left=int(data["left"][i]),
                    top=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                    confidence=conf,
                    block_num=int(data["block_num"][i]),
                    par_num=int(data["par_num"][i]),
                    line_num=int(data["line_num"][i]),
                    word_num=int(data["word_num"][i]),
                )
            )

        if config.detect_bold_italic and words:
            self._annotate_styles(gray, words)

        return OcrResult(
            words=words,
            width=gray.shape[1],
            height=gray.shape[0],
            languages=config.languages,
        )

    @staticmethod
    def _annotate_styles(gray: np.ndarray, words: list[OcrWord]) -> None:
        """Estima negrita/cursiva por palabra. La negrita se decide en
        relación al grosor de trazo mediano del bloque al que pertenece la
        palabra (un libro con cuerpo de texto fino y títulos gruesos no
        debería marcar el cuerpo entero como negrita)."""
        h, w = gray.shape
        stroke_ratios: dict[int, list[float]] = {}
        per_word_ratio: list[float] = []
        per_word_italic: list[bool] = []

        for word in words:
            x0, y0 = max(0, word.left), max(0, word.top)
            x1, y1 = min(w, word.right), min(h, word.bottom)
            crop = gray[y0:y1, x0:x1]
            italic, ratio = detect_style(crop)
            per_word_ratio.append(ratio)
            per_word_italic.append(italic)
            stroke_ratios.setdefault(word.block_num, []).append(ratio)

        block_medians = {
            block: statistics.median(r for r in ratios if r > 0) if any(r > 0 for r in ratios) else 0.0
            for block, ratios in stroke_ratios.items()
        }

        for word, ratio, italic in zip(words, per_word_ratio, per_word_italic):
            word.is_italic = italic
            word.is_bold = is_bold(ratio, block_medians.get(word.block_num, 0.0))
