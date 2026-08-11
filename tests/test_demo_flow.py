from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.demo.demo_image import create_demo_image
from app.export.debug_exporter import export_debug_json
from app.export.svg_exporter import SVGExporter
from app.export.verifier import verify_export_geometry
from app.geometry.coordinate_mapper import CoordinateMapper
from app.imaging.detector import DetectorSettings, MotifDetector
from app.models import Detection


class DemoFlowTests(unittest.TestCase):
    def test_demo_detection_exports_and_round_trip(self) -> None:
        image = create_demo_image()
        height, width = image.shape[:2]
        mapper = CoordinateMapper(width, height)
        candidates = MotifDetector().detect(image, DetectorSettings())
        self.assertGreaterEqual(len(candidates), 8)
        self.assertLessEqual(len(candidates), 12)

        detections = [
            Detection.from_pixel_center(
                index,
                candidate.center_px,
                mapper,
                candidate.bounding_box_px,
                candidate.score,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        self.assertTrue(any(item.valid_cut for item in detections))
        self.assertTrue(any(not item.valid_cut for item in detections))

        verification = verify_export_geometry(mapper, detections)
        self.assertLess(verification.maximum_error_x_px, 1e-9)
        self.assertLess(verification.maximum_error_y_px, 1e-9)

        with tempfile.TemporaryDirectory() as directory:
            svg_path = Path(directory) / "demo.svg"
            json_path = Path(directory) / "demo.json"
            svg_result = SVGExporter().export(svg_path, mapper, detections)
            export_debug_json(json_path, mapper, detections)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertTrue(svg_path.exists())
            self.assertEqual(svg_result.rectangle_count, len(verification.overlay_rectangles_px))
            self.assertEqual(len(payload["detections"]), len(detections))
            self.assertEqual(payload["bed_width_inches"], 36.0)
            self.assertEqual(payload["bed_height_inches"], 24.0)


if __name__ == "__main__":
    unittest.main()
