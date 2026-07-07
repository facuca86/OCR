"""Traductor por defecto cuando se activa la traducción: usa un modelo
Claude vía la API de Anthropic.

Se traduce por lotes de bloques (no todo el libro de una vez, para no
exceder el límite de contexto/salida, ni bloque por bloque, que sería
lentísimo y caro en llamadas). Cada bloque se envuelve en delimitadores
`<<<BLOCK_i>>> ... <<<END_i>>>` y se le pide al modelo que devuelva
exactamente los mismos delimitadores: así se puede verificar que no faltan
ni sobran bloques y, si el modelo se equivoca en alguno, solo ese bloque
cae al texto original en vez de perder el lote entero.
"""

from __future__ import annotations

import logging
import os
import re

from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun
from ocr_book.translation.base import TranslationEngine
from ocr_book.utils.errors import EngineNotAvailableError

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<<<BLOCK_(\d+)>>>\s*(.*?)\s*<<<END_\1>>>", re.DOTALL)
_MAX_BATCH_CHARS = 3000

_SYSTEM_PROMPT = """Eres un traductor profesional especializado en literatura y documentos técnicos.
Vas a traducir el contenido de un libro, bloque a bloque, al idioma solicitado.

Reglas estrictas:
1. Cada bloque de entrada está delimitado por `<<<BLOCK_i>>>` y `<<<END_i>>>`. Devuelve cada \
traducción con EXACTAMENTE los mismos delimitadores, mismo número i, en el mismo orden.
2. No añadas, elimines ni fusiones bloques. No añadas explicaciones, notas ni texto fuera de \
los delimitadores.
3. Conserva el tono, el registro y el significado del original; no traduzcas de forma literal \
palabra por palabra si eso suena poco natural.
4. Conserva nombres propios, cifras y signos de puntuación estructurales (comillas, guiones de \
diálogo) salvo que la convención del idioma destino exija cambiarlos.
5. Traduce siempre al idioma solicitado, incluso si el texto de un bloque concreto ya está en \
ese idioma (en ese caso, devuélvelo tal cual)."""


class AnthropicTranslator(TranslationEngine):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def translate(
        self, document: Document, target_language: str, source_language: str | None = None
    ) -> Document:
        if not self.is_available():
            raise EngineNotAvailableError(
                "El traductor de Anthropic requiere el paquete 'anthropic' instalado y la "
                "variable de entorno ANTHROPIC_API_KEY configurada."
            )

        translated = Document(title=document.title, source_language=target_language)
        blocks = list(document.blocks)
        batches = self._batch_blocks(blocks)

        translated_texts: dict[int, str] = {}
        for batch_indices in batches:
            batch_blocks = [blocks[i] for i in batch_indices]
            try:
                results = self._translate_batch(batch_blocks, target_language)
            except Exception:
                logger.exception("Fallo al traducir un lote; esos bloques se dejan sin traducir.")
                results = {}
            for local_i, global_i in enumerate(batch_indices):
                if local_i in results:
                    translated_texts[global_i] = results[local_i]

        for i, block in enumerate(blocks):
            if i in translated_texts and block.text.strip():
                new_block = Block(
                    type=block.type,
                    runs=[TextRun(translated_texts[i], bold=False, italic=False)],
                    level=block.level,
                    list_ordered=block.list_ordered,
                    footnote_marker=block.footnote_marker,
                    first_line_indent=block.first_line_indent,
                    source_page=block.source_page,
                )
                translated.add(new_block)
            else:
                translated.add(block)

        translated.title = next(
            (b.text for b in translated.blocks if b.type == BlockType.TITLE), translated.title
        )
        return translated

    @staticmethod
    def _batch_blocks(blocks: list[Block]) -> list[list[int]]:
        batches: list[list[int]] = []
        current: list[int] = []
        current_chars = 0
        for i, block in enumerate(blocks):
            length = len(block.text)
            if not block.text.strip():
                continue
            if current and current_chars + length > _MAX_BATCH_CHARS:
                batches.append(current)
                current, current_chars = [], 0
            current.append(i)
            current_chars += length
        if current:
            batches.append(current)
        return batches

    def _translate_batch(self, batch_blocks: list[Block], target_language: str) -> dict[int, str]:
        prompt_parts = []
        for local_i, block in enumerate(batch_blocks):
            prompt_parts.append(f"<<<BLOCK_{local_i}>>>\n{block.text}\n<<<END_{local_i}>>>")
        user_prompt = (
            f"Traduce el siguiente contenido al idioma con código '{target_language}'.\n\n"
            + "\n".join(prompt_parts)
        )

        estimated_tokens = max(1024, sum(len(b.text) for b in batch_blocks) // 2)
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=estimated_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        response_text = "".join(
            part.text for part in response.content if getattr(part, "type", None) == "text"
        )

        results: dict[int, str] = {}
        for match in _TAG_RE.finditer(response_text):
            index = int(match.group(1))
            results[index] = match.group(2).strip()
        return results
