"""Agrupa bloques consecutivos del mismo tipo "contenedor" (listas), que
varios formatos de salida (HTML, Markdown, EPUB) necesitan envolver en un
único `<ul>`/`<ol>` en vez de exportar cada ítem suelto."""

from __future__ import annotations

from ocr_book.reconstruction.document_model import Block, BlockType


def group_list_runs(blocks: list[Block]) -> list[Block | list[Block]]:
    """Devuelve una lista donde cada `Block` normal aparece tal cual, pero
    las rachas de `LIST_ITEM` consecutivos se agrupan en una sublista."""
    grouped: list[Block | list[Block]] = []
    current_list: list[Block] = []

    for block in blocks:
        if block.type == BlockType.LIST_ITEM:
            current_list.append(block)
            continue
        if current_list:
            grouped.append(current_list)
            current_list = []
        grouped.append(block)

    if current_list:
        grouped.append(current_list)

    return grouped
