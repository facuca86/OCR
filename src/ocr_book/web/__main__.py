"""Punto de entrada del servidor web: `ocrbook-web` (ver pyproject.toml) o
`python -m ocr_book.web`."""

from __future__ import annotations

import logging

import uvicorn

from ocr_book.utils.logging_config import configure_logging
from ocr_book.web.app import create_app
from ocr_book.web.config import load_settings_from_env


def main() -> None:
    configure_logging(level=logging.INFO)
    settings = load_settings_from_env()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
