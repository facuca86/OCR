"""Modelo de datos común que devuelve cualquier motor OCR.

Independiente del motor usado (Tesseract, PaddleOCR, EasyOCR...), para que
el resto del pipeline (layout, reconstrucción) nunca dependa de un motor
concreto.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OcrWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float  # 0-100
    block_num: int
    par_num: int
    line_num: int
    word_num: int
    is_bold: bool = False
    is_italic: bool = False

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass
class OcrLine:
    block_num: int
    par_num: int
    line_num: int
    words: list[OcrWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        lefts = [w.left for w in self.words]
        tops = [w.top for w in self.words]
        rights = [w.right for w in self.words]
        bottoms = [w.bottom for w in self.words]
        return (min(lefts), min(tops), max(rights), max(bottoms))

    @property
    def mean_confidence(self) -> float:
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)


@dataclass
class OcrResult:
    words: list[OcrWord]
    width: int
    height: int
    languages: list[str]

    @property
    def lines(self) -> list[OcrLine]:
        grouped: dict[tuple[int, int, int], OcrLine] = {}
        for word in self.words:
            key = (word.block_num, word.par_num, word.line_num)
            if key not in grouped:
                grouped[key] = OcrLine(block_num=key[0], par_num=key[1], line_num=key[2])
            grouped[key].words.append(word)
        return list(grouped.values())

    @property
    def full_text(self) -> str:
        return "\n".join(line.text for line in self.lines)
