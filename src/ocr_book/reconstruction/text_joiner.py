"""Heurísticas de unión de líneas: el corazón de la reconstrucción.

Aquí se decide, línea a línea, si un salto pertenece únicamente al ancho
de columna (debe desaparecer y fundirse en un espacio, o en nada si la
palabra estaba cortada por un guion) o si de verdad empieza un párrafo
nuevo (debe conservarse como salto real).
"""

from __future__ import annotations

import re
import statistics

from ocr_book.ocr.models import OcrLine, OcrWord
from ocr_book.reconstruction.document_model import TextRun

_BULLET_RE = re.compile(r"^[•∙◦‣·*-]\s+")
_NUMBERED_LIST_RE = re.compile(r"^(\d{1,3}|[a-zA-Z]|[ivxlcdm]{1,6})[.\)]\s+")
_SENTENCE_END_RE = re.compile(r"[.?!:;»”\"'\)\]]$")
_PARAGRAPH_GAP_MULTIPLIER = 1.6
_INDENT_CHAR_WIDTH_MULTIPLIER = 1.8


def ends_sentence(text: str) -> bool:
    """Si el texto no termina en puntuación fuerte, muy probablemente el
    párrafo continúa en la siguiente línea/bloque en vez de haber
    terminado ahí."""
    stripped = text.rstrip()
    if not stripped:
        return True
    return bool(_SENTENCE_END_RE.search(stripped))


def looks_like_list_item(text: str) -> tuple[bool, bool]:
    """Devuelve (es_lista, es_numerada) según si el texto empieza con una
    viñeta o con un marcador de numeración/letra."""
    stripped = text.lstrip()
    if _BULLET_RE.match(stripped):
        return True, False
    if _NUMBERED_LIST_RE.match(stripped):
        return True, True
    return False, False


def _should_merge_hyphenated(line_text: str, next_first_word: str) -> bool:
    """Regla estándar y conservadora: un guion al final de línea, precedido
    de una letra, seguido de una palabra que empieza en minúscula, es casi
    siempre un corte de sílaba por ajuste de línea, no un guion real
    (una palabra compuesta partida justo ahí en el original es el caso
    raro que esta heurística no distingue)."""
    stripped = line_text.rstrip()
    if len(stripped) < 2 or stripped[-1] != "-" or not stripped[-2].isalpha():
        return False
    if not next_first_word or not next_first_word[0].islower():
        return False
    return True


def estimate_indent_threshold(lines: list[OcrLine]) -> float:
    heights = [line.bbox[3] - line.bbox[1] for line in lines]
    median_height = statistics.median(heights) if heights else 20.0
    approx_char_width = median_height * 0.55
    return approx_char_width * _INDENT_CHAR_WIDTH_MULTIPLIER


def split_into_paragraphs(lines: list[OcrLine]) -> list[list[OcrLine]]:
    """Agrupa una secuencia de líneas de OCR (ya en orden de lectura,
    típicamente todas las líneas de una misma región de layout) en
    párrafos, detectando sangría de primera línea o un hueco vertical
    mayor al interlineado habitual como inicio de párrafo nuevo."""
    if not lines:
        return []
    if len(lines) == 1:
        return [[lines[0]]]

    lefts = [line.bbox[0] for line in lines]
    baseline_left = statistics.median(lefts)
    indent_threshold = estimate_indent_threshold(lines)

    vertical_gaps = [lines[i].bbox[1] - lines[i - 1].bbox[3] for i in range(1, len(lines))]
    positive_gaps = [g for g in vertical_gaps if g > 0]
    typical_gap = statistics.median(positive_gaps) if positive_gaps else 0.0

    paragraphs: list[list[OcrLine]] = [[lines[0]]]
    for i in range(1, len(lines)):
        line = lines[i]
        gap = vertical_gaps[i - 1]
        is_indented = (line.bbox[0] - baseline_left) > indent_threshold
        is_large_gap = typical_gap > 0 and gap > typical_gap * _PARAGRAPH_GAP_MULTIPLIER
        starts_list_item, _ = looks_like_list_item(line.text)

        if is_indented or is_large_gap or starts_list_item:
            paragraphs.append([line])
        else:
            paragraphs[-1].append(line)

    return paragraphs


def is_first_line_indented(paragraph_lines: list[OcrLine], baseline_left: float, indent_threshold: float) -> bool:
    if not paragraph_lines:
        return False
    return (paragraph_lines[0].bbox[0] - baseline_left) > indent_threshold


def build_runs(lines: list[OcrLine]) -> list[TextRun]:
    """Une las palabras de todas las líneas de un párrafo en runs de texto
    con estilo uniforme, resolviendo guiones de fin de línea y
    preservando negrita/cursiva por tramos."""
    # (texto_del_token_con_espacio_final_si_corresponde, bold, italic)
    tokens: list[tuple[str, bool, bool]] = []

    for line_idx, line in enumerate(lines):
        words = line.words
        for word_idx, word in enumerate(words):
            text = word.text
            trailing_space = True

            is_last_word_of_line = word_idx == len(words) - 1
            if is_last_word_of_line and line_idx < len(lines) - 1:
                next_words = lines[line_idx + 1].words
                next_first = next_words[0].text if next_words else ""
                if _should_merge_hyphenated(text, next_first):
                    text = text[:-1]
                    trailing_space = False

            is_last_token_overall = is_last_word_of_line and line_idx == len(lines) - 1
            if is_last_token_overall:
                trailing_space = False

            tokens.append((text + (" " if trailing_space else ""), word.is_bold, word.is_italic))

    if not tokens:
        return []

    runs: list[TextRun] = []
    current_text, current_bold, current_italic = tokens[0]
    for text, bold, italic in tokens[1:]:
        if bold == current_bold and italic == current_italic:
            current_text += text
        else:
            runs.append(TextRun(current_text, current_bold, current_italic))
            current_text, current_bold, current_italic = text, bold, italic
    runs.append(TextRun(current_text, current_bold, current_italic))
    return runs


def dominant_style(words: list[OcrWord]) -> tuple[bool, bool]:
    """Negrita/cursiva "dominante" de un conjunto de palabras (más de la
    mitad), usado para decidir el estilo de bloques cortos como títulos."""
    if not words:
        return False, False
    bold = sum(1 for w in words if w.is_bold) > len(words) / 2
    italic = sum(1 for w in words if w.is_italic) > len(words) / 2
    return bold, italic
