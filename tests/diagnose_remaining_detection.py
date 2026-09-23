"""Read-only diagnosis of remaining failures, including one isolated ablation.

Run: python -m tests.diagnose_remaining_detection
No application files, thresholds or saved settings are changed. The ablation
removes one early-return condition in memory and restores the method afterwards.
Manual witness points are unambiguous artwork pixels, not complete mask labels.
"""
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

import app.imaging.detector as module
from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.extent_review import review_extents


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/qa/remaining-diagnosis'
WITNESSES = [
    {'cell': [1, 1], 'name': 'dalmatian', 'points': [(165, 264), (230, 264)]},
    {'cell': [3, 1], 'name': 'pug', 'points': [(625, 257), (688, 257), (657, 224)]},
    {'cell': [6, 2], 'name': 'french_bulldog', 'points': [(1327, 481), (1389, 481)]},
    {'cell': [1, 3], 'name': 'golden_retriever', 'points': [(160, 710), (221, 710)]},
]


def seed_diagnostics(image, core_bounds):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    left, top, right, bottom = core_bounds
    inset = max(1, round(min(right-left, bottom-top)*.035))
    sample = lab[top+inset:bottom-inset, left+inset:right-inset]
    border = np.concatenate([sample[0], sample[-1], sample[:, 0], sample[:, -1]])
    background = np.median(border, axis=0)
    distance = np.linalg.norm(lab-background, axis=2)
    border_distance = np.linalg.norm(border-background, axis=1)
    threshold = max(10., float(np.percentile(border_distance, 65)))
    rim = np.zeros(image.shape[:2], bool)
    rim[[0, -1], :] = True
    rim[:, [0, -1]] = True
    sure_bg = rim & (distance <= max(3., float(np.percentile(border_distance, 25))))
    return {'sure_background_pixels': int(sure_bg.sum()),
            'probable_foreground_pixels': int((distance[top:bottom, left:right] > threshold).sum())}


def traced_detection(image, label, region_function):
    folder = OUTPUT / label
    folder.mkdir(parents=True, exist_ok=True)
    calls = []
    original_grabcut = cv2.grabCut

    def trace_region(crop, minimum_area, core_bounds=None):
        index = len(calls)
        row = {'index': index, 'cell_row_major': [index % 6+1, index // 6+1],
               'core_bounds': core_bounds, 'minimum_area': minimum_area,
               **seed_diagnostics(crop, core_bounds)}
        # This trace is for the known 6x4 diagnostic fixture only. The detector
        # is never given dimensions or these cell labels.
        calls.append(row)

        def trace_grabcut(pixels, mask, *args, **kwargs):
            before = mask.copy()
            value = original_grabcut(pixels, mask, *args, **kwargs)
            selected = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD))
            row.update(grabcut_executed=True, foreground_fraction=float(selected.mean()),
                       foreground_box=cv2.boundingRect(selected.astype(np.uint8)))
            if index in (0, 2, 11, 12):
                cv2.imwrite(str(folder / f'cell-{index:02d}-seeds.png'), np.isin(before, (1, 3)).astype(np.uint8)*255)
                cv2.imwrite(str(folder / f'cell-{index:02d}-mask.png'), selected.astype(np.uint8)*255)
            return value

        with patch('cv2.grabCut', side_effect=trace_grabcut):
            result = region_function(crop, minimum_area, core_bounds)
        row['returned_region'] = asdict(result) if result else None
        if index in (0, 2, 11, 12):
            cv2.imwrite(str(folder / f'cell-{index:02d}-input.png'), crop)
        return result

    with patch.object(MotifDetector, '_local_colour_region', side_effect=trace_region):
        detector = MotifDetector()
        result = detector.detect_with_layout(image, DetectorSettings())
    return result, calls, detector.last_diagnostics


def in_box(point, box):
    x, y, w, h = box
    return x <= point[0] < x+w and y <= point[1] < y+h


def witness_metrics(result, xs, ys):
    output = []
    spacing = min(np.median(np.diff(result.panel_grid.x_lines_px)),
                  np.median(np.diff(result.panel_grid.y_lines_px)))
    pad = max(6, round(spacing*.18))
    for witness in WITNESSES:
        column, row = witness['cell']
        candidate = next(c for c in result.candidates if
                         xs[column-1] <= c.center_px[0] < xs[column]
                         and ys[row-1] <= c.center_px[1] < ys[row])
        x, y, w, h = candidate.bounding_box_px
        review_box = (x-pad, y-pad, w+pad*2, h+pad*2)
        output.append({**witness, 'detected_box': candidate.bounding_box_px,
                       'review_window': review_box, 'review_reasons': candidate.review_reasons,
                       'points_outside_detection': [p for p in witness['points'] if not in_box(p, candidate.bounding_box_px)],
                       'points_outside_review_window': [p for p in witness['points'] if not in_box(p, review_box)]})
    return output


def mechanism_probes():
    # The foreground is exactly the same complete ellipse in both images.
    foreground = np.zeros((240, 240), np.uint8)
    cv2.ellipse(foreground, (120, 120), (35, 55), 0, 0, 360, 255, -1)
    bbox = cv2.boundingRect(foreground)
    candidate = MotifCandidate((120, 120), bbox, .9, int(np.count_nonzero(foreground)))
    reviews = []
    for stripes in (False, True):
        image = np.full((240, 240, 3), 230, np.uint8)
        if stripes:
            for x in range(0, 240, 15):
                image[:, x:x+3] = 210
        image[foreground > 0] = (50, 80, 110)
        result = review_extents(image, (candidate,))[0]
        reviews.append({'striped_background': stripes, 'review_reasons': result.review_reasons})
        cv2.imwrite(str(OUTPUT / ('complete-striped.png' if stripes else 'complete-plain.png')), image)
    local_mask = np.zeros((200, 200), np.uint8)
    local_mask[60:140, :60] = 255
    cleaned = MotifDetector._remove_camera_surround(local_mask)
    return {'complete_figure_background_comparison': reviews,
            'local_border_component': {'input_pixels': int(np.count_nonzero(local_mask)),
                                       'retained_pixels': int(np.count_nonzero(cleaned))}}


def comparison_image(image, baseline, alternative):
    # An annotated diagnostic plot, never a replacement test input.
    left, top, right, bottom = 510, 45, 785, 315
    panels = []
    for title, result in (('Current detection', baseline), ('Only remove early return', alternative)):
        canvas = image[top:bottom, left:right].copy()
        candidate = next(c for c in result.candidates if 543 < c.center_px[0] < 774 and c.center_px[1] < 282)
        x, y, w, h = candidate.bounding_box_px
        cv2.rectangle(canvas, (x-left, y-top), (x+w-left, y+h-top), (0, 130, 255), 2)
        for point in WITNESSES[1]['points']:
            cv2.circle(canvas, (point[0]-left, point[1]-top), 4, (240, 100, 20), -1)
        canvas = cv2.copyMakeBorder(canvas, 35, 0, 0, 0, cv2.BORDER_CONSTANT, value=(245, 245, 245))
        cv2.putText(canvas, title, (8, 23), cv2.FONT_HERSHEY_SIMPLEX, .53, (25, 25, 25), 1)
        panels.append(canvas)
    cv2.imwrite(str(OUTPUT / 'pug-controlled-comparison.png'), np.hstack(panels))


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'tests/fixtures/generated/straight/dogs_6x4.png'
    image = cv2.imread(str(source))
    manifest = json.loads((source.parent / 'manifest.json').read_text(encoding='utf-8'))
    annotation = next(c for c in manifest['cases'] if c['file'] == source.name)
    original = MotifDetector._local_colour_region
    baseline, calls, diagnostics = traced_detection(image, 'baseline', original)
    # Counterfactual with exactly one condition removed, in an isolated namespace.
    code = inspect.getsource(original)
    code = '\n'.join(line[4:] for line in code.splitlines()[1:])
    condition = 'not np.any(sure_background) or '
    assert code.count(condition) == 1, 'Update diagnostic when the implementation changes'
    namespace = dict(module.__dict__)
    exec(code.replace(condition, ''), namespace)
    alternative, alt_calls, _ = traced_detection(image, 'ablation', namespace['_local_colour_region'])
    metrics = witness_metrics(baseline, annotation['x_lines_px'], annotation['y_lines_px'])
    alt_metrics = witness_metrics(alternative, annotation['x_lines_px'], annotation['y_lines_px'])
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'detector_revision': module.DETECTOR_REVISION,
              'application_files_changed': False,
              'baseline': {'count': len(baseline.candidates), 'calls': calls, 'witnesses': metrics,
                           'diagnostics': diagnostics},
              'ablation_remove_hard_bg_guard_only': {'count': len(alternative.candidates),
                                                    'calls': alt_calls, 'witnesses': alt_metrics},
              'mechanism_probes': mechanism_probes(),
              'grid_line_max_error_px': {
                  'x': float(np.max(abs(np.asarray(baseline.panel_grid.x_lines_px)-annotation['x_lines_px']))),
                  'y': float(np.max(abs(np.asarray(baseline.panel_grid.y_lines_px)-annotation['y_lines_px'])))}}
    (OUTPUT / 'diagnosis.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    comparison_image(image, baseline, alternative)
    print('Region calls:', len(calls), 'GrabCut skipped:', sum(not c.get('grabcut_executed') for c in calls))
    print('No definite background:', sum(c['sure_background_pixels'] == 0 for c in calls))
    print('Insufficient probable foreground:', sum(c['probable_foreground_pixels'] < c['minimum_area'] for c in calls))
    for before, after in zip(metrics, alt_metrics):
        print(before['name'], 'missing witness points:', len(before['points_outside_detection']),
              'after ablation:', len(after['points_outside_detection']),
              'outside original review window:', len(before['points_outside_review_window']))
    print('Mechanism probes:', report['mechanism_probes'])
    print('Grid max line errors:', report['grid_line_max_error_px'])


if __name__ == '__main__':
    main()
