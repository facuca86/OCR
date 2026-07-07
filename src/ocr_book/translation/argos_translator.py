"""Traductor local/offline opcional, basado en Argos Translate (modelos
OpenNMT descargables una sola vez). Útil sin conexión o cuando se prioriza
la privacidad del contenido sobre la máxima calidad de traducción."""

from __future__ import annotations

import logging

from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun
from ocr_book.translation.base import TranslationEngine
from ocr_book.utils.errors import EngineNotAvailableError

logger = logging.getLogger(__name__)


class ArgosTranslateEngine(TranslationEngine):
    name = "argos"

    def is_available(self) -> bool:
        try:
            import argostranslate.translate  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_translation(self, source_language: str, target_language: str):
        import argostranslate.translate as argos_translate

        installed = argos_translate.get_installed_languages()
        from_candidates = [lang for lang in installed if lang.code == source_language]
        to_candidates = [lang for lang in installed if lang.code == target_language]
        if not from_candidates or not to_candidates:
            raise EngineNotAvailableError(
                f"No hay un paquete de idioma instalado para '{source_language}' -> "
                f"'{target_language}' en Argos Translate. Instálalo con "
                "argostranslate.package.install_from_path(...) antes de usar este motor."
            )
        return from_candidates[0].get_translation(to_candidates[0])

    def translate(
        self, document: Document, target_language: str, source_language: str | None = None
    ) -> Document:
        if not self.is_available():
            raise EngineNotAvailableError(
                "Argos Translate no está instalado. Instala el extra: pip install "
                "'ocr-book[translation-local]' o 'argostranslate'."
            )
        if not source_language:
            raise EngineNotAvailableError(
                "Argos Translate necesita el idioma de origen explícito (detéctalo antes "
                "con ocr_book.translation.language_detection)."
            )

        translation = self._get_translation(source_language, target_language)

        translated = Document(title=document.title, source_language=target_language)
        for block in document.blocks:
            if not block.text.strip():
                translated.add(block)
                continue
            try:
                translated_text = translation.translate(block.text)
            except Exception:
                logger.exception("Fallo al traducir un bloque con Argos Translate; se deja el original.")
                translated.add(block)
                continue

            translated.add(
                Block(
                    type=block.type,
                    runs=[TextRun(translated_text, bold=False, italic=False)],
                    level=block.level,
                    list_ordered=block.list_ordered,
                    footnote_marker=block.footnote_marker,
                    first_line_indent=block.first_line_indent,
                    source_page=block.source_page,
                )
            )

        translated.title = next(
            (b.text for b in translated.blocks if b.type == BlockType.TITLE), translated.title
        )
        return translated
