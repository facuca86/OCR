"""Construye el `Document` final a partir del layout ya clasificado de
cada página, en tres pasadas:

1. Cada `Region` de cada página se convierte en uno o más `Block`
   (una región de cuerpo puede contener más de un párrafo).
2. Los párrafos de cita se detectan comparando el margen de cada región
   contra el margen habitual de la columna.
3. Una pasada final recorre todo el documento (a través de páginas)
   fusionando un párrafo con el siguiente cuando el primero no termina en
   puntuación fuerte: así se reconstruyen párrafos que la paginación o el
   análisis de layout cortaron a mitad de frase, incluyendo párrafos que
   continúan de una página a la siguiente.
"""

from __future__ import annotations

import re
import statistics

from ocr_book.layout.models import PageLayout, Region, RegionType
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun
from ocr_book.reconstruction.text_joiner import (
    build_runs,
    dominant_style,
    ends_sentence,
    estimate_indent_threshold,
    is_first_line_indented,
    looks_like_list_item,
    split_into_paragraphs,
)

_REGION_TO_BLOCK_TYPE = {
    RegionType.TITLE: BlockType.TITLE,
    RegionType.HEADING: BlockType.HEADING,
}

_QUOTE_INDENT_MULTIPLIER = 1.8
_FOOTNOTE_MARKER_RE = re.compile(r"^(\d{1,3})[.\)]?\s+")


class DocumentReconstructor:
    """Recibe el layout de cada página (en el orden del libro) y produce
    un `Document` reflowed, listo para exportar a cualquier formato.

    Los encabezados, pies de página y números de página nunca forman parte
    del documento reconstruido: son artefactos de la paginación del
    escaneo, no contenido del libro, y no tienen cabida en un ebook
    reflowed. Si el usuario quiere conservarlos por completo, debe
    desactivar su detección en `LayoutConfig` (`remove_headers=False`,
    etc.) para que el análisis de layout no los separe del cuerpo."""

    def build(self, page_layouts: list[PageLayout]) -> Document:
        document = Document()

        # Referencia de margen de columna por página, para detectar citas
        # (párrafos con sangría simétrica mayor a la del resto del cuerpo).
        for page_index, layout in enumerate(page_layouts):
            column_left_margins = self._column_left_margins(layout)
            for region in layout.regions_in_reading_order():
                blocks = self._region_to_blocks(region, page_index, column_left_margins)
                for block in blocks:
                    document.add(block)

        self._merge_continued_paragraphs(document)
        document.title = self._infer_title(document)
        return document

    @staticmethod
    def _column_left_margins(layout: PageLayout) -> dict[int, float]:
        by_column: dict[int, list[float]] = {}
        for region in layout.regions:
            if region.type != RegionType.BODY_TEXT:
                continue
            by_column.setdefault(region.column_index, []).append(region.bbox[0])
        return {col: statistics.median(lefts) for col, lefts in by_column.items()}

    def _region_to_blocks(
        self, region: Region, page_index: int, column_left_margins: dict[int, float]
    ) -> list[Block]:
        if region.type in (RegionType.HEADER, RegionType.FOOTER, RegionType.PAGE_NUMBER):
            return []

        if region.type in _REGION_TO_BLOCK_TYPE:
            return [self._build_heading_block(region, page_index)]

        if region.type == RegionType.FOOTNOTE:
            return [self._build_footnote_block(region, page_index)]

        return self._build_body_blocks(region, page_index, column_left_margins)

    @staticmethod
    def _build_heading_block(region: Region, page_index: int) -> Block:
        all_words = [w for line in region.lines for w in line.words]
        bold, italic = dominant_style(all_words)
        text = " ".join(line.text for line in region.lines)
        return Block(
            type=_REGION_TO_BLOCK_TYPE[region.type],
            runs=[TextRun(text, bold=bold, italic=italic)],
            level=1 if region.type == RegionType.TITLE else 2,
            source_page=page_index,
        )

    @staticmethod
    def _build_footnote_block(region: Region, page_index: int) -> Block:
        runs = build_runs(region.lines)
        marker = None
        if runs:
            match = _FOOTNOTE_MARKER_RE.match(runs[0].text)
            if match:
                marker = match.group(1)
                runs[0] = TextRun(runs[0].text[match.end() :], runs[0].bold, runs[0].italic)
        return Block(type=BlockType.FOOTNOTE, runs=runs, footnote_marker=marker, source_page=page_index)

    def _build_body_blocks(
        self, region: Region, page_index: int, column_left_margins: dict[int, float]
    ) -> list[Block]:
        paragraphs = split_into_paragraphs(region.lines)
        if not paragraphs:
            return []

        indent_threshold = estimate_indent_threshold(region.lines)
        baseline_left = statistics.median(line.bbox[0] for line in region.lines)
        column_baseline = column_left_margins.get(region.column_index, baseline_left)

        blocks: list[Block] = []
        for paragraph_lines in paragraphs:
            runs = build_runs(paragraph_lines)
            if not runs:
                continue

            first_text = paragraph_lines[0].text
            is_list, is_ordered = looks_like_list_item(first_text)
            indented = is_first_line_indented(paragraph_lines, baseline_left, indent_threshold)

            paragraph_left = statistics.median(line.bbox[0] for line in paragraph_lines)
            paragraph_right = statistics.median(line.bbox[2] for line in paragraph_lines)
            region_right = region.bbox[2]
            is_quote = (
                len(paragraph_lines) > 1
                and (paragraph_left - column_baseline) > indent_threshold * _QUOTE_INDENT_MULTIPLIER
                and (region_right - paragraph_right) > indent_threshold
            )

            if is_list:
                block_type = BlockType.LIST_ITEM
            elif is_quote:
                block_type = BlockType.QUOTE
            else:
                block_type = BlockType.PARAGRAPH

            blocks.append(
                Block(
                    type=block_type,
                    runs=runs,
                    list_ordered=is_ordered,
                    first_line_indent=indented,
                    source_page=page_index,
                )
            )
        return blocks

    @staticmethod
    def _merge_continued_paragraphs(document: Document) -> None:
        """Un párrafo que no termina en puntuación fuerte casi siempre
        continúa en el siguiente bloque de texto corrido (misma página o
        página siguiente), salvo que ese siguiente bloque sea en realidad
        un título, una cita, una lista o una nota: esos sí representan un
        cambio de estructura real."""
        mergeable_types = {BlockType.PARAGRAPH}
        merged: list[Block] = []
        for block in document.blocks:
            if (
                merged
                and merged[-1].type in mergeable_types
                and block.type in mergeable_types
                and not ends_sentence(merged[-1].text)
            ):
                merged[-1].append_runs(block.runs)
                continue
            merged.append(block)
        document.blocks = merged

    @staticmethod
    def _infer_title(document: Document) -> str:
        for block in document.blocks:
            if block.type == BlockType.TITLE:
                return block.text
        return ""
