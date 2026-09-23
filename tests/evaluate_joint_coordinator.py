"""Compare the preserved pre-change implementation with the joint coordinator."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import types

import cv2
import numpy as np

from app.imaging.detector import MotifDetector, DetectorSettings
from tests.evaluate_adaptive_planning import peak_memory_mb

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qa/joint-coordinator'


def baseline():
    modules={}
    for name in ('detection_plan','contrast_grid','detector'):
        module=types.ModuleType('app.imaging._joint_baseline_'+name)
        module.__package__='app.imaging'
        sys.modules[module.__name__]=module
        exec(compile((OUT/(name+'.py')).read_text(),str(OUT/(name+'.py')),'exec'),module.__dict__)
        modules[name]=module
    modules['detector'].choose_grid=modules['detection_plan'].choose_grid
    modules['detector'].infer_contrast_geometry=modules['contrast_grid'].infer_contrast_geometry
    return modules['detector'].MotifDetector


def main():
    previous=json.loads((ROOT/'docs/qa/transport-shared/all-fixtures/fixture-results.json').read_text())
    paths=[ROOT/'tests/fixtures'/row['file'] for row in previous]
    paths.extend(ROOT/'tests/fixtures'/p for p in ('floral_patchwork_recovered.png','transport_irregular_shadows.png'))
    paths.extend(sorted((ROOT/'tests/fixtures/acceptance').glob('*.png')))
    rows=[]; old=baseline()
    for path in dict.fromkeys(paths):
        image=cv2.imread(str(path)); digest=hashlib.sha256(image.tobytes()).hexdigest()
        record={'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        for label,cls in (('before',old),('after',MotifDetector)):
            detector=cls();start=time.perf_counter()
            result=detector.detect_with_layout(image,DetectorSettings())
            record[label]={'count':len(result.candidates),'seconds':time.perf_counter()-start,
                           'grid':asdict(result.panel_grid) if result.panel_grid else None,
                           'candidates':[asdict(c) for c in result.candidates],
                           'diagnostics':detector.last_diagnostics}
            assert hashlib.sha256(image.tobytes()).hexdigest()==digest
            if label=='after':
                canvas=image.copy()
                for c in result.candidates:
                    x,y,w,h=c.bounding_box_px;cv2.rectangle(canvas,(x,y),(x+w,y+h),(0,0,255),2)
                cv2.imwrite(str(OUT/(path.stem+'-verified.png')),canvas)
        # Exact equality is stronger than a count check for already-working cases.
        a,b=record['before'],record['after']
        record['same_candidate_geometry']=(
            sorted((c['bounding_box_px'],c['center_px']) for c in a['candidates'])==
            sorted((c['bounding_box_px'],c['center_px']) for c in b['candidates']))
        rows.append(record)
        print(path.name,a['count'],'->',b['count'],'same boxes',record['same_candidate_geometry'],flush=True)
    report={'cases':rows,'peak_process_mb':peak_memory_mb(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (ROOT/'app').rglob('*.py')}}
    (OUT/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')


def render_ui():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase,QFont
    from app.main import APP_STYLESHEET
    from app.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    app.setFont(QFont('Segoe UI',10));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
    records=[]
    for name in ('patchwork_animals_5x4','pastel_4x4','space_dark_3x5'):
        window=MainWindow();window.resize(1440,960);window.show()
        original=cv2.imread(str(ROOT/'tests/fixtures/acceptance'/(name+'.png')))
        window._load_image(original,name)
        window.detector.bed_reference=None
        window.detect_motifs();app.processEvents()
        np.testing.assert_array_equal(window.image_bgr,original)
        window.statusBar().showMessage(f'Verification: {len(window.detections)} cuts — {name}')
        window.grab().save(str(OUT/(name+'-ui.png')))
        records.append({'image':name,'count':len(window.detections),
                        'grid':[window.panel_grid.columns,window.panel_grid.rows],
                        'cut_inches':[window.cut_width_inches,window.cut_height_inches],
                        'overlaps':sum(d.overlaps_cut for d in window.detections),
                        'artwork_clipped':sum(d.artwork_clipped for d in window.detections),
                        'reviews':sum(bool(d.review_reasons) for d in window.detections),
                        'inferred':sum(d.inferred for d in window.detections)})
        window.close()
    (OUT/'ui-results.json').write_text(json.dumps(records,indent=2)+'\n')
    print(records)


if __name__=='__main__':
    render_ui() if '--ui' in sys.argv else main()
