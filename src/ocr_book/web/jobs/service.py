"""Capa que conecta una subida HTTP con el store de jobs y la cola de
procesamiento. No reimplementa detección de tipo de archivo: reutiliza
`importers.factory.get_importer` (la misma fábrica que usa el pipeline)
solo para decidir si el archivo subido es soportado, antes de guardarlo."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import fitz
from fastapi import UploadFile
from starlette.datastructures import FormData

from ocr_book.importers.factory import get_importer
from ocr_book.utils.errors import UnsupportedFileError
from ocr_book.web.config_form import build_app_config
from ocr_book.web.jobs.models import Job
from ocr_book.web.jobs.runner import JobRunner
from ocr_book.web.jobs.store import JobStore

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024


class InvalidUploadError(ValueError):
    """Error de subida apto para mostrar al usuario tal cual."""


def _safe_filename(name: str) -> str:
    return Path(name).name or "documento"


async def _save_upload(upload: UploadFile, destination: Path, max_upload_mb: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = max_upload_mb * 1024 * 1024
    written = 0
    with destination.open("wb") as out:
        while chunk := await upload.read(_CHUNK_SIZE):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                destination.unlink(missing_ok=True)
                raise InvalidUploadError(f"El archivo supera el límite de {max_upload_mb} MB.")
            out.write(chunk)
    if written == 0:
        destination.unlink(missing_ok=True)
        raise InvalidUploadError("El archivo subido está vacío.")
    return written


def _page_count(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        with fitz.open(path) as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001 - el conteo de páginas es solo informativo
        logger.warning("No se pudo contar páginas de %s", path, exc_info=True)
        return None


async def create_job(
    store: JobStore,
    runner: JobRunner,
    uploads_dir: Path,
    upload: UploadFile,
    form: FormData,
    max_upload_mb: int,
) -> Job:
    if not upload.filename:
        raise InvalidUploadError("No se recibió ningún archivo.")

    filename = _safe_filename(upload.filename)
    try:
        get_importer(Path(filename))
    except UnsupportedFileError as exc:
        raise InvalidUploadError(str(exc)) from exc

    config = build_app_config(form)  # puede lanzar InvalidJobConfigError

    job_id = uuid.uuid4().hex
    input_path = uploads_dir / job_id / "input" / filename
    await _save_upload(upload, input_path, max_upload_mb)

    page_count = _page_count(input_path)

    job = store.create_job(
        job_id=job_id,
        filename=filename,
        config_json=config.model_dump_json(),
        page_count=page_count,
    )
    runner.enqueue(job_id)
    return job
