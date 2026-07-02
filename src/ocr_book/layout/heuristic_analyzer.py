"""Analizador de layout heurístico: reconstruye columnas, encabezados,
pies de página, notas al pie, numeración y títulos a partir únicamente de
la posición y el tamaño de las palabras que devuelve el motor OCR.

Ver `ARCHITECTURE.md` (sección 4) para la justificación de por qué se
eligió un enfoque heurístico en vez de un modelo de segmentación entrenado
como primera implementación.
"""

from __future__ import annotations

import statistics

from ocr_book.config.schema import LayoutConfig
from ocr_book.layout import classifiers as clf
from ocr_book.layout.base import LayoutAnalyzer
from ocr_book.layout.columns import assign_column_index, detect_column_ranges
from ocr_book.layout.models import PageLayout, Region, RegionType
from ocr_book.layout.reading_order import order_body_regions
from ocr_book.ocr.models import OcrLine, OcrResult


def _group_lines_into_blocks(lines: list[OcrLine]) -> list[list[OcrLine]]:
    """Agrupa líneas por (block_num, par_num), tal como las delimitó el
    motor OCR, preservando el orden de aparición de cada grupo."""
    groups: dict[tuple[int, int], list[OcrLine]] = {}
    order: list[tuple[int, int]] = []
    for line in lines:
        key = (line.block_num, line.par_num)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(line)
    return [groups[key] for key in order]


class HeuristicLayoutAnalyzer(LayoutAnalyzer):
    def analyze(self, ocr_result: OcrResult, config: LayoutConfig) -> PageLayout:
        page_width, page_height = ocr_result.width, ocr_result.height
        lines = [line for line in ocr_result.lines if line.text.strip()]

        header_lines, footer_lines, page_number_lines, remaining = self._split_margins(
            lines, page_height, config
        )

        blocks = _group_lines_into_blocks(remaining)
        footnote_blocks, flow_blocks = self._split_footnotes(blocks, page_height, config)

        flow_regions = self._build_flow_regions(flow_blocks, page_width, page_height, config)
        footnote_regions = [
            self._block_to_region(b, RegionType.FOOTNOTE, column_index=0) for b in footnote_blocks
        ]
        header_regions = [
            self._block_to_region(b, RegionType.HEADER, column_index=0)
            for b in _group_lines_into_blocks(header_lines)
        ]
        footer_regions = [
            self._block_to_region(b, RegionType.FOOTER, column_index=0)
            for b in _group_lines_into_blocks(footer_lines)
        ]
        page_number_regions = [
            self._block_to_region(b, RegionType.PAGE_NUMBER, column_index=0)
            for b in _group_lines_into_blocks(page_number_lines)
        ]

        header_regions.sort(key=lambda r: r.bbox[1])
        footnote_regions.sort(key=lambda r: r.bbox[1])
        footer_and_page_number = sorted(footer_regions + page_number_regions, key=lambda r: r.bbox[1])

        if config.remove_headers:
            header_regions = []
        if config.remove_footers:
            footer_and_page_number = [r for r in footer_and_page_number if r.type != RegionType.FOOTER]
        if config.remove_page_numbers:
            footer_and_page_number = [r for r in footer_and_page_number if r.type != RegionType.PAGE_NUMBER]

        all_regions = [*header_regions, *flow_regions, *footnote_regions, *footer_and_page_number]
        for i, region in enumerate(all_regions):
            region.reading_order = i

        return PageLayout(width=page_width, height=page_height, regions=all_regions)

    @staticmethod
    def _split_margins(
        lines: list[OcrLine], page_height: int, config: LayoutConfig
    ) -> tuple[list[OcrLine], list[OcrLine], list[OcrLine], list[OcrLine]]:
        header, footer, page_number, remaining = [], [], [], []
        for line in lines:
            _left, top, _right, bottom = line.bbox
            y_center = (top + bottom) / 2

            if config.detect_page_numbers and clf.looks_like_page_number(line.text) and (
                clf.is_in_header_zone(y_center, page_height) or clf.is_in_footer_zone(y_center, page_height)
            ):
                page_number.append(line)
            elif config.detect_headers and clf.is_in_header_zone(y_center, page_height):
                header.append(line)
            elif config.detect_footers and clf.is_in_footer_zone(y_center, page_height):
                footer.append(line)
            else:
                remaining.append(line)
        return header, footer, page_number, remaining

    @staticmethod
    def _split_footnotes(
        blocks: list[list[OcrLine]], page_height: int, config: LayoutConfig
    ) -> tuple[list[list[OcrLine]], list[list[OcrLine]]]:
        if not config.detect_footnotes or not blocks:
            return [], blocks

        heights = [_mean_line_height(b) for b in blocks]
        median_height = statistics.median(heights) if heights else 0.0

        footnotes, flow = [], []
        for block, height in zip(blocks, heights):
            _left, top, _right, bottom = _block_bbox(block)
            y_center = (top + bottom) / 2
            first_line_text = block[0].text
            in_zone = clf.is_in_footnote_zone(y_center, page_height)
            smaller_font = clf.is_footnote_candidate(height, median_height)
            has_marker = clf.looks_like_footnote_marker(first_line_text)
            if in_zone and (smaller_font or has_marker):
                footnotes.append(block)
            else:
                flow.append(block)
        return footnotes, flow

    def _build_flow_regions(
        self,
        blocks: list[list[OcrLine]],
        page_width: int,
        page_height: int,
        config: LayoutConfig,
    ) -> list[Region]:
        if not blocks:
            return []

        heights = [_mean_line_height(b) for b in blocks]
        body_median_height = statistics.median(heights) if heights else 0.0

        bboxes = [_block_bbox(b) for b in blocks]
        if config.detect_columns:
            column_ranges = detect_column_ranges(bboxes, 0, page_width, max_columns=config.max_columns)
        else:
            column_ranges = [(0, page_width)]

        regions: list[Region] = []
        for block, height, bbox in zip(blocks, heights, bboxes):
            top = bbox[1]
            if clf.is_title(height, body_median_height, top, page_height):
                region_type = RegionType.TITLE
            elif clf.is_heading(height, body_median_height):
                region_type = RegionType.HEADING
            else:
                region_type = RegionType.BODY_TEXT

            column_index = assign_column_index(bbox, column_ranges)
            regions.append(self._block_to_region(block, region_type, column_index))

        return order_body_regions(regions)

    @staticmethod
    def _block_to_region(block: list[OcrLine], region_type: RegionType, column_index: int) -> Region:
        first = block[0]
        return Region(
            type=region_type,
            lines=block,
            block_num=first.block_num,
            par_num=first.par_num,
            column_index=column_index,
        )


def _block_bbox(block: list[OcrLine]) -> tuple[int, int, int, int]:
    lefts, tops, rights, bottoms = zip(*(line.bbox for line in block))
    return (min(lefts), min(tops), max(rights), max(bottoms))


def _mean_line_height(block: list[OcrLine]) -> float:
    heights = [line.bbox[3] - line.bbox[1] for line in block]
    return sum(heights) / len(heights) if heights else 0.0
