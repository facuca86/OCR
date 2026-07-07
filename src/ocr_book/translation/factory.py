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
