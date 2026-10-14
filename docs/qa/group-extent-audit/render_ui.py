"""Render actual cut-size controls and warnings for the supplied clean sources."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import json
from dataclasses import asdict
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow

out=Path('docs/qa/group-extent-audit/fixed')
app=QApplication.instance() or QApplication([])
for filename in ('segoeui.ttf','segoeuib.ttf','segoeuii.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/filename))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
for name in ('cocktails','quotes'):
    window=MainWindow();window.resize(1420,1000);window.show();app.processEvents()
    window._load_image(cv2.imread(f'tests/fixtures/customer_20261012/{name}_groups.png'),name)
    window.panel.cut_width_spin.setValue(4);window.detect_motifs();app.processEvents()
    assert window.cut_width_inches==4 and window.panel.cut_width_spin.value()==4
    records=[]
    for size in (4,4.6,5) if name=='quotes' else (4,5):
        window.panel.cut_width_spin.setValue(size);app.processEvents()
        window.grab().save(str(out/f'{name}-{size:g}in-ui.png'))
        records.append({'size_inches':size,'detections':[asdict(d) for d in window.detections],
                        'layout':asdict(window.logical_layout),
                        'artwork_clipped':sum(d.artwork_clipped for d in window.detections),
                        'overlapping':sum(d.overlaps_cut for d in window.detections)})
        print(name,size,records[-1]['artwork_clipped'],records[-1]['overlapping'],flush=True)
    (out/f'{name}-ui-sizes.json').write_text(json.dumps(records,indent=2))
    window.close();app.processEvents()
