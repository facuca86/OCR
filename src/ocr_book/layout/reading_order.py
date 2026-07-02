"""Reconstruye el orden de lectura real de los bloques de cuerpo de texto,
respetando columnas y bloques que las atraviesan (p. ej. un subtítulo de
sección que abarca dos columnas).

Algoritmo ("por bandas"): los bloques que abarcan (casi) todo el ancho de
la zona de cuerpo actúan como separadores horizontales. Entre dos
separadores consecutivos, se leen todas las columnas de izquierda a
derecha, cada una de arriba hacia abajo — el orden natural de lectura de un
libro o revista maquetados a varias columnas.
"""

from __future__ import annotations

from ocr_book.layout.models import Region


def order_body_regions(regions: list[Region]) -> list[Region]:
    columns: dict[int, list[Region]] = {}
    spanning: list[Region] = []

    for region in regions:
        if region.column_index == -1:
            spanning.append(region)
        else:
            columns.setdefault(region.column_index, []).append(region)

    for items in columns.values():
        items.sort(key=lambda r: r.bbox[1])
    spanning.sort(key=lambda r: r.bbox[1])
    column_keys = sorted(columns.keys())

    ordered: list[Region] = []
    pointers = {c: 0 for c in column_keys}

    def flush_columns_above(y_limit: float) -> None:
        for c in column_keys:
            items = columns[c]
            while pointers[c] < len(items) and items[pointers[c]].bbox[1] < y_limit:
                ordered.append(items[pointers[c]])
                pointers[c] += 1

    for span in spanning:
        flush_columns_above(span.bbox[1])
        ordered.append(span)

    for c in column_keys:
        items = columns[c]
        while pointers[c] < len(items):
            ordered.append(items[pointers[c]])
            pointers[c] += 1

    return ordered
