"""Esquema tipado de configuración de la aplicación.

Todo lo que el usuario puede ajustar (idioma OCR, motor, resolución,
traducción, formatos de salida, uso de GPU, etc.) vive aquí como un único
árbol de modelos Pydantic, para que un `config.yaml` inválido falle rápido
y con un mensaje claro en vez de romper el pipeline a mitad de un libro.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class OcrEngineName(str, Enum):
    TESSERACT = "tesseract"
    PADDLEOCR = "paddleocr"
    EASYOCR = "easyocr"


class LayoutAnalyzerName(str, Enum):
    HEURISTIC = "heuristic"


class BinarizationMethod(str, Enum):
    NONE = "none"
    OTSU = "otsu"
    ADAPTIVE_GAUSSIAN = "adaptive_gaussian"
    SAUVOLA = "sauvola"


class TranslationEngineName(str, Enum):
    NONE = "none"
    ANTHROPIC = "anthropic"
    ARGOS = "argos"


class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    EPUB = "epub"
    TXT = "txt"
    MARKDOWN = "markdown"


class PreprocessingConfig(BaseModel):
    """Ajustes del módulo de preprocesamiento (todo activable/desactivable)."""

    enabled: bool = True
    denoise: bool = True
    enhance_contrast: bool = True
    deskew: bool = True
    binarize: bool = True
    binarization_method: BinarizationMethod = BinarizationMethod.ADAPTIVE_GAUSSIAN
    detect_orientation: bool = True
    remove_borders: bool = True
    crop_margins: bool = True
    target_dpi: int = Field(default=300, ge=72, le=1200)
    max_dimension_px: int = Field(
        default=6000,
        ge=1000,
        description=(
            "Límite de seguridad: si el lado mayor de la página supera esto (escaneos a "
            "resolución inusualmente alta), se reduce antes de procesar. Evita que una "
            "página fuera de lo común dispare tiempos de proceso desproporcionados."
        ),
    )


class LayoutConfig(BaseModel):
    analyzer: LayoutAnalyzerName = LayoutAnalyzerName.HEURISTIC
    detect_columns: bool = True
    max_columns: int = Field(default=4, ge=1, le=8)
    detect_headers: bool = True
    detect_footers: bool = True
    detect_footnotes: bool = True
    detect_page_numbers: bool = True
    remove_headers: bool = False
    remove_footers: bool = False
    remove_page_numbers: bool = False


class OcrConfig(BaseModel):
    engine: OcrEngineName = OcrEngineName.TESSERACT
    languages: list[str] = Field(default_factory=lambda: ["spa", "eng"])
    use_gpu: bool = False
    psm: int = Field(default=3, ge=0, le=13, description="Tesseract page segmentation mode")
    oem: int = Field(default=1, ge=0, le=3, description="Tesseract OCR engine mode (1=LSTM)")
    min_confidence: float = Field(default=40.0, ge=0.0, le=100.0)
    detect_bold_italic: bool = True


class TranslationConfig(BaseModel):
    enabled: bool = False
    engine: TranslationEngineName = TranslationEngineName.ANTHROPIC
    source_language: str | None = Field(
        default=None, description="Código ISO 639-1; None = autodetectar"
    )
    target_language: str = "en"
    preserve_structure: bool = True
    anthropic_model: str = "claude-sonnet-5"


class ExportConfig(BaseModel):
    formats: list[ExportFormat] = Field(default_factory=lambda: [ExportFormat.PDF])
    output_dir: Path = Path("./output")
    keep_images: bool = True
    keep_tables: bool = True
    image_quality: int = Field(default=85, ge=1, le=100)
    image_max_width_px: int = Field(default=1600, ge=200)
    embed_page_numbers: bool = False


class PerformanceConfig(BaseModel):
    max_workers: int | None = Field(
        default=None, description="None = usar todos los núcleos disponibles"
    )
    use_gpu: bool = False
    batch_size: int = Field(default=1, ge=1)


class AppConfig(BaseModel):
    """Configuración completa de la aplicación."""

    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    model_config = {"extra": "forbid"}
