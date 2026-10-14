"""Real UI verification of the new customer source and its shadow variant."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import QEventLoop,QTimer
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow
from app.export.debug_exporter import export_debug_json
from tests.evaluate_accessory_columns import variants
app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','consola.ttf'):
 QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/name))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
image=cv2.imread(str(ROOT/'tests/fixtures/customer_20261012/animals_accessories_columns_4x3.png'))
for name,pixels,_,_ in variants(image):
 if name not in ('original','diagonal_shadow'):continue
 window=MainWindow();window.resize(1420,1000);window.show();window._load_image(pixels,name)
 window.detect_motifs(background=True)
 loop=QEventLoop()
 window._detection_worker.finished.connect(loop.quit)
 timer=QTimer(loop);timer.setSingleShot(True);timer.timeout.connect(loop.quit);timer.start(60000)
 loop.exec();timer.stop()
 if window._detection_worker is not None:
  window._detection_worker.cancel();loop.exec()
  raise RuntimeError('Analysis exceeded the 60-second UI check limit')
 assert window._detection_worker is None
 assert len(window.detections)==12
 app.processEvents();window.grab().save(str(Path(__file__).parent/(name+'-ui.png')))
 export_debug_json(Path(__file__).parent/(name+'-ui.json'),window.mapper,window.detections,detection_run=window.detection_diagnostics,logical_layout=window.logical_layout)
 print(name,len(window.detections),'excluded',sum(not d.enabled for d in window.detections),flush=True)
 window.close()
