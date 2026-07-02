"""Tesseract usa códigos ISO 639-2/T de 3 letras (spa, eng, fra...); los
motores basados en deep learning (PaddleOCR, EasyOCR) usan sus propios
códigos cortos. Esta tabla traduce el primer idioma configurado por el
usuario al código que cada motor opcional espera."""

from __future__ import annotations

TESSERACT_TO_PADDLEOCR = {
    "eng": "en",
    "spa": "es",
    "fra": "fr",
    "deu": "german",
    "ita": "it",
    "por": "pt",
    "nld": "nl",
    "rus": "ru",
    "chi_sim": "ch",
    "chi_tra": "chinese_cht",
    "jpn": "japan",
    "kor": "korean",
    "ara": "ar",
}

TESSERACT_TO_EASYOCR = {
    "eng": "en",
    "spa": "es",
    "fra": "fr",
    "deu": "de",
    "ita": "it",
    "por": "pt",
    "nld": "nl",
    "rus": "ru",
    "chi_sim": "ch_sim",
    "chi_tra": "ch_tra",
    "jpn": "ja",
    "kor": "ko",
    "ara": "ar",
}


def to_paddleocr_lang(tesseract_langs: list[str]) -> str:
    primary = tesseract_langs[0] if tesseract_langs else "eng"
    return TESSERACT_TO_PADDLEOCR.get(primary, "en")


def to_easyocr_langs(tesseract_langs: list[str]) -> list[str]:
    mapped = [TESSERACT_TO_EASYOCR.get(lang, "en") for lang in tesseract_langs]
    return list(dict.fromkeys(mapped)) or ["en"]
