"""Carga y guardado de configuración desde/hacia YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from ocr_book.config.schema import AppConfig


def load_config(path: str | Path | None) -> AppConfig:
    """Carga la configuración desde un YAML. Si `path` es None, usa los
    valores por defecto de `AppConfig`."""
    if path is None:
        return AppConfig()

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return AppConfig.model_validate(raw)


def save_config(config: AppConfig, path: str | Path) -> None:
    """Guarda la configuración actual como YAML legible."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
