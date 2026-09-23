"""Whole-image guidance, with AI-generated development fixtures and negatives."""
from dataclasses import replace
from pathlib import Path
import os
import unittest

import cv2
import numpy as np

from app.imaging.detector import MotifCandidate, MotifDetector, DetectorSettings
from app.imaging.grid_guidance import extend_visual_grid, preserve_spanning_artwork
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid


FIXTURES = Path(__file__).parent / "fixtures/generated"


def candidate(box):
    x, y, w, h = box
    return MotifCandidate((x+w/2, y+h/2), box, .8, int(w*h*.6))


class GridGuidanceTests(unittest.TestCase):
    def test_generated_panels_recover_each_occupied_cell(self):
        # Counts are expectations only, never passed to the detector. Mapping
        # each result to an independently inspected cell catches duplicate
        # detections even when the aggregate count happens to be correct.
        cases = (
            ("pastel_animals_6x4.png", (65, 65), (237, 224)),
            ("folk_floral_6x4.png", (70, 70), (230, 207)),
        )
        for name, origin, spacing in cases:
            with self.subTest(name=name):
                image = cv2.imread(str(FIXTURES / name))
                original = image.copy()
                detector = MotifDetector()
                result = detector.detect_with_layout(image, DetectorSettings())
                self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 4))
                self.assertEqual(len(result.candidates), 24)
                cells = [(int((c.center_px[0]-origin[0])/spacing[0]),
                          int((c.center_px[1]-origin[1])/spacing[1])) for c in result.candidates]
                self.assertEqual(set(cells), {(col, row) for row in range(4) for col in range(6)})
                self.assertTrue(any("Extended" in note for note in detector.last_diagnostics["grid_notes"]))
                np.testing.assert_array_equal(image, original)

    def test_generated_spanning_artwork_is_whole_and_does_not_occupy_twice(self):
        image = cv2.imread(str(FIXTURES / "transport_spanning_5x4.png"))
        result = MotifDetector().detect_with_layout(image, DetectorSettings())
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (5, 4))
        self.assertEqual(len(result.candidates), 19)
        giraffes = [c for c in result.candidates if c.bounding_box_px[3] > 300]
        self.assertEqual(len(giraffes), 1)
        x, y, w, h = giraffes[0].bounding_box_px
        self.assertLessEqual(y, 330)  # head and feet, not one half of the motif
        self.assertGreaterEqual(y+h, 675)
        observations = [LayoutObservation(i, c.center_px, c.bounding_box_px)
                        for i, c in enumerate(result.candidates)]
        layout = layout_from_panel_grid(observations, result.panel_grid)
        self.assertTrue(all(m.status == "matched" for m in layout.matches))
        self.assertEqual(len(layout.missing), 1)
        self.assertTrue(layout.missing[0].covered_by_artwork)

    def test_extension_requires_distinct_cells_and_stricter_image_evidence(self):
        grid = PanelGrid.regular(600, 500, 4, 3, bounds_px=(50, 50, 450, 350),
                                 confidence=.95, source="visual")
        one = candidate((65, 370, 60, 60))
        duplicate = candidate((70, 372, 60, 60))
        two = candidate((265, 370, 60, 60))
        for primary, strict in (([], []), ([one], [one]), ([one, duplicate], [one, duplicate]),
                                ([one, two], [])):
            with self.subTest(primary=len(primary), strict=len(strict)):
                self.assertEqual(extend_visual_grid(grid, primary, strict, (500, 600, 3), None), grid)
        extended = extend_visual_grid(grid, [one, two], [one, two], (500, 600, 3), None)
        self.assertEqual(extended.y_lines_px, (*grid.y_lines_px, 450))
        self.assertEqual(extended.x_lines_px, grid.x_lines_px)

    def test_extension_respects_fabric_bounds_and_manual_guides(self):
        grid = PanelGrid.regular(600, 500, 4, 3, bounds_px=(50, 50, 450, 350),
                                 confidence=.95, source="visual")
        items = [candidate((65, 370, 60, 60)), candidate((265, 370, 60, 60))]
        mask = np.zeros((500, 600), np.uint8)
        mask[50:350, 50:450] = 255
        self.assertEqual(extend_visual_grid(grid, items, items, (500, 600, 3), mask), grid)
        manual = replace(grid, source="manual")
        self.assertEqual(extend_visual_grid(manual, items, items, (500, 600, 3), None), manual)

    def test_neighbours_are_not_joined_without_an_unmerged_spanning_region(self):
        grid = PanelGrid.regular(400, 400, 4, 4, confidence=.95, source="visual")
        top, bottom = candidate((120, 20, 60, 65)), candidate((120, 115, 60, 65))
        merged = candidate((120, 20, 60, 160))
        result = preserve_spanning_artwork([top, bottom], [merged], [top, bottom], grid)
        self.assertEqual(result, [top, bottom])

    def test_wide_background_cluster_cannot_merge_four_cells(self):
        grid = PanelGrid.regular(400, 400, 4, 4, confidence=.95, source="visual")
        local = [candidate((x, y, 60, 65)) for y in (20, 115) for x in (20, 115)]
        cluster = candidate((20, 20, 160, 160))
        self.assertEqual(preserve_spanning_artwork(local, [cluster], [cluster], grid), local)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.models import Detection


class GuidedCutsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_generated_giraffe_stays_one_cut_after_confirmation_and_guided_redetection(self):
        window = MainWindow()
        try:
            window._load_image(cv2.imread(str(FIXTURES / "transport_spanning_5x4.png")), "Synthetic test")
            window.detect_motifs()
            self.assertEqual(len(window.detections), 19)
            self.assertFalse(any(d.inferred for d in window.detections))
            self.assertTrue(any(d.artwork_clipped for d in window.detections))
            self.assertTrue(any(m.review_reason for m in window.logical_layout.matches))
            window.confirm_grid()
            self.assertEqual(len(window.detections), 19)
            window.panel_grid = replace(window.panel_grid, source="manual", confidence=1.)
            window.detect_in_current_grid()
            self.assertEqual(len(window.detections), 19)
            self.assertFalse(any(d.inferred for d in window.detections))
        finally:
            window.close()

    def test_stale_automatic_cut_removed_but_explicit_manual_choice_preserved(self):
        window = MainWindow()
        try:
            window._load_image(cv2.imread(str(FIXTURES / "transport_spanning_5x4.png")), "Synthetic test")
            window.detect_motifs()
            gap = next(p for p in window.logical_layout.missing if p.covered_by_artwork)
            cell = gap.column, gap.row
            extra = Detection.from_pixel_center(99, gap.center_px, window.mapper)
            extra.inferred = True
            extra.place_on_grid(gap.center_px, cell, window.mapper)
            window.detections.append(extra)
            window._sync_automatic_grid_cuts()
            self.assertNotIn(extra, window.detections)
            extra.manual = True
            window.detections.append(extra)
            window._sync_automatic_grid_cuts()
            self.assertIn(extra, window.detections)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
