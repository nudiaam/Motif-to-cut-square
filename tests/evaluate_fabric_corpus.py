"""Measure detection, cut geometry and SVG on a local fabric corpus.

Run from the repository root. The private inputs are referenced by a manifest;
only the measurements are written to the chosen output directory.
"""

import argparse
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from app import __version__
from app.export.svg_exporter import SVG_NAMESPACE, cuts_for_output
from app.imaging.detector import DetectorSettings
from app.ui.main_window import MainWindow


def reference_cells(reference):
    cols, rows = reference['shape']
    if 'xs' in reference:
        xs, ys = reference['xs'], reference['ys']
        return {(c, r): np.float32(((xs[c], ys[r]), (xs[c+1], ys[r]),
                                   (xs[c+1], ys[r+1]), (xs[c], ys[r+1])))
                for r in range(rows) for c in range(cols)}
    transform = cv2.getPerspectiveTransform(
        np.float32(((0, 0), (cols, 0), (cols, rows), (0, rows))),
        np.float32(reference['quad']),
    )
    return {(c, r): cv2.perspectiveTransform(np.float32([[(c, r), (c+1, r),
                (c+1, r+1), (c, r+1)]]), transform)[0]
            for r in range(rows) for c in range(cols)}


def measure_cuts(window, size, reference):
    window.change_cut_size(size, size)
    mapper = window.mapper
    cuts = cuts_for_output(mapper, window.detections)
    geometry = [cut.square_inches.as_tuple() for cut in cuts]
    svg = window.svg_exporter.build_tree(mapper, window.detections)
    outlines = [tuple(float(rect.attrib[key]) for key in ('x', 'y', 'width', 'height'))
                for rect in svg.findall(f'{{{SVG_NAMESPACE}}}rect')]
    reference_margins, centre_errors = [], []
    for cut in cuts:
        polygon = reference.get(cut.layout_cell)
        if polygon is None:
            continue
        x, y, width, height = mapper.inches_rect_to_pixel(cut.square_inches.as_tuple())
        corners = ((x, y), (x+width, y), (x+width, y+height), (x, y+height))
        reference_margins.append(min(cv2.pointPolygonTest(polygon, point, True) for point in corners))
        centre_errors.append(float(np.linalg.norm(np.asarray(cut.center_px) - np.mean(polygon, axis=0))))
    return {
        'exported': len(cuts), 'crossings': sum(bool(cut.panel_boundary_reason(mapper)) for cut in cuts),
        'overlap_cuts': sum(cut.overlaps_cut for cut in cuts),
        'artwork_clipped': sum(cut.confirmed_artwork_clipped for cut in cuts),
        'artwork_uncertain': sum(cut.artwork_extent_uncertain for cut in cuts),
        'independent_cells_compared': len(centre_errors),
        'independent_crossings_over_6_px': sum(distance < -6. for distance in reference_margins),
        'max_independent_centre_error_px': max(centre_errors, default=None),
        'svg_matches': len(outlines) == len(geometry) and (not geometry or
                        bool(np.allclose(outlines, geometry, rtol=0, atol=1.e-10))),
        'geometry_inches': geometry,
    }


def run_case(case, image, use_fallback):
    window = MainWindow()
    try:
        window._load_image(image, case['id'])
        initial_size = case.get('initial_size', 5)
        window.change_cut_size(initial_size, initial_size)
        settings = window.panel.detector_settings(window.mapper)
        if case.get('report'):
            report = json.loads((ROOT / case['report']).read_text(encoding='utf-8'))
            settings = DetectorSettings(**report['detection_run']['settings'])
            window.detector.bed_reference = cv2.imread(str(ROOT / case['bed_reference']))
        route = nullcontext() if use_fallback else patch(
            'app.imaging.printed_partition.infer_straight_printed_partition', return_value=None)
        started = perf_counter()
        with route:
            result = window.detector.detect_with_layout(image, settings)
        seconds = perf_counter() - started
        diagnostics = window.detector.last_diagnostics
        window._apply_detection_result(result, diagnostics)
        primary = window.logical_layout
        boxes = [c.bounding_box_px for c in result.candidates]
        witnesses = [[i for i, (x, y, width, height) in enumerate(boxes)
                       if all(x <= px < x+width and y <= py < y+height for px, py in group)]
                     for group in case.get('witnesses', [])]
        expected = case.get('reference')
        reference = (reference_cells(expected) if expected and
                     (list(expected['shape']) == [primary.columns, primary.rows] or case.get('reference_prefix'))
                     else {})
        return {
            'candidates': len(result.candidates), 'initial_cut_size': initial_size,
            'count': len(window.detections), 'grid': [primary.columns, primary.rows],
            'grid_source': primary.source, 'grid_reliable': primary.reliable,
            'outliers': sum(match.status != 'matched' for match in primary.matches),
            'detector_seconds': seconds, 'identity': diagnostics['identity']['input_sha256'],
            'result_sha256': diagnostics['result_sha256'], 'settings': asdict(settings),
            'used_touching_fallback': any(p.get('method') == 'sustained_printed_transitions'
                                          for p in diagnostics['detection_plans']),
            'witnesses': len(witnesses), 'witnesses_with_unique_hit': sum(len(h) == 1 for h in witnesses),
            'distinct_witness_owners': len({h[0] for h in witnesses if len(h) == 1}),
            'sizes': {str(size): measure_cuts(window, size, reference) for size in (4, 5)},
        }
    finally:
        window.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    args = parser.parse_args()
    cv2.setNumThreads(2)
    app = QApplication([])
    cases = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases[args.shard::args.shards]:
        path = ROOT / case['path']
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if case.get('sha256') and digest != case['sha256']:
            raise ValueError(f'Input differs from its manifest: {path}')
        current = run_case(case, image, use_fallback=True)
        previous = (run_case(case, image, use_fallback=False)
                    if current['used_touching_fallback'] or case.get('paired') else None)
        results.append({'id': case['id'], 'sha256': digest, 'current': current, 'without_fallback': previous})
        args.output.write_text(json.dumps({'version': __version__, 'cases': results}, indent=2), encoding='utf-8')
        print(case['id'], current['count'], current['grid'], current['grid_source'],
              f"{current['detector_seconds']:.2f}s", 'paired' if previous else '', flush=True)
    assert app is not None


if __name__ == '__main__':
    main()
