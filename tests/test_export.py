from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from app.export.svg_exporter import SVG_NAMESPACE, SVGExporter
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit
from app.models import Detection
from app.export.verifier import verify_export_geometry


class SVGExporterTests(unittest.TestCase):
    def test_svg_physical_size_and_only_valid_enabled_rectangles(self) -> None:
        mapper = CoordinateMapper(1800, 1200)
        detections = [
            Detection.from_pixel_center(1, (900, 600), mapper),
            Detection.from_pixel_center(2, (50, 50), mapper),  # invalid
            Detection.from_pixel_center(3, (1200, 800), mapper, enabled=False),
            Detection.from_pixel_center(4, (400, 300), mapper),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cuts.svg"
            result = SVGExporter().export(path, mapper, detections)
            root = ET.parse(path).getroot()

        self.assertEqual(root.attrib["width"], "36in")
        self.assertEqual(root.attrib["height"], "24in")
        self.assertEqual(root.attrib["viewBox"], "0 0 36 24")
        rectangles = root.findall(f"{{{SVG_NAMESPACE}}}rect")
        self.assertEqual(len(rectangles), 2)
        self.assertEqual(result.rectangle_count, 2)
        self.assertTrue(all(rect.attrib["width"] == "5" for rect in rectangles))
        self.assertTrue(all(rect.attrib["height"] == "5" for rect in rectangles))

    def test_svg_can_export_in_millimetres(self) -> None:
        mapper = CoordinateMapper(1800, 1200)
        detection = Detection.from_pixel_center(1, (900, 600), mapper)
        tree = SVGExporter().build_tree(
            mapper, [detection], LengthUnit.MILLIMETRES
        )
        root = tree.getroot()
        self.assertEqual(root.attrib["width"], "914.4mm")
        self.assertEqual(root.attrib["height"], "609.6mm")
        self.assertEqual(root.attrib["viewBox"], "0 0 914.4 609.6")
        rectangle = root.findall(f"{{{SVG_NAMESPACE}}}rect")[0]
        self.assertEqual(rectangle.attrib["width"], "127")
        self.assertEqual(rectangle.attrib["height"], "127")
        verification = verify_export_geometry(
            mapper, [detection], LengthUnit.MILLIMETRES
        )
        self.assertLess(verification.maximum_error_x_px, 1e-9)
        self.assertLess(verification.maximum_error_y_px, 1e-9)


if __name__ == "__main__":
    unittest.main()
