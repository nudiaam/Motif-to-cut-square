from __future__ import annotations

import math
import unittest

from app.export.svg_exporter import SVG_NAMESPACE, SVGExporter
from app.geometry.coordinate_mapper import CoordinateMapper
from app.models import Detection, recalculate_cut_overlaps, resolve_cut_overlaps


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

    def test_resolver_moves_only_colliding_cuts_to_nearest_free_positions(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        second = self._detection(2, 12.0, 10.0)
        safe = self._detection(3, 25.0, 10.0)
        original_first = first.center_inches
        original_second = second.center_inches
        original_safe = safe.center_inches

        moved_ids, unresolved_ids = resolve_cut_overlaps(
            [first, second, safe], self.mapper
        )

        self.assertEqual(moved_ids, [1, 2])
        self.assertEqual(unresolved_ids, [])
        self.assertNotEqual(first.center_inches, original_first)
        self.assertNotEqual(second.center_inches, original_second)
        self.assertEqual(safe.center_inches, original_safe)
        self.assertAlmostEqual(
            original_first[0] - first.center_inches[0],
            second.center_inches[0] - original_second[0],
            places=9,
        )
        self.assertEqual(first.preferred_center_px, self.mapper.inches_to_pixel(*original_first))
        self.assertEqual(second.preferred_center_px, self.mapper.inches_to_pixel(*original_second))
        self.assertTrue(all(item.exportable for item in (first, second, safe)))

    def test_resolver_reports_when_the_bed_has_no_free_position(self) -> None:
        mapper = CoordinateMapper(500, 500, 5.0, 5.0)
        first = Detection.from_pixel_center(1, (250.0, 250.0), mapper)
        second = Detection.from_pixel_center(2, (250.0, 250.0), mapper)

        moved_ids, unresolved_ids = resolve_cut_overlaps(
            [first, second], mapper
        )

        self.assertEqual(moved_ids, [])
        self.assertEqual(unresolved_ids, [1, 2])

    def test_dense_grid_is_spread_around_visual_centres(self) -> None:
        preferred = [
            (4.0 + 4.7 * column, 3.8 + 4.7 * row)
            for row in range(4)
            for column in range(6)
        ]
        detections = [
            self._detection(index, *center)
            for index, center in enumerate(preferred, start=1)
        ]

        moved_ids, unresolved_ids = resolve_cut_overlaps(
            detections, self.mapper
        )

        shifts = [
            math.dist(detection.center_inches, center)
            for detection, center in zip(detections, preferred)
        ]
        self.assertEqual(len(moved_ids), 24)
        self.assertEqual(unresolved_ids, [])
        self.assertLess(max(shifts), 1.0)
        self.assertLess(sum(shifts) / len(shifts), 0.7)


if __name__ == "__main__":
    unittest.main()
