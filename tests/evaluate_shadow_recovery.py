"""Save comparable corpus results and original-pixel overlays for shadow recovery."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector
from tests.diagnose_irregular_shadows import shadow_field
from tests.evaluate_adaptive_planning import peak_memory_mb
from tests.test_irregular_shadows import TRANSPORT_WITNESSES


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/qa/shadow-recovery'


def run(image,name,previous_count=None,witnesses=()):
    digest = hashlib.sha256(image.tobytes()).hexdigest()
    detector = MotifDetector()
    started = time.perf_counter()
    result = detector.detect_with_layout(image,DetectorSettings())
    elapsed = time.perf_counter()-started
    assert hashlib.sha256(image.tobytes()).hexdigest() == digest
    checks = []
    for (col,row),points in witnesses:
        grid = result.panel_grid
        center = ((grid.x_lines_px[col-1]+grid.x_lines_px[col])/2,
                  (grid.y_lines_px[row-1]+grid.y_lines_px[row])/2)
        candidate = min(result.candidates,key=lambda c:np.linalg.norm(np.array(c.center_px)-center))
        x,y,w,h = candidate.bounding_box_px
        checks.append({'cell':[col,row], 'contained':[bool(x <= px <= x+w and y <= py <= y+h) for px,py in points]})
    row = {'name':name,'previous_count':previous_count,'count':len(result.candidates),
           'seconds':elapsed,'grid':asdict(result.panel_grid) if result.panel_grid else None,
           'candidates':[asdict(c) for c in result.candidates],
           'diagnostics':detector.last_diagnostics,'source_unchanged':True,'witnesses':checks}
    overlay = image.copy()
    for c in result.candidates:
        x,y,w,h = c.bounding_box_px
        cv2.rectangle(overlay,(x,y),(x+w,y+h),(0,0,255),2)
    cv2.imwrite(str(OUT/(name+'-bounds.png')),overlay)
    print(name,row['count'],(result.panel_grid.columns,result.panel_grid.rows) if result.panel_grid else None,
          round(elapsed,2),'s',flush=True)
    return row


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fixtures = ROOT/'tests/fixtures'
    previous = json.loads((ROOT/'docs/qa/transport-shared/all-fixtures/fixture-results.json').read_text())
    cases = [run(cv2.imread(str(fixtures/p['file'])),Path(p['file']).stem,p['count']) for p in previous]
    cases.append(run(cv2.imread(str(fixtures/'floral_patchwork_recovered.png')),'floral_recovered',24))
    shadows = []
    for name,path in (('transport','transport_dashed_shared.png'),
                      ('dogs','generated/straight/dogs_6x4.png'),
                      ('hearts','generated/straight/hearts_6x4.png')):
        image = cv2.imread(str(fixtures/path))
        shadows.append(run(image,name+'_control',24))
        for kind in ('horizontal','vertical','diagonal','patches'):
            changed = (image.astype(np.float32)*shadow_field(image,kind)[...,None]).astype(np.uint8)
            shadows.append(run(changed,name+'_'+kind))
    original = cv2.imread(str(fixtures/'transport_irregular_shadows.png'))
    shadows.append(run(original,'new_original',15,TRANSPORT_WITNESSES))
    variants = []
    for scale in (.5,1.5):
        image = cv2.resize(original,None,fx=scale,fy=scale)
        variants.append(run(image,'new_scale_'+str(scale)))
    report = {'previous_collections':cases,'controlled_shadows':shadows,'resolution_variants':variants,
              'peak_process_mb':peak_memory_mb(),
              'limitations':['Point witnesses are partial extent annotations, not full silhouettes.',
                             'Timings describe this CPU and include full detection and review.',
                             'No GPU, network model, or new dependency is used.']}
    (OUT/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def render_ui():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase,QFont
    from app.ui.main_window import MainWindow
    from app.main import APP_STYLESHEET
    OUT.mkdir(parents=True,exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font = Path('C:/Windows/Fonts/segoeui.ttf')
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont('Segoe UI',10))
    app.setStyle('Fusion'); app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow(); window.resize(1440,960); window.show()
    window._load_image(cv2.imread(str(ROOT/'tests/fixtures/transport_irregular_shadows.png')),
                       'Shadow recovery verification')
    window.detector.bed_reference = None
    window.detect_motifs()
    records = []
    for size in (5.,4.5):
        # Exercise the user-facing size control, including its paired square side.
        window.panel.cut_width_spin.setValue(size)
        app.processEvents()
        window.statusBar().showMessage('Verification: 24 compositions on the original image')
        suffix = '' if size == 5. else '-4_5in'
        window.grab().save(str(OUT/('new-original-ui'+suffix+'.png')))
        records.append({'count':len(window.detections),'cut_inches':[window.cut_width_inches,window.cut_height_inches],
                        'overlaps':sum(d.overlaps_cut for d in window.detections),
                        'artwork_clipped':sum(d.artwork_clipped for d in window.detections),
                        'extent_reviews':sum(bool(d.review_reasons) for d in window.detections),
                        'invalid':sum(not d.valid_cut for d in window.detections)})
    (OUT/'ui-verification.json').write_text(json.dumps(records,indent=2)+'\n')
    window.close()
    print(records)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui',action='store_true')
    args = parser.parse_args()
    render_ui() if args.ui else main()
