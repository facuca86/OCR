"""Acceso a los objetos compartidos del proceso (store, cola de jobs,
ajustes) guardados en `app.state`. Un solo lugar para que las rutas no
lean `request.app.state.x` con nombres mágicos repetidos por todos lados."""

from __future__ import annotations

from fastapi import Request

from ocr_book.web.config import WebSettings
from ocr_book.web.jobs.runner import JobRunner
from ocr_book.web.jobs.store import JobStore


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner


def get_settings(request: Request) -> WebSettings:
    return request.app.state.settings
