"""Zona de arrastrar y soltar archivos (PDF o imágenes)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_ACCEPTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


class DropZone(QWidget):
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        self._label = QLabel(
            "Arrastra aquí tus PDF o imágenes escaneadas\n(o haz clic en \"Añadir archivos…\")"
        )
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self._has_accepted_file(event):
            self.setProperty("dragOver", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in _ACCEPTED_SUFFIXES
        ]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    @staticmethod
    def _has_accepted_file(event: QDragEnterEvent) -> bool:
        return any(
            Path(url.toLocalFile()).suffix.lower() in _ACCEPTED_SUFFIXES
            for url in event.mimeData().urls()
            if url.isLocalFile()
        )
