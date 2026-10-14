"""Preview the actual Qt status strip with a simulated slow worker for capture."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys, time
from unittest.mock import patch
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow
from app.imaging.detector import DetectionResult
app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'consola.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts') / name))
app.setFont(QFont('Segoe UI', 10))
app.setStyle('Fusion')
app.setStyleSheet(APP_STYLESHEET)
window = MainWindow()
window.resize(1420, 880)
window.show()
window._load_image(cv2.imread(str(ROOT / 'tests/fixtures/generated/customer_20261012/christmas_6x4.png')), 'Christmas test')
def slow(detector, image, settings):
    for _ in range(500):
        detector._progress('Analysing panel layout…')
        time.sleep(.01)
    return DetectionResult(())
with patch('app.ui.detection_worker.MotifDetector.detect_with_layout', slow):
    window.detect_motifs(background=True)
    QTest.qWait(150)
    window.grab().save(str(ROOT / 'docs/qa/customer-improvements/inline-analysis-ui.png'))
    window.analysis_cancel.click()
    while window._detection_worker is not None:
        QTest.qWait(10)
window.close()
