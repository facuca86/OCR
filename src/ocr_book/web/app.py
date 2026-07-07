"""Fábrica de la aplicación FastAPI. `create_app` no lee variables de
entorno directamente: recibe (o construye) un `WebSettings`, para que los
tests puedan pasar un `workdir` y un `token` propios sin pisar un servidor
real corriendo en la misma máquina."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, Response

from ocr_book.web.auth import TokenAuthMiddleware
from ocr_book.web.config import WebSettings, load_settings_from_env
from ocr_book.web.jobs.runner import JobRunner
from ocr_book.web.jobs.store import JobStore
from ocr_book.web.routes import api, pages

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or load_settings_from_env()
    settings.ensure_dirs()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = JobStore(settings.db_path)
        runner = JobRunner(store, settings.uploads_dir)
        runner.start()

        app.state.settings = settings
        app.state.store = store
        app.state.runner = runner

        if settings.token_was_generated:
            logger.warning(
                "OCRBOOK_WEB_TOKEN no está definido: se generó un token temporal para "
                "esta ejecución. Definí la variable de entorno para tener un token "
                "estable entre reinicios. Token de esta sesión: %s",
                settings.token,
            )

        yield

        if runner.stop():
            store.close()
        else:
            logger.warning(
                "El job en curso no terminó al apagar el servidor; se deja la conexión "
                "de la base de datos abierta para que el hilo en segundo plano pueda "
                "seguir escribiendo su resultado."
            )

    app = FastAPI(title="OCR Book — interfaz web", lifespan=lifespan)
    app.add_middleware(TokenAuthMiddleware, token=settings.token)

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    app.include_router(pages.router)
    app.include_router(api.router)

    return app
