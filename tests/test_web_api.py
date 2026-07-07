"""Pruebas de la API web (FastAPI TestClient): subida válida, subida de
formato no soportado, consulta de estado de un job inexistente y el flujo
completo subida -> procesamiento -> descarga, usando los mismos PDFs
sintéticos de fixtures que usa el resto de la suite (no libros reales)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ocr_book.web.app import create_app
from ocr_book.web.config import WebSettings

TOKEN = "test-token-12345"


def _make_client(tmp_path: Path) -> TestClient:
    settings = WebSettings(token=TOKEN, workdir=tmp_path / "web_data")
    settings.ensure_dirs()
    app = create_app(settings)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return client


def _minimal_form() -> dict:
    return {
        "ocr_engine": "tesseract",
        "ocr_languages": ["eng"],
        "export_formats": ["txt"],
    }


def test_unauthenticated_request_is_rejected(tmp_path: Path) -> None:
    settings = WebSettings(token=TOKEN, workdir=tmp_path / "web_data")
    settings.ensure_dirs()
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/api/jobs")
        assert response.status_code == 401


def test_status_for_unknown_job_returns_404(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.get("/api/jobs/does-not-exist/status")
        assert response.status_code == 404


def test_upload_of_unsupported_format_is_rejected(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.post(
            "/api/jobs",
            data=_minimal_form(),
            files={"file": ("notes.txt", b"plain text, not a supported document", "text/plain")},
        )
        assert response.status_code == 400
        assert "no hay importador" in response.json()["detail"].lower() or "importador" in response.json()["detail"].lower()


def test_upload_valid_pdf_creates_pending_job(tmp_path: Path, single_column_pdf: Path) -> None:
    with _make_client(tmp_path) as client:
        with single_column_pdf.open("rb") as fh:
            response = client.post(
                "/api/jobs",
                data=_minimal_form(),
                files={"file": (single_column_pdf.name, fh, "application/pdf")},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] in ("pending", "running", "done")
        assert body["filename"] == single_column_pdf.name
        assert body["page_count"] is not None and body["page_count"] > 0


def test_engines_endpoint_lists_choices(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        response = client.get("/api/engines")
        assert response.status_code == 200
        body = response.json()
        assert any(e["value"] == "tesseract" and e["available"] for e in body["ocr_engines"])
        assert "pdf" in body["export_formats"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="requiere el binario 'tesseract'")
def test_full_flow_upload_process_download(tmp_path: Path, single_column_pdf: Path) -> None:
    with _make_client(tmp_path) as client:
        with single_column_pdf.open("rb") as fh:
            response = client.post(
                "/api/jobs",
                data={
                    "ocr_engine": "tesseract",
                    "ocr_languages": ["spa", "eng"],
                    "export_formats": ["txt"],
                },
                files={"file": (single_column_pdf.name, fh, "application/pdf")},
            )
        assert response.status_code == 201
        job_id = response.json()["id"]

        deadline = time.monotonic() + 90
        status_body = None
        while time.monotonic() < deadline:
            status_response = client.get(f"/api/jobs/{job_id}/status")
            assert status_response.status_code == 200
            status_body = status_response.json()
            if status_body["status"] in ("done", "error"):
                break
            time.sleep(1)

        assert status_body is not None
        assert status_body["status"] == "done", status_body.get("error")
        assert "txt" in status_body["output_formats"]

        download = client.get(f"/api/jobs/{job_id}/download/txt")
        assert download.status_code == 200
        text = download.content.decode("utf-8").lower()
        assert "comienzo" in text
        assert "desarrollo" in text

        history = client.get("/api/jobs")
        assert history.status_code == 200
        assert any(j["id"] == job_id for j in history.json())
