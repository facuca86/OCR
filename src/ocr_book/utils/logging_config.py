"""Configuración centralizada de logging.

La GUI y el CLI llaman a `configure_logging()` una sola vez al arrancar; el
resto del código solo hace `logging.getLogger(__name__)`. También se ofrece
un `QueueHandler`-friendly setup para que la GUI pueda mostrar los logs en
un panel de "registro de errores" sin bloquear el hilo de la interfaz.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    extra_handlers: list[logging.Handler] | None = None,
) -> logging.Logger:
    logger = logging.getLogger("ocr_book")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    for handler in extra_handlers or []:
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger
