"""Modelo de datos y contrato común para todos los importadores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class SourcePage:
    """Una página de entrada, ya sea escaneada (imagen) o con texto nativo."""

    index: int
    image: np.ndarray | None  # BGR uint8, presente si hace falta OCR
    embedded_text: str | None  # texto ya seleccionable extraído del PDF, si existe
    dpi: int
    width: int
    height: int


@dataclass
class SourceDocument:
    """Resultado de importar un archivo: una secuencia de páginas."""

    source_path: Path
    pages: list[SourcePage] = field(default_factory=list)
    has_text_layer: bool = False

    def __len__(self) -> int:
        return len(self.pages)


class Importer(ABC):
    """Interfaz de un importador de archivos de entrada."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Indica si este importador sabe abrir el archivo dado."""

    @abstractmethod
    def load(self, path: Path, dpi: int = 300) -> SourceDocument:
        """Carga el archivo y devuelve sus páginas."""
