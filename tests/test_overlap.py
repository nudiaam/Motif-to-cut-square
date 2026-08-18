from __future__ import annotations

import math
import unittest

from app.export.svg_exporter import SVG_NAMESPACE, SVGExporter
from app.geometry.coordinate_mapper import CoordinateMapper
from app.models import (
    Detection,
    center_cuts_on_visual_anchors,
    recalculate_cut_overlaps,
    resolve_cut_overlaps,
)


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

    def test_colliding_cuts_are_still_exported_with_a_warning(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        second = self._detection(2, 12.0, 10.0)
        safe = self._detection(3, 25.0, 10.0)
        root = SVGExporter().build_tree(self.mapper, [first, second, safe]).getroot()
        rectangles = root.findall(f"{{{SVG_NAMESPACE}}}rect")
        # Every checked cut is exported; overlaps only raise a warning, they no
        # longer silently drop the geometry.
        self.assertEqual(len(rectangles), 3)
        self.assertTrue(first.overlaps_cut)
        self.assertTrue(second.overlaps_cut)
        self.assertFalse(first.exportable)
        self.assertFalse(second.exportable)
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

    def test_dense_varied_artwork_is_fixed_then_centered_without_regression(self) -> None:
        detections = []
        for row in range(4):
            for column in range(6):
                detection_id = row * 6 + column + 1
                anchor = (3.5 + column * 4.9, 3.5 + row * 4.9)
                artwork_center = (
                    anchor[0] + ((detection_id % 3) - 1) * 0.28,
                    anchor[1] + ((detection_id % 4) - 1.5) * 0.18,
                )
                artwork_width = 3.0 + (detection_id % 4) * 0.20
                artwork_height = 3.0 + (detection_id % 5) * 0.18
                artwork_rect = (
                    artwork_center[0] - artwork_width / 2,
                    artwork_center[1] - artwork_height / 2,
                    artwork_width,
                    artwork_height,
                )
                box_px = tuple(
                    int(round(value))
                    for value in self.mapper.inches_rect_to_pixel(artwork_rect)
                )
                detections.append(
                    Detection.from_pixel_center(
                        detection_id,
                        self.mapper.inches_to_pixel(*anchor),
                        self.mapper,
                        bounding_box_px=box_px,
                    )
                )

        recalculate_cut_overlaps(detections)
        self.assertTrue(any(item.overlaps_cut for item in detections))
        _moved, unresolved = resolve_cut_overlaps(detections, self.mapper)
        self.assertEqual(unresolved, [])
        self.assertFalse(any(item.overlaps_cut for item in detections))

        _centered, problems = center_cuts_on_visual_anchors(
            detections, self.mapper
        )
        self.assertEqual(problems, [])
        self.assertTrue(all(item.exportable for item in detections))
        self.assertTrue(
            all(item.contains_artwork(self.mapper) for item in detections)
        )

    def test_overlap_solver_does_not_ignore_a_misaligned_feasible_cut(self) -> None:
        first = Detection.from_pixel_center(
            1,
            self.mapper.inches_to_pixel(10.0, 10.0),
            self.mapper,
            bounding_box_px=tuple(
                int(round(value))
                for value in self.mapper.inches_rect_to_pixel(
                    (8.5, 8.5, 3.0, 3.0)
                )
            ),
        )
        second = Detection.from_pixel_center(
            2,
            self.mapper.inches_to_pixel(12.0, 10.0),
            self.mapper,
            bounding_box_px=tuple(
                int(round(value))
                for value in self.mapper.inches_rect_to_pixel(
                    (13.0, 8.5, 3.0, 3.0)
                )
            ),
        )
        self.assertFalse(second.valid_cut)
        self.assertTrue(second.has_feasible_placement(self.mapper))

        _moved, unresolved = resolve_cut_overlaps(
            [first, second], self.mapper
        )

        self.assertEqual(unresolved, [])
        self.assertTrue(first.valid_cut)
        self.assertTrue(second.valid_cut)
        self.assertFalse(first.overlaps_cut)
        self.assertFalse(second.overlaps_cut)

    def test_centering_returns_to_visual_anchors_when_space_is_free(self) -> None:
        first = self._detection(1, 8.0, 10.0)
        second = self._detection(2, 20.0, 10.0)
        first.move_to_inches((6.0, 10.0), self.mapper, preserve_preferred_center=True)
        second.move_to_inches((22.0, 10.0), self.mapper, preserve_preferred_center=True)

        moved_ids, limited_ids = center_cuts_on_visual_anchors(
            [first, second], self.mapper
        )

        self.assertEqual(moved_ids, [1, 2])
        self.assertEqual(limited_ids, [])
        self.assertEqual(first.center_inches, (8.0, 10.0))
        self.assertEqual(second.center_inches, (20.0, 10.0))
        self.assertTrue(first.exportable)
        self.assertTrue(second.exportable)

    def test_centering_stays_nearest_to_anchors_without_recreating_overlap(self) -> None:
        first = self._detection(1, 10.0, 10.0)
        second = self._detection(2, 14.0, 10.0)
        first.move_to_inches((8.0, 10.0), self.mapper, preserve_preferred_center=True)
        second.move_to_inches((16.0, 10.0), self.mapper, preserve_preferred_center=True)
        recalculate_cut_overlaps([first, second])
        self.assertFalse(first.overlaps_cut)
        self.assertFalse(second.overlaps_cut)

        moved_ids, problem_ids = center_cuts_on_visual_anchors(
            [first, second], self.mapper
        )

        self.assertEqual(moved_ids, [1, 2])
        self.assertEqual(problem_ids, [])
        self.assertFalse(first.overlaps_cut)
        self.assertFalse(second.overlaps_cut)
        self.assertAlmostEqual(
            second.center_inches[0] - first.center_inches[0], 5.01
        )
        self.assertAlmostEqual(
            first.center_inches[0] + second.center_inches[0], 24.0
        )

    def test_automatic_cut_centers_on_complete_artwork_bounds(self) -> None:
        detection = Detection.from_pixel_center(
            1,
            self.mapper.inches_to_pixel(10.0, 12.0),
            self.mapper,
            bounding_box_px=(375, 350, 250, 250),
        )

        moved_ids, problem_ids = center_cuts_on_visual_anchors(
            [detection], self.mapper
        )

        self.assertEqual(moved_ids, [1])
        self.assertEqual(problem_ids, [])
        self.assertEqual(detection.center_inches, (10.0, 9.5))
        artwork_x, artwork_y, artwork_width, artwork_height = (
            self.mapper.pixel_rect_to_inches(detection.bounding_box_px)
        )
        square = detection.square_inches
        self.assertLessEqual(square.x, artwork_x)
        self.assertLessEqual(square.y, artwork_y)
        self.assertGreaterEqual(square.x + square.width, artwork_x + artwork_width)
        self.assertGreaterEqual(square.y + square.height, artwork_y + artwork_height)

    def test_overlap_fix_keeps_complete_artwork_inside_each_cut(self) -> None:
        first = Detection.from_pixel_center(
            1,
            self.mapper.inches_to_pixel(10.0, 10.0),
            self.mapper,
            bounding_box_px=(425, 425, 150, 150),
        )
        second = Detection.from_pixel_center(
            2,
            self.mapper.inches_to_pixel(14.8, 10.0),
            self.mapper,
            bounding_box_px=(665, 425, 150, 150),
        )
        center_cuts_on_visual_anchors([first, second], self.mapper)

        _moved_ids, unresolved_ids = resolve_cut_overlaps(
            [first, second], self.mapper
        )

        self.assertEqual(unresolved_ids, [])
        for detection in (first, second):
            artwork_x, artwork_y, artwork_width, artwork_height = (
                self.mapper.pixel_rect_to_inches(detection.bounding_box_px)
            )
            square = detection.square_inches
            self.assertLessEqual(square.x, artwork_x + 1e-9)
            self.assertLessEqual(square.y, artwork_y + 1e-9)
            self.assertGreaterEqual(
                square.x + square.width + 1e-9, artwork_x + artwork_width
            )
            self.assertGreaterEqual(
                square.y + square.height + 1e-9, artwork_y + artwork_height
            )

    def test_oversized_artwork_is_centered_but_not_exportable(self) -> None:
        detection = Detection.from_pixel_center(
            1,
            self.mapper.inches_to_pixel(12.0, 10.0),
            self.mapper,
            bounding_box_px=(450, 400, 300, 200),  # 6 x 4 inches
        )

        _moved_ids, problem_ids = center_cuts_on_visual_anchors(
            [detection], self.mapper
        )

        self.assertEqual(problem_ids, [1])
        self.assertEqual(detection.center_inches, (12.0, 10.0))
        self.assertFalse(detection.contains_artwork(self.mapper))
        self.assertFalse(detection.valid_cut)
        self.assertFalse(detection.exportable)


if __name__ == "__main__":
    unittest.main()
