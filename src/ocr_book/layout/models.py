"""Modelo de datos de la página tras el análisis de layout: no solo texto
en cajas, sino regiones clasificadas y ordenadas según el orden de
lectura real."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocr_book.ocr.models import OcrLine


class RegionType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    BODY_TEXT = "body_text"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    PAGE_NUMBER = "page_number"


@dataclass
class Region:
    """Una región lógica de la página (un título, un párrafo, una nota al
    pie...), ya en su posición dentro del orden de lectura."""

    type: RegionType
    lines: list[OcrLine]
    block_num: int
    par_num: int
    column_index: int
    reading_order: int = 0

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        lefts, tops, rights, bottoms = zip(*(line.bbox for line in self.lines))
        return (min(lefts), min(tops), max(rights), max(bottoms))

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def mean_line_height(self) -> float:
        heights = [line.bbox[3] - line.bbox[1] for line in self.lines]
        return sum(heights) / len(heights) if heights else 0.0


@dataclass
class PageLayout:
    width: int
    height: int
    regions: list[Region] = field(default_factory=list)

    def regions_in_reading_order(self) -> list[Region]:
        return sorted(self.regions, key=lambda r: r.reading_order)
