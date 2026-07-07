"""Excepciones propias del dominio, para que la UI y el CLI puedan
distinguir errores esperables (archivo inválido, motor no instalado) de
bugs inesperados."""


class OcrBookError(Exception):
    """Excepción base de la aplicación."""


class UnsupportedFileError(OcrBookError):
    """El archivo de entrada no es un PDF ni una imagen soportada."""


class EngineNotAvailableError(OcrBookError):
    """Un motor (OCR, layout, traducción) requerido no está instalado."""


class PipelineCancelledError(OcrBookError):
    """El procesamiento fue cancelado por el usuario."""
