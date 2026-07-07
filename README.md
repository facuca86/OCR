# OCR Book — reconstrucción inteligente de libros escaneados

Convierte PDFs escaneados (o imágenes sueltas) en documentos digitales
limpios y agradables de leer: no es "solo OCR", reconstruye el orden de
lectura, los párrafos, los títulos, las listas, las citas y las notas al
pie como lo haría un libro nacido digital, con traducción automática
opcional.

Ver [`ARCHITECTURE.md`](./ARCHITECTURE.md) para el análisis y la
justificación de las decisiones técnicas (por qué Python, por qué
PySide6, por qué Tesseract por defecto, cómo se reconstruye el orden de
lectura, etc.).

## Características

- Detecta automáticamente si un PDF ya tiene texto seleccionable o si es
  un escaneo puro que necesita OCR.
- Preprocesamiento configurable: deskew, eliminación de ruido, contraste
  (CLAHE), binarización (Otsu / adaptativa / Sauvola), corrección de
  orientación, recorte de bordes negros y márgenes.
- Detección de columnas a nivel de píxel (antes del OCR, para no mezclar
  texto de columnas distintas), encabezados, pies de página, numeración y
  notas al pie.
- Motor OCR por defecto: Tesseract 5. PaddleOCR y EasyOCR como motores
  opcionales intercambiables.
- Reconstrucción de párrafos: une líneas ajustadas por ancho de columna,
  resuelve palabras cortadas por guion, distingue sangría/salto de
  párrafo real, detecta listas y citas, preserva negrita/cursiva.
- Traducción opcional a nivel de documento (preserva la estructura),
  usando Claude (Anthropic) o un motor local/offline (Argos Translate).
- Exporta a PDF, DOCX, HTML, EPUB, TXT y Markdown desde el mismo modelo
  de documento intermedio.
- Procesa páginas en paralelo (multiproceso) y soporta libros de cientos
  de páginas.
- Interfaz gráfica (PySide6) con arrastrar y soltar, vista previa,
  configuración completa, barra de progreso, registro y cancelación; y
  una CLI equivalente para procesos por lotes.

## Requisitos del sistema

Además de Python 3.10+, el pipeline necesita el binario de Tesseract
instalado en el sistema (Tesseract no es una librería Python, `pytesseract`
solo lo invoca):

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng poppler-utils

# macOS (Homebrew)
brew install tesseract tesseract-lang poppler

# Windows
# Instalar desde https://github.com/UB-Mannheim/tesseract/wiki
```

Instala los paquetes de idioma de Tesseract (`tesseract-ocr-<código>`) que
necesites además de español/inglés.

Para exportar a PDF (WeasyPrint) hacen falta las librerías de sistema
Pango/Cairo, normalmente ya presentes en la mayoría de distribuciones
Linux de escritorio; en Debian/Ubuntu: `libpango-1.0-0 libpangocairo-1.0-0
libcairo2`.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # motor principal (sin GUI)
pip install -e .                     # instala el comando `ocrbook`
```

Extras opcionales (instalar solo lo que se necesite):

```bash
pip install PySide6                       # interfaz gráfica
pip install fastapi "uvicorn[standard]" jinja2 python-multipart  # interfaz web
pip install paddleocr paddlepaddle         # motor OCR alternativo de alta precisión
pip install easyocr                        # motor OCR alternativo
pip install argostranslate                 # traducción local/offline
pip install anthropic                      # traducción vía Claude (requiere ANTHROPIC_API_KEY)
```

O, con el extra correspondiente definido en `pyproject.toml`:

```bash
pip install -e ".[web]"
```

(`requirements-optional.txt` lista lo mismo por si prefieres instalarlo
todo de una vez.)

## Uso

### Línea de comandos

```bash
ocrbook mi_libro_escaneado.pdf -o ./output -f pdf -f epub --lang spa --lang eng
```

Opciones más comunes:

| Opción | Descripción |
|---|---|
| `-o, --output` | Carpeta de salida |
| `-f, --format` | Formato de salida (repetible): `pdf`, `docx`, `html`, `epub`, `txt`, `markdown` |
| `--lang` | Idioma(s) OCR en código Tesseract (repetible): `spa`, `eng`, `fra`... |
| `--engine` | Motor OCR: `tesseract` (por defecto), `paddleocr`, `easyocr` |
| `--translate-to` | Activa la traducción al idioma indicado (código ISO 639-1, ej. `en`) |
| `--translation-engine` | `anthropic` (por defecto) o `argos` |
| `--workers` | Número de procesos paralelos (por defecto, todos los núcleos) |
| `--gpu / --no-gpu` | Forzar uso de GPU en motores que lo soporten |
| `--config` | Ruta a un `config.yaml` propio (ver `config/default_config.yaml`) |

### Interfaz gráfica

```bash
pip install PySide6
ocrbook-gui
```

Permite arrastrar archivos, configurar OCR/traducción/salida, ver una
vista previa de la página de entrada y del documento reconstruido,
seguir el progreso, revisar el registro y cancelar en cualquier momento.

### Interfaz web

Una interfaz web (FastAPI + HTML/JS simple, sin build) sobre el mismo
`PipelineOrchestrator` que usan la CLI y la GUI, pensada para poder correr
en un servidor propio (no solo localhost) y procesar un libro a la vez.
Ver [`ARCHITECTURE.md`](./ARCHITECTURE.md#13-interfaz-web) para el porqué
de las decisiones (FastAPI, polling en vez de WebSocket/SSE, SQLite en vez
de una cola pesada tipo Celery, auth por token).

```bash
pip install -e ".[web]"

# Definí un token de acceso (recomendado en cualquier deploy que no sea
# 100% localhost). Si no lo definís, se genera uno aleatorio al arrancar
# y se imprime en el log del servidor: no queda abierta por defecto.
export OCRBOOK_WEB_TOKEN="elegí-un-token-largo-y-aleatorio"

# Carpeta de trabajo (subidas + salidas + historial en SQLite). Por
# defecto ./web_data, fuera del control de versiones.
export OCRBOOK_WEB_WORKDIR="./web_data"

ocrbook-web
# equivalente: python -m ocr_book.web
```

Por defecto escucha en `127.0.0.1:8000` (variables `OCRBOOK_WEB_HOST` /
`OCRBOOK_WEB_PORT` para cambiarlo). Para exponerlo en un servidor remoto,
ponelo detrás de un reverse proxy con HTTPS (nginx/Caddy) — la app en sí
no termina TLS.

Variables de entorno soportadas:

| Variable | Descripción | Por defecto |
|---|---|---|
| `OCRBOOK_WEB_TOKEN` | Token de acceso (se pide en `/login`). | uno aleatorio, generado y logueado al arrancar |
| `OCRBOOK_WEB_WORKDIR` | Carpeta para subidas, salidas y `jobs.db` (SQLite). | `./web_data` |
| `OCRBOOK_WEB_MAX_JOB_AGE_DAYS` | Antigüedad a partir de la cual "Eliminar jobs antiguos" (en `/history`) los borra. | `30` |
| `OCRBOOK_WEB_MAX_UPLOAD_MB` | Tamaño máximo de archivo subido. | `300` |
| `OCRBOOK_WEB_HOST` / `OCRBOOK_WEB_PORT` | Dirección/puerto de escucha. | `127.0.0.1` / `8000` |

Flujo: subís un PDF o imagen, elegís idioma/motor OCR, traducción
opcional, formatos de salida y las opciones de limpieza de página que ya
existen en `AppConfig` (mismo esquema que la CLI/GUI: no hay un
subconjunto hardcodeado aparte); el servidor procesa el libro en segundo
plano (uno a la vez) y la página de estado hace polling cada pocos
segundos hasta que termina, mostrando los enlaces de descarga y, si se
generó HTML, una vista previa embebida. `keep_images`/`keep_tables`
aparecen deshabilitados en el formulario con la nota "no implementado
aún", porque el analizador de layout todavía no los soporta (ver
"Limitaciones conocidas" más abajo) — no se ofrece una opción que no hace
nada silenciosamente.

Landing page estática (`index.html`, para GitHub Pages u otro hosting
estático): es solo una página de presentación con un enlace a la URL de
tu propio servidor ya desplegado — GitHub Pages no puede ejecutar Python,
así que no reemplaza a `ocrbook-web`.

### Uso programático

```python
from ocr_book.config import AppConfig
from ocr_book.pipeline import PipelineOrchestrator

config = AppConfig()
config.ocr.languages = ["spa", "eng"]
config.translation.enabled = True
config.translation.target_language = "en"

orchestrator = PipelineOrchestrator(config)
outputs = orchestrator.process_and_export("libro.pdf", "output/libro")
```

## Configuración

Todo el comportamiento configurable (idioma OCR, idioma destino, motor
OCR, resolución, formato de salida, uso de GPU, compresión/calidad de
imagen, eliminar encabezados/pies, conservar imágenes/tablas...) vive en
un único árbol tipado (`ocr_book.config.AppConfig`). Genera y edita tu
propio `config.yaml` a partir de `config/default_config.yaml`, y pásalo
con `ocrbook libro.pdf --config mi_config.yaml`.

## Arquitectura del código

```
src/ocr_book/
  config/          esquema y carga de configuración (pydantic + YAML)
  importers/       PDF/imagen -> páginas; detección de texto nativo vs. escaneo
  preprocessing/   deskew, ruido, contraste, binarización, bordes/márgenes
  layout/          columnas, encabezados/pies/notas, orden de lectura
  ocr/             interfaz de motor OCR + Tesseract/PaddleOCR/EasyOCR
  reconstruction/  modelo de documento + heurísticas de párrafo/lista/cita
  translation/     interfaz de traducción + Anthropic/Argos/NoOp
  export/          TXT/Markdown/HTML/DOCX/EPUB/PDF desde el modelo de documento
  pipeline/        orquestador (paralelismo, progreso, cancelación) + CLI
  gui/             aplicación PySide6
  web/             interfaz web (FastAPI + Jinja2/JS), backend sobre el mismo orquestador
```

Cada punto de extensión es una interfaz (`Importer`, `LayoutAnalyzer`,
`OcrEngine`, `TranslationEngine`, `Exporter`); para añadir un motor o
formato nuevo, se implementa la interfaz y se registra en la fábrica
correspondiente (`*/factory.py`), sin tocar el resto del pipeline.

## Desarrollo

```bash
pip install -r requirements.txt
pip install -e ".[dev,web]"  # el extra "web" hace falta para tests/test_web_api.py
pytest                       # suite completa (usa PDFs sintéticos generados en tests/fixtures)
ruff check src/              # lint
```

Los scripts `scripts/make_test_pdf.py` y `scripts/make_multicolumn_test_pdf.py`
generan PDFs "escaneados" sintéticos (con ruido, ligera rotación, dos
columnas, encabezado, pie de página y nota al pie) usados como fixtures de
prueba, sin depender de libros reales con derechos de autor.

## Limitaciones conocidas

- La extracción de **imágenes y tablas** como bloques propios del
  documento reconstruido no está implementada todavía: el modelo de datos
  y la configuración (`keep_images`, `keep_tables`) ya están preparados
  para ello, pero el analizador de layout heurístico actual solo clasifica
  texto (título, cuerpo, listas, citas, notas). Es el punto de extensión
  más natural para un modelo de segmentación de layout más avanzado (ver
  `ARCHITECTURE.md`, sección 4).
- La negrita/cursiva se detecta por análisis de trazo (heurística), no es
  perfecta en escaneos muy degradados.
- La traducción con Claude requiere `ANTHROPIC_API_KEY`; con Argos
  Translate requiere haber instalado antes el paquete de idioma
  correspondiente (100% offline, pero de menor calidad).
