from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid
from app.imaging.visual_grid import infer_printed_panel_grid


CAMERA_FIXTURE = Path(__file__).parent / "fixtures" / "pastel_panels_camera.png"


def printed_fabric(columns: int, rows: int, *, missing=(), panels=True) -> np.ndarray:
    """Different counts, blank margins, bed surround and off-centre artwork."""
    step = 110
    image = np.full((rows * step + 100, columns * step + 100, 3), 24, np.uint8)
    image[20:-20, 20:-20] = (231, 239, 241)
    for row in range(rows):
        for col in range(columns):
            x, y = 50 + col * step, 50 + row * step
            if panels:
                color = [(204, 215, 230), (207, 226, 216), (229, 217, 212)][(col + row) % 3]
                cv2.rectangle(image, (x + 10, y + 10), (x + 100, y + 100), color, -1)
            if (col, row) not in missing:
                cv2.ellipse(image, (x + 55 + (col % 3 - 1) * 5, y + 55),
                            (17, 24), 0, 0, 360, (55, 87, 120), -1)
    return image


class VisualGridTests(unittest.TestCase):
    def test_counts_are_inferred_without_parameters_and_margins_are_not_cells(self):
        for columns, rows in [(3, 2), (4, 5), (7, 3), (8, 6), (2, 7), (11, 3)]:
            with self.subTest(columns=columns, rows=rows):
                grid = infer_printed_panel_grid(printed_fabric(columns, rows))
                self.assertIsNotNone(grid)
                self.assertEqual((grid.columns, grid.rows), (columns, rows))
                self.assertGreater(grid.confidence, .86)
                np.testing.assert_allclose(grid.bounds_px,
                                           (50, 50, 50 + columns * 110, 50 + rows * 110), atol=2)

    def test_camera_photo_detects_grid_and_real_artwork_without_manual_setup(self):
        image = cv2.imread(str(CAMERA_FIXTURE))
        result = MotifDetector().detect_with_layout(image, DetectorSettings())
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 4))
        self.assertEqual(result.panel_grid.source, "visual")
        self.assertGreater(result.panel_grid.confidence, .9)
        self.assertEqual(len(result.candidates), 24)
        layout = layout_from_panel_grid([
            LayoutObservation(i, c.center_px) for i, c in enumerate(result.candidates)
        ], result.panel_grid)
        self.assertTrue(all(m.status == "matched" for m in layout.matches))
        self.assertFalse(layout.missing)
        # These fixture-specific expected regions are a regression oracle, never
        # input to the detector. No laser-bed feature can count as an illustration.
        for match in layout.matches:
            cx, cy = match.observed_px
            self.assertLess(abs(cx - (230 + 200 * match.column)), 60)
            self.assertLess(abs(cy - (240 + 210 * match.row)), 60)

    def test_uniform_fabric_motifs_do_not_count_as_printed_panel_bands(self):
        self.assertIsNone(infer_printed_panel_grid(printed_fabric(5, 4, panels=False)))
        self.assertIsNone(infer_printed_panel_grid(np.full((600, 900, 3), 220, np.uint8)))

    def test_empty_cell_remains_a_proposal_not_a_detected_cut(self):
        result = MotifDetector().detect_with_layout(
            printed_fabric(5, 4, missing=((2, 2),)), DetectorSettings(minimum_area_px=150))
        self.assertEqual(len(result.candidates), 19)
        observations = [LayoutObservation(i, c.center_px) for i, c in enumerate(result.candidates)]
        layout = layout_from_panel_grid(observations, result.panel_grid)
        self.assertEqual([(m.column, m.row, m.review_state) for m in layout.missing],
                         [(2, 2, "proposed")])
        uncertain = layout_from_panel_grid(observations, replace(result.panel_grid, confidence=.83))
        self.assertEqual(uncertain.missing[0].review_state, "pending")

    def test_artwork_assignment_never_refits_visual_centres_and_marks_outliers(self):
        grid = infer_printed_panel_grid(printed_fabric(3, 2))
        observations = [LayoutObservation(1, (105., 105.)),
                        LayoutObservation(2, (135., 138.)),  # duplicate of first cell
                        LayoutObservation(3, (410., 30.)),  # bed, outside the panel
                        LayoutObservation(4, (235., 210.))]  # off-centre in row 2
        layout = layout_from_panel_grid(observations, grid)
        self.assertEqual([m.status for m in layout.matches],
                         ["matched", "duplicate", "outlier", "matched"])
        np.testing.assert_allclose(layout.position(1, 1), (215.5, 215.5), atol=1)
        without_artwork = layout_from_panel_grid([], grid)
        self.assertEqual(layout.position(1, 1), without_artwork.position(1, 1))
        self.assertEqual(len(without_artwork.missing), 6)


if __name__ == "__main__":
    unittest.main()
