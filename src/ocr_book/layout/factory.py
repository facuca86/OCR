from __future__ import annotations

from ocr_book.config.schema import LayoutAnalyzerName, LayoutConfig
from ocr_book.layout.base import LayoutAnalyzer
from ocr_book.layout.heuristic_analyzer import HeuristicLayoutAnalyzer

_ANALYZERS = {
    LayoutAnalyzerName.HEURISTIC: HeuristicLayoutAnalyzer,
}


def get_layout_analyzer(config: LayoutConfig) -> LayoutAnalyzer:
    return _ANALYZERS[config.analyzer]()
