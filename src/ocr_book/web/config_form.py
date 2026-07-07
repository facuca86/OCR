"""Traduce el formulario de subida (HTML) a un `AppConfig` real, pasando
siempre por `AppConfig.model_validate` para que las mismas reglas de
validación que usan la CLI y la GUI (rangos, enums) apliquen también acá,
en vez de mantener una copia paralela de las reglas."""

from __future__ import annotations

from pydantic import ValidationError
from starlette.datastructures import FormData

from ocr_book.config.schema import AppConfig


class InvalidJobConfigError(ValueError):
    """Configuración de job inválida; el mensaje es apto para mostrar al
    usuario tal cual (no un stacktrace)."""


def _checkbox(form: FormData, name: str) -> bool:
    return form.get(name) is not None


def build_app_config(form: FormData) -> AppConfig:
    ocr_languages = form.getlist("ocr_languages")
    if not ocr_languages:
        raise InvalidJobConfigError("Elegí al menos un idioma para el OCR.")

    export_formats = form.getlist("export_formats")
    if not export_formats:
        raise InvalidJobConfigError("Elegí al menos un formato de salida.")

    use_gpu = _checkbox(form, "use_gpu")
    translation_enabled = _checkbox(form, "translation_enabled")

    target_language = str(form.get("translation_target_language_custom") or "").strip()
    if not target_language:
        target_language = str(form.get("translation_target_language") or "en").strip()

    data = {
        "ocr": {
            "engine": form.get("ocr_engine", "tesseract"),
            "languages": ocr_languages,
            "use_gpu": use_gpu,
        },
        "translation": {
            "enabled": translation_enabled,
            "engine": form.get("translation_engine", "anthropic"),
            "target_language": target_language,
        },
        "export": {
            "formats": export_formats,
            # keep_images / keep_tables no están implementados en el
            # pipeline todavía (ver README, sección "Limitaciones
            # conocidas"): se dejan en su valor por defecto y el
            # formulario no los ofrece como opción real.
        },
        "layout": {
            "remove_headers": _checkbox(form, "remove_headers"),
            "remove_footers": _checkbox(form, "remove_footers"),
            "remove_page_numbers": _checkbox(form, "remove_page_numbers"),
        },
        "performance": {
            "use_gpu": use_gpu,
        },
    }

    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        location = " → ".join(str(part) for part in first_error["loc"])
        raise InvalidJobConfigError(f"Configuración inválida en '{location}': {first_error['msg']}") from exc
