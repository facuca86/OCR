"""Hoja de estilos (QSS) para una apariencia moderna y limpia."""

APP_STYLE = """
QWidget {
    background-color: #1e1f26;
    color: #e6e6ea;
    font-family: "Segoe UI", "Helvetica Neue", "Liberation Sans", sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e1f26;
}
#DropZone {
    border: 2px dashed #4a4d5e;
    border-radius: 10px;
    background-color: #262832;
    padding: 24px;
}
#DropZone[dragOver="true"] {
    border-color: #5b8cff;
    background-color: #2a2f45;
}
QGroupBox {
    border: 1px solid #34364a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #9ea3c2;
}
QPushButton {
    background-color: #3b5bff;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover { background-color: #5372ff; }
QPushButton:disabled { background-color: #33354a; color: #7a7d92; }
QPushButton#CancelButton { background-color: #45475a; }
QPushButton#CancelButton:hover { background-color: #55586e; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit, QTextBrowser, QSpinBox {
    background-color: #262832;
    border: 1px solid #34364a;
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: #3b5bff;
}
QCheckBox { spacing: 6px; }
QProgressBar {
    border: 1px solid #34364a;
    border-radius: 6px;
    text-align: center;
    background-color: #262832;
}
QProgressBar::chunk {
    background-color: #3b5bff;
    border-radius: 6px;
}
QTabWidget::pane {
    border: 1px solid #34364a;
    border-radius: 8px;
}
QTabBar::tab {
    background: #262832;
    padding: 8px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #3b5bff;
    color: white;
}
"""
