from __future__ import annotations

from pathlib import Path

from ocr_book.config.schema import ExportConfig
from ocr_book.export.base import Exporter
from ocr_book.export.block_grouping import group_list_runs
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun


def _runs_to_markdown(runs: list[TextRun]) -> str:
    parts = []
    for run in runs:
        text = run.text
        if run.bold and run.italic:
            text = f"***{text}***"
        elif run.bold:
            text = f"**{text}**"
        elif run.italic:
            text = f"*{text}*"
        parts.append(text)
    return "".join(parts)


def _render_block(block: Block) -> str:
    text = _runs_to_markdown(block.runs)
    if block.type == BlockType.TITLE:
        return f"# {text}"
    if block.type == BlockType.HEADING:
        return f"## {text}"
    if block.type == BlockType.QUOTE:
        return "\n".join(f"> {line}" for line in text.splitlines() or [text])
    if block.type == BlockType.FOOTNOTE:
        marker = block.footnote_marker or "*"
        return f"[^{marker}]: {text}"
    return text


def document_to_markdown(document: Document) -> str:
    lines: list[str] = []
    for item in group_list_runs(document.blocks):
        if isinstance(item, list):
            ordered = item[0].list_ordered
            for i, li in enumerate(item, start=1):
                marker = f"{i}." if ordered else "-"
                lines.append(f"{marker} {_runs_to_markdown(li.runs)}")
        else:
            lines.append(_render_block(item))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


class MarkdownExporter(Exporter):
    extension = ".md"

    def export(self, document: Document, output_path: Path, config: ExportConfig) -> Path:
        output_path = output_path.with_suffix(self.extension)
        output_path.write_text(document_to_markdown(document), encoding="utf-8")
        return output_path
