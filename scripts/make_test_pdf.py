"""Genera un PDF de prueba tipo "escaneo" a partir de texto sintético.

Renderiza texto en una imagen (con una ligera rotación y ruido para simular
un escaneo real), y la empaqueta como PDF de una o varias páginas. Útil
para pruebas end-to-end del pipeline sin depender de archivos reales.

Uso: python scripts/make_test_pdf.py salida.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PARAGRAPH_1 = (
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat."
)

PARAGRAPH_2 = (
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum "
    "dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non "
    "proident, sunt in culpa qui officia deserunt mollit anim id est "
    "laborum."
)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
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


def build_page(title: str, paragraphs: list[str], size=(1700, 2200)) -> Image.Image:
    image = Image.new("L", size, color=255)
    draw = ImageDraw.Draw(image)

    try:
        title_font = ImageFont.truetype("DejaVuSerif-Bold.ttf", 48)
        body_font = ImageFont.truetype("DejaVuSerif.ttf", 32)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    margin = 180
    y = 160
    draw.text((margin, y), title, font=title_font, fill=0)
    y += 100

    for para in paragraphs:
        lines = _wrap(para, body_font, size[0] - 2 * margin, draw)
        for line in lines:
            draw.text((margin, y), line, font=body_font, fill=0)
            y += 46
        y += 40  # espacio entre párrafos

    # Simula ruido de escaneo leve
    array = np.array(image).astype(np.int16)
    noise = np.random.normal(0, 4, array.shape)
    array = np.clip(array + noise, 0, 255).astype(np.uint8)
    noisy = Image.fromarray(array, mode="L")

    # Ligerísima rotación para ejercitar el deskew
    rotated = noisy.rotate(0.6, expand=False, fillcolor=255)
    return rotated.convert("RGB")


def main(output_path: str) -> None:
    pages = [
        build_page("Capítulo 1: El comienzo", [PARAGRAPH_1, PARAGRAPH_2]),
        build_page("Capítulo 2: El desarrollo", [PARAGRAPH_2, PARAGRAPH_1]),
    ]
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # resolution=200 hace que PIL calcule el tamaño de página en puntos PDF
    # a partir de los píxeles como si el lienzo fuese un escaneo real a
    # 200 dpi (1700x2200 px -> ~612x792 pt, tamaño carta). Sin esto, PIL
    # trata cada píxel como un punto PDF y genera una página del tamaño de
    # un póster, lo que dispara artificialmente el tiempo de OCR.
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=200.0)
    print(f"PDF de prueba generado en: {out.resolve()}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/sample_scanned.pdf")
