"""Reconocimiento consciente de columnas.

Antes de invocar al motor OCR, la página se divide en tres bandas
horizontales:

- banda superior (posible encabezado / margen),
- banda de cuerpo, donde sí se detectan y separan columnas,
- banda inferior (posible nota al pie / pie de página / numeración).

Las bandas superior e inferior se reconocen siempre a ancho completo, sin
dividir en columnas. Es necesario: un número de página centrado a menudo
cae justo en el hueco que separa dos columnas del cuerpo, y si se
recortara la imagen por columnas en toda la altura de la página, ese
elemento no pertenecería a ningún recorte y se perdería por completo. Las
notas al pie, por la misma razón, casi siempre ocupan el ancho completo de
la página incluso cuando el cuerpo está a dos o más columnas.

Los puntos de corte de esas bandas NO son un porcentaje fijo de la altura:
se buscan huecos de tinta reales cerca del margen superior/inferior
(`layout/row_bands.py`). Una franja fija cortaría por la mitad un párrafo
de cuerpo normal en una página sin encabezado ni notas al pie que llegara
casi hasta el borde inferior.

Dentro de la banda de cuerpo, se detectan las columnas a nivel de píxel
(ver `layout/columns.py`) y se ejecuta el reconocimiento por separado
sobre cada recorte. Esto evita que un motor con segmentación automática
(Tesseract en particular) fusione dos columnas próximas en un único
bloque y mezcle palabras de ambas dentro de la misma línea, algo que ya
no se puede corregir después con heurísticas de layout una vez el texto
está intercalado.

Cada banda/columna se etiqueta con un `block_num` desplazado para que el
resto del pipeline pueda asumir con seguridad que un mismo `block_num`
nunca cruza dos columnas ni dos bandas.
"""

from __future__ import annotations

import numpy as np

from ocr_book.config.schema import LayoutConfig, OcrConfig
from ocr_book.layout.columns import detect_column_ranges_from_image
from ocr_book.layout.row_bands import find_bottom_cut, find_header_cut
from ocr_book.ocr.base import OcrEngine
from ocr_book.ocr.models import OcrResult, OcrWord

_BLOCK_OFFSET = 100_000


def _recognize_crop(
    engine: OcrEngine, crop: np.ndarray, ocr_config: OcrConfig, x_offset: int, y_offset: int, block_prefix: int
) -> list[OcrWord]:
    if crop.shape[0] == 0 or crop.shape[1] == 0:
        return []
    result = engine.recognize(crop, ocr_config)
    for word in result.words:
        word.left += x_offset
        word.top += y_offset
        word.block_num += block_prefix
    return result.words


def recognize_with_columns(
    engine: OcrEngine, image: np.ndarray, ocr_config: OcrConfig, layout_config: LayoutConfig
) -> OcrResult:
    height, width = image.shape[0], image.shape[1]

    if not layout_config.detect_columns:
        return engine.recognize(image, ocr_config)

    header_y_end = find_header_cut(image)
    footnote_y_start = max(find_bottom_cut(image), header_y_end)

    all_words: list[OcrWord] = []

    all_words += _recognize_crop(engine, image[0:header_y_end], ocr_config, 0, 0, block_prefix=0)

    body = image[header_y_end:footnote_y_start]
    column_ranges = (
        detect_column_ranges_from_image(body, max_columns=layout_config.max_columns)
        if body.shape[0] > 0
        else []
    )
    if len(column_ranges) <= 1:
        all_words += _recognize_crop(
            engine, body, ocr_config, 0, header_y_end, block_prefix=_BLOCK_OFFSET
        )
    else:
        for column_index, (x0, x1) in enumerate(column_ranges):
            crop = body[:, x0:x1]
            all_words += _recognize_crop(
                engine,
                crop,
                ocr_config,
                x0,
                header_y_end,
                block_prefix=(column_index + 1) * _BLOCK_OFFSET,
            )

    bottom_prefix = (layout_config.max_columns + 2) * _BLOCK_OFFSET
    all_words += _recognize_crop(
        engine, image[footnote_y_start:height], ocr_config, 0, footnote_y_start, block_prefix=bottom_prefix
    )

    return OcrResult(words=all_words, width=width, height=height, languages=ocr_config.languages)
