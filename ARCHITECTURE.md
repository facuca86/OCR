# Arquitectura del proyecto — Análisis y justificación técnica

Este documento explica el razonamiento detrás de la elección de tecnologías,
antes de entrar en el código. El objetivo del proyecto no es "hacer OCR", es
**reconstruir un libro digital de alta calidad** a partir de páginas
escaneadas: orden de lectura correcto, párrafos bien formados, estilos
conservados y, opcionalmente, traducción fiel a la estructura original.

## 1. Lenguaje principal: Python

| Alternativa | Por qué se descarta como núcleo |
|---|---|
| C#/.NET (Avalonia) | Buen framework de UI, pero el ecosistema de visión por computador, OCR y NLP en .NET es mucho más pobre; terminaría llamando a Python de todos modos. |
| Rust/Go/C++ | Excelente rendimiento, pero cada integración con motores OCR modernos (PaddleOCR, EasyOCR, modelos Transformer) exige reimplementar bindings o llamar a Python igualmente. El tiempo de desarrollo no se traduce en mejor calidad de OCR. |
| Node.js/Electron | Fuerte para UI, débil para el pipeline de imagen/ML; requeriría un backend separado en otro lenguaje. |
| **Python (elegido)** | Es, con diferencia, el lenguaje con mejor soporte para OpenCV, Tesseract (`pytesseract`), PaddleOCR, EasyOCR, modelos Transformer (TrOCR, docTR), PyMuPDF, librerías de generación de documentos (python-docx, ebooklib, WeasyPrint) y traducción (Argos Translate, MarianMT, APIs de LLM). Al ser todo el pipeline CPU/GPU-bound y basado en modelos de ML, Python es el lenguaje "nativo" de este dominio. |

**Conclusión**: todo el pipeline de procesamiento (preprocesado, OCR, layout,
reconstrucción, traducción, exportación) se implementa en Python puro. Las
partes críticas en rendimiento (OpenCV, Tesseract, PyTorch/Paddle) ya están
escritas en C/C++/CUDA por debajo, así que Python no introduce un cuello de
botella real: solo orquesta.

## 2. Interfaz gráfica: PySide6 (Qt 6)

Se evaluaron las opciones que el usuario permitió explícitamente:

- **Electron**: requiere mantener dos stacks (Node para la UI, Python para el
  motor) comunicados por IPC/HTTP, duplicando la lógica de configuración y
  complicando el empaquetado y la depuración.
- **Tauri**: más liviano que Electron, pero igualmente exige un backend
  Python separado (sidecar) con el mismo problema de doble stack y de paso
  de datos binarios (imágenes, PDFs) entre procesos.
- **Flutter**: UI muy pulida, pero el motor de OCR seguiría en Python; habría
  que exponerlo como servicio HTTP/gRPC, añadiendo complejidad operativa sin
  beneficio de calidad.
- **Web (navegador)**: útil para SaaS, pero el usuario quiere una app de
  escritorio con arrastrar-soltar de archivos locales y acceso a la GPU
  local; una web app añade fricción (servidor, CORS, subida de archivos
  potencialmente enormes).
- **PySide6/Qt (elegido)**: se queda en un único lenguaje y proceso, con
  bindings oficiales de Qt para Python (licencia LGPL). Permite:
  - arrastrar y soltar archivos de forma nativa,
  - hilos en segundo plano (`QThreadPool`/`QRunnable`) para no bloquear la UI
    mientras se procesa,
  - widgets modernos personalizables con QSS (hoja de estilos tipo CSS),
  - integración directa con el motor sin serialización de por medio,
  - empaquetado multiplataforma (Windows/macOS/Linux) con `pyinstaller`.

**Conclusión**: un único stack Python de extremo a extremo reduce
superficie de fallos y facilita que "cada módulo se pueda reemplazar por
otro" (requisito del proyecto), porque la UI simplemente llama a interfaces
Python, sin capa de red intermedia.

## 3. Preprocesamiento de imagen: OpenCV + Pillow

OpenCV es el estándar de facto para visión por computador clásica y ofrece
todas las primitivas necesarias sin depender de modelos de ML pesados:

- **Deskew**: `minAreaRect` sobre la máscara de texto binarizada, o transformada
  de Hough sobre bordes, para estimar y corregir el ángulo de inclinación.
- **Denoise**: `fastNlMeansDenoising` para ruido de escaneo, mediana para
  "sal y pimienta".
- **Contraste**: CLAHE (*Contrast Limited Adaptive Histogram Equalization*),
  mejor que una ecualización global porque no sobre-satura zonas ya claras.
- **Binarización**: umbral adaptativo (Gaussiano) u Otsu según el
  histograma de la página; se deja configurable porque textos con manchas
  de humedad o papel amarillento se benefician de estrategias distintas.
- **Orientación**: se delega en el OSD (*Orientation and Script Detection*)
  de Tesseract, que ya incluye un clasificador entrenado para 0/90/180/270°.
- **Recorte de bordes/márgenes**: detección de contornos + proyección de
  histogramas de píxeles negros por fila/columna para localizar el borde
  real del papel dentro del área escaneada.

Cada operación es una función pura `ndarray -> ndarray` registrada en un
`PreprocessingPipeline` configurable, de forma que activarlas/desactivarlas
o reordenarlas no requiere tocar código, solo el archivo de configuración.

## 4. Análisis de layout: heurístico, con interfaz para modelos ML

Reconstruir el **orden de lectura** (columnas, títulos, notas al pie,
encabezados repetidos, pies de página, numeración) es el problema más
importante después del OCR en sí. Hay dos familias de enfoques:

1. **Heurístico geométrico**: usar la jerarquía nativa de Tesseract
   (`page → block → paragraph → line → word`, con cajas delimitadoras) y
   aplicar reglas: agrupar bloques por columnas usando clustering de
   coordenadas X, detectar encabezados/pies por su posición constante y
   repetición entre páginas, detectar títulos por tamaño de fuente relativo
   y centrado, detectar notas al pie por estar bajo una línea horizontal en
   la parte inferior con fuente más pequeña.
2. **Modelos de segmentación de layout** (LayoutParser, PP-StructureV2,
   Detectron2 con modelos PubLayNet/DocLayNet): mayor precisión en
   documentos complejos, pero dependencias pesadas (PyTorch/Paddle + pesos
   de varios cientos de MB) y tiempos de instalación/inferencia mucho
   mayores.

**Decisión**: implementar primero el analizador heurístico (rápido, sin
dependencias pesadas, funciona en CPU, resultados ya muy buenos en libros
con maquetación razonable) detrás de una interfaz `LayoutAnalyzer`. Se deja
preparado el punto de extensión (`layout/ml_analyzer.py`, no incluido por
defecto) para enchufar PP-StructureV2 cuando el usuario quiera exprimir
precisión máxima en documentos con tablas/columnas muy irregulares — el
resto del pipeline no necesita cambiar porque ambos devuelven el mismo
modelo `PageLayout`.

## 5. Motores OCR: arquitectura plug-in, Tesseract como motor por defecto

| Motor | Ventajas | Desventajas | Rol |
|---|---|---|---|
| **Tesseract 5 (LSTM)** | Maduro, +100 idiomas, salida jerárquica con posición y confianza por palabra, detecta negrita/cursiva vía análisis de trazo, sin dependencias de GPU, instalación ligera. | Algo menos preciso que los motores basados en deep learning modernos en escaneos muy degradados. | **Motor por defecto**, siempre disponible. |
| **PaddleOCR** | Excelente precisión, detección + reconocimiento en un solo modelo, buen soporte CJK. | Dependencia de PaddlePaddle (pesada), primera ejecución descarga modelos. | Motor **opcional de alta precisión**, activable por configuración. |
| **EasyOCR** | Fácil de usar, base PyTorch, +80 idiomas. | Más lento en CPU, dependencia de PyTorch. | Alternativa opcional, útil si PaddleOCR no está disponible en la plataforma. |
| **TrOCR / docTR (Transformers)** | Estado del arte en reconocimiento de texto manuscrito/degradado. | Muy pesado, requiere GPU para ser práctico en libros de cientos de páginas. | Punto de extensión documentado (`ocr/transformer_engine.py`), no incluido por defecto para no forzar una descarga de varios GB. |

Todos implementan la interfaz `OcrEngine.recognize(image, lang) -> OcrResult`,
donde `OcrResult` contiene palabras con caja, confianza, y flags de
negrita/cursiva cuando el motor los soporta. Esto permite:

- cambiar de motor por configuración sin tocar el resto del pipeline,
- en el futuro, ejecutar dos motores sobre la misma página y quedarse con
  la transcripción de mayor confianza palabra por palabra (*ensemble*),
  ya soportado por el modelo de datos aunque no activado por defecto.

## 6. Reconstrucción de texto: el corazón del proyecto

Este módulo no depende de librerías externas más allá de la biblioteca
estándar: es lógica pura sobre el modelo `PageLayout` + `OcrResult`.

Reglas clave implementadas (ver `reconstruction/text_joiner.py`):

- **Unión de líneas dentro de un párrafo**: dos líneas consecutivas del
  mismo bloque se funden con un espacio, *salvo* que la línea anterior
  termine en puntuación fuerte (`.`, `:`, `?`, `!`, `»`) seguida de un
  salto detectado como fin de párrafo por sangría/espaciado vertical
  mayor al interlineado habitual del bloque.
- **Palabras cortadas por guion**: si una línea termina en `-` y la
  siguiente palabra comienza en minúscula, se elimina el guion y se
  concatena (`adipis-` + `cing` → `adipiscing`), salvo excepciones de
  guiones "duros" (palabras compuestas conocidas) configurables.
- **Sangría y saltos reales de párrafo**: se estima el ancho de columna y
  el interlineado modal del bloque; una línea que empieza más a la derecha
  de lo habitual (sangría) o cuya línea anterior deja un hueco vertical
  mayor, marca inicio de párrafo nuevo.
- **Negrita/cursiva**: se preservan como *runs* con atributos dentro de un
  párrafo (no todo-o-nada por línea), igual que lo haría un procesador de
  texto.
- **Estructura**: título de capítulo, subtítulos, listas (detección de
  viñetas/numeración al inicio de línea), citas (bloques con sangría
  simétrica y a veces fuente distinta) y notas al pie se modelan como tipos
  de bloque distintos en un **modelo de documento propio** (`Document`,
  `Paragraph`, `Heading`, `ListBlock`, `Quote`, `Footnote`, `ImageBlock`,
  `TableBlock`), independiente de cualquier formato de salida.

Ese modelo de documento intermedio es la pieza que hace posible exportar a
PDF, DOCX, HTML, EPUB, Markdown o TXT sin duplicar lógica: cada exportador
solo sabe recorrer `Document`, no sabe nada de OCR ni de layout.

## 7. Traducción: motor abstracto, por defecto basado en LLM

La traducción palabra-por-palabra rompe la estructura de un libro. Por eso:

- Se traduce a nivel de **bloque** (`Paragraph`, `Heading`, etc.), nunca a
  nivel de línea OCR, preservando el modelo de documento (un párrafo de
  entrada produce un párrafo de salida, un título sigue siendo título).
- Interfaz `TranslationEngine.translate(document, target_lang) -> Document`.
- Implementaciones:
  - `NoOpTranslator`: no traduce (opción "mantener idioma original").
  - `AnthropicTranslator` (por defecto cuando se activa traducción): usa un
    modelo Claude vía API, con un *prompt* que exige preservar Markdown
    estructural (títulos, listas, énfasis) y no añadir ni quitar párrafos.
    Es la opción de mayor calidad para preservar tono, notas al pie y
    coherencia entre capítulos.
  - `ArgosTranslateEngine` (opcional, 100% local/offline, basado en
    modelos OpenNMT): para usuarios sin conexión o que priorizan
    privacidad, con calidad algo menor.
- Detección de idioma de origen con `langdetect` (rápido, sin dependencias
  pesadas) antes de traducir.

El motor se selecciona por configuración (`translation.engine: anthropic |
argos | none`), cumpliendo el requisito de "abstraer el motor para poder
cambiarlo fácilmente".

## 8. Exportación

Formato de salida → librería:

- **TXT / Markdown**: serialización directa del `Document`, sin dependencias.
- **HTML**: plantilla propia con CSS embebido pensado para lectura (tipografía
  serif, ancho de línea limitado, sangrías de párrafo, notas al pie como
  enlaces).
- **DOCX**: `python-docx`, mapea `Heading`→heading styles, `Quote`→estilo cita,
  listas→estilos de lista nativos de Word, *runs* con negrita/cursiva.
- **EPUB**: `ebooklib`, genera capítulos XHTML a partir del mismo HTML base,
  con tabla de contenidos generada desde los `Heading`.
- **PDF**: se renderiza el mismo HTML/CSS con **WeasyPrint** en lugar de
  dibujar con ReportLab a bajo nivel. Motivo: WeasyPrint soporta CSS de
  paginación (saltos de página, encabezados/pies, numeración), lo que da un
  PDF con tipografía moderna y agradable de leer, reutilizando el mismo
  motor de plantillas que el exportador HTML (menos código duplicado).

## 9. Configuración

`pydantic-settings` valida un `config.yaml` (o variables de entorno) contra
un esquema tipado (`ConfigSchema`), de forma que errores de configuración
(idioma inválido, motor inexistente) se detectan al arrancar, no a mitad de
un libro de 800 páginas. El archivo cubre exactamente los puntos pedidos:
idioma OCR, idioma destino, motor OCR, resolución de render, formato(s) de
salida, uso de GPU, compresión/calidad de imágenes embebidas, eliminación
de encabezados/pies, conservación de imágenes y tablas.

## 10. Rendimiento y paralelismo

- El pipeline procesa **una página = una unidad de trabajo**. Las páginas
  se distribuyen en un `ProcessPoolExecutor` (paralelismo real entre
  núcleos, evita el GIL) para preprocesado + OCR, que es la parte
  CPU-bound.
- Los motores que soportan GPU (PaddleOCR, EasyOCR) se ejecutan en el
  proceso principal en modo secuencial por lote cuando `use_gpu: true`,
  porque una GPU no se beneficia de multiproceso (se satura con un único
  flujo de trabajo bien alimentado); en CPU se reparte entre procesos.
- El orquestador expone *callbacks* de progreso por página y un
  `cancel_event` (`multiprocessing.Event`) que se revisa entre páginas para
  permitir cancelación cooperativa desde la UI.
- Los libros de cientos/miles de páginas se procesan en streaming: cada
  página procesada se libera de memoria tan pronto se serializa su
  `PageResult`, evitando mantener todas las imágenes decodificadas a la vez.

## 11. Modularidad y sustitución de componentes

Todos los puntos de extensión son interfaces (`abc.ABC`) con una única
responsabilidad: `Importer`, `PreprocessingOperation`, `LayoutAnalyzer`,
`OcrEngine`, `TranslationEngine`, `Exporter`. El `PipelineOrchestrator` solo
conoce estas interfaces, nunca una implementación concreta directamente:
las instancias se construyen en *factories* (`ocr/engine_factory.py`,
`export/factory.py`, `translation/factory.py`) a partir del `ConfigSchema`.
Esto satisface el requisito de que "cada módulo debe poder reemplazarse por
otro" sin tocar el resto del sistema.

## 13. Interfaz web

La GUI (PySide6) asume un usuario con acceso a la máquina donde corre el
proceso (arrastrar y soltar archivos locales, ver una vista previa nativa).
El objetivo de la interfaz web es distinto: poder lanzar conversiones desde
un navegador contra un servidor propio, potencialmente remoto, sin abrir
una sesión de escritorio. Se agrega como una capa nueva (`ocr_book.web/`)
que **no duplica lógica de negocio**: llama a `PipelineOrchestrator`
exactamente igual que la CLI y la GUI, solo cambia cómo se dispara y cómo
se reporta el resultado.

### 13.1 FastAPI + HTML servido por el propio backend (sin build de frontend)

Se evaluó una SPA (React/Vue) contra un backend HTTP separado, pero para
"subir un archivo, elegir opciones, ver progreso, descargar el resultado"
una SPA es una superficie de mantenimiento (build, bundler, versión de
Node, estado en el cliente) que no aporta nada frente a plantillas
Jinja2 servidas directamente por FastAPI con un poco de JS vanilla para el
polling y el drag&drop. Esto prioriza lo que pidió el proyecto
explícitamente: simplicidad de mantenimiento por sobre sofisticación. Si
en el futuro la interfaz necesita interactividad rica (edición del
documento reconstruido, por ejemplo), ese es el momento de justificar una
SPA — no antes.

FastAPI en particular (sobre Flask/Django) porque: valida el *payload* del
formulario reutilizando el mismo `AppConfig` de Pydantic que ya existe
(sin reescribir una capa de validación paralela), tiene soporte nativo de
`UploadFile`/`BackgroundTasks`/`TestClient` sin dependencias extra, y su
tipado explícito documenta la API casi gratis (`/docs` autogenerado).

### 13.2 Un job a la vez, con un hilo propio en vez de una cola pesada

El caso de uso declarado es **un libro a la vez**, no un servicio
multi-tenant de alto volumen. Meter Celery/RQ + Redis (procesos aparte,
broker, *result backend*, *worker* a supervisar) sería infraestructura sin
beneficio real para ese caso de uso, y además el propio
`PipelineOrchestrator` ya paraleliza *dentro* de un job (`ProcessPoolExecutor`
por página); una cola distribuida paralelizaría *entre* jobs, que es
justamente lo que no hace falta todavía.

En su lugar, `JobRunner` (`web/jobs/runner.py`) es un único hilo en segundo
plano que consume un `queue.Queue` FIFO: la subida encola un `job_id` y
responde de inmediato (no bloquea el request mientras se procesa el
libro), el hilo los toma de a uno y llama a
`orchestrator.process_and_export(...)`. La estructura queda preparada para
crecer sin reescritura: `JobRunner` es el único punto que conocería una
cola distribuida si hiciera falta (cambiar `queue.Queue` +
`threading.Thread` por un *broker* real), las rutas HTTP y el store no
cambian porque solo conocen la interfaz "encolar un id, consultar su
estado".

### 13.3 Progreso por *polling*, no WebSocket/SSE

El pipeline ya expone progreso por página vía `ProgressCallback`
(`pipeline/progress.py`), el mismo mecanismo que usan la GUI (señales Qt) y
la CLI (línea de texto). Para la web, en vez de mantener una conexión
persistente (WebSocket o Server-Sent Events) con toda la complejidad que
suma (reconexión, *keep-alive*, proxies que no siempre dejan pasar
conexiones largas), el callback simplemente escribe el último evento en el
store (SQLite) y el navegador pregunta `/api/jobs/{id}/status` cada 2-3
segundos con `fetch`. El requisito explícito era "no necesito progreso en
tiempo real fino", así que el costo de una conexión persistente no se
justifica frente a un `setTimeout` con `fetch`.

### 13.4 Persistencia: SQLite, no una base de datos aparte

El historial de jobs (para que sobreviva a un reinicio del proceso) vive
en un único archivo SQLite (`web/jobs/store.py`), sin servidor de base de
datos que desplegar/mantener aparte. Alcanza sobradamente para el volumen
de escritura de "un job a la vez" y para las consultas que hace la
interfaz (listar, obtener por id, actualizar progreso). No se evaluó
Postgres/MySQL porque agregarían una dependencia operativa (proceso
aparte, credenciales, migración) sin necesidad real dado el volumen; si en
el futuro hiciera falta multi-instancia (varios procesos del servidor web
compartiendo estado), ese es el punto en el que SQLite deja de alcanzar y
se justifica un motor cliente-servidor — no antes.

### 13.5 Autenticación: token simple, no un sistema de usuarios

Como el server está pensado para eventualmente correr fuera de
`localhost`, no debía quedar abierto por defecto. Se implementó el nivel
mínimo razonable para una instancia de uso personal/reducido: un único
token (`OCRBOOK_WEB_TOKEN`) comparado con `secrets.compare_digest`,
guardado en una cookie tras `/login`, y aceptado también como
`Authorization: Bearer` para scripts/tests. Si no se define la variable de
entorno, se genera un token aleatorio al arrancar y se loguea (igual que
hace Jupyter), para que "no configrar nada" nunca signifique "abierto a
cualquiera". No se implementó un sistema de usuarios/roles porque no hay
ningún requisito de multi-usuario: sería complejidad sin caso de uso
detrás. Para producción real, la recomendación (documentada en el README)
es poner esto detrás de un reverse proxy con HTTPS, ya que la app no
termina TLS por sí sola.

### 13.6 GitHub Pages: solo una landing page estática

Se agrega un `index.html` en la raíz del repo pensado para GitHub Pages,
pero GitHub Pages solo sirve archivos estáticos: no puede ejecutar Python,
FastAPI ni el pipeline de OCR. Por eso ese archivo es exclusivamente una
página de presentación del proyecto con un enlace a donde el usuario haya
desplegado su propio `ocrbook-web` — no es, ni pretende ser, un
reemplazo del servidor.

## 14. Resumen de la pila tecnológica

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Interfaz | PySide6 (Qt 6) |
| PDF/Imágenes | PyMuPDF, Pillow |
| Preprocesamiento | OpenCV |
| OCR | Tesseract 5 (`pytesseract`) por defecto; PaddleOCR/EasyOCR opcionales |
| Layout | Heurístico propio sobre jerarquía Tesseract; extensible a PP-Structure |
| Traducción | Claude (Anthropic API) por defecto; Argos Translate offline opcional |
| Exportación | python-docx, ebooklib, WeasyPrint, plantillas HTML/Markdown propias |
| Configuración | pydantic-settings + YAML |
| Paralelismo | `concurrent.futures.ProcessPoolExecutor` |
| CLI | Click |
| Interfaz web | FastAPI + Jinja2 + JS vanilla (polling), SQLite, `uvicorn` |
| Tests | pytest (+ `fastapi.testclient` para la interfaz web) |

Esta combinación prioriza **calidad de OCR y de reconstrucción** (motores
intercambiables, heurísticas de párrafo dedicadas, traducción consciente de
estructura) sin sacrificar la posibilidad de ejecutar el proyecto en una
máquina normal (CPU, sin GPU), que era el otro requisito explícito.
