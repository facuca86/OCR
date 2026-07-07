from __future__ import annotations

from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.export.base import Exporter
from ocr_book.export.block_grouping import group_list_runs
from ocr_book.reconstruction.document_model import Block, BlockType, Document


def _render_block(block: Block) -> str:
    if block.type == BlockType.TITLE:
        return f"{block.text.upper()}\n{'=' * min(len(block.text), 60)}"
    if block.type == BlockType.HEADING:
        return f"{block.text}\n{'-' * min(len(block.text), 60)}"
    if block.type == BlockType.QUOTE:
        return "\n".join(f"    {line}" for line in block.text.splitlines() or [block.text])
    if block.type == BlockType.FOOTNOTE:
        marker = f"[{block.footnote_marker}] " if block.footnote_marker else ""
        return f"{marker}{block.text}"
    return block.text


def document_to_text(document: Document) -> str:
    lines: list[str] = []
    for item in group_list_runs(document.blocks):
        if isinstance(item, list):
            prefix_ordered = item[0].list_ordered
            for i, li in enumerate(item, start=1):
                marker = f"{i}." if prefix_ordered else "-"
                lines.append(f"{marker} {li.text}")
        else:
            lines.append(_render_block(item))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class TxtExporter(Exporter):
    extension = ".txt"

    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        output_path = output_path.with_suffix(self.extension)
        output_path.write_text(document_to_text(document), encoding="utf-8")
        return output_path
