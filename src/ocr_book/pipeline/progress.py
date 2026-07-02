"""Modelo de progreso reportado por el pipeline: la GUI y el CLI se
suscriben con un simple `Callable[[ProgressEvent], None]`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ProgressEvent:
    stage: str  # "import", "ocr", "reconstruction", "translation", "export"
    current: int
    total: int
    message: str = ""


ProgressCallback = Callable[[ProgressEvent], None]


def noop_progress(_event: ProgressEvent) -> None:
    pass
