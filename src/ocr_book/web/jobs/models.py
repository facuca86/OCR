"""Modelo de un job de conversión tal como se persiste en el store. No
confundir con `ocr_book.pipeline.progress.ProgressEvent`, que es el evento
puntual que el orquestador emite por página: `Job` es el registro
acumulado que la interfaz web expone por polling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str
    filename: str
    status: JobStatus
    config_json: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    stage: str = ""
    current: int = 0
    total: int = 0
    message: str = ""
    error: str | None = None
    page_count: int | None = None
    output_formats_json: str = "[]"
