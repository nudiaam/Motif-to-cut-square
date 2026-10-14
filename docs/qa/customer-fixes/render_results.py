"""Capture real detection results, without substituting detector output."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,json
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow
from app.export.debug_exporter import export_debug_json
app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','consola.ttf'):
 QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/name))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
image=cv2.imread(str(ROOT/'tests/fixtures/customer_20261012/animals_accessories_4x3.png'))
alphabet=cv2.imread(str(ROOT/'tests/fixtures/generated/customer_20261012/alphabet_6x4.png'))[:860]
birds=cv2.imread(str(ROOT/'tests/fixtures/customer_20261012/birds_partial_6x4.png'))
for name,pixels in [('animals',image),('partial-row',alphabet),('birds',birds)]:
 window=MainWindow();window.resize(1420,1000);window.show()
 window._load_image(pixels,name);window.detect_motifs();app.processEvents()
 window.grab().save(str(Path(__file__).parent/(name+'-ui.png')))
 export_debug_json(Path(__file__).parent/(name+'-ui.json'),window.mapper,window.detections,detection_run=window.detection_diagnostics,logical_layout=window.logical_layout)
 print(name,'total',len(window.detections),'enabled',sum(d.enabled for d in window.detections),'partial',sum(d.source_incomplete for d in window.detections),flush=True)
 window.close()
