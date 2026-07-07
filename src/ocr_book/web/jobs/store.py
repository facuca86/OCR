"""Persistencia de jobs en SQLite: un único archivo, sin servidor de base
de datos aparte. Alcanza sobradamente para "un libro a la vez" y para que
el historial sobreviva a un reinicio del proceso; si en el futuro hiciera
falta una cola multi-worker (Celery/RQ), este store se reemplaza sin tocar
las rutas HTTP, que solo conocen `JobStore`."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from ocr_book.web.jobs.models import Job, JobStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    stage TEXT NOT NULL DEFAULT '',
    current INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    error TEXT,
    page_count INTEGER,
    output_formats_json TEXT NOT NULL DEFAULT '[]'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        filename=row["filename"],
        status=JobStatus(row["status"]),
        config_json=row["config_json"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        stage=row["stage"],
        current=row["current"],
        total=row["total"],
        message=row["message"],
        error=row["error"],
        page_count=row["page_count"],
        output_formats_json=row["output_formats_json"],
    )


class JobStore:
    """Envoltorio simple y thread-safe sobre sqlite3. Se usa desde hilos de
    petición HTTP y desde el hilo del `JobRunner` a la vez, por eso el
    lock: sqlite3 permite `check_same_thread=False`, pero no serializa
    escrituras concurrentes por sí solo."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_job(self, job_id: str, filename: str, config_json: str, page_count: int | None) -> Job:
        job = Job(
            id=job_id,
            filename=filename,
            status=JobStatus.PENDING,
            config_json=config_json,
            created_at=_now(),
            page_count=page_count,
        )
        with self._lock:
            self._conn.execute(
                """INSERT INTO jobs (id, filename, status, config_json, created_at, page_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (job.id, job.filename, job.status.value, job.config_json, job.created_at, job.page_count),
            )
            self._conn.commit()
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def list_jobs(self, limit: int = 100) -> list[Job]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, started_at = ? WHERE id = ?",
                (JobStatus.RUNNING.value, _now(), job_id),
            )
            self._conn.commit()

    def update_progress(self, job_id: str, stage: str, current: int, total: int, message: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET stage = ?, current = ?, total = ?, message = ? WHERE id = ?",
                (stage, current, total, message, job_id),
            )
            self._conn.commit()

    def mark_done(self, job_id: str, output_formats: list[str]) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, finished_at = ?, output_formats_json = ? WHERE id = ?",
                (JobStatus.DONE.value, _now(), json.dumps(output_formats), job_id),
            )
            self._conn.commit()

    def mark_error(self, job_id: str, error_message: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
                (JobStatus.ERROR.value, _now(), error_message, job_id),
            )
            self._conn.commit()

    def jobs_older_than(self, max_age_days: int) -> list[Job]:
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
        return [
            job
            for job in self.list_jobs(limit=10_000)
            if datetime.fromisoformat(job.created_at).timestamp() < cutoff
        ]

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self._conn.commit()
