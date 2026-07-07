"""Calibra y verifica la heurística de negrita/cursiva contra renders
reales de Liberation Serif (regular/negrita/cursiva/negrita-cursiva), para
evitar que una futura modificación reintroduzca falsos positivos como los
detectados durante el desarrollo (palabras cortas sin astas marcadas como
negrita, texto regular marcado como cursiva)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from ocr_book.ocr.style_detection import detect_style, is_bold

FONT_DIR = "/usr/share/fonts/truetype/liberation"
FONTS = {
    "regular": f"{FONT_DIR}/LiberationSerif-Regular.ttf",
    "bold": f"{FONT_DIR}/LiberationSerif-Bold.ttf",
    "italic": f"{FONT_DIR}/LiberationSerif-Italic.ttf",
}
WORDS = ["Texto", "ejemplo", "varias", "letras", "different", "ex", "non", "commodo"]


def _render_word(word: str, font_path: str, size: int = 60) -> np.ndarray:
    font = ImageFont.truetype(font_path, size)
    image = Image.new("L", (500, 110), 255)
    draw = ImageDraw.Draw(image)
    draw.text((10, 15), word, font=font, fill=0)
    array = np.array(image)
    ys, xs = np.where(array < 200)
    pad = 4
    y0, y1 = max(0, ys.min() - pad), min(array.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(array.shape[1], xs.max() + pad)
    return array[y0:y1, x0:x1]


@pytest.mark.parametrize("word", WORDS)
def test_regular_text_is_not_italic(word: str) -> None:
    crop = _render_word(word, FONTS["regular"])
    is_italic, _ = detect_style(crop)
    assert not is_italic, f"falso positivo de cursiva en texto regular: {word!r}"


# "ex" y "non" quedan fuera: son palabras cortas formadas solo por letras
# redondas/rectas (n, o) que apenas aportan señal de cizalladura; la
# heurística prioriza no dar falsos positivos sobre no perderse estos
# casos límite (ver docstring de style_detection.py).
_ITALIC_RECALL_WORDS = [w for w in WORDS if w not in ("ex", "non")]


@pytest.mark.parametrize("word", _ITALIC_RECALL_WORDS)
def test_italic_text_is_detected(word: str) -> None:
    crop = _render_word(word, FONTS["italic"])
    is_italic, _ = detect_style(crop)
    assert is_italic, f"no se detectó cursiva en: {word!r}"


def test_bold_detection_relative_to_block_median() -> None:
    """Simula un bloque donde la mayoría de palabras son regulares y una es
    negrita: solo la negrita debe superar el umbral relativo al bloque."""
    regular_widths = [detect_style(_render_word(w, FONTS["regular"]))[1] for w in WORDS]
    block_median = float(np.median(regular_widths))

    for word in WORDS:
        _, width_regular = detect_style(_render_word(word, FONTS["regular"]))
        assert not is_bold(width_regular, block_median), f"falso positivo de negrita: {word!r}"

    for word in WORDS:
        _, width_bold = detect_style(_render_word(word, FONTS["bold"]))
        assert is_bold(width_bold, block_median), f"no se detectó negrita en: {word!r}"
