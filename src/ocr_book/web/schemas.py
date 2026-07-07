"""Modelos de request/response de la API JSON (`/api/...`)."""

from __future__ import annotations

import json

from pydantic import BaseModel

from ocr_book.web.jobs.models import Job, JobStatus


class JobStatusResponse(BaseModel):
    id: str
    filename: str
    status: JobStatus
    stage: str
    current: int
    total: int
    message: str
    error: str | None
    page_count: int | None
    output_formats: list[str]
    created_at: str
    started_at: str | None
    finished_at: str | None

    @classmethod
    def from_job(cls, job: Job) -> "JobStatusResponse":
        return cls(
            id=job.id,
            filename=job.filename,
            status=job.status,
            stage=job.stage,
            current=job.current,
            total=job.total,
            message=job.message,
            error=job.error,
            page_count=job.page_count,
            output_formats=json.loads(job.output_formats_json),
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class EnginesResponse(BaseModel):
    ocr_engines: list[dict]
    translation_engines: list[dict]
    export_formats: list[str]
    ocr_languages: list[dict]
    translation_target_languages: list[dict]
