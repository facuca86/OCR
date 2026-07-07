"""Opciones que el formulario web ofrece, derivadas de las fuentes de
verdad ya existentes (`AppConfig`, `*/factory.py`, `ocr/language_codes.py`)
en vez de listas paralelas que puedan desincronizarse."""

from __future__ import annotations

from ocr_book.config.schema import ExportFormat, OcrEngineName, TranslationEngineName
from ocr_book.ocr.engine_factory import list_available_engines as list_available_ocr_engines
from ocr_book.ocr.language_codes import TESSERACT_TO_EASYOCR
from ocr_book.translation.factory import list_available_engines as list_available_translation_engines

# Solo texto de presentación (nombre legible del código de idioma). El
# conjunto de códigos en sí sale de `ocr.language_codes`, que ya es la
# fuente de verdad de qué idiomas soportan los motores opcionales.
_LANGUAGE_LABELS: dict[str, str] = {
    "spa": "Español",
    "eng": "Inglés",
    "fra": "Francés",
    "deu": "Alemán",
    "ita": "Italiano",
    "por": "Portugués",
    "nld": "Neerlandés",
    "rus": "Ruso",
    "chi_sim": "Chino simplificado",
    "chi_tra": "Chino tradicional",
    "jpn": "Japonés",
    "kor": "Coreano",
    "ara": "Árabe",
}

_TARGET_LANGUAGE_LABELS: dict[str, str] = {
    "en": "Inglés",
    "es": "Español",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "nl": "Neerlandés",
    "ru": "Ruso",
    "ja": "Japonés",
    "ko": "Coreano",
    "ar": "Árabe",
}


def ocr_language_choices() -> list[tuple[str, str]]:
    return [(code, _LANGUAGE_LABELS.get(code, code)) for code in TESSERACT_TO_EASYOCR]


def translation_target_choices() -> list[tuple[str, str]]:
    return [(code, f"{label} ({code})") for code, label in _TARGET_LANGUAGE_LABELS.items()]


def ocr_engine_choices() -> list[tuple[str, str, bool]]:
    """(valor, etiqueta, disponible) para cada motor OCR conocido en
    `OcrEngineName`, marcando como no disponible el que no tenga sus
    dependencias instaladas (para deshabilitarlo en el form, no fallar al
    enviar)."""
    available = set(list_available_ocr_engines())
    return [(engine.value, engine.value, engine in available) for engine in OcrEngineName]


def translation_engine_choices() -> list[tuple[str, str, bool]]:
    available = set(list_available_translation_engines())
    return [
        (engine.value, engine.value, engine in available)
        for engine in TranslationEngineName
        if engine != TranslationEngineName.NONE
    ]


def export_format_choices() -> list[str]:
    return [fmt.value for fmt in ExportFormat]
