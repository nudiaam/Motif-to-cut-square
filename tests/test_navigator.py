"""Navigator panel: overview map, visible-area box and zoom controls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.navigator import scale_to_slider, slider_to_scale


class NavigatorTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.window = MainWindow()
        self.addCleanup(self.window.close)
        self.window.resize(1400, 800)
        self.window.show()
        self.window._load_image(np.full((600, 900, 3), 200, np.uint8), 'navigator')
        self.app.processEvents()
        self.canvas = self.window.canvas
        self.nav = self.window.navigator

    def visible(self):
        return self.canvas.visible_bed_rect_inches()

    def test_slider_mapping_round_trips_across_the_zoom_range(self):
        for scale in (0.25, 0.5, 1.0, 2.0, 5.0, 12.0):
            self.assertAlmostEqual(slider_to_scale(scale_to_slider(scale)), scale, delta=scale * 0.01)

    def test_fit_view_shows_the_whole_bed_and_panel_starts_collapsed(self):
        self.assertFalse(self.nav.expanded)
        x, y, w, h = self.visible()
        width, height = self.canvas.bed_size_inches()
        self.assertAlmostEqual(x, 0, places=6)
        self.assertAlmostEqual(y, 0, places=6)
        self.assertAlmostEqual(w, width, places=6)
        self.assertAlmostEqual(h, height, places=6)

    def test_zooming_in_opens_the_navigator_and_tracks_the_visible_area(self):
        self.canvas.set_view_scale(4.0)
        self.app.processEvents()
        self.assertTrue(self.nav.expanded)
        self.assertEqual(self.nav.percent_label.text(), '400%')
        self.assertEqual(self.nav.slider.value(), scale_to_slider(4.0))
        _x, _y, w, h = self.visible()
        width, height = self.canvas.bed_size_inches()
        self.assertLess(w, width / 2)
        self.assertLess(h, height / 2)
        box = self.nav.view.view_rect()
        target = self.nav.view.bed_target()
        self.assertTrue(target.contains(box))
        self.assertAlmostEqual(box.width() / target.width(), w / width, places=3)

    def test_clicking_and_dragging_the_map_moves_the_view_there(self):
        self.canvas.set_view_scale(4.0)
        self.app.processEvents()
        view = self.nav.view
        target = view.bed_target()
        width, height = self.canvas.bed_size_inches()
        for index, (fx, fy) in enumerate(((0.25, 0.3), (0.7, 0.6))):
            point = QPointF(target.left() + fx * target.width(), target.top() + fy * target.height())
            if index == 0:
                QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=point.toPoint())
            else:
                QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=target.center().toPoint())
                QTest.mouseMove(view, point.toPoint())
                QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=point.toPoint())
            self.app.processEvents()
            x, y, w, h = self.visible()
            self.assertAlmostEqual((x + w / 2) / width, fx, delta=0.02)
            self.assertAlmostEqual((y + h / 2) / height, fy, delta=0.02)

    def test_slider_buttons_and_fit_change_the_canvas_zoom(self):
        self.nav.set_expanded(True)
        self.nav.slider.setValue(scale_to_slider(3.0))
        self.assertAlmostEqual(self.canvas.view_scale, 3.0, delta=0.03)
        before = self.canvas.view_scale
        self.nav.zoom_in_button.click()
        self.assertGreater(self.canvas.view_scale, before)
        self.nav.zoom_out_button.click()
        self.nav.zoom_out_button.click()
        self.assertLess(self.canvas.view_scale, before)
        self.nav.fit_button.click()
        self.assertEqual(self.canvas.view_scale, 1.0)

    def test_collapsing_while_zoomed_is_respected(self):
        self.canvas.set_view_scale(3.0)
        self.app.processEvents()
        self.assertTrue(self.nav.expanded)
        self.nav.set_expanded(False)
        self.canvas.set_view_scale(5.0)
        self.app.processEvents()
        self.assertFalse(self.nav.expanded)

    def test_expanded_navigator_settles_without_continuous_canvas_repaints(self):
        from unittest.mock import patch
        self.canvas.set_view_scale(3.0)
        QTest.qWait(100)
        with patch.object(self.canvas, '_paint_detections',
                          wraps=self.canvas._paint_detections) as paint:
            QTest.qWait(150)
            self.assertLessEqual(paint.call_count, 2)

    def test_navigating_keeps_cut_positions_and_serialized_svg_unchanged(self):
        from xml.etree.ElementTree import tostring
        self.window.add_center(450, 300)
        def svg():
            return tostring(self.window.svg_exporter.build_tree(
                self.window.mapper, self.window.detections).getroot())
        original = svg()
        self.canvas.set_view_scale(4.0)
        self.canvas.center_view_on_bed_inches(12, 10)
        self.window.resize(1500, 900)
        self.app.processEvents()
        self.assertEqual(svg(), original)
        self.nav.fit_button.click()
        self.assertEqual(svg(), original)


if __name__ == '__main__':
    unittest.main()
