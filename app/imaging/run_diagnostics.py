"""Stable input identities and run comparisons; timings are deliberately separate."""
import hashlib
import json
import platform

import cv2
import numpy as np


def image_identity(image):
    if image is None:
        return None
    array = np.ascontiguousarray(image)
    digest = hashlib.sha256()
    digest.update(str((array.shape, array.dtype.str)).encode('ascii'))
    digest.update(memoryview(array))
    return {'pixel_sha256': digest.hexdigest(), 'shape': list(array.shape),
            'dtype': array.dtype.str}


def run_identity(image, reference, settings, route='automatic', guides=None):
    inputs = {'image': image_identity(image), 'reference': image_identity(reference),
              'settings': settings, 'route': route, 'confirmed_guides': guides}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {**inputs, 'input_sha256': digest,
            'runtime': {'python': platform.python_version(), 'opencv': cv2.__version__,
                        'numpy': np.__version__}}


def compare_reports(first, second):
    """Report changed evidence before interpreting changed cuts as improvement."""
    a, b = first.get('detection_run') or {}, second.get('detection_run') or {}
    ia, ib = a.get('identity') or {}, b.get('identity') or {}
    if not ia or not ib:
        return {'comparable': False, 'reason': 'A report lacks input fingerprints; save both runs with the updated app.'}
    changed = [key for key in ('image', 'reference', 'settings', 'route', 'confirmed_guides', 'runtime')
               if ia.get(key) != ib.get(key)]
    if a.get('detector_revision') != b.get('detector_revision'):
        changed.append('detector_revision')
    context = ('image_placement_inches', 'bed_width_inches', 'bed_height_inches', 'machine_name')
    changed += [key for key in context if first.get(key) != second.get(key)]
    return {'comparable': not changed, 'changed_inputs': changed,
            'same_detection_result': a.get('result_sha256') == b.get('result_sha256')
                if a.get('result_sha256') and b.get('result_sha256') else None,
            'same_reviewed_cuts': first.get('detections') == second.get('detections'),
            'note': 'Equal counts alone do not establish equal artwork or cut positions.'}


def result_identity(candidates, grid):
    from dataclasses import asdict
    payload = {'candidates': [asdict(c) for c in candidates],
               'grid': asdict(grid) if grid else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
