"""Punto de entrada de la interfaz gráfica."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ocr_book.gui.main_window import MainWindow
from ocr_book.gui.styles import APP_STYLE
from ocr_book.utils.logging_config import configure_logging


def run_gui() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
