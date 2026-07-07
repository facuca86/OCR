"""Construye HTML a partir de un `Document`. Lo reutilizan el exportador
HTML, el exportador PDF (renderiza este mismo HTML con WeasyPrint) y el
exportador EPUB (cada capítulo es este HTML envuelto en XHTML)."""

from __future__ import annotations

import html

from ocr_book.export.block_grouping import group_list_runs
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun

BASE_CSS = """
body {
    font-family: "Georgia", "Liberation Serif", serif;
    line-height: 1.5;
    max-width: 42em;
    margin: 2em auto;
    padding: 0 1.5em;
    color: #1a1a1a;
}
h1, h2 {
    font-family: "Helvetica Neue", "Liberation Sans", sans-serif;
    line-height: 1.25;
}
h1 { font-size: 1.9em; margin-top: 2em; }
h2 { font-size: 1.35em; margin-top: 1.6em; }
p { margin: 0.7em 0; text-align: justify; hyphens: auto; }
p.indent { text-indent: 1.6em; margin: 0; }
blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 3px solid #ccc;
    font-style: italic;
    color: #333;
}
ul, ol { margin: 0.7em 0; padding-left: 2em; }
li { margin: 0.3em 0; }
.footnote {
    font-size: 0.85em;
    color: #444;
    border-top: 1px solid #ddd;
    padding-top: 0.4em;
    margin-top: 1.2em;
}
.footnote sup { margin-right: 0.3em; font-weight: bold; }
"""


def _runs_to_html(runs: list[TextRun]) -> str:
    parts = []
    for run in runs:
        text = html.escape(run.text)
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        parts.append(text)
    return "".join(parts)


def _render_block(block: Block) -> str:
    inner = _runs_to_html(block.runs)
    if block.type == BlockType.TITLE:
        return f"<h1>{inner}</h1>"
    if block.type == BlockType.HEADING:
        return f"<h2>{inner}</h2>"
    if block.type == BlockType.QUOTE:
        return f"<blockquote><p>{inner}</p></blockquote>"
    if block.type == BlockType.FOOTNOTE:
        marker = html.escape(block.footnote_marker or "")
        sup = f"<sup>{marker}</sup> " if marker else ""
        return f'<p class="footnote">{sup}{inner}</p>'
    css_class = ' class="indent"' if block.first_line_indent else ""
    return f"<p{css_class}>{inner}</p>"


def _render_list(items: list[Block]) -> str:
    tag = "ol" if items[0].list_ordered else "ul"
    lis = "\n".join(f"<li>{_runs_to_html(item.runs)}</li>" for item in items)
    return f"<{tag}>\n{lis}\n</{tag}>"


def render_blocks_to_html(blocks: list[Block]) -> str:
    pieces: list[str] = []
    for item in group_list_runs(blocks):
        if isinstance(item, list):
            pieces.append(_render_list(item))
        else:
            pieces.append(_render_block(item))
    return "\n".join(pieces)


def wrap_html_document(title: str, body_html: str, lang: str = "es", extra_css: str = "") -> str:
    safe_title = html.escape(title or "Documento")
    return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}">
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>{BASE_CSS}{extra_css}</style>
</head>
<body>
{body_html}
</body>
</html>"""


def document_to_html(document: Document, lang: str = "es", extra_css: str = "") -> str:
    body_html = render_blocks_to_html(document.blocks)
    return wrap_html_document(document.title, body_html, lang=lang, extra_css=extra_css)
