"""Page and outline regressions for the Epilog Dashboard print path."""
import os
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from app.export.epilog_dashboard import _outline, _paper_settings, _render_page, send_to_dashboard
from app.export.svg_exporter import SVGExporter, SVG_NAMESPACE
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_square import CutSquare
from app.models import Detection
from app.ui.main_window import MainWindow


class EpilogDashboardTests(TestCase):
    def test_custom_paper_dimensions_keep_landscape_axes(self):
        self.assertEqual(_paper_settings(36, 24), (2, 9144, 6096))
        self.assertEqual(_paper_settings(12, 18), (1, 4572, 3048))

    def test_wrong_page_size_or_orientation_is_rejected_before_starting_a_job(self):
        for width, height in ((100, 100), (24, 36)):
            with self.subTest(width=width, height=height), patch("app.export.epilog_dashboard._api") as api:
                caps = {88: 600, 90: 600, 110: width * 600, 111: height * 600}
                api.return_value = lambda _dc, index: caps[index]
                with self.assertRaisesRegex(OSError, f"{width} × {height}"):
                    _render_page(None, None, "Test", 36, 24, [CutSquare(1, 1, 2, 2)])
                api.assert_called_once()
                self.assertEqual(api.call_args.args[1], "GetDeviceCaps")

    def test_conversion_preserves_physical_origin_and_compensates_driver_margins(self):
        outline = _outline(CutSquare(33, 21, 2, 2), 600, 300, 15, 10)
        self.assertEqual(outline, (
            (19785, 6290), (20985, 6290), (20985, 6890), (19785, 6890), (19785, 6290),
        ))

    def test_invalid_or_empty_jobs_never_reach_the_queue(self):
        for cuts in ([], [CutSquare(35, 1, 2, 2)], [CutSquare(1, 1, -1, 2)]):
            with self.subTest(cuts=cuts), patch("app.export.epilog_dashboard._require_local_dashboard_queue") as queue:
                with self.assertRaises(ValueError):
                    send_to_dashboard("Test", 36, 24, cuts)
                queue.assert_not_called()

    def test_step_four_sends_the_same_checked_rectangles_as_the_svg(self):
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.addCleanup(window.close)
        window.mapper = CoordinateMapper(2340, 1560)
        window.detections = [
            Detection.from_pixel_center(1, (390, 390), window.mapper),
            Detection.from_pixel_center(2, (900, 820), window.mapper, enabled=False),
            Detection.from_pixel_center(3, (1920, 1200), window.mapper),
            Detection.from_pixel_center(4, (60, 110), window.mapper),
        ]
        with patch("app.ui.main_window.send_to_dashboard") as send, patch.object(
            window, "_confirm_output", return_value=True
        ) as confirm:
            window.open_in_epilog_dashboard()
            send.assert_not_called()
            window._detection_review_complete = True
            window.show_preflight()
            window.workflow_export_button.click()
            confirm.assert_called_once()
            _, width, height, actual = send.call_args.args
        self.assertEqual(window._workflow_phase, "export")
        self.assertEqual((width, height), (36, 24))
        svg = SVGExporter().build_tree(window.mapper, window.detections)
        expected = [
            tuple(float(rect.get(key)) for key in ("x", "y", "width", "height"))
            for rect in svg.findall(f"{{{SVG_NAMESPACE}}}rect")
        ]
        self.assertEqual(len(expected), 2)
        for cut, coordinates in zip(actual, expected, strict=True):
            for value, wanted in zip(cut.as_tuple(), coordinates, strict=True):
                self.assertAlmostEqual(value, wanted)

    def test_driver_error_leaves_review_and_svg_fallback_available(self):
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.addCleanup(window.close)
        window.mapper = CoordinateMapper(2340, 1560)
        window.detections = [Detection.from_pixel_center(1, (390, 390), window.mapper)]
        window._detection_review_complete = True
        window.show_preflight()
        error = "Install the Epilog Software Suite to add the Epilog Engraver queue."
        with (
            patch("app.ui.main_window.send_to_dashboard", side_effect=OSError(error)),
            patch.object(QMessageBox, "critical") as critical,
        ):
            window.workflow_export_button.click()
        critical.assert_called_once_with(window, "Could not open Epilog Dashboard preview", error)
        self.assertEqual(window._workflow_phase, "review")
        self.assertTrue(window.panel.save_svg_button.isEnabled())
