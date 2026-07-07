"""API JSON: pensada tanto para el JS de las páginas (polling de estado)
como para uso programático/tests (`Authorization: Bearer <token>`)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

from ocr_book.web import engines
from ocr_book.web.config import WebSettings
from ocr_book.web.dependencies import get_runner, get_settings, get_store
from ocr_book.web.jobs.service import InvalidUploadError, create_job
from ocr_book.web.jobs.store import JobStore
from ocr_book.web.jobs.runner import JobRunner
from ocr_book.web.schemas import EnginesResponse, JobStatusResponse

router = APIRouter(prefix="/api")


@router.get("/engines", response_model=EnginesResponse)
def list_engines() -> EnginesResponse:
    return EnginesResponse(
        ocr_engines=[{"value": v, "label": lbl, "available": av} for v, lbl, av in engines.ocr_engine_choices()],
        translation_engines=[
            {"value": v, "label": lbl, "available": av} for v, lbl, av in engines.translation_engine_choices()
        ],
        export_formats=engines.export_format_choices(),
        ocr_languages=[{"value": v, "label": lbl} for v, lbl in engines.ocr_language_choices()],
        translation_target_languages=[
            {"value": v, "label": lbl} for v, lbl in engines.translation_target_choices()
        ],
    )


@router.post("/jobs", response_model=JobStatusResponse, status_code=201)
async def api_create_job(
    request: Request,
    file: UploadFile = File(...),
    store: JobStore = Depends(get_store),
    runner: JobRunner = Depends(get_runner),
    settings: WebSettings = Depends(get_settings),
) -> JobStatusResponse:
    form = await request.form()
    try:
        job = await create_job(store, runner, settings.uploads_dir, file, form, settings.max_upload_mb)
    except (InvalidUploadError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JobStatusResponse.from_job(job)


@router.get("/jobs", response_model=list[JobStatusResponse])
def api_list_jobs(store: JobStore = Depends(get_store)) -> list[JobStatusResponse]:
    return [JobStatusResponse.from_job(job) for job in store.list_jobs()]


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
def api_job_status(job_id: str, store: JobStore = Depends(get_store)) -> JobStatusResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe un job con ese id.")
    return JobStatusResponse.from_job(job)


@router.get("/jobs/{job_id}/download/{fmt}")
def api_download(
    job_id: str,
    fmt: str,
    store: JobStore = Depends(get_store),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe un job con ese id.")

    available_formats = json.loads(job.output_formats_json)
    if fmt not in available_formats:
        raise HTTPException(status_code=404, detail=f"El job no generó una salida en formato '{fmt}'.")

    output_dir = settings.uploads_dir / job_id / "output"
    stem = Path(job.filename).stem
    matches = list(output_dir.glob(f"{stem}.{fmt}"))
    if not matches:
        raise HTTPException(status_code=404, detail="El archivo de salida ya no está disponible.")

    return FileResponse(matches[0], filename=matches[0].name)


@router.get("/jobs/{job_id}/preview")
def api_preview(
    job_id: str,
    store: JobStore = Depends(get_store),
    settings: WebSettings = Depends(get_settings),
) -> FileResponse:
    """Igual que `/download/html` pero sin `Content-Disposition: attachment`,
    para poder embeberla en un <iframe> en vez de forzar la descarga."""
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe un job con ese id.")
    if "html" not in json.loads(job.output_formats_json):
        raise HTTPException(status_code=404, detail="Este job no generó una vista previa HTML.")

    output_dir = settings.uploads_dir / job_id / "output"
    stem = Path(job.filename).stem
    matches = list(output_dir.glob(f"{stem}.html"))
    if not matches:
        raise HTTPException(status_code=404, detail="La vista previa ya no está disponible.")

    return FileResponse(matches[0], media_type="text/html")
