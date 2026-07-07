"""Trabajo por página, ejecutado en procesos separados.

`ProcessPoolExecutor` no puede compartir un motor OCR ya cargado entre
procesos (más aún si carga un modelo en GPU), así que cada proceso
trabajador construye su propio preprocesador/motor/analizador **una sola
vez**, en `init_worker`, y los reutiliza para todas las páginas que le
toquen — cargar un modelo por página sería prohibitivamente lento.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

from ocr_book.config.schema import AppConfig
from ocr_book.layout.factory import get_layout_analyzer
from ocr_book.layout.models import PageLayout
from ocr_book.ocr.column_ocr import recognize_with_columns
from ocr_book.ocr.engine_factory import get_engine
from ocr_book.preprocessing.pipeline import PreprocessingPipeline

_worker_state: dict = {}


def init_worker(config: AppConfig) -> None:
    # La paralelización real ocurre entre procesos (una página por
    # worker); si además OpenCV y Tesseract intentan usar todos los
    # núcleos DENTRO de cada proceso, N workers sobresuscriben la CPU muy
    # por encima de los núcleos físicos y el tiempo por página se dispara
    # en vez de mejorar. Cada worker se limita a un solo hilo interno.
    cv2.setNumThreads(1)
    os.environ["OMP_THREAD_LIMIT"] = "1"

    _worker_state["pipeline"] = PreprocessingPipeline(config.preprocessing)
    _worker_state["engine"] = get_engine(config.ocr)
    _worker_state["analyzer"] = get_layout_analyzer(config.layout)
    _worker_state["config"] = config


def process_page(image: np.ndarray) -> PageLayout:
    state = _worker_state
    config: AppConfig = state["config"]
    processed = state["pipeline"].run(image)
    ocr_result = recognize_with_columns(state["engine"], processed, config.ocr, config.layout)
    return state["analyzer"].analyze(ocr_result, config.layout)
