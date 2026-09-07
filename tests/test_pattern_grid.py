from dataclasses import replace
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.detector import MotifDetector, DetectorSettings
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid
from app.imaging.pattern_grid import infer_repeated_artwork
from tests.test_visual_grid import printed_fabric


TRANSPORT_FIXTURE = Path(__file__).parent / 'fixtures' / 'transport_camera.png'


class PatternGridTests(unittest.TestCase):
    def test_original_photo_preserves_19_complete_illustrations(self):
        image = cv2.imread(str(TRANSPORT_FIXTURE))
        result = MotifDetector().detect_with_layout(image, DetectorSettings())
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (5, 4))
        self.assertEqual(result.panel_grid.source, 'pattern')
        self.assertGreaterEqual(result.panel_grid.confidence, .78)
        self.assertEqual(len(result.candidates), 19)
        # The giraffe is one drawing spanning two rows, not two illustrations.
        giraffes = [c for c in result.candidates if 1160 < c.center_px[0] < 1340
                    and 360 < c.center_px[1] < 720]
        self.assertEqual(len(giraffes), 1)
        self.assertGreater(giraffes[0].bounding_box_px[3], 300)
        observations = [LayoutObservation(i, c.center_px, c.bounding_box_px)
                        for i, c in enumerate(result.candidates)]
        layout = layout_from_panel_grid(observations, result.panel_grid)
        self.assertTrue(all(m.status == 'matched' for m in layout.matches))
        self.assertEqual(len({(m.column, m.row) for m in layout.matches}), 19)
        self.assertEqual(sum(bool(m.review_reason) for m in layout.matches), 1)
        self.assertEqual([(m.column, m.row, m.review_state) for m in layout.missing],
                         [(4, 2, 'pending')])
        # Even artificially high structural confidence must not propose a second giraffe cut.
        certain = layout_from_panel_grid(observations, replace(result.panel_grid, confidence=.98))
        self.assertEqual(certain.missing[0].review_state, 'pending')
        self.assertIn('Covered', certain.missing[0].reason)

    def test_different_counts_without_visible_panels(self):
        for columns, rows in [(3, 2), (4, 5), (7, 3), (2, 7), (8, 6)]:
            with self.subTest(columns=columns, rows=rows):
                result = infer_repeated_artwork(printed_fabric(columns, rows, panels=False))
                self.assertIsNotNone(result)
                self.assertEqual((result.grid.columns, result.grid.rows), (columns, rows))
                self.assertEqual(len(result.regions), columns * rows)

    def test_resize_and_blank_cell_without_assumed_detection(self):
        image = cv2.imread(str(TRANSPORT_FIXTURE))
        smaller = infer_repeated_artwork(cv2.resize(image, None, fx=.65, fy=.65), minimum_area_px=211)
        self.assertIsNotNone(smaller)
        self.assertEqual((smaller.grid.columns, smaller.grid.rows), (5, 4))
        self.assertEqual(len(smaller.regions), 19)
        result = infer_repeated_artwork(printed_fabric(5, 4, panels=False, missing=((2, 2),)))
        self.assertEqual(len(result.regions), 19)
        self.assertGreaterEqual(result.grid.confidence, .86)

    def test_single_outer_row_anchor_extends_continuous_background_grid(self):
        missing = tuple((column, 3) for column in range(6) if column != 2)
        image = printed_fabric(6, 4, panels=False, missing=missing)
        # A thin connected extension mimics smoke, a branch, or a long tail:
        # it shifts the full bounding box without shifting the visual core.
        cv2.line(image, (325, 435), (385, 435), (55, 87, 120), 6)
        result = infer_repeated_artwork(
            image,
            minimum_area_px=150,
        )

        self.assertIsNotNone(result)
        self.assertEqual((result.grid.columns, result.grid.rows), (6, 4))
        self.assertEqual(len(result.regions), 19)
        self.assertGreaterEqual(result.grid.confidence, .78)

    def test_blank_and_irregular_images_do_not_authorize_a_grid(self):
        self.assertIsNone(infer_repeated_artwork(np.full((600, 900, 3), 235, np.uint8)))
        image = np.full((700, 900, 3), 235, np.uint8)
        rng = np.random.default_rng(91)
        for x, y in rng.integers((60, 60), (840, 640), size=(20, 2)):
            cv2.ellipse(image, (int(x), int(y)), (20, 25), 0, 0, 360, (70, 95, 130), -1)
        self.assertIsNone(infer_repeated_artwork(image))

    def test_manual_guides_clear_the_old_affine_geometry(self):
        grid = infer_repeated_artwork(printed_fabric(4, 3, panels=False)).grid
        self.assertIsNotNone(grid.lattice)
        self.assertIsNone(grid.move_line('x', 1, grid.x_lines_px[1]+5).lattice)
        self.assertIsNone(grid.distribute('y').lattice)
        self.assertIsNone(grid.with_dimensions(540, 430, 3, 3).lattice)
