"""Render the real Qt review screen with the unchanged default 5-inch cut size."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow
from app.export.debug_exporter import export_detection_bundle

app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','consola.ttf'):
    font=Path('C:/Windows/Fonts')/name
    if font.exists(): QFontDatabase.addApplicationFont(str(font))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
out=Path(__file__).resolve().parent
for name in ('alphabet_6x4','christmas_6x4'):
    window=MainWindow();window.resize(1420,1000);window.show()
    window._load_image(cv2.imread(str(ROOT/'tests/fixtures/generated/customer_20261012'/(name+'.png'))),name)
    window.detect_motifs();app.processEvents()
    window.grab().save(str(out/(name+'-ui.png')))
    export_detection_bundle(out/(name+'-package.zip'),window.image_bgr,window.detector.bed_reference,
        window.mapper,window.detections,logical_layout=window.logical_layout,
        detection_run=window.detection_diagnostics)
    print(name,window.panel.review_breakdown_label.text(),flush=True)
    window.close()
