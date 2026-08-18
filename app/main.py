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
QFrame#reviewWorkflow {
    background: #202a31;
    border-bottom: 1px solid #44515b;
}
QLabel#reviewTitle {
    color: #73e6ff;
    font-size: 8pt;
    font-weight: bold;
    letter-spacing: 1px;
}
QPushButton#reviewAction {
    background: #313b44;
    border: 1px solid #53616d;
    border-radius: 4px;
    padding: 8px 10px;
    color: #e8edf1;
    text-align: left;
    min-height: 30px;
}
QPushButton#reviewAction:hover { background: #3d4954; border-color: #718391; }
QPushButton#reviewAction[workflowState="active"] {
    background: #147664;
    border: 2px solid #57e6bd;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#reviewAction[workflowState="active"]:hover { background: #198c76; }
QPushButton#reviewAction[workflowState="complete"] {
    background: #263b37;
    border-color: #3e7165;
    color: #9bd8c7;
}
QPushButton#reviewAction[workflowState="warning"] {
    background: #4a3925;
    border-color: #d69a48;
    color: #ffd394;
}
QPushButton#reviewAction[workflowState="neutral"],
QPushButton#reviewAction[workflowState="available"] {
    background: #313b44;
    border-color: #53616d;
    color: #e8edf1;
}
QPushButton#reviewAction:disabled {
    background: #252c32;
    border-color: #39434b;
    color: #7f8b94;
}
QLabel#reviewGuidance {
    color: #c6d1d8;
    font-size: 9pt;
    padding-bottom: 0;
}
QLabel#contextTitle {
    color: #73e6ff;
    font-size: 10pt;
    font-weight: bold;
    letter-spacing: 1px;
}
QLabel#contextHint {
    color: #c6d1d8;
    font-size: 9pt;
    padding-bottom: 4px;
}
QPushButton#primaryPanelAction {
    background: #147664;
    border: 2px solid #57e6bd;
    color: #ffffff;
    font-weight: bold;
    min-height: 30px;
}
QPushButton#primaryPanelAction:hover { background: #198c76; }
QPushButton#primaryPanelAction:disabled {
    background: #252c32;
    border-color: #39434b;
    color: #7f8b94;
}
QPushButton#advancedToggle {
    background: #282e36;
    color: #c5ced6;
    text-align: left;
    padding: 8px 10px;
}
QPushButton#reviewSecondaryAction, QToolButton#reviewSecondaryAction,
QToolButton#cutPreviewToggle {
    background: #2d3740;
    border: 1px solid #4c5964;
    border-radius: 4px;
    padding: 7px 10px;
    color: #dce4e9;
}
QPushButton#reviewSecondaryAction:hover, QToolButton#reviewSecondaryAction:hover,
QToolButton#cutPreviewToggle:hover {
    background: #3a4651;
}
QToolButton#reviewSecondaryAction:checked {
    background: #145d70;
    border: 2px solid #55e6ff;
    color: #ffffff;
    font-weight: bold;
}
QToolButton#cutPreviewToggle:checked {
    background: #145d70;
    border-color: #55e6ff;
    color: white;
}
QFrame#navigationHelp {
    background: #282e36;
    border: 1px solid #39424c;
    border-radius: 4px;
}
QToolButton#navigationToggle {
    background: transparent;
    color: #9ca8b3;
    border: none;
    padding: 3px 5px;
    font-size: 9pt;
}
QToolButton#navigationToggle:hover { color: #d7dee4; }
QToolButton#cutPreviewToggle {
    background: #282e36;
    color: #d7dee4;
    border: 1px solid #46515e;
    border-radius: 4px;
    padding: 7px 12px;
    margin: 10px 12px;
}
QToolButton#cutPreviewToggle:hover {
    background: #353d47;
    border-color: #657282;
}
QToolButton#cutPreviewToggle:checked {
    background: #197a67;
    border-color: #39d6a4;
    color: #ffffff;
}
QToolButton#cutPreviewToggle:disabled {
    color: #6d7781;
    border-color: #343b44;
}
QWidget#navigationDetails { background: transparent; border: none; }
QLabel#navigationText {
    color: #c5ced6;
    font-size: 9pt;
}
QFrame#panelSection {
    background: #282e36;
    border: 1px solid #39424c;
    border-radius: 5px;
}
QFrame#panelGridSection {
    background: #282e36;
    border: 1px solid #39424c;
    border-radius: 5px;
}
QFrame#panelGridSection[workflowActive="true"] {
    background: #263a35;
    border: 2px solid #39d6a4;
}
QFrame#panelGridSection[workflowActive="true"] QLabel#sectionTitle {
    color: #72f0c5;
}
QLabel#mutedHint { color: #8996a1; font-size: 8pt; }
QToolButton {
    background: transparent;
    border: none;
    color: #c9d4dc;
    padding: 3px 1px;
}
QToolButton:hover { color: #ffffff; }
QLabel#panelTitle { color: #39d6a4; letter-spacing: 1px; }
QLabel#sectionTitle {
    color: #91a0af;
    font-size: 9pt;
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
    border-radius: 8px;
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
QListWidget::item:selected {
    background: #145668;
    color: white;
    border-left: 4px solid #55e6ff;
}
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background: #1d2228;
    border: 1px solid #46515e;
    border-radius: 3px;
    padding: 3px;
}
QPushButton:focus, QToolButton:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QLineEdit:focus, QListWidget:focus {
    border: 2px solid #73e6ff;
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
