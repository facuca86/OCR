"""Configuración de la interfaz web, separada de `ocr_book.config` (que es
la configuración del *pipeline*, no del servidor). Se lee de variables de
entorno para facilitar el despliegue (contenedor, systemd, etc.) sin tocar
archivos."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WebSettings:
    """Ajustes del servidor web. `token` protege el acceso; si no se
    define explícitamente por variable de entorno se genera uno aleatorio
    al arrancar y se imprime en el log, para no dejar la instancia abierta
    por defecto."""

    token: str = field(default_factory=lambda: "")
    workdir: Path = field(default_factory=lambda: Path("./web_data"))
    max_job_age_days: int = 30
    max_upload_mb: int = 300
    host: str = "127.0.0.1"
    port: int = 8000
    token_was_generated: bool = False

    @property
    def uploads_dir(self) -> Path:
        return self.workdir / "jobs"

    @property
    def db_path(self) -> Path:
        return self.workdir / "jobs.db"

    def ensure_dirs(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


def load_settings_from_env() -> WebSettings:
    token = os.environ.get("OCRBOOK_WEB_TOKEN", "").strip()
    generated = False
    if not token:
        token = secrets.token_urlsafe(24)
        generated = True

    settings = WebSettings(
        token=token,
        workdir=Path(os.environ.get("OCRBOOK_WEB_WORKDIR", "./web_data")),
        max_job_age_days=int(os.environ.get("OCRBOOK_WEB_MAX_JOB_AGE_DAYS", "30")),
        max_upload_mb=int(os.environ.get("OCRBOOK_WEB_MAX_UPLOAD_MB", "300")),
        host=os.environ.get("OCRBOOK_WEB_HOST", "127.0.0.1"),
        port=int(os.environ.get("OCRBOOK_WEB_PORT", "8000")),
        token_was_generated=generated,
    )
    settings.ensure_dirs()
    return settings
