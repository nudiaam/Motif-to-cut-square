from __future__ import annotations

import unittest

from app.export.svg_exporter import SVG_NAMESPACE, SVGExporter
from app.geometry.coordinate_mapper import CoordinateMapper
from app.models import Detection, recalculate_cut_overlaps


class CutOverlapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = CoordinateMapper(1800, 1200)

    def _detection(
        self, detection_id: int, x_in: float, y_in: float, enabled: bool = True
    ) -> Detection:
        return Detection.from_pixel_center(
            detection_id,
            self.mapper.inches_to_pixel(x_in, y_in),
            self.mapper,
            enabled=enabled,
        )

    def test_touching_and_overlapping_cuts_are_both_marked(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        touching = self._detection(2, 15.0, 10.0)
        separate = self._detection(3, 25.0, 10.0)
        recalculate_cut_overlaps([first, touching, separate])
        self.assertTrue(first.overlaps_cut)
        self.assertTrue(touching.overlaps_cut)
        self.assertFalse(separate.overlaps_cut)
        self.assertFalse(first.exportable)

    def test_disabled_cut_does_not_create_a_collision(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        disabled = self._detection(2, 10.0, 10.0, enabled=False)
        recalculate_cut_overlaps([first, disabled])
        self.assertFalse(first.overlaps_cut)
        self.assertFalse(disabled.overlaps_cut)
        self.assertTrue(first.exportable)

    def test_colliding_cuts_are_not_exported(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        second = self._detection(2, 12.0, 10.0)
        safe = self._detection(3, 25.0, 10.0)
        root = SVGExporter().build_tree(self.mapper, [first, second, safe]).getroot()
        rectangles = root.findall(f"{{{SVG_NAMESPACE}}}rect")
        self.assertEqual(len(rectangles), 1)
        self.assertTrue(first.overlaps_cut)
        self.assertTrue(second.overlaps_cut)
        self.assertTrue(safe.exportable)


if __name__ == "__main__":
    unittest.main()
