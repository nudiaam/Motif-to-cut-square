"""Reproduce local corroboration, prior controls, framing probes and UI output."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from app.imaging.detector import MotifDetector,DetectorSettings

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qa/mixed-icons'
FIXTURE=ROOT/'tests/fixtures/acceptance/mixed_icons_6x4.png'


def evaluate():
    previous=json.loads((ROOT/'docs/qa/joint-coordinator/comparison.json').read_text())
    records=[]
    geometry=lambda cs:sorted((tuple(c['bounding_box_px']),tuple(c['center_px'])) for c in cs)
    for case in previous['cases']:
        result=MotifDetector().detect_with_layout(cv2.imread(str(ROOT/case['file'])),DetectorSettings())
        before=case['after']['candidates']
        records.append({'file':case['file'],'previous_count':len(before),'count':len(result.candidates),
                        'same_boxes_and_centres':geometry(before)==geometry([asdict(c) for c in result.candidates])})
        print(records[-1],flush=True)
    (OUT/'previous-controls.json').write_text(json.dumps(records,indent=2))
    image=cv2.imread(str(FIXTURE));variants=[]
    for name,source in [('original',image),('half',cv2.resize(image,None,fx=.5,fy=.5)),
                        ('surround',cv2.copyMakeBorder(image,60,60,60,60,cv2.BORDER_CONSTANT,value=(45,45,45)))]:
        digest=hashlib.sha256(source.tobytes()).hexdigest()
        detector=MotifDetector();result=detector.detect_with_layout(source,DetectorSettings())
        assert hashlib.sha256(source.tobytes()).hexdigest()==digest
        variants.append({'variant':name,'count':len(result.candidates),'diagnostics':detector.last_diagnostics})
    (OUT/'variants.json').write_text(json.dumps(variants,indent=2))


def render_ui():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase,QFont
    from app.ui.main_window import MainWindow
    from app.main import APP_STYLESHEET
    app=QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
    window=MainWindow();window.resize(1440,960);window.show()
    image=cv2.imread(str(FIXTURE));window._load_image(image,'Mixed printed fabric')
    window.detector.bed_reference=None
    window.detect_motifs();app.processEvents()
    window.statusBar().showMessage(f'{len(window.detections)} cuts on the supplied original — review before continuing')
    window.grab().save(str(OUT/'ui.png'))
    record={'count':len(window.detections),'grid':[window.panel_grid.columns,window.panel_grid.rows],
            'cut_inches':[window.cut_width_inches,window.cut_height_inches],
            'overlaps':sum(d.overlaps_cut for d in window.detections),
            'artwork_clipped':sum(d.artwork_clipped for d in window.detections),
            'extent_reviews':sum(bool(d.review_reasons) for d in window.detections),
            'inferred':sum(d.inferred for d in window.detections)}
    (OUT/'ui.json').write_text(json.dumps(record,indent=2));print(record)
    np.testing.assert_array_equal(window.image_bgr,image)
    window.close()


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    render_ui() if '--ui' in sys.argv else evaluate()
