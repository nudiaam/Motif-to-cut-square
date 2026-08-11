from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSpinBox  # noqa: E402

from app.ui.help_widgets import DelayedHelpToolBar, InfoButton  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_demo_detect_verify_and_manual_editing(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        window.detect_motifs()
        self.assertGreaterEqual(len(window.detections), 8)
        self.assertLessEqual(len(window.detections), 12)

        window.verify_export()
        self.assertIn("Maximum round-trip error", window.panel.verification_label.text())

        first_id = window.detections[0].id
        window.move_detection(first_id, 0.0, 0.0)
        self.assertFalse(window.detections[0].valid_cut)

        previous_count = len(window.detections)
        assert window.mapper is not None
        safe_center = window.mapper.inches_to_pixel(18.0, 12.0)
        window.add_center(*safe_center)
        self.assertEqual(len(window.detections), previous_count + 1)
        self.assertTrue(window._find_detection(window.selected_id).valid_cut)  # type: ignore[arg-type, union-attr]

        window.delete_selected()
        self.assertEqual(len(window.detections), previous_count)
        window.close()

    def test_contextual_help_is_registered(self) -> None:
        window = MainWindow()
        window.resize(1280, 800)
        window.show()
        self.application.processEvents()
        info_buttons = window.panel.findChildren(InfoButton)
        self.assertEqual(len(info_buttons), 21)
        self.assertTrue(all(button.help_text.strip() for button in info_buttons))

        toolbar = window.findChild(DelayedHelpToolBar, "mainToolbar")
        self.assertIsNotNone(toolbar)
        assert toolbar is not None
        self.assertEqual(toolbar.HOVER_DELAY_MS, 1300)
        self.assertEqual(len(toolbar._help_by_widget), 10)
        self.assertTrue(all(text.strip() for text in toolbar._help_by_widget.values()))
        self.assertEqual(window.canvas.toolTip(), "")
        self.assertFalse(window.navigation_details.isVisible())
        canvas_geometry = window.canvas.geometry()
        window.navigation_toggle.setChecked(True)
        self.application.processEvents()
        self.assertFalse(window.navigation_details.isHidden())
        self.assertEqual(window.canvas.geometry(), canvas_geometry)
        self.assertLess(window.navigation_help.width(), window.canvas.width())
        window.navigation_toggle.setChecked(False)
        self.assertTrue(window.navigation_details.isHidden())
        window.close()

    def test_working_units_cut_size_and_physical_minimum_area(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.mapper is not None

        window.panel.minimum_area_unit_combo.setCurrentIndex(1)
        window.panel.minimum_area_spin.setValue(1.0)
        settings = window.panel.detector_settings(window.mapper)
        self.assertEqual(
            settings.minimum_area_px,
            round(window.mapper.px_per_inch_x * window.mapper.px_per_inch_y),
        )

        millimetres_index = window.panel.working_unit_combo.findData("mm")
        window.panel.working_unit_combo.setCurrentIndex(millimetres_index)
        self.assertEqual(window.working_unit.value, "mm")
        self.assertAlmostEqual(window.panel.cut_width_spin.value(), 127.0, places=3)

        window.panel.keep_square_checkbox.setChecked(False)
        window.panel.cut_width_spin.setValue(100.0)
        window.panel.cut_height_spin.setValue(80.0)
        self.assertAlmostEqual(window.cut_width_inches, 100.0 / 25.4, places=9)
        self.assertAlmostEqual(window.cut_height_inches, 80.0 / 25.4, places=9)
        window.close()

    def test_square_size_can_be_edited_from_either_dimension(self) -> None:
        window = MainWindow()
        self.assertTrue(window.panel.keep_square_checkbox.isChecked())
        self.assertTrue(window.panel.cut_width_spin.isEnabled())
        self.assertTrue(window.panel.cut_height_spin.isEnabled())
        window.panel.cut_width_spin.setValue(4.0)
        self.assertEqual(window.panel.cut_height_spin.value(), 4.0)
        window.panel.cut_height_spin.setValue(6.0)
        self.assertEqual(window.panel.cut_width_spin.value(), 6.0)
        self.assertEqual(window.cut_width_inches, 6.0)
        self.assertEqual(window.cut_height_inches, 6.0)
        window.close()

    def test_panel_width_and_spin_buttons_stay_visible_after_size_change(self) -> None:
        window = MainWindow()
        window.resize(1280, 800)
        window.show()
        window.load_demo_image()
        self.application.processEvents()
        initial_width = window.panel.width()

        window.panel.cut_width_spin.setValue(6.0)
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(12.0, 10.0))
        self.application.processEvents()

        self.assertEqual(initial_width, 420)
        self.assertEqual(window.panel.width(), initial_width)
        self.assertIn("COLLISION", window.panel.detection_list.item(0).text())
        for spin in (window.panel.cut_width_spin, window.panel.cut_height_spin):
            option = QStyleOptionSpinBox()
            spin.initStyleOption(option)
            for control in (
                QStyle.SubControl.SC_SpinBoxUp,
                QStyle.SubControl.SC_SpinBoxDown,
            ):
                button = spin.style().subControlRect(
                    QStyle.ComplexControl.CC_SpinBox,
                    option,
                    control,
                    spin,
                )
                self.assertGreater(button.width(), 0)
                self.assertGreaterEqual(button.left(), 0)
                self.assertLess(button.right(), spin.width())
        window.close()

    def test_cut_collisions_update_status_and_counts(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.mapper is not None
        first = window.mapper.inches_to_pixel(10.0, 10.0)
        second = window.mapper.inches_to_pixel(12.0, 10.0)
        window.add_center(*first)
        window.add_center(*second)
        self.assertTrue(all(item.overlaps_cut for item in window.detections))
        self.assertTrue(window.fix_overlaps_action.isVisible())
        self.assertEqual(window.panel.valid_value_label.text(), "0")
        self.assertEqual(window.panel.invalid_value_label.text(), "2")
        self.assertEqual(window.panel.disabled_value_label.text(), "0")
        window.set_detection_enabled(window.detections[1].id, False)
        self.assertFalse(window.detections[0].overlaps_cut)
        self.assertEqual(window.panel.valid_value_label.text(), "1")
        self.assertEqual(window.panel.invalid_value_label.text(), "0")
        self.assertEqual(window.panel.disabled_value_label.text(), "1")
        window.close()

    def test_fix_overlaps_action_preserves_manual_repositioning(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(12.0, 10.0))
        original_first = window.detections[0].center_inches

        window.fix_overlaps()

        self.assertFalse(any(item.overlaps_cut for item in window.detections))
        self.assertNotEqual(window.detections[0].center_inches, original_first)
        self.assertFalse(window.fix_overlaps_action.isVisible())
        moved = window.detections[1]
        manual_position = window.mapper.inches_to_pixel(22.0, 15.0)
        window.move_detection(moved.id, *manual_position)
        self.assertAlmostEqual(moved.center_inches[0], 22.0)
        self.assertAlmostEqual(moved.center_inches[1], 15.0)
        window.close()

    def test_detection_controls_reset_on_double_click(self) -> None:
        window = MainWindow()
        window.show()
        self.application.processEvents()
        window.panel.sensitivity_slider.setValue(10)
        window.panel.cleanup_slider.setValue(90)
        window.panel.merge_distance_spin.setValue(2.0)
        window.panel.minimum_area_spin.setValue(2000)
        QTest.mouseDClick(window.panel.sensitivity_slider, Qt.MouseButton.LeftButton)
        QTest.mouseDClick(window.panel.cleanup_slider, Qt.MouseButton.LeftButton)
        QTest.mouseDClick(window.panel.merge_distance_spin.lineEdit(), Qt.MouseButton.LeftButton)
        QTest.mouseDClick(window.panel.minimum_area_spin.lineEdit(), Qt.MouseButton.LeftButton)
        self.assertEqual(window.panel.sensitivity_slider.value(), 65)
        self.assertEqual(window.panel.cleanup_slider.value(), 25)
        self.assertAlmostEqual(window.panel.merge_distance_spin.value(), 0.35)
        self.assertEqual(window.panel.minimum_area_spin.value(), 500)
        window.close()

    def test_image_placement_is_proportional_and_updates_detection_geometry(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        window.detect_motifs()
        assert window.mapper is not None
        first = window.detections[0]
        original_center = first.center_inches
        window.change_image_placement(3.0, 2.0, 30.0, 20.0)
        self.assertEqual(window.mapper.image_bed_rect_inches, (3.0, 2.0, 30.0, 20.0))
        self.assertAlmostEqual(
            window.mapper.image_width_in / window.mapper.image_height_in, 1.5
        )
        self.assertNotEqual(first.center_inches, original_center)
        window.panel.set_image_locked(False)
        self.assertFalse(window.canvas._image_locked)
        window.panel.set_image_locked(True)
        self.assertTrue(window.canvas._image_locked)
        window.close()

    def test_unlocked_image_can_be_moved_and_scaled_from_canvas(self) -> None:
        window = MainWindow()
        window.resize(1280, 800)
        window.show()
        window.load_demo_image()
        window.change_image_placement(3.0, 2.0, 30.0, 20.0)
        window.panel.set_image_locked(False)
        self.application.processEvents()
        assert window.mapper is not None

        image_rect = window.canvas._image_rect_widget()
        start_center = image_rect.center().toPoint()
        QTest.mousePress(window.canvas, Qt.MouseButton.LeftButton, pos=start_center)
        QTest.mouseMove(window.canvas, start_center + QPoint(12, 8))
        QTest.mouseRelease(
            window.canvas, Qt.MouseButton.LeftButton, pos=start_center + QPoint(12, 8)
        )
        moved_rect = window.mapper.image_bed_rect_inches
        self.assertGreater(moved_rect[0], 3.0)
        self.assertGreater(moved_rect[1], 2.0)

        handle = window.canvas._image_rect_widget().bottomRight().toPoint()
        QTest.mousePress(window.canvas, Qt.MouseButton.LeftButton, pos=handle)
        QTest.mouseMove(window.canvas, handle - QPoint(24, 16))
        QTest.mouseRelease(
            window.canvas, Qt.MouseButton.LeftButton, pos=handle - QPoint(24, 16)
        )
        scaled_rect = window.mapper.image_bed_rect_inches
        self.assertLess(scaled_rect[2], moved_rect[2])
        self.assertAlmostEqual(scaled_rect[2] / scaled_rect[3], 1.5, places=9)
        window.close()

    def test_canvas_zoom_keeps_anchor_and_space_drag_pans(self) -> None:
        window = MainWindow()
        window.resize(1280, 800)
        window.show()
        window.load_demo_image()
        self.application.processEvents()
        canvas = window.canvas

        anchor = QPointF(canvas.width() * 0.42, canvas.height() * 0.38)
        physical_before = canvas._widget_to_bed_inches(anchor)
        fitted_width = canvas._bed_rect().width()
        canvas.zoom_in(anchor)
        physical_after = canvas._widget_to_bed_inches(anchor)
        self.assertGreater(canvas._bed_rect().width(), fitted_width)
        self.assertAlmostEqual(physical_before[0], physical_after[0], places=9)
        self.assertAlmostEqual(physical_before[1], physical_after[1], places=9)

        original_offset = QPointF(canvas._view_offset)
        start = canvas.rect().center()
        QTest.keyPress(canvas, Qt.Key.Key_Space)
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(canvas, start + QPoint(24, 17))
        QTest.mouseRelease(
            canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(24, 17)
        )
        QTest.keyRelease(canvas, Qt.Key.Key_Space)
        self.assertNotEqual(canvas._view_offset, original_offset)

        QTest.keyClick(canvas, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(canvas.view_scale, 1.0)
        self.assertEqual(canvas._view_offset, QPointF())

        QTest.keyClick(canvas, Qt.Key.Key_Z)
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=start)
        self.assertGreater(canvas.view_scale, 1.0)
        QTest.mouseClick(
            canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.AltModifier,
            pos=start,
        )
        self.assertAlmostEqual(canvas.view_scale, 1.0)
        QTest.keyClick(canvas, Qt.Key.Key_V)
        self.assertFalse(canvas._zoom_tool_active)
        window.close()


if __name__ == "__main__":
    unittest.main()
