import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from app.geometry.coordinate_mapper import CoordinateMapper
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.models import Detection
from app.ui.main_window import MainWindow
from app.ui.cut_status import OVERLAP_COLOR, REVIEW_COLOR, cut_status_color


class DetectionDiagnosticsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()

    def test_report_available_before_acceptance_includes_failed_reference_and_settings(self):
        window = self.window
        window.load_demo_image()
        window.detector.bed_reference = np.zeros((100, 100, 3), np.uint8)
        window.detect_motifs()
        self.assertIn("not applied", window.panel.detection_reference_label.text())
        self.assertTrue(window.panel.detection_report_button.isEnabled())
        self.assertFalse(window._detection_review_complete)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch("app.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(path), "")):
                window.save_detection_report()
            report = json.loads(path.read_text(encoding="utf-8"))
        run = report["detection_run"]
        self.assertFalse(run["reference_applied"])
        self.assertIn("framing", run["reference_status"])
        self.assertEqual(run["settings"]["sensitivity"], 65)
        self.assertTrue(run["detector_revision"])
        self.assertEqual(len(report["detections"]), len(window.detections))
        self.assertEqual(run["grid"]["source"], window.detection_panel_grid.source)

    def test_diagnostics_follow_undo_and_clear_for_new_image(self):
        window = self.window
        window.load_demo_image()
        window.detect_motifs()
        first = window.detection_diagnostics.copy()
        window.panel.sensitivity_slider.setValue(55)
        window.detect_motifs(replace_confirmed=True)
        self.assertEqual(window.detection_diagnostics["settings"]["sensitivity"], 55)
        window.undo()
        self.assertEqual(window.detection_diagnostics, first)
        window._load_image(np.full((400, 600, 3), 230, np.uint8), "new image")
        self.assertEqual(window.detection_diagnostics, {})
        self.assertTrue(window.panel.detection_reference_label.isHidden())
        self.assertFalse(window.panel.detection_report_button.isEnabled())

    def test_manual_redetection_does_not_claim_a_reference_was_used(self):
        window = self.window
        window.load_demo_image()
        window.detect_motifs()
        window.panel_grid = window.panel_grid.with_dimensions(1350, 900, 4, 3)
        window.detect_in_current_grid()
        self.assertFalse(window.detection_diagnostics["reference_applied"])
        self.assertIn("confirmed panel guides", window.detection_diagnostics["reference_status"])
        self.assertEqual(window.detection_diagnostics["grid"]["source"], "manual")

    def test_clipped_grid_artwork_is_a_warning_even_when_cut_is_inside_bed(self):
        window = self.window
        mapper = CoordinateMapper(600, 400)
        detection = Detection.from_pixel_center(1, (300, 200), mapper,
                                               bounding_box_px=(250, 170, 100, 60),
                                               cut_width_inches=1, cut_height_inches=1)
        detection.place_on_grid((300, 200), (0, 0), mapper)
        self.assertTrue(detection.valid_cut)
        self.assertTrue(detection.artwork_clipped)
        window.panel.set_image_info(mapper)
        window.panel.set_detections([detection], set())
        self.assertIn("CLIPPED", window.panel.detection_list.item(0).text())
        self.assertEqual(window.panel.valid_value_label.text(), "0")
        self.assertEqual(window.panel.invalid_value_label.text(), "1")
        window.mapper = mapper
        window.detections = [detection]
        window._detection_review_complete = True
        window.show_preflight()
        self.assertIn("WITH WARNINGS", window.panel.verification_label.text())

    def test_duplicate_warning_is_visible_before_detection_confirmation(self):
        window = self.window
        mapper = CoordinateMapper(600, 400)
        grid = PanelGrid.regular(600, 400, 4, 4, confidence=.95, source="visual")
        detections = [Detection.from_pixel_center(i, (x, 50), mapper,
                                                  cut_width_inches=.2, cut_height_inches=.2)
                      for i, x in enumerate((30, 120), start=1)]
        layout = layout_from_panel_grid([LayoutObservation(d.id, d.center_px) for d in detections], grid)
        window.panel.set_phase("detect")
        window.panel.set_image_info(mapper)
        window.panel.set_logical_layout(layout)
        window.panel.set_detections(detections, set())
        self.assertIn("outliers/duplicates need review", window.panel.layout_status_label.text())
        texts = [window.panel.detection_list.item(i).text() for i in range(2)]
        self.assertTrue(any("REVIEW" in text and "duplicate" in text for text in texts))
        self.assertEqual(window.panel.invalid_value_label.text(), "1")

    def test_extent_uncertainty_is_not_ready_even_when_detected_box_fits(self):
        window = self.window
        window._load_image(np.full((400, 600, 3), 230, np.uint8), "extent review test")
        mapper = CoordinateMapper(600, 400)
        detection = Detection.from_pixel_center(1, (300, 200), mapper,
            bounding_box_px=(280, 180, 40, 40), cut_width_inches=5, cut_height_inches=5,
            review_reasons=("Image evidence continues beyond the detected artwork",))
        self.assertTrue(detection.contains_artwork(mapper))
        self.assertTrue(detection.exportable)
        window.mapper = mapper
        window.detections = [detection]
        window.panel.set_image_info(mapper)
        window.panel.set_detections([detection], {1}, 1)
        window.detection_diagnostics = {"detector_revision": "controlled extent review test"}
        self.assertIn("REVIEW", window.panel.detection_list.item(0).text())
        self.assertEqual(window.panel.valid_value_label.text(), "0")
        self.assertIn("Review required", window.panel.detail_label.text())
        self.assertEqual(window._cut_warning_count(), 1)
        window._detection_review_complete = True
        window.show_preflight()
        self.assertIn("Uncertain artwork extent: 1", window.panel.verification_label.text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch("app.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(path), "")):
                window.save_detection_report()
            report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["detections"][0]["review_reasons"], list(detection.review_reasons))

    def test_artwork_review_and_overlap_have_distinct_consistent_colours(self):
        mapper = CoordinateMapper(600, 400)
        review = Detection.from_pixel_center(1, (160, 200), mapper,
            review_reasons=("Check full artwork",))
        overlap = Detection.from_pixel_center(2, (300, 200), mapper,
            review_reasons=("Check full artwork",))
        overlap.overlaps_cut = True
        self.window.panel.set_image_info(mapper)
        self.window.panel.set_detections([review, overlap], set())
        colours = [self.window.panel.detection_list.item(i).foreground().color().name()
                   for i in range(2)]
        self.assertEqual(colours, [REVIEW_COLOR, OVERLAP_COLOR])
        self.assertEqual(cut_status_color(review), colours[0])
        self.assertEqual(cut_status_color(overlap), colours[1])
        self.assertIn("REVIEW", self.window.panel.detection_list.item(0).text())
        self.assertIn("OVERLAP", self.window.panel.detection_list.item(1).text())
        self.assertIn("Check full artwork", self.window.panel.detection_list.item(1).toolTip())
        self.assertIn("Overlapping cuts", self.window.panel.cut_color_legend.text())


if __name__ == "__main__":
    unittest.main()
