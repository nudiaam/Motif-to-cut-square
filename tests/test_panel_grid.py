from __future__ import annotations

import unittest

from app.imaging.detector import MotifDetector
from app.imaging.panel_grid import PanelGrid
from tests.test_patterned_quilt_acceptance import _patterned_quilt, _settings


class PanelGridTests(unittest.TestCase):
    def test_regular_grid_can_be_edited_and_redistributed(self) -> None:
        grid = PanelGrid.regular(900, 600, columns=6, rows=4)

        moved = grid.move_line("x", 2, 325.0)
        self.assertEqual(moved.x_lines_px[2], 325.0)
        self.assertEqual(moved.source, "manual")

        distributed = moved.distribute("x")
        self.assertEqual(
            distributed.x_lines_px,
            (0.0, 150.0, 300.0, 450.0, 600.0, 750.0, 900.0),
        )
        self.assertEqual(distributed.y_lines_px, grid.y_lines_px)

    def test_dimensions_preserve_manually_adjusted_outer_bounds(self) -> None:
        grid = PanelGrid.regular(
            1000,
            700,
            columns=5,
            rows=4,
            bounds_px=(40.0, 30.0, 960.0, 670.0),
        )

        resized = grid.with_dimensions(1000, 700, columns=8, rows=6)

        self.assertEqual(resized.bounds_px, grid.bounds_px)
        self.assertEqual((resized.columns, resized.rows), (8, 6))

    def test_patterned_quilt_reports_grid_and_one_candidate_per_panel(self) -> None:
        image = _patterned_quilt()
        result = MotifDetector().detect_with_layout(image, _settings(image))

        self.assertIsNotNone(result.panel_grid)
        assert result.panel_grid is not None
        self.assertEqual(
            (result.panel_grid.columns, result.panel_grid.rows), (6, 4)
        )
        self.assertEqual(len(result.candidates), 24)
        occupied = {
            (
                int(candidate.center_px[0] * 6 / image.shape[1]),
                int(candidate.center_px[1] * 4 / image.shape[0]),
            )
            for candidate in result.candidates
        }
        self.assertEqual(len(occupied), 24)


if __name__ == "__main__":
    unittest.main()
