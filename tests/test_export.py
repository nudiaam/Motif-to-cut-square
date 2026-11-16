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
    def test_svg_physical_size_exports_enabled_unblocked_rectangles(self) -> None:
        mapper = CoordinateMapper(1800, 1200)
        detections = [
            Detection.from_pixel_center(1, (900, 600), mapper),
            Detection.from_pixel_center(2, (50, 50), mapper, enabled=False),  # outside bed
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

    def test_svg_requests_bed_size_print_page_without_margins(self) -> None:
        # This checks the SVG declaration. Actual browser/driver output needs
        # a separate integration check; CSS alone cannot force print settings.
        mapper = CoordinateMapper(1800, 1200)
        detections = [Detection.from_pixel_center(1, (900, 600), mapper)]
        for unit, expected in ((LengthUnit.INCHES, "size: 36in 24in; margin: 0;"),
                               (LengthUnit.MILLIMETRES, "size: 914.4mm 609.6mm; margin: 0;")):
            root = SVGExporter().build_tree(mapper, detections, unit).getroot()
            styles = root.findall(f"{{{SVG_NAMESPACE}}}style")
            self.assertEqual(len(styles), 1)
            self.assertIn("@page", styles[0].text)
            self.assertIn(expected, styles[0].text)

    def test_panel_and_source_warnings_export_but_outside_bed_cuts_are_omitted(self):
        mapper = CoordinateMapper(1800, 1200)
        cases = [
            Detection.from_pixel_center(1, (50, 50), mapper),
            Detection.from_pixel_center(2, (900, 600), mapper, source_incomplete=True),
            Detection.from_pixel_center(3, (150, 600), mapper, (-10, 500, 180, 100)),
            Detection.from_pixel_center(4, (900, 600), mapper),
        ]
        cases[-1].cut_region_required = True
        for detection in cases:
            with self.subTest(id=detection.id), tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'warning.svg'
                self.assertTrue(detection.cut_warning_reason(mapper) or detection.review_reasons_for(mapper))
                self.assertIsNone(detection.cut_hard_block_reason(mapper))
                SVGExporter().export(path,mapper,[detection])
                root=ET.parse(path).getroot()
                expected = 0 if detection.id == 1 else 1
                self.assertEqual(len(root.findall(f'{{{SVG_NAMESPACE}}}rect')),expected)
                self.assertEqual(len(verify_export_geometry(mapper,[detection]).overlay_rectangles_px),expected)
                detection.enabled=False
                self.assertEqual(len(SVGExporter().build_tree(mapper,[detection]).findall(f'{{{SVG_NAMESPACE}}}rect')),0)

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

    def test_five_inch_warning_in_four_inch_cell_exports_exact_size_and_centre(self):
        from app.imaging.panel_grid import PanelGrid
        from app.imaging.logical_layout import LayoutObservation,layout_from_panel_grid
        from app.models import apply_logical_layout
        mapper=CoordinateMapper(1200,1200,12,12)
        grid=PanelGrid((200.,600.,1000.),(200.,600.,1000.),1.,'manual')
        d=Detection.from_pixel_center(1,(390,420),mapper,(380,380,40,40))
        layout=layout_from_panel_grid([LayoutObservation(1,(400,400),d.bounding_box_px)],grid)
        apply_logical_layout([d],mapper,layout)
        self.assertEqual(d.center_px,(400.,400.))
        self.assertIsNotNone(d.panel_boundary_reason(mapper))
        self.assertTrue(d.enabled)
        # Inspect serialized numbers, without using the exporter/verifier's own
        # coordinate conversion to establish the expected result.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'oversize.svg'
            SVGExporter().export(path,mapper,[d])
            rect=ET.parse(path).getroot().find(f'{{{SVG_NAMESPACE}}}rect')
        self.assertEqual(tuple(float(rect.attrib[k]) for k in ('x','y','width','height')),
                         (1.5,1.5,5.,5.))
        d.enabled=False
        self.assertEqual(SVGExporter().build_tree(mapper,[d]).findall(f'{{{SVG_NAMESPACE}}}rect'),[])


if __name__ == "__main__":
    unittest.main()
