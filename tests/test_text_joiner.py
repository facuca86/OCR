"""Pruebas unitarias de las heurísticas de unión de líneas y párrafos,
usando objetos OcrWord/OcrLine construidos a mano (sin pasar por imagen ni
OCR real) para poder controlar con precisión posición, huecos e
indentación en cada caso."""

from __future__ import annotations

from ocr_book.ocr.models import OcrLine, OcrWord
from ocr_book.reconstruction.text_joiner import (
    build_runs,
    ends_sentence,
    looks_like_list_item,
    split_into_paragraphs,
)

LEFT = 100
LINE_HEIGHT = 40
LINE_PITCH = 46  # interlineado normal (hueco pequeño entre líneas)


def _word(text: str, left: int, width: int = 80, bold: bool = False, italic: bool = False, top: int = 0) -> OcrWord:
    return OcrWord(
        text=text,
        left=left,
        top=top,
        width=width,
        height=LINE_HEIGHT,
        confidence=95.0,
        block_num=1,
        par_num=1,
        line_num=0,
        word_num=0,
        is_bold=bold,
        is_italic=italic,
    )


def _line(words: list[OcrWord], top: int, line_num: int = 0) -> OcrLine:
    for w in words:
        w.top = top
    return OcrLine(block_num=1, par_num=1, line_num=line_num, words=words)


def _make_words_line(text: str, left: int, top: int) -> OcrLine:
    words = []
    x = left
    for token in text.split():
        w = _word(token, x, width=len(token) * 15, top=top)
        words.append(w)
        x += w.width + 15
    return _line(words, top)


def test_wrapped_lines_without_real_break_are_joined_into_one_paragraph() -> None:
    """Ejemplo del enunciado: dos líneas impresas de un mismo párrafo,
    mismo margen izquierdo, hueco de interlineado normal -> un párrafo."""
    line1 = _make_words_line(
        "Lorem ipsum dolor sit amet consectetur adipiscing", LEFT, top=0
    )
    line2 = _make_words_line("elit sed do eiusmod tempor incididunt ut labore.", LEFT, top=LINE_PITCH)

    paragraphs = split_into_paragraphs([line1, line2])
    assert len(paragraphs) == 1

    runs = build_runs(paragraphs[0])
    text = "".join(r.text for r in runs)
    assert text == (
        "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
        "eiusmod tempor incididunt ut labore."
    )


def test_real_paragraph_break_detected_by_vertical_gap() -> None:
    line1 = _make_words_line("Primera linea del primer parrafo.", LEFT, top=0)
    line2 = _make_words_line("Segunda linea del primer parrafo.", LEFT, top=LINE_PITCH)
    # hueco mucho mayor que el interlineado normal: nuevo párrafo
    line3 = _make_words_line("Primera linea del segundo parrafo.", LEFT, top=LINE_PITCH * 2 + 70)

    paragraphs = split_into_paragraphs([line1, line2, line3])
    assert len(paragraphs) == 2
    assert paragraphs[0] == [line1, line2]
    assert paragraphs[1] == [line3]


def test_real_paragraph_break_detected_by_first_line_indent() -> None:
    line1 = _make_words_line("Fin del parrafo anterior en esta linea.", LEFT, top=0)
    # sangría de primera línea, mismo interlineado (estilo libro clásico, sin línea en blanco)
    line2 = _make_words_line("Nuevo parrafo con sangria inicial aqui.", LEFT + 80, top=LINE_PITCH)
    line3 = _make_words_line("continua el mismo parrafo sin sangria.", LEFT, top=LINE_PITCH * 2)

    paragraphs = split_into_paragraphs([line1, line2, line3])
    assert len(paragraphs) == 2
    assert paragraphs[0] == [line1]
    assert paragraphs[1] == [line2, line3]


def test_hyphenated_word_is_merged_across_line_break() -> None:
    line1 = _make_words_line("Esto es un ejemplo de una palabra parti-", LEFT, top=0)
    line2 = _make_words_line("da al final de la linea impresa.", LEFT, top=LINE_PITCH)

    runs = build_runs([line1, line2])
    text = "".join(r.text for r in runs)
    assert "partida" in text
    assert "parti-" not in text
    assert "parti- da" not in text


def test_hyphen_not_merged_when_next_word_is_capitalized() -> None:
    """Un guion al final de línea seguido de una palabra en mayúscula no
    es un corte de sílaba (podría ser una lista o un guion real); no debe
    fusionarse."""
    line1 = _make_words_line("Punto final de la oracion-", LEFT, top=0)
    line2 = _make_words_line("Nueva oracion en mayuscula.", LEFT, top=LINE_PITCH)

    runs = build_runs([line1, line2])
    text = "".join(r.text for r in runs)
    assert "oracion- Nueva" in text


def test_bold_and_italic_runs_are_preserved_within_a_paragraph() -> None:
    w1 = _word("Texto", LEFT, width=90)
    w2 = _word("en negrita", LEFT + 105, width=140, bold=True)
    w3 = _word("normal.", LEFT + 260, width=100)
    line = _line([w1, w2, w3], top=0)

    runs = build_runs([line])
    assert [r.text.strip() for r in runs] == ["Texto", "en negrita", "normal."]
    assert runs[0].bold is False
    assert runs[1].bold is True
    assert runs[2].bold is False


def test_looks_like_list_item_detects_bullets_and_numbering() -> None:
    assert looks_like_list_item("- Primer elemento de la lista")[0] is True
    assert looks_like_list_item("1. Primer elemento numerado")[0] is True
    assert looks_like_list_item("1. Primer elemento numerado")[1] is True
    assert looks_like_list_item("Texto normal sin marcador")[0] is False


def test_ends_sentence_detects_terminal_punctuation() -> None:
    assert ends_sentence("Esto termina aqui.") is True
    assert ends_sentence("Esto continua en la siguiente linea") is False
    assert ends_sentence("") is True
