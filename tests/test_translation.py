"""Pruebas del módulo de traducción: NoOp, detección de idioma, la
fábrica de motores y la lógica de lotes/parseo del traductor de Anthropic
(usando un cliente simulado, sin llamar a la API real)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ocr_book.config.schema import TranslationConfig, TranslationEngineName
from ocr_book.reconstruction.document_model import Block, BlockType, Document, TextRun
from ocr_book.translation import NoOpTranslator, detect_document_language, get_translation_engine
from ocr_book.translation.anthropic_translator import AnthropicTranslator


def _doc(*texts: str) -> Document:
    document = Document()
    for text in texts:
        document.add(Block(type=BlockType.PARAGRAPH, runs=[TextRun(text)]))
    return document


def test_noop_translator_returns_document_unchanged() -> None:
    document = _doc("Hola mundo.")
    result = NoOpTranslator().translate(document, target_language="en")
    assert result is document


def test_detect_document_language_spanish() -> None:
    document = _doc(
        "Este es un texto en español con varias palabras para que el detector de "
        "idioma tenga suficiente contexto y no se equivoque."
    )
    assert detect_document_language(document) == "es"


def test_detect_document_language_english() -> None:
    document = _doc(
        "This is an English text with several words so that the language detector "
        "has enough context to make an accurate guess."
    )
    assert detect_document_language(document) == "en"


def test_factory_returns_noop_when_translation_disabled() -> None:
    config = TranslationConfig(enabled=False)
    engine = get_translation_engine(config)
    assert isinstance(engine, NoOpTranslator)


def test_factory_returns_noop_for_none_engine() -> None:
    config = TranslationConfig(enabled=True, engine=TranslationEngineName.NONE)
    engine = get_translation_engine(config)
    assert isinstance(engine, NoOpTranslator)


def test_anthropic_translator_batches_and_parses_tagged_response() -> None:
    document = Document(title="Titulo")
    document.add(Block(type=BlockType.TITLE, runs=[TextRun("Capitulo uno")]))
    document.add(Block(type=BlockType.PARAGRAPH, runs=[TextRun("Hola mundo, esto es una prueba.")]))

    translator = AnthropicTranslator(api_key="fake-key-for-test")

    fake_response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text=(
                    "<<<BLOCK_0>>>\nChapter one\n<<<END_0>>>\n"
                    "<<<BLOCK_1>>>\nHello world, this is a test.\n<<<END_1>>>"
                ),
            )
        ]
    )
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response
    translator._client = fake_client
    translator._api_key = "fake-key-for-test"

    result = translator.translate(document, target_language="en")

    assert result.blocks[0].text == "Chapter one"
    assert result.blocks[0].type == BlockType.TITLE
    assert result.blocks[1].text == "Hello world, this is a test."
    assert result.blocks[1].type == BlockType.PARAGRAPH
    fake_client.messages.create.assert_called_once()


def test_anthropic_translator_falls_back_to_original_on_missing_tag() -> None:
    """Si el modelo se salta un bloque en la respuesta, ese bloque debe
    conservar el texto original en vez de perderse o romper el resto."""
    document = _doc("Primer parrafo.", "Segundo parrafo.")
    translator = AnthropicTranslator(api_key="fake-key-for-test")

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="<<<BLOCK_0>>>\nFirst paragraph.\n<<<END_0>>>")]
    )
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response
    translator._client = fake_client
    translator._api_key = "fake-key-for-test"

    result = translator.translate(document, target_language="en")

    assert result.blocks[0].text == "First paragraph."
    assert result.blocks[1].text == "Segundo parrafo."
