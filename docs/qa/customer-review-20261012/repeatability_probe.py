"""Read-only detector audit on existing clean fixtures; no screenshot inputs.

Run from the repository root:
  .venv/Scripts/python.exe docs/qa/customer-review-20261012/repeatability_probe.py
"""
import cProfile
import hashlib
import io
import json
from pathlib import Path
import pstats
import sys
import time
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from app.imaging.detector import DETECTOR_REVISION, DetectorSettings, MotifDetector

OUT = Path(__file__).resolve().parent
FIXTURES = (
    "generated/straight/dogs_6x4.png",
    "floral_patchwork_recovered.png",
    "transport_dashed_shared.png",
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    report = {"revision": DETECTOR_REVISION, "python": sys.version,
              "opencv": cv2.__version__, "numpy": np.__version__,
              "settings": asdict(DetectorSettings()), "cases": []}
    for fixture in FIXTURES:
        path = ROOT / "tests/fixtures" / fixture
        image = cv2.imread(str(path))
        original = image.copy()
        detector = MotifDetector()
        detector.bed_reference = cv2.imread(str(ROOT / "assets/references/epilog/empty_bed.png"))
        runs = []
        for index in range(3):
            if index == 2:
                detector = MotifDetector()
                detector.bed_reference = cv2.imread(str(ROOT / "assets/references/epilog/empty_bed.png"))
            start = time.perf_counter()
            result = detector.detect_with_layout(image, DetectorSettings())
            runs.append({"fresh_instance": index != 1,
                         "seconds": round(time.perf_counter()-start, 3),
                         "count": len(result.candidates),
                         "grid": [result.panel_grid.columns, result.panel_grid.rows] if result.panel_grid else None,
                         "result_sha256": fingerprint(asdict(result)),
                         "diagnostics_sha256": fingerprint(detector.last_diagnostics),
                         "reference_status": detector.reference_status,
                         "review_count": sum(bool(c.review_reasons) for c in result.candidates)})
        case = {"fixture": fixture, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "input_unchanged": bool(np.array_equal(image, original)),
                "same_results": len({r["result_sha256"] for r in runs}) == 1,
                "same_diagnostics": len({r["diagnostics_sha256"] for r in runs}) == 1,
                "runs": runs}
        report["cases"].append(case)
        print(json.dumps(case), flush=True)
    profiler = cProfile.Profile()
    profiler.runcall(detector.detect_with_layout, image, DetectorSettings())
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(35)
    (OUT / "profile.txt").write_text("Fixture: " + FIXTURES[-1] + "\n" + stream.getvalue(), encoding="utf-8")
    (OUT / "repeatability.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
