"""Ventana principal de la aplicación de escritorio."""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

import fitz
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ocr_book.config.schema import (
    AppConfig,
    ExportFormat,
    OcrEngineName,
    TranslationEngineName,
)
from ocr_book.gui.widgets.drop_zone import DropZone
from ocr_book.gui.worker import ConversionWorker
from ocr_book.pipeline.progress import ProgressEvent

logger = logging.getLogger("ocr_book.gui")

_COMMON_OCR_LANGUAGES = [
    ("spa", "Español"),
    ("eng", "Inglés"),
    ("fra", "Francés"),
    ("deu", "Alemán"),
    ("ita", "Italiano"),
    ("por", "Portugués"),
]

_TRANSLATION_TARGET_LANGUAGES = [
    ("en", "Inglés"),
    ("es", "Español"),
    ("fr", "Francés"),
    ("de", "Alemán"),
    ("it", "Italiano"),
    ("pt", "Portugués"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OCR Book — reconstrucción inteligente de libros escaneados")
        self.resize(1180, 760)

        self._pending_files: deque[Path] = deque()
        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 760])

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._add_files)
        layout.addWidget(self._drop_zone)

        add_button = QPushButton("Añadir archivos…")
        add_button.clicked.connect(self._pick_files)
        layout.addWidget(add_button)

        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        layout.addWidget(self._file_list, stretch=1)

        remove_button = QPushButton("Quitar seleccionado")
        remove_button.clicked.connect(self._remove_selected_file)
        layout.addWidget(remove_button)

        layout.addWidget(self._build_ocr_group())
        layout.addWidget(self._build_translation_group())
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_performance_group())

        button_row = QHBoxLayout()
        self._start_button = QPushButton("Procesar")
        self._start_button.clicked.connect(self._start_processing)
        self._cancel_button = QPushButton("Cancelar")
        self._cancel_button.setObjectName("CancelButton")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._cancel_processing)
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._cancel_button)
        layout.addLayout(button_row)

        return panel

    def _build_ocr_group(self) -> QGroupBox:
        group = QGroupBox("Configuración OCR")
        layout = QVBoxLayout(group)

        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Motor:"))
        self._engine_combo = QComboBox()
        for engine in OcrEngineName:
            self._engine_combo.addItem(engine.value, engine)
        engine_row.addWidget(self._engine_combo)
        layout.addLayout(engine_row)

        layout.addWidget(QLabel("Idiomas del documento:"))
        self._language_checks: dict[str, QCheckBox] = {}
        lang_grid = QHBoxLayout()
        for code, label in _COMMON_OCR_LANGUAGES:
            checkbox = QCheckBox(label)
            checkbox.setChecked(code in ("spa", "eng"))
            self._language_checks[code] = checkbox
            lang_grid.addWidget(checkbox)
        layout.addLayout(lang_grid)

        self._gpu_checkbox = QCheckBox("Usar GPU si está disponible")
        layout.addWidget(self._gpu_checkbox)

        return group

    def _build_translation_group(self) -> QGroupBox:
        group = QGroupBox("Traducción")
        layout = QVBoxLayout(group)

        self._translate_checkbox = QCheckBox("Traducir automáticamente")
        layout.addWidget(self._translate_checkbox)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Idioma destino:"))
        self._target_lang_combo = QComboBox()
        for code, label in _TRANSLATION_TARGET_LANGUAGES:
            self._target_lang_combo.addItem(f"{label} ({code})", code)
        target_row.addWidget(self._target_lang_combo)
        layout.addLayout(target_row)

        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Motor de traducción:"))
        self._translation_engine_combo = QComboBox()
        for engine in (TranslationEngineName.ANTHROPIC, TranslationEngineName.ARGOS):
            self._translation_engine_combo.addItem(engine.value, engine)
        engine_row.addWidget(self._translation_engine_combo)
        layout.addLayout(engine_row)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Salida")
        layout = QVBoxLayout(group)

        folder_row = QHBoxLayout()
        self._output_dir_edit = QLineEdit(str(Path("./output").resolve()))
        folder_row.addWidget(self._output_dir_edit, stretch=1)
        browse_button = QPushButton("Examinar…")
        browse_button.clicked.connect(self._pick_output_dir)
        folder_row.addWidget(browse_button)
        layout.addLayout(folder_row)

        layout.addWidget(QLabel("Formatos de exportación:"))
        format_row = QHBoxLayout()
        self._format_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            checkbox = QCheckBox(fmt.value.upper())
            checkbox.setChecked(fmt == ExportFormat.PDF)
            self._format_checks[fmt] = checkbox
            format_row.addWidget(checkbox)
        layout.addLayout(format_row)

        return group

    def _build_performance_group(self) -> QGroupBox:
        group = QGroupBox("Rendimiento")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("Procesos paralelos (0 = automático):"))
        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(0, 64)
        self._workers_spin.setValue(0)
        layout.addWidget(self._workers_spin)
        return group

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Listo.")
        layout.addWidget(self._status_label)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        self._preview_image_label = QLabel("Sin vista previa todavía.")
        self._preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tabs.addTab(self._preview_image_label, "Vista previa de entrada")

        self._preview_html = QTextBrowser()
        tabs.addTab(self._preview_html, "Documento reconstruido")

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        tabs.addTab(self._log_view, "Registro")

        return panel

    # ------------------------------------------------------------- eventos
    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar libros escaneados", "",
            "Documentos soportados (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)",
        )
        if paths:
            self._add_files([Path(p) for p in paths])

    def _add_files(self, paths: list[Path]) -> None:
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._file_list.addItem(item)
        if self._file_list.count() == len(paths):
            self._file_list.setCurrentRow(0)

    def _remove_selected_file(self) -> None:
        row = self._file_list.currentRow()
        if row >= 0:
            self._file_list.takeItem(row)

    def _pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Carpeta de salida", self._output_dir_edit.text())
        if directory:
            self._output_dir_edit.setText(directory)

    def _on_file_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._file_list.item(row)
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        self._show_input_preview(path)

    def _show_input_preview(self, path: Path) -> None:
        try:
            if path.suffix.lower() == ".pdf":
                doc = fitz.open(path)
                pixmap = doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                image = QImage(
                    pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888
                )
                doc.close()
            else:
                image = QImage(str(path))
            qpixmap = QPixmap.fromImage(image).scaledToWidth(520, Qt.TransformationMode.SmoothTransformation)
            self._preview_image_label.setPixmap(qpixmap)
        except Exception:
            logger.exception("No se pudo generar la vista previa de %s", path)
            self._preview_image_label.setText("No se pudo generar la vista previa.")

    # --------------------------------------------------------- procesado
    def _collect_config(self) -> AppConfig:
        config = AppConfig()
        config.ocr.engine = self._engine_combo.currentData()
        config.ocr.languages = [code for code, box in self._language_checks.items() if box.isChecked()] or ["eng"]
        config.ocr.use_gpu = self._gpu_checkbox.isChecked()
        config.performance.use_gpu = self._gpu_checkbox.isChecked()

        config.translation.enabled = self._translate_checkbox.isChecked()
        config.translation.target_language = self._target_lang_combo.currentData()
        config.translation.engine = self._translation_engine_combo.currentData()

        config.export.output_dir = Path(self._output_dir_edit.text())
        selected_formats = [fmt for fmt, box in self._format_checks.items() if box.isChecked()]
        config.export.formats = selected_formats or [ExportFormat.PDF]

        workers = self._workers_spin.value()
        config.performance.max_workers = workers if workers > 0 else None

        return config

    def _start_processing(self) -> None:
        if self._file_list.count() == 0:
            QMessageBox.warning(self, "Sin archivos", "Añade al menos un archivo antes de procesar.")
            return

        self._pending_files = deque(
            Path(self._file_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self._file_list.count())
        )
        self._start_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._log_view.clear()
        self._process_next_file()

    def _process_next_file(self) -> None:
        if not self._pending_files:
            self._status_label.setText("Todo listo.")
            self._start_button.setEnabled(True)
            self._cancel_button.setEnabled(False)
            return

        input_path = self._pending_files.popleft()
        config = self._collect_config()
        config.export.output_dir.mkdir(parents=True, exist_ok=True)
        output_basename = config.export.output_dir / input_path.stem

        self._status_label.setText(f"Procesando {input_path.name}…")
        self._progress_bar.setValue(0)

        self._thread = QThread()
        self._worker = ConversionWorker(config, input_path, output_basename)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished.connect(self._on_file_finished)
        self._worker.failed.connect(self._on_file_failed)
        self._worker.cancelled.connect(self._on_file_cancelled)
        for signal in (self._worker.finished, self._worker.failed, self._worker.cancelled):
            signal.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)

        self._thread.start()

    def _cancel_processing(self) -> None:
        self._pending_files.clear()
        if self._worker is not None:
            self._worker.cancel()
        self._status_label.setText("Cancelando…")

    def _on_progress(self, event: ProgressEvent) -> None:
        if event.total:
            self._progress_bar.setValue(int(100 * event.current / event.total))
        self._status_label.setText(event.message or event.stage)

    def _append_log(self, message: str) -> None:
        self._log_view.appendPlainText(message)

    def _on_file_finished(self, outputs: list[Path]) -> None:
        self._append_log(f"Completado: {', '.join(str(p) for p in outputs)}")
        html_output = next((p for p in outputs if p.suffix.lower() == ".html"), None)
        if html_output is not None:
            self._preview_html.setHtml(html_output.read_text(encoding="utf-8"))
        self._process_next_file()

    def _on_file_failed(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error al procesar", message)
        self._process_next_file()

    def _on_file_cancelled(self) -> None:
        self._append_log("Procesamiento cancelado por el usuario.")
        self._status_label.setText("Cancelado.")
        self._start_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
