"""Rutas que devuelven HTML (Jinja2 + un poco de JS para el polling de
estado). Sin frontend build: plantillas servidas directamente por FastAPI,
como pidió el proyecto (simplicidad de mantenimiento por sobre
sofisticación)."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ocr_book.web import engines
from ocr_book.web.auth import COOKIE_NAME
from ocr_book.web.config import WebSettings
from ocr_book.web.dependencies import get_runner, get_settings, get_store
from ocr_book.web.jobs.service import InvalidUploadError, create_job
from ocr_book.web.jobs.store import JobStore
from ocr_book.web.jobs.runner import JobRunner

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _form_choices() -> dict:
    return {
        "ocr_engines": engines.ocr_engine_choices(),
        "translation_engines": engines.translation_engine_choices(),
        "export_formats": engines.export_format_choices(),
        "ocr_languages": engines.ocr_language_choices(),
        "translation_targets": engines.translation_target_choices(),
    }


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/") -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"next": next, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, settings: WebSettings = Depends(get_settings)) -> HTMLResponse:
    form = await request.form()
    token = str(form.get("token") or "")
    next_url = str(form.get("next") or "/")
    if not secrets.compare_digest(token, settings.token):
        return templates.TemplateResponse(
            request, "login.html", {"next": next_url, "error": "Token incorrecto."}, status_code=401
        )

    response = RedirectResponse(url=next_url or "/", status_code=303)
    response.set_cookie(COOKIE_NAME, settings.token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "upload.html", {"error": None, **_form_choices()})


@router.post("/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    file: UploadFile = File(...),
    store: JobStore = Depends(get_store),
    runner: JobRunner = Depends(get_runner),
    settings: WebSettings = Depends(get_settings),
):
    form = await request.form()
    try:
        job = await create_job(store, runner, settings.uploads_dir, file, form, settings.max_upload_mb)
    except (InvalidUploadError, ValueError) as exc:
        return templates.TemplateResponse(
            request, "upload.html", {"error": str(exc), **_form_choices()}, status_code=400
        )

    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_status_page(request: Request, job_id: str, store: JobStore = Depends(get_store)):
    job = store.get_job(job_id)
    if job is None:
        return templates.TemplateResponse(request, "job_not_found.html", {"job_id": job_id}, status_code=404)
    return templates.TemplateResponse(request, "status.html", {"job": job})


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, store: JobStore = Depends(get_store)):
    jobs = store.list_jobs()
    return templates.TemplateResponse(request, "history.html", {"jobs": jobs})


@router.post("/admin/cleanup")
def cleanup_old_jobs(
    request: Request,
    store: JobStore = Depends(get_store),
    settings: WebSettings = Depends(get_settings),
):
    import shutil

    for job in store.jobs_older_than(settings.max_job_age_days):
        shutil.rmtree(settings.uploads_dir / job.id, ignore_errors=True)
        store.delete_job(job.id)
    return RedirectResponse(url="/history", status_code=303)
