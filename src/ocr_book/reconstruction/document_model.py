"""Modelo de documento intermedio, independiente de cualquier formato de
salida. Cada exportador (PDF, DOCX, HTML, EPUB, TXT, Markdown) solo sabe
recorrer este árbol; ninguno sabe nada de OCR ni de layout."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    QUOTE = "quote"
    FOOTNOTE = "footnote"
    IMAGE = "image"
    TABLE = "table"


@dataclass
class TextRun:
    """Un fragmento de texto con un único estilo tipográfico uniforme."""

    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Block:
    type: BlockType
    runs: list[TextRun] = field(default_factory=list)
    level: int = 1  # nivel de encabezado (1 = título) o de anidamiento de lista
    list_ordered: bool = False
    footnote_marker: str | None = None
    first_line_indent: bool = False
    source_page: int = 0

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)

    def append_runs(self, other: list[TextRun], separator: str = " ") -> None:
        """Añade runs de otro bloque al final, insertando un separador
        entre el último run existente y el primero nuevo si hace falta.
        Se usa para fusionar un párrafo que continúa en la página o región
        siguiente."""
        if not other:
            return
        if self.runs and separator:
            last = self.runs[-1]
            first = other[0]
            if last.bold == first.bold and last.italic == first.italic:
                self.runs[-1] = TextRun(last.text + separator + first.text, last.bold, last.italic)
                self.runs.extend(other[1:])
                return
            self.runs[-1] = TextRun(last.text + separator, last.bold, last.italic)
        self.runs.extend(other)


@dataclass
class Document:
    title: str = ""
    source_language: str | None = None
    blocks: list[Block] = field(default_factory=list)

    def add(self, block: Block) -> None:
        self.blocks.append(block)
