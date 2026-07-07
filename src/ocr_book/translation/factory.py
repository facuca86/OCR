from __future__ import annotations

from ocr_book.config.schema import TranslationConfig, TranslationEngineName
from ocr_book.translation.base import TranslationEngine
from ocr_book.translation.noop import NoOpTranslator


def get_translation_engine(config: TranslationConfig) -> TranslationEngine:
    if not config.enabled or config.engine == TranslationEngineName.NONE:
        return NoOpTranslator()

    if config.engine == TranslationEngineName.ANTHROPIC:
        from ocr_book.translation.anthropic_translator import AnthropicTranslator

        return AnthropicTranslator(model=config.anthropic_model)

    if config.engine == TranslationEngineName.ARGOS:
        from ocr_book.translation.argos_translator import ArgosTranslateEngine

        return ArgosTranslateEngine()

    raise ValueError(f"Motor de traducción desconocido: {config.engine}")


def list_available_engines() -> list[TranslationEngineName]:
    """Motores de traducción cuyas dependencias/credenciales están
    disponibles en este sistema (`NONE` no se incluye: se representa en la
    interfaz web como la casilla "activar traducción" desmarcada, no como
    una opción de motor)."""
    from ocr_book.translation.anthropic_translator import AnthropicTranslator
    from ocr_book.translation.argos_translator import ArgosTranslateEngine

    candidates = {
        TranslationEngineName.ANTHROPIC: AnthropicTranslator(),
        TranslationEngineName.ARGOS: ArgosTranslateEngine(),
    }
    return [name for name, engine in candidates.items() if engine.is_available()]
