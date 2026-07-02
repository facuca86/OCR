"""Ejecuta el pipeline en un hilo aparte para no bloquear la interfaz.

`PipelineOrchestrator` ya reparte el trabajo pesado entre procesos; este
`QObject` solo se encarga de invocarlo desde un `QThread` y traducir sus
callbacks de progreso a señales Qt, que sí pueden cruzar de forma segura
al hilo de la interfaz.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ocr_book.config.schema import AppConfig
from ocr_book.pipeline.orchestrator import PipelineOrchestrator
from ocr_book.pipeline.progress import ProgressEvent
from ocr_book.utils.errors import PipelineCancelledError


class ConversionWorker(QObject):
    progress = Signal(object)  # ProgressEvent
    log_message = Signal(str)
    finished = Signal(list)  # list[Path]
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, config: AppConfig, input_path: Path, output_basename: Path):
        super().__init__()
        self.config = config
        self.input_path = input_path
        self.output_basename = output_basename
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        orchestrator = PipelineOrchestrator(self.config)

        def on_progress(event: ProgressEvent) -> None:
            self.progress.emit(event)
            self.log_message.emit(f"[{event.stage}] {event.current}/{event.total} {event.message}")

        try:
            outputs = orchestrator.process_and_export(
                self.input_path,
                self.output_basename,
                progress_callback=on_progress,
                cancel_event=self.cancel_event,
            )
        except PipelineCancelledError:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001 - se reporta a la UI, no se relanza
            self.failed.emit(str(exc))
            return

        self.finished.emit(outputs)
