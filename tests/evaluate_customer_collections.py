"""Snapshot clean fixtures and generated collection probes; never screenshot inputs."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
from app.imaging.detector import DetectorSettings, MotifDetector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--new-only', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).parent / 'fixtures'
    paths = sorted((root/'generated/customer_20261012').glob('*.png'))
    if not args.new_only:
        paths += sorted(root.glob('*.png')) + sorted((root/'acceptance').glob('*.png'))
        paths += sorted((root/'generated/straight').glob('*.png'))
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for path in paths:
        image = cv2.imread(str(path))
        detector = MotifDetector()
        start = time.perf_counter()
        result = detector.detect_with_layout(image, DetectorSettings())
        elapsed = time.perf_counter()-start
        data = asdict(result)
        record = {'file': str(path.relative_to(root)), 'seconds': elapsed,
                  'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'count': len(result.candidates), 'result': data,
                  'reviews': dict(Counter(r for c in result.candidates for r in c.review_reasons)),
                  'diagnostics': detector.last_diagnostics}
        records.append(record)
        (args.output/'results.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
        print(path.name, len(result.candidates), round(elapsed, 2), flush=True)
        if 'customer_20261012' in str(path):
            overlay = image.copy()
            if result.panel_grid:
                for _,_,(x,y,w,h) in result.panel_grid.cells():
                    cv2.rectangle(overlay,(x,y),(x+w,y+h),(255,130,60),2)
            for c in result.candidates:
                x,y,w,h=c.bounding_box_px
                cv2.rectangle(overlay,(x,y),(x+w,y+h),(40,30,235),2)
            cv2.imwrite(str(args.output/(path.stem+'-bounds.png')),overlay)


if __name__ == '__main__':
    main()
