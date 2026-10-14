"""Save the actual workflow states at the unchanged five-inch cut size."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import asdict
import json,cv2,numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.main import APP_STYLESHEET
from app.ui.main_window import MainWindow
from tests.holdout_group_truth import CASES
from tests.test_holdout_groups import assess

ROOT=Path('docs/qa/holdout-20261014');OUT=ROOT/'verified';OUT.mkdir(exist_ok=True)
app=QApplication.instance() or QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','segoeuii.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/name))
app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
records=[]
for name,(shape,points) in CASES.items():
    window=MainWindow();window.resize(1420,1000);window.show();app.processEvents()
    window._load_image(cv2.imread(str(ROOT/f'{name}.png')),name);window.detect_motifs();app.processEvents()
    window.grab().save(str(OUT/f'{name}-5in-ui.png'))
    record={'source':name,'count':len(window.detections),'clipped':sum(d.artwork_clipped for d in window.detections),
        'overlapping':sum(d.overlaps_cut for d in window.detections),'excluded':sum(not d.enabled for d in window.detections),
        'detections':[asdict(d) for d in window.detections],'layout':asdict(window.logical_layout),'diagnostics':window.detection_diagnostics}
    records.append(record);(OUT/'ui-results.json').write_text(json.dumps(records,indent=2))
    print(name,record['count'],'clipped',record['clipped'],'overlapping',record['overlapping'],flush=True)
    # Clear source evidence is exported separately from the physical cuts.
    image=cv2.imread(str(ROOT/f'{name}.png'))
    for d in window.detections:
        if d.bounding_box_px:
            x,y,w,h=d.bounding_box_px;cv2.rectangle(image,(x,y),(x+w,y+h),(200,140,20),2)
    cv2.imwrite(str(OUT/f'{name}-groups.png'),image)
    window.close();app.processEvents()
