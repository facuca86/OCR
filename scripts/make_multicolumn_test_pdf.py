"""Genera un PDF de prueba con dos columnas, encabezado, pie de página,
número de página y una nota al pie, para probar el analizador de layout.

Uso: python scripts/make_multicolumn_test_pdf.py salida.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COL1 = (
    "Esta es la primera columna del documento. Contiene varias líneas de "
    "texto de cuerpo para que el analizador de layout pueda estimar la "
    "altura de línea típica del cuerpo del texto de esta página."
)
COL2 = (
    "Esta es la segunda columna, situada a la derecha de la primera. El "
    "lector debe continuar aquí solo después de terminar toda la columna "
    "izquierda, no línea por línea intercalada con la de al lado."
)


def _wrap(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def build_page(size=(1700, 2200)) -> Image.Image:
    image = Image.new("L", size, color=255)
    draw = ImageDraw.Draw(image)
    font_dir = "/usr/share/fonts/truetype/liberation"
    title_font = ImageFont.truetype(f"{font_dir}/LiberationSerif-Bold.ttf", 46)
    body_font = ImageFont.truetype(f"{font_dir}/LiberationSerif-Regular.ttf", 30)
    small_font = ImageFont.truetype(f"{font_dir}/LiberationSerif-Regular.ttf", 20)

    # Encabezado
    draw.text((650, 60), "Mi Libro de Prueba", font=small_font, fill=0)

    # Titulo
    draw.text((150, 160), "Capitulo 2: Las columnas", font=title_font, fill=0)

    col_width = (size[0] - 300) // 2 - 40
    y_start = 280

    # Columna izquierda
    y = y_start
    for line in _wrap(COL1, body_font, col_width, draw):
        draw.text((150, y), line, font=body_font, fill=0)
        y += 42

    # Columna derecha
    right_x = 150 + col_width + 80
    y = y_start
    for line in _wrap(COL2, body_font, col_width, draw):
        draw.text((right_x, y), line, font=body_font, fill=0)
        y += 42

    # Nota al pie (cerca de la parte inferior, fuente pequeña)
    footnote_y = size[1] - 260
    draw.text((150, footnote_y), "1 Esta es una nota al pie de ejemplo con letra mas pequena.", font=small_font, fill=0)

    # Pie de pagina / numero de pagina
    draw.text((size[0] // 2 - 10, size[1] - 90), "42", font=small_font, fill=0)

    return image.convert("RGB")


def main(output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Ver el comentario equivalente en make_test_pdf.py: resolution=200
    # evita que la página del PDF salga con el tamaño de un póster.
    build_page().save(out, resolution=200.0)
    print(f"PDF de prueba multi-columna generado en: {out.resolve()}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/sample_multicolumn.pdf")
