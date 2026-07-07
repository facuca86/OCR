"""Exportador a EPUB: cada `TITLE` (capítulo) del documento se convierte
en un capítulo XHTML independiente, con tabla de contenidos generada
automáticamente a partir de esos títulos."""

from __future__ import annotations

import html
import uuid
from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.export.base import Exporter
from ocr_book.export.html_builder import BASE_CSS, render_blocks_to_html
from ocr_book.reconstruction.document_model import Block, BlockType, Document
from ocr_book.utils.errors import EngineNotAvailableError


class EpubExporter(Exporter):
    extension = ".epub"

    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        try:
            from ebooklib import epub
        except ImportError as exc:
            raise EngineNotAvailableError(
                "El exportador EPUB requiere ebooklib. Instálalo con: pip install ebooklib"
            ) from exc

        lang = document.source_language or "es"
        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(document.title or "Documento")
        book.set_language(lang)

        chapters = self._split_into_chapters(document.blocks)
        epub_items = []
        for i, (chapter_title, blocks) in enumerate(chapters, start=1):
            body_html = render_blocks_to_html(blocks)
            item = epub.EpubHtml(
                title=chapter_title, file_name=f"chap_{i}.xhtml", lang=lang
            )
            item.content = (
                f"<html><head><meta charset='utf-8'/>"
                f"<title>{html.escape(chapter_title)}</title>"
                f"<style>{BASE_CSS}</style></head><body>{body_html}</body></html>"
            )
            book.add_item(item)
            epub_items.append(item)

        book.toc = tuple(epub_items)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *epub_items]

        output_path = output_path.with_suffix(self.extension)
        epub.write_epub(str(output_path), book)
        return output_path

    @staticmethod
    def _split_into_chapters(blocks: list[Block]) -> list[tuple[str, list[Block]]]:
        chapters: list[tuple[str, list[Block]]] = []
        current_title = "Documento"
        current_blocks: list[Block] = []

        for block in blocks:
            if block.type == BlockType.TITLE:
                if current_blocks:
                    chapters.append((current_title, current_blocks))
                current_title = block.text or f"Capítulo {len(chapters) + 1}"
                current_blocks = [block]
            else:
                current_blocks.append(block)

        if current_blocks:
            chapters.append((current_title, current_blocks))
        return chapters or [("Documento", blocks)]
