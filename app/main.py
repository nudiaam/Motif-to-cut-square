"""Application entry point: run with ``python -m app.main``."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


APP_STYLESHEET = """
QMainWindow {
    background: #20252c;
}
QWidget {
    color: #e7ebef;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QWidget#sidePanelContent { background: #20252c; }
QLabel { background: transparent; }
QToolBar#mainToolbar {
    background: #292f37;
    border: none;
    border-bottom: 1px solid #3c444e;
    spacing: 4px;
    padding: 6px;
}
QToolBar QToolButton {
    background: #353d47;
    border: 1px solid #46515e;
    border-radius: 4px;
    padding: 7px 11px;
    color: #f1f4f7;
}
QToolBar QToolButton:hover { background: #42505d; }
QToolBar QToolButton:pressed, QToolBar QToolButton:checked {
    background: #197a67;
    border-color: #39d6a4;
}
QFrame#panelSection {
    background: #282e36;
    border: 1px solid #39424c;
    border-radius: 5px;
}
QLabel#panelTitle { color: #39d6a4; letter-spacing: 1px; }
QLabel#sectionTitle {
    color: #91a0af;
    font-size: 8pt;
    font-weight: bold;
    letter-spacing: 1px;
}
QLabel#parameterTitle, QLabel#statTitle {
    color: #aab5c0;
    font-size: 8pt;
    font-weight: bold;
}
QLabel#statValue {
    color: #f1f4f7;
    font-size: 12pt;
    font-weight: bold;
}
QToolButton#infoButton {
    background: transparent;
    color: #8995a0;
    border: 1px solid #73808c;
    border-radius: 5px;
    padding: 0;
}
QToolButton#infoButton:hover {
    color: #c2ccd5;
    border-color: #aeb9c3;
    background: transparent;
}
QLabel#infoBlock, QLabel#detailBlock {
    font-family: "Cascadia Mono", Consolas, monospace;
    color: #dce3e9;
}
QListWidget {
    background: #1d2228;
    border: 1px solid #3a434d;
    alternate-background-color: #222830;
    outline: none;
}
QListWidget::item { padding: 5px; }
QListWidget::item:selected { background: #3f4d5b; color: white; }
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background: #1d2228;
    border: 1px solid #46515e;
    border-radius: 3px;
    padding: 3px;
}
QComboBox::drop-down { border: none; width: 18px; }
QPushButton {
    background: #353d47;
    border: 1px solid #46515e;
    border-radius: 4px;
    padding: 5px 8px;
}
QPushButton:hover { background: #42505d; }
QSlider::groove:horizontal { height: 4px; background: #46515e; }
QSlider::handle:horizontal {
    width: 14px; margin: -5px 0; border-radius: 7px; background: #39d6a4;
}
QCheckBox::indicator { width: 15px; height: 15px; }
QLabel#verificationLabel {
    background: #1b2026;
    border-left: 3px solid #d989ff;
    padding: 7px;
    color: #d9c2e5;
}
QLabel#assumptionBanner {
    background: #2b2521;
    color: #dcb98b;
    border-top: 1px solid #5a4632;
    padding: 6px 12px;
    font-size: 9pt;
}
QStatusBar { background: #191d22; color: #aeb8c2; }
QMessageBox { background: #252b32; }
QToolTip {
    background: #101419;
    color: #f1f4f7;
    border: 1px solid #39d6a4;
    padding: 7px;
    font-size: 9pt;
}
QScrollBar:vertical {
    background: #1b2026;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #586572;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background: #71808e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Lalikul.CutPrep.Demo"
            )
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Lalikul Cut Prep")
    app.setApplicationDisplayName("Lalikul Cut Prep")
    app.setOrganizationName("Lalikul")
    icon_path = Path(__file__).resolve().parent / "assets" / "lalikul-cut-prep.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
