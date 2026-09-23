"""Report frontal synthetic cases without encoding failures as desired behavior.

Run: python -m tests.evaluate_straight_panels
This is an evaluation report, not part of unittest discovery. Nonzero exit
means some annotated cell is missing, duplicated, or has an outside detection.
Cell coverage does not certify complete artwork bounds or physical cuts.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector


FIXTURES = Path(__file__).parent / "fixtures/generated/straight"


def evaluate():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for case in manifest["cases"]:
        path = FIXTURES / case["file"]
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot read fixture: {path}")
        detector = MotifDetector()
        start = time.perf_counter()
        result = detector.detect_with_layout(image, DetectorSettings())
        elapsed = time.perf_counter() - start
        xs, ys = case["x_lines_px"], case["y_lines_px"]
        by_cell, outside = {}, []
        for index, candidate in enumerate(result.candidates, 1):
            x, y = candidate.center_px
            cell = (int(np.searchsorted(xs, x, side="right")),
                    int(np.searchsorted(ys, y, side="right")))
            if 1 <= cell[0] < len(xs) and 1 <= cell[1] < len(ys):
                by_cell.setdefault(cell, []).append(index)
            else:
                outside.append(index)
        missing = [(c, r) for r in range(1, len(ys)) for c in range(1, len(xs))
                   if (c, r) not in by_cell]
        duplicates = [{"cell": cell, "candidates": ids}
                      for cell, ids in by_cell.items() if len(ids) > 1]
        passed = not (missing or duplicates or outside)
        results.append({
            "file": case["file"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "expected_compositions": case["expected_compositions"],
            "candidate_count": len(result.candidates), "occupied_cells": len(by_cell),
            "missing_cells": missing, "duplicate_cells": duplicates,
            "outside_candidates": outside, "cell_coverage_passed": passed,
            "seconds": elapsed, "diagnostics": detector.last_diagnostics,
            "candidates": [asdict(c) for c in result.candidates],
        })
        print(f"{case['file']}: {len(result.candidates)} candidates, "
              f"{len(by_cell)}/{case['expected_compositions']} occupied cells, "
              f"{len(duplicates)} duplicate cells; {'PASS' if passed else 'FAIL'}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tmp/straight-panel-evaluation.json"))
    args = parser.parse_args()
    results = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r["cell_coverage_passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
