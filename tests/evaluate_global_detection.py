"""Save detector diagnostics and optional UI previews; counts are not accuracy.

python -m tests.evaluate_global_detection --output docs/qa/global-rework --screenshots
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time

import cv2

from app.imaging.detector import DetectorSettings, MotifDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('tmp/global-evaluation'))
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixtures = Path(__file__).parent / 'fixtures'
    paths = sorted((fixtures / 'generated').rglob('*.png'))
    paths += [fixtures / name for name in ('pastel_panels_camera.png', 'patchwork_camera.png',
                                          'transport_camera.png', 'vehicles_panels.png')]
    rows = []
    for path in paths:
        image = cv2.imread(str(path))
        detector = MotifDetector()
        start = time.perf_counter()
        result = detector.detect_with_layout(image, DetectorSettings())
        row = {'file': path.relative_to(fixtures).as_posix(),
               'count': len(result.candidates),
               'review_count': sum(bool(c.review_reasons) for c in result.candidates),
               'seconds': time.perf_counter()-start,
               'grid': asdict(result.panel_grid) if result.panel_grid else None,
               'diagnostics': detector.last_diagnostics}
        rows.append(row)
        print(path.name, row['count'], 'compositions,', row['review_count'], 'extent/layout reviews', flush=True)
    (args.output / 'fixture-results.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    if not args.screenshots:
        return
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    from app.main import APP_STYLESHEET
    from app.ui.main_window import MainWindow
    from app.export.debug_exporter import export_debug_json
    application = QApplication.instance() or QApplication([])
    # Offscreen Qt does not always discover installed Windows fonts.
    for name in ('segoeui.ttf', 'segoeuib.ttf'):
        font = Path('C:/Windows/Fonts') / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    application.setFont(QFont('Segoe UI', 10))
    application.setStyle('Fusion')
    application.setStyleSheet(APP_STYLESHEET)
    ui_rows = []
    for name in ('pastel_6x4', 'dogs_6x4', 'hearts_6x4'):
        image = cv2.imread(str(fixtures / 'generated/straight' / (name+'.png')))
        window = MainWindow()
        window.resize(1440, 980)
        window.show()
        application.processEvents()
        window._load_image(image, name)
        window.change_cut_size(5, 5)
        window.detect_motifs()
        application.processEvents()
        window.grab().save(str(args.output / (name+'-ui.png')))
        export_debug_json(args.output / (name+'.json'), window.mapper, window.detections,
                          logical_layout=window.logical_layout, detection_run=window.detection_diagnostics)
        overlay = image.copy()
        for detection in window.detections:
            if detection.bounding_box_px:
                x, y, w, h = detection.bounding_box_px
                color = (40, 130, 240) if detection.review_reasons else (40, 180, 40)
                cv2.rectangle(overlay, (x, y), (x+w, y+h), color, 2)
                cv2.putText(overlay, str(detection.id), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
        cv2.imwrite(str(args.output / (name+'-bounds.png')), overlay)
        row = {'file': name+'.png', 'total': len(window.detections),
               'ready': int(window.panel.valid_value_label.text()),
               'problems': int(window.panel.invalid_value_label.text()),
               'inferred': sum(d.inferred for d in window.detections)}
        ui_rows.append(row)
        print('UI', row, flush=True)
        window.close()
    (args.output / 'ui-results.json').write_text(json.dumps(ui_rows, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
