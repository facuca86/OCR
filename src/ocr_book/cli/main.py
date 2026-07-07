"""Interfaz de línea de comandos: automatiza el mismo motor que usa la
GUI, útil para procesar libros por lotes o en un servidor sin pantalla."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from ocr_book.config.loader import load_config
from ocr_book.config.schema import ExportFormat, OcrEngineName, TranslationEngineName
from ocr_book.pipeline.orchestrator import PipelineOrchestrator
from ocr_book.pipeline.progress import ProgressEvent
from ocr_book.utils.logging_config import configure_logging


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None,
    help="Ruta a un config.yaml. Si se omite, se usan los valores por defecto.",
)
@click.option("--output", "-o", "output_dir", type=click.Path(path_type=Path), default=None, help="Carpeta de salida.")
@click.option(
    "--format", "-f", "formats", multiple=True,
    type=click.Choice([f.value for f in ExportFormat]), help="Formato de salida (repetible: -f pdf -f epub).",
)
@click.option("--lang", "ocr_langs", multiple=True, help="Idioma(s) OCR en código Tesseract, ej: --lang spa --lang eng.")
@click.option("--engine", type=click.Choice([e.value for e in OcrEngineName]), default=None, help="Motor OCR.")
@click.option("--translate-to", default=None, help="Activa la traducción al idioma indicado (ej: en, fr).")
@click.option(
    "--translation-engine", type=click.Choice([e.value for e in TranslationEngineName]), default=None,
    help="Motor de traducción.",
)
@click.option("--workers", type=int, default=None, help="Número de procesos paralelos (por defecto: todos los núcleos).")
@click.option("--gpu/--no-gpu", default=None, help="Forzar uso (o no) de GPU en motores que lo soporten.")
@click.option("-v", "--verbose", is_flag=True, help="Muestra logs de depuración.")
def cli(
    input_path: Path,
    config_path: Path | None,
    output_dir: Path | None,
    formats: tuple[str, ...],
    ocr_langs: tuple[str, ...],
    engine: str | None,
    translate_to: str | None,
    translation_engine: str | None,
    workers: int | None,
    gpu: bool | None,
    verbose: bool,
) -> None:
    """Convierte INPUT_PATH (un PDF escaneado o una imagen) en un documento
    digital reconstruido, con traducción opcional."""
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    config = load_config(config_path)

    if output_dir:
        config.export.output_dir = output_dir
    if formats:
        config.export.formats = [ExportFormat(f) for f in formats]
    if ocr_langs:
        config.ocr.languages = list(ocr_langs)
    if engine:
        config.ocr.engine = OcrEngineName(engine)
    if translate_to:
        config.translation.enabled = True
        config.translation.target_language = translate_to
    if translation_engine:
        config.translation.engine = TranslationEngineName(translation_engine)
    if workers is not None:
        config.performance.max_workers = workers
    if gpu is not None:
        config.ocr.use_gpu = gpu
        config.performance.use_gpu = gpu

    config.export.output_dir.mkdir(parents=True, exist_ok=True)
    output_basename = config.export.output_dir / Path(input_path).stem

    orchestrator = PipelineOrchestrator(config)

    def on_progress(event: ProgressEvent) -> None:
        click.echo(f"[{event.stage}] {event.current}/{event.total} {event.message}")

    try:
        outputs = orchestrator.process_and_export(input_path, output_basename, progress_callback=on_progress)
    except Exception as exc:  # noqa: BLE001 - se reporta al usuario y se sale con código de error
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("\nListo. Archivos generados:")
    for path in outputs:
        click.echo(f"  {path}")


if __name__ == "__main__":
    cli()
