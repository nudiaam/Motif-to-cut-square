"""Reproduce coverage, shadow probes, witness boxes and CPU-only timings.

Run: python -m tests.evaluate_adaptive_planning
Box containment is a partial oracle, not a full silhouette accuracy measurement.
"""
from dataclasses import asdict
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector
from tests.diagnose_remaining_detection import WITNESSES, in_box


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/qa/adaptive-planning'


def peak_memory_mb():
    """Whole evaluator process peak working set on Windows, including OpenCV."""
    if sys.platform != 'win32':
        return None
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                'PagefileUsage', 'PeakPagefileUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not get_memory(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return counters.PeakWorkingSetSize / (1024*1024)


def run_case(image, name, expected_count, overlay=False):
    detector = MotifDetector()
    source_hash = hashlib.sha256(image.tobytes()).hexdigest()
    started = time.perf_counter()
    result = detector.detect_with_layout(image, DetectorSettings())
    elapsed = time.perf_counter() - started
    assert hashlib.sha256(image.tobytes()).hexdigest() == source_hash
    row = {'name': name, 'expected_compositions': expected_count,
           'count': len(result.candidates), 'seconds': elapsed,
           'review_count': sum(bool(c.review_reasons) for c in result.candidates),
           'grid_dimensions': [result.panel_grid.columns, result.panel_grid.rows] if result.panel_grid else None,
           'diagnostics': detector.last_diagnostics,
           'candidates': [asdict(c) for c in result.candidates]}
    if name.startswith('dogs'):
        witnesses = []
        for witness in WITNESSES:
            col, grid_row = np.array(witness['cell']) - 1
            grid = result.panel_grid
            if grid is None or col >= grid.columns or grid_row >= grid.rows:
                witnesses.append({**witness, 'contained': [False]*len(witness['points'])})
                continue
            cx = (grid.x_lines_px[col]+grid.x_lines_px[col+1])/2
            cy = (grid.y_lines_px[grid_row]+grid.y_lines_px[grid_row+1])/2
            candidate = min(result.candidates, key=lambda c: (c.center_px[0]-cx)**2+(c.center_px[1]-cy)**2)
            witnesses.append({**witness, 'contained': [in_box(p, candidate.bounding_box_px) for p in witness['points']]})
        row['witnesses'] = witnesses
    if overlay:
        preview = image.copy()
        for candidate in result.candidates:
            x,y,w,h = candidate.bounding_box_px
            cv2.rectangle(preview, (x,y), (x+w,y+h), (0,80,240), 2)
        cv2.imwrite(str(OUTPUT/(name+'-bounds.png')), preview)
    print(name, row['count'], row['grid_dimensions'], round(elapsed,2), 's', flush=True)
    return row


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fixture = ROOT/'tests/fixtures'
    files = sorted((fixture/'generated').rglob('*.png'))
    files += [fixture/name for name in (
        'pastel_panels_camera.png', 'patchwork_camera.png', 'transport_camera.png',
        'vehicles_panels.png', 'floral_patchwork_recovered.png')]
    rows = []
    for path in files:
        expected = 19 if path.stem in ('transport_camera','transport_spanning_5x4') else 24
        rows.append(run_case(cv2.imread(str(path)), path.stem, expected,
                             overlay=path.stem in ('dogs_6x4','hearts_6x4','floral_patchwork_recovered')))
    dogs = cv2.imread(str(fixture/'generated/straight/dogs_6x4.png'))
    for gain in (.85,.65,.45):
        shadow = dogs.copy()
        shadow[730:] = (shadow[730:].astype(np.float32)*gain).astype(np.uint8)
        rows.append(run_case(shadow, f'dogs_shadow_hard_{gain}', 24, overlay=gain==.45))
    gains = np.ones(dogs.shape[0],np.float32)
    gains[650:] = np.linspace(1,.45,len(gains)-650)
    smooth = (dogs.astype(np.float32)*gains[:,None,None]).astype(np.uint8)
    rows.append(run_case(smooth, 'dogs_shadow_smooth', 24))
    report = {'cases':rows, 'peak_evaluator_working_set_mb':peak_memory_mb(),
              'memory_scope':'whole CPU evaluation process, includes images and OpenCV, excludes Qt UI',
              'limitations':['No annotated complete masks; box witnesses are partial checks.',
                             'Synthetic shadows are probes, not new independent collections.',
                             'Review counts are not detection error rates.']}
    (OUTPUT/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
