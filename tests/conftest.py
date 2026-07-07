"""Fixtures compartidas: PDFs sintéticos "escaneados" usados por varias
suites de pruebas (layout, reconstrucción, orquestador). Se generan una
única vez por sesión si no existen ya en `tests/fixtures/`, así el
repositorio no necesita versionar binarios PDF generados."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


@pytest.fixture(scope="session")
def single_column_pdf() -> Path:
    path = FIXTURES_DIR / "sample_scanned.pdf"
    if not path.exists():
        subprocess.run([sys.executable, str(SCRIPTS_DIR / "make_test_pdf.py"), str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def multicolumn_pdf() -> Path:
    path = FIXTURES_DIR / "sample_multicolumn.pdf"
    if not path.exists():
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "make_multicolumn_test_pdf.py"), str(path)], check=True
        )
    return path
