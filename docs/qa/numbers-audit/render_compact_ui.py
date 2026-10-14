"""Actual UI grouping and warnings at the user's three-inch cut size."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import json,cv2
from dataclasses import asdict
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow

out=Path('docs/qa/numbers-audit/alternating-columns/fixed');out.mkdir(exist_ok=True)
app=QApplication.instance() or QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','segoeuii.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/name))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
window=MainWindow();window.resize(1420,1000);window.show();app.processEvents()
window._load_image(cv2.imread('tests/fixtures/customer_20261012/numbers_compact_5x4.png'),'Compact number/object composition check')
window.panel.cut_width_spin.setValue(3);window.detect_motifs();app.processEvents()
window.grab().save(str(out/'numbers-compact-3in-ui.png'))
data={'detections':[asdict(d) for d in window.detections],'layout':asdict(window.logical_layout),
      'cut_size_inches':3,'clipped':sum(d.artwork_clipped for d in window.detections),
      'overlapping':sum(d.overlaps_cut for d in window.detections),'diagnostics':window.detection_diagnostics}
(out/'numbers-compact-ui.json').write_text(json.dumps(data,indent=2))
print(len(window.detections),'clipped',data['clipped'],'overlap',data['overlapping'])
window.close()
