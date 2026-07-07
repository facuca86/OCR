"""Ejecuta jobs de a uno, en un único hilo en segundo plano, delegando
todo el trabajo real a `PipelineOrchestrator` (el mismo que usan la GUI y
la CLI). No hay pool de workers ni cola distribuida a propósito: el caso
de uso es "un libro a la vez" (ver ARCHITECTURE.md); si en el futuro hace
falta paralelizar entre libros, `JobRunner` es el único punto que cambia
(pasar de `queue.Queue` + `threading.Thread` a Celery/RQ), sin tocar rutas
HTTP ni el store."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

from ocr_book.config.schema import AppConfig
from ocr_book.pipeline.orchestrator import PipelineOrchestrator
from ocr_book.pipeline.progress import ProgressEvent
from ocr_book.web.jobs.store import JobStore

logger = logging.getLogger(__name__)

_STOP = object()


class JobRunner:
    def __init__(self, store: JobStore, uploads_dir: Path):
        self._store = store
        self._uploads_dir = uploads_dir
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="ocrbook-job-runner", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        """Pide al hilo que termine tras el job en curso (si hay uno) y
        espera hasta `timeout` segundos. Devuelve `True` si el hilo llegó a
        terminar: si el job en curso tarda más que eso, el hilo (daemon)
        sigue corriendo en segundo plano y el llamador no debe cerrar
        recursos compartidos (como la conexión SQLite) que ese job todavía
        esté usando."""
        self._queue.put(_STOP)
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def enqueue(self, job_id: str) -> None:
        self._queue.put(job_id)

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            job_id = item
            try:
                self._run_job(job_id)
            except Exception:  # noqa: BLE001 - un job roto no debe matar el hilo de la cola
                logger.exception("Fallo inesperado ejecutando el job %s", job_id)
                self._store.mark_error(job_id, "Error interno inesperado. Revisa los logs del servidor.")

    def _run_job(self, job_id: str) -> None:
        job = self._store.get_job(job_id)
        if job is None:
            logger.warning("Job %s desapareció del store antes de poder procesarse.", job_id)
            return

        job_dir = self._uploads_dir / job_id
        input_path = job_dir / "input" / job.filename
        output_dir = job_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        config = AppConfig.model_validate_json(job.config_json)
        config.export.output_dir = output_dir

        self._store.mark_running(job_id)

        def on_progress(event: ProgressEvent) -> None:
            self._store.update_progress(job_id, event.stage, event.current, event.total, event.message)

        try:
            orchestrator = PipelineOrchestrator(config)
            outputs = orchestrator.process_and_export(
                input_path,
                output_dir / Path(job.filename).stem,
                progress_callback=on_progress,
            )
        except Exception as exc:  # noqa: BLE001 - se traduce a un mensaje legible para la UI
            logger.exception("Error procesando el job %s (%s)", job_id, job.filename)
            self._store.mark_error(job_id, str(exc) or exc.__class__.__name__)
            return

        formats = [path.suffix.lstrip(".") for path in outputs]
        self._store.mark_done(job_id, formats)
