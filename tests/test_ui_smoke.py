from __future__ import annotations

import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QStyle, QStyleOptionSpinBox  # noqa: E402

from app.ui.help_widgets import DelayedHelpToolBar, InfoButton  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.imaging.panel_grid import PanelGrid  # noqa: E402
from tests.test_logical_layout import cut_fixture  # noqa: E402


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
        self.assertEqual(window._workflow_phase, "detect")
        self.assertFalse(window.workflow_review_button.isEnabled())
        window.panel.confirm_detection_button.click()
        self.application.processEvents()
        self.assertEqual(window._workflow_phase, "review")
        self.assertEqual(window.selected_ids, set())
        self.assertIsNone(window.selected_id)
        self.assertEqual(window.panel.detection_list.selectedItems(), [])

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

    def test_camera_patchwork_materializes_missing_grid_cells_without_extra_ui(self) -> None:
        import cv2
        from tests.test_camera_panel import PATCHWORK_FIXTURE
        window = MainWindow()
        try:
            image = cv2.imread(str(PATCHWORK_FIXTURE))
            window._load_image(image,'patchwork regression')
            mapper = window.mapper
            window.change_cut_size(4,4)
            window.detect_motifs()
            self.assertIs(window.mapper,mapper)
            np.testing.assert_array_equal(window.image_bgr,image)
            self.assertEqual((window.logical_layout.columns,window.logical_layout.rows),(6,4))
            self.assertEqual(len(window.detections),24)
            self.assertEqual(sum(d.inferred for d in window.detections),2)
            self.assertEqual(window._workflow_phase,'detect')
            self.assertTrue(all(d.grid_positioned and d.cut_width_inches == 4 for d in window.detections))
            positions = {d.id:d.center_px for d in window.detections}
            self.assertFalse(hasattr(window.panel, 'inferred_positions_list'))
            self.assertFalse(hasattr(window.panel, 'inferred_positions_label'))
            self.assertFalse(window.canvas._layout_review_details)
            window.confirm_detection()
            self.assertTrue(window.canvas._layout_review_details)
            inferred = next(d for d in window.detections if d.inferred)
            window.selected_ids = {inferred.id}
            window.selected_id = inferred.id
            window.delete_selected()
            self.assertEqual(len(window.detections),23)
            self.assertIn(inferred.layout_cell, window._suppressed_grid_cells)
            window._refresh()
            self.assertEqual(len(window.detections),23)
            window.undo()
            self.assertEqual(len(window.detections),24)
            window.center_cuts()
            self.assertEqual({d.id:d.center_px for d in window.detections},positions)
            window.change_cut_size(3.9,3.9)
            self.assertFalse(any(d.overlaps_cut for d in window.detections))
            window.undo()
            self.assertEqual({d.id:d.center_px for d in window.detections},positions)
            self.assertTrue(all(d.cut_width_inches == 4 for d in window.detections))
        finally:
            window.close()

    def test_transport_image_has_grid_before_review_and_keeps_spanning_artwork(self) -> None:
        import cv2
        from tests.test_pattern_grid import TRANSPORT_FIXTURE
        window = MainWindow()
        try:
            window._load_image(cv2.imread(str(TRANSPORT_FIXTURE)), 'transport regression')
            window.detect_motifs()  # Default 5-inch cuts, no dimensions entered.
            self.assertEqual(window._workflow_phase, 'detect')
            self.assertEqual((window.logical_layout.columns, window.logical_layout.rows), (5, 4))
            self.assertEqual(len(window.detections), 20)
            self.assertEqual(sum(d.inferred for d in window.detections), 1)
            self.assertTrue(all(d.grid_positioned for d in window.detections))
            self.assertTrue(all(d.cut_width_inches == 5 for d in window.detections))
            self.assertGreater(sum(d.overlaps_cut for d in window.detections), 0)
            positions = {d.id: d.center_px for d in window.detections}
            for d in window.detections:
                self.assertEqual(d.center_px, window.logical_layout.position(*d.layout_cell))
            self.assertNotIn('spans multiple cells', window.panel.layout_status_label.text())
            self.assertFalse(hasattr(window.panel, 'inferred_positions_list'))
            window.confirm_detection()
            self.assertIn('spans multiple cells', window.panel.layout_status_label.text())
            window.fix_overlaps()
            self.assertEqual({d.id: d.center_px for d in window.detections}, positions)
            window.change_cut_size(4, 4)
            self.assertFalse(any(d.overlaps_cut for d in window.detections))
            window.undo()
            self.assertTrue(all(d.cut_width_inches == 5 for d in window.detections))
            window.handle_grid_action('redetect')
            self.assertEqual(window.panel_grid.source, 'pattern')
            window.confirm_grid()
            self.assertEqual(len(window.detections), 20)
            self.assertEqual({d.id: d.center_px for d in window.detections}, positions)
        finally:
            window.close()

    def test_single_outer_anchor_completes_grid_and_squares_without_user_step(self) -> None:
        import cv2
        from tests.test_visual_grid import printed_fabric
        missing = tuple((column, 3) for column in range(6) if column != 2)
        image = printed_fabric(6, 4, panels=False, missing=missing)
        cv2.line(image, (325, 435), (385, 435), (55, 87, 120), 6)
        window = MainWindow()
        try:
            window._load_image(image, "outer row regression")
            window.detect_motifs()

            self.assertEqual((window.logical_layout.columns, window.logical_layout.rows), (6, 4))
            self.assertTrue(window.logical_layout.reliable)
            self.assertEqual(len(window.detections), 24)
            self.assertEqual(sum(item.inferred for item in window.detections), 5)
            self.assertFalse(hasattr(window.panel, "inferred_positions_list"))
            for item in window.detections:
                self.assertEqual(item.center_px, window.logical_layout.position(*item.layout_cell))
        finally:
            window.close()

    def test_vehicle_panels_keep_the_full_six_by_four_grid(self) -> None:
        """A strong panel style must not regress when robust anchors are used."""
        import cv2
        from tests.test_camera_panel import PATCHWORK_FIXTURE

        image = cv2.imread(str(PATCHWORK_FIXTURE.parent / "vehicles_panels.png"))
        window = MainWindow()
        try:
            window._load_image(image, "vehicle panels regression")
            window.detect_motifs()

            self.assertTrue(window.logical_layout.reliable, window.logical_layout)
            self.assertEqual((window.logical_layout.columns, window.logical_layout.rows), (6, 4))
            self.assertEqual(len(window.detections), 24)
            self.assertEqual(sum(item.inferred for item in window.detections), 0)
            self.assertTrue(all(item.grid_positioned for item in window.detections))
            for item in window.detections:
                self.assertEqual(
                    item.center_px,
                    window.logical_layout.position(*item.layout_cell),
                )
        finally:
            window.close()

    def test_bed_reference_completes_missing_row_in_detection(self):
        import cv2
        from tests.test_bed_reference import REFERENCE
        reference=cv2.imread(str(REFERENCE))
        image=reference.copy()
        image[65:420,90:630]=225
        for r in range(3):
            for c in range(6):
                cv2.ellipse(image,(135+c*90,110+r*88),(20,26),0,0,360,(65,90,130),-1)
        window=MainWindow()
        try:
            window.detector.bed_reference=reference
            window._load_image(image,'reference integration')
            window.detect_motifs()
            self.assertEqual((window.logical_layout.columns,window.logical_layout.rows),(6,4))
            self.assertEqual(len(window.detections),24)
            self.assertEqual(sum(d.inferred for d in window.detections),6)
            self.assertTrue(all(d.grid_positioned for d in window.detections))
            self.assertEqual(window._workflow_phase,'detect')
            self.assertIsNotNone(window.panel.load_bed_reference_button)
            np.testing.assert_array_equal(window.image_bgr,image)
        finally:
            window.close()

    def test_camera_grid_controls_cuts_through_review_resize_and_undo(self) -> None:
        import cv2
        from tests.test_visual_grid import CAMERA_FIXTURE
        window = MainWindow()
        try:
            window._load_image(cv2.imread(str(CAMERA_FIXTURE)), "camera regression")
            window.change_cut_size(4., 4.)
            window.detect_motifs()
            self.assertEqual(window._workflow_phase, "detect")
            self.assertEqual(window.logical_layout.source, "visual")
            self.assertEqual((window.logical_layout.columns, window.logical_layout.rows), (6, 4))
            self.assertEqual(len(window.detections), 24)
            self.assertTrue(all(d.grid_positioned and d.valid_cut and not d.overlaps_cut
                                for d in window.detections))
            positions = {d.id: d.center_px for d in window.detections}
            boxes = {d.id: d.bounding_box_px for d in window.detections}
            for d in window.detections:
                self.assertEqual(d.center_px, window.logical_layout.position(*d.layout_cell))
            self.assertTrue(any(d.center_px != d.original_center_px for d in window.detections))
            window.confirm_detection()
            self.assertEqual(window._workflow_phase, "review")
            window.center_cuts()
            window.change_cut_size(3.5, 3.5)
            window.undo()
            self.assertEqual({d.id: d.center_px for d in window.detections}, positions)
            self.assertEqual({d.id: d.bounding_box_px for d in window.detections}, boxes)
            # Editing fallback guides must not silently change the reviewed cuts.
            committed_grid = window.detection_panel_grid
            window.change_grid_dimensions(5, 3)
            window._refresh()
            self.assertEqual(window.detection_panel_grid, committed_grid)
            self.assertEqual({d.id: d.center_px for d in window.detections}, positions)
            window.undo()
            self.assertEqual(window.detection_panel_grid, committed_grid)
            self.assertEqual({d.id: d.center_px for d in window.detections}, positions)
        finally:
            window.close()

    def test_logical_layout_is_automatic_and_manual_override_does_not_deform_it(self) -> None:
        window = MainWindow()
        try:
            window._load_image(np.full((650, 900, 3), 245, dtype=np.uint8), "layout test")
            window.mapper, window.detections, _ = cut_fixture(missing=((2, 2),))
            window._refresh()
            self.assertTrue(window.logical_layout.reliable)
            self.assertEqual(len(window.logical_layout.missing), 1)
            self.assertFalse(hasattr(window, "apply_layout_button"))
            target = next(d for d in window.detections if d.id == 8)
            original = target.original_center_px
            adjusted = target.center_px
            self.assertNotEqual(adjusted, original)
            self.assertEqual(adjusted, window.logical_layout.position(2, 1))
            self.assertEqual(window._workflow_phase, "detect")
            window.confirm_detection()
            self.assertEqual(target.center_px, adjusted)
            self.assertIsNotNone(target.layout_anchor_px)
            self.assertTrue(window.canvas._layout_visible)
            self.assertEqual(len(window.detections), 20)
            positions = {d.id: d.center_px for d in window.detections}
            window.move_detection(8, 444., 263.)
            self.assertTrue(target.manual)
            self.assertIsNone(target.layout_anchor_px)
            self.assertEqual({d.id: d.center_px for d in window.detections if d.id != 8},
                             {i: p for i, p in positions.items() if i != 8})
            self.assertTrue(all(d.grid_positioned for d in window.detections if d.id != 8))
            window._review_centering_complete = False
            window.center_cuts()
            self.assertEqual(target.center_px, (444., 263.))
            window.undo()  # centring
            window.undo()
            target = next(d for d in window.detections if d.id == 8)
            self.assertFalse(target.manual)
            self.assertEqual(target.center_px, adjusted)
            self.assertIsNotNone(target.layout_anchor_px)
            window.center_cuts()
            np.testing.assert_allclose(target.center_px, adjusted)
            window.selected_ids = {8}
            window.selected_id = 8
            window.delete_selected()
            self.assertTrue(all(d.grid_positioned for d in window.detections))
            for d in window.detections:
                self.assertEqual(d.center_px, window.logical_layout.position(*d.layout_cell))
            window.undo()
            self.assertEqual(len(window.detections), 20)
            self.assertIsNotNone(next(d for d in window.detections if d.id == 8).layout_anchor_px)
            window._load_image(np.full((600, 800, 3), 240, dtype=np.uint8), "replacement")
            self.assertEqual(window.logical_layout.matches, ())
            self.assertEqual(window.canvas._logical_layout.missing, ())
        finally:
            window.close()

    def test_missing_grid_cut_is_automatic_internal_and_deletion_is_respected(self) -> None:
        from app.export.svg_exporter import SVG_NAMESPACE
        window = MainWindow()
        try:
            window._load_image(np.full((650, 900, 3), 240, dtype=np.uint8), "gap test")
            window.mapper, window.detections, _ = cut_fixture(missing=((2, 2),))
            window._refresh()
            initial_layout = window.logical_layout
            self.assertEqual(len(window.detections), 20)
            self.assertFalse(hasattr(window.panel, "inferred_positions_list"))
            inferred = next(d for d in window.detections if d.inferred)
            self.assertIsNone(inferred.bounding_box_px)
            self.assertIsNone(inferred.original_center_px)
            self.assertEqual(inferred.center_px, initial_layout.position(2, 2))
            self.assertEqual(window.logical_layout, initial_layout)
            self.assertEqual(len(window.svg_exporter.build_tree(window.mapper, window.detections).findall(
                f"{{{SVG_NAMESPACE}}}rect")), 20)
            window.confirm_detection()
            window.selected_ids = {inferred.id}
            window.selected_id = inferred.id
            window.delete_selected()
            self.assertEqual(len(window.detections), 19)
            self.assertIn((2, 2), window._suppressed_grid_cells)
            window._refresh()
            self.assertEqual(len(window.detections), 19)
            self.assertEqual(len(window.svg_exporter.build_tree(window.mapper, window.detections).findall(
                f"{{{SVG_NAMESPACE}}}rect")), 19)
            window.undo()
            self.assertEqual(len(window.detections), 20)
            inferred = next(d for d in window.detections if d.inferred)
            self.assertEqual(inferred.center_px, window.logical_layout.position(*inferred.layout_cell))
            window.selected_ids = {1}
            window.selected_id = 1
            window.delete_selected()
            self.assertEqual(len(window.logical_layout.matches), 18)  # inferred cut is not evidence
            inferred = next(d for d in window.detections if d.inferred)
            self.assertEqual(inferred.center_px, window.logical_layout.position(*inferred.layout_cell))
            window.undo()  # deletion
            self.assertEqual(len(window.detections), 20)
        finally:
            window.close()

    def test_low_confidence_holes_are_pending_without_cut_proposals(self) -> None:
        window = MainWindow()
        try:
            window._load_image(np.full((650, 900, 3), 240, dtype=np.uint8), "pending test")
            window.mapper, window.detections, _ = cut_fixture(
                missing=((1, 1), (2, 2), (3, 1), (3, 3), (0, 2), (4, 0), (0, 0)))
            original = [d.center_px for d in window.detections]
            window._refresh()
            self.assertFalse(window.logical_layout.reliable)
            self.assertEqual([d.center_px for d in window.detections], original)
            self.assertFalse(any(d.inferred for d in window.detections))
            self.assertFalse(hasattr(window.panel, "inferred_positions_list"))
            self.assertEqual(len(window.detections), len(original))
        finally:
            window.close()

    def test_detect_and_redetect_show_grid_centres_before_confirmation(self) -> None:
        import cv2
        from tests.test_logical_layout import observations
        image = np.full((650, 900, 3), (232, 240, 241), dtype=np.uint8)
        for p in observations(missing=((2, 2),)):
            center = tuple(int(v) for v in p.center_px)
            if p.detection_id == 8:
                center = center[0] + 10, center[1] - 3
            cv2.ellipse(image, center, (44 if p.detection_id % 2 else 27, 27), 0, 0, 360, (77, 125, 202), -1)
        window = MainWindow()
        try:
            window._load_image(image, "real detection test")
            for _ in range(2):
                window.detect_motifs(replace_confirmed=True)
                self.assertTrue(window.logical_layout.reliable)
                self.assertFalse(window._detection_review_complete)
                self.assertEqual(window._workflow_phase, "detect")
                self.assertEqual(len(window.detections), 20)
                for d in window.detections:
                    self.assertEqual(d.center_px, window.logical_layout.position(*d.layout_cell))
                self.assertTrue(any(np.linalg.norm(np.array(d.center_px) - d.original_center_px) > 5
                                    for d in window.detections if d.original_center_px is not None))
            positions = [d.center_px for d in window.detections]
            window.change_cut_size(5.5, 5.5)
            self.assertEqual([d.center_px for d in window.detections], positions)
            window.confirm_detection()
            self.assertFalse(window.center_cuts_button.isEnabled())
            window.undo()  # size
            self.assertEqual([d.center_px for d in window.detections], positions)
            window.undo()  # re-detection
            self.assertEqual([d.center_px for d in window.detections], positions)
            window.undo()  # first detection
            self.assertEqual(window.detections, [])
        finally:
            window.close()

    def test_contextual_help_is_registered(self) -> None:
        window = MainWindow()
        window.resize(1280, 800)
        window.show()
        self.application.processEvents()
        info_buttons = window.panel.findChildren(InfoButton)
        self.assertEqual(len(info_buttons), 24)
        self.assertTrue(all(button.help_text.strip() for button in info_buttons))

        toolbar = window.findChild(DelayedHelpToolBar, "mainToolbar")
        self.assertIsNotNone(toolbar)
        assert toolbar is not None
        self.assertEqual(toolbar.HOVER_DELAY_MS, 1300)
        self.assertEqual(len(toolbar._help_by_widget), 4)
        self.assertTrue(all(text.strip() for text in toolbar._help_by_widget.values()))
        self.assertTrue(window.review_strip.isVisible())
        self.assertTrue(window.fix_overlaps_button.toolTip().strip())
        self.assertTrue(window.center_cuts_button.toolTip().strip())
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

    def test_prototype_assumption_banner_is_not_present(self) -> None:
        window = MainWindow()
        self.assertFalse(hasattr(window, "assumption_label"))
        window.close()

    def test_cut_preview_dims_the_bed_outside_exportable_cuts(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        image = np.full((240, 360, 3), 220, dtype=np.uint8)
        window._load_image(image, "Preview test image loaded")
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(18.0, 12.0))
        self.application.processEvents()

        self.assertTrue(window.cut_preview_toggle.isEnabled())
        window.cut_preview_toggle.setChecked(True)
        self.application.processEvents()
        self.assertTrue(window.canvas.cut_preview_active)
        rendered = window.canvas.grab().toImage()
        inside = window.canvas._pixel_to_widget(190.0, 130.0).toPoint()
        outside = window.canvas._pixel_to_widget(10.0, 10.0).toPoint()
        inside_color = rendered.pixelColor(inside)
        outside_color = rendered.pixelColor(outside)
        self.assertGreater(
            inside_color.red() + inside_color.green() + inside_color.blue(),
            outside_color.red() + outside_color.green() + outside_color.blue() + 200,
        )

        window.clear_detections()
        self.assertFalse(window.cut_preview_toggle.isChecked())
        self.assertFalse(window.cut_preview_toggle.isEnabled())
        self.assertFalse(window.canvas.cut_preview_active)
        window.close()

    def test_selected_cut_uses_cyan_square_fill_border_and_center_without_halo(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        image = np.full((240, 360, 3), 220, dtype=np.uint8)
        window._load_image(image, "Selection test image loaded")
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(18.0, 12.0))
        self.application.processEvents()

        detection = window.detections[0]
        square_px = window.mapper.inches_rect_to_pixel(
            detection.square_inches.as_tuple()
        )
        square = window.canvas._pixel_rect_to_widget(square_px)
        rendered = window.canvas.grab().toImage()
        border = rendered.pixelColor(
            int(round(square.center().x())), int(round(square.top()))
        )
        center = rendered.pixelColor(square.center().toPoint())
        interior = rendered.pixelColor(
            int(round(square.left() + 14)), int(round(square.top() + 14))
        )
        outside = rendered.pixelColor(
            int(round(square.center().x())), int(round(square.top() - 6))
        )

        for selected_color in (border, center):
            self.assertGreater(selected_color.green(), 190)
            self.assertGreater(selected_color.blue(), 210)
            self.assertLess(selected_color.red(), 150)
        self.assertGreater(interior.blue(), interior.red() + 20)
        self.assertFalse(
            outside.green() > 190
            and outside.blue() > 210
            and outside.red() < 150
        )
        window.close()

    def test_center_step_preserves_collision_free_layout(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(14.0, 10.0))
        first, second = window.detections
        first.move_to_inches(
            (8.0, 10.0), window.mapper, preserve_preferred_center=True
        )
        second.move_to_inches(
            (16.0, 10.0), window.mapper, preserve_preferred_center=True
        )
        window._refresh()

        self.assertFalse(window.review_strip.isHidden())
        self.assertTrue(window.center_cuts_button.isEnabled())
        window.center_cuts()

        self.assertFalse(first.overlaps_cut)
        self.assertFalse(second.overlaps_cut)
        self.assertAlmostEqual(
            second.center_inches[0] - first.center_inches[0], 5.01
        )
        self.assertAlmostEqual(
            first.center_inches[0] + second.center_inches[0], 24.0
        )
        self.assertFalse(window.fix_overlaps_button.isEnabled())
        self.assertFalse(window.center_cuts_button.isEnabled())
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

        self.assertEqual(initial_width, 360)
        self.assertEqual(window.panel.width(), initial_width)
        self.assertIn("OVERLAP", window.panel.detection_list.item(0).text())
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
        self.assertFalse(window.review_strip.isHidden())
        self.assertFalse(window.center_cuts_button.isEnabled())
        self.assertTrue(window.fix_overlaps_button.isEnabled())
        self.assertEqual(window.panel.valid_value_label.text(), "0")
        self.assertEqual(window.panel.invalid_value_label.text(), "2")
        self.assertEqual(window.panel.disabled_value_label.text(), "0")
        window.set_detection_enabled(window.detections[1].id, False)
        self.assertFalse(window.detections[0].overlaps_cut)
        self.assertTrue(window.center_cuts_button.isEnabled())
        self.assertFalse(window.fix_overlaps_button.isEnabled())
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
        window.confirm_detection()
        original_first = window.detections[0].center_inches

        window.fix_overlaps()

        self.assertFalse(any(item.overlaps_cut for item in window.detections))
        self.assertNotEqual(window.detections[0].center_inches, original_first)
        self.assertFalse(window.fix_overlaps_button.isEnabled())
        self.assertTrue(window.center_cuts_button.isEnabled())
        window.center_cuts()
        self.assertFalse(window.center_cuts_button.isEnabled())
        self.assertIn("Review complete", window.review_guidance.text())
        moved = window.detections[1]
        manual_position = window.mapper.inches_to_pixel(22.0, 15.0)
        window.move_detection(moved.id, *manual_position)
        self.assertAlmostEqual(moved.center_inches[0], 22.0)
        self.assertAlmostEqual(moved.center_inches[1], 15.0)
        self.assertTrue(window._review_centering_complete)
        self.assertFalse(window.center_cuts_button.isEnabled())
        window.close()

    def test_contextual_actions_run_the_review_workflow(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(14.0, 10.0))
        window.confirm_detection()
        self.application.processEvents()

        self.assertFalse(window.center_cuts_button.isEnabled())
        self.assertTrue(window.fix_overlaps_button.isEnabled())
        window.fix_overlaps_button.click()
        self.application.processEvents()
        self.assertTrue(window.center_cuts_button.isEnabled())
        self.assertFalse(window.fix_overlaps_button.isEnabled())

        window.center_cuts_button.click()
        self.application.processEvents()
        self.assertFalse(any(item.overlaps_cut for item in window.detections))
        self.assertIn("Review complete", window.review_guidance.text())

        window.select_detection(window.detections[0].id)
        QTest.keyClick(window, Qt.Key.Key_Delete)
        self.application.processEvents()
        self.assertEqual(len(window.detections), 1)
        window.close()

    def test_shift_select_deletes_many_and_ctrl_z_restores_them(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(22.0, 10.0))
        self.application.processEvents()

        first_point = window.canvas._pixel_to_widget(
            *window.detections[0].center_px
        ).toPoint()
        second_point = window.canvas._pixel_to_widget(
            *window.detections[1].center_px
        ).toPoint()
        QTest.mouseClick(
            window.canvas, Qt.MouseButton.LeftButton, pos=first_point
        )
        QTest.mouseClick(
            window.canvas,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ShiftModifier,
            pos=second_point,
        )
        self.application.processEvents()

        self.assertEqual(window.selected_ids, {1, 2})
        self.assertIn("(2)", window.remove_detection_button.text())
        QTest.keyClick(window, Qt.Key.Key_Delete)
        self.application.processEvents()
        self.assertEqual(window.detections, [])
        self.assertTrue(window.undo_action.isEnabled())

        QTest.keyClick(
            window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        )
        self.application.processEvents()
        self.assertEqual([item.id for item in window.detections], [1, 2])
        self.assertEqual(window.selected_ids, {1, 2})
        window.close()

    def test_clicking_selected_square_toggles_it_off(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(18.0, 12.0))
        window.clear_selection()
        center = window.canvas._pixel_to_widget(
            *window.detections[0].center_px
        ).toPoint()

        QTest.mouseClick(window.canvas, Qt.MouseButton.LeftButton, pos=center)
        self.application.processEvents()
        self.assertEqual(window.selected_ids, {1})

        QTest.mouseClick(window.canvas, Qt.MouseButton.LeftButton, pos=center)
        self.application.processEvents()
        self.assertEqual(window.selected_ids, set())
        self.assertIsNone(window.selected_id)
        self.assertEqual(window.panel.detection_list.selectedItems(), [])
        window.close()

    def test_empty_canvas_click_preserves_multi_selection(self) -> None:
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(22.0, 10.0))
        window.select_detection(1)
        window.select_detection(2, additive=True)
        blank_point = (
            window.canvas._bed_rect().bottomRight() - QPointF(8.0, 8.0)
        ).toPoint()

        self.assertIsNone(window.canvas._hit_test(QPointF(blank_point)))
        QTest.mouseClick(
            window.canvas, Qt.MouseButton.LeftButton, pos=blank_point
        )
        self.application.processEvents()

        self.assertEqual(window.selected_ids, {1, 2})
        list_blank = QPoint(
            5, window.panel.detection_list.viewport().height() - 5
        )
        self.assertIsNone(window.panel.detection_list.itemAt(list_blank))
        QTest.mouseClick(
            window.panel.detection_list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=list_blank,
        )
        self.application.processEvents()
        self.assertEqual(window.selected_ids, {1, 2})
        window.close()

    def test_center_and_overlap_fix_leave_nothing_selected(self) -> None:
        window = MainWindow()
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(14.0, 10.0))
        window.select_detection(1)
        window.select_detection(2, additive=True)

        window.fix_overlaps()
        self.assertEqual(window.selected_ids, set())
        detection_count = len(window.detections)
        QTest.keyClick(window, Qt.Key.Key_3)
        self.assertEqual(len(window.detections), detection_count)

        window.select_detection(1)
        window.center_cuts()
        self.assertEqual(window.selected_ids, set())
        window.close()

    def test_review_bar_has_distinct_complete_state_and_no_toolbar_duplicates(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.confirm_detection()
        window.center_cuts()

        self.assertEqual(
            window.center_cuts_button.property("workflowState"), "complete"
        )
        self.assertEqual(
            window.remove_detection_button.property("workflowState"), "neutral"
        )
        self.assertIn("Review complete", window.review_guidance.text())
        toolbar = window.findChild(DelayedHelpToolBar, "mainToolbar")
        assert toolbar is not None
        toolbar_texts = {action.text() for action in toolbar.actions()}
        self.assertIn("Undo", toolbar_texts)
        self.assertNotIn("Delete", toolbar_texts)
        self.assertNotIn("Clear Detections", toolbar_texts)
        window.close()

    def test_workflow_is_horizontal_and_preview_stays_on_canvas(self) -> None:
        window = MainWindow()
        window.resize(1400, 820)
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.clear_selection()
        self.application.processEvents()

        workflow_bottom = window.review_strip.mapToGlobal(
            window.review_strip.rect().bottomLeft()
        ).y()
        canvas_top = window.canvas.mapToGlobal(window.canvas.rect().topLeft()).y()
        canvas_right = window.canvas.mapToGlobal(
            window.canvas.rect().bottomRight()
        ).x()
        panel_left = window.panel.mapToGlobal(window.panel.rect().topLeft()).x()
        self.assertLessEqual(workflow_bottom, canvas_top)
        self.assertLessEqual(canvas_right, panel_left)
        self.assertEqual(
            [
                window.workflow_grid_button.text(),
                window.workflow_detect_button.text(),
                window.workflow_review_button.text(),
                window.workflow_check_button.text(),
                window.workflow_export_button.text(),
            ],
            [
                "1  Prepare image",
                "2  Detect + check",
                "3  Review cuts",
                "4  Check output",
                "5  Export SVG",
            ],
        )
        window.close()

    def test_ctrl_z_steps_back_through_overlap_fix_and_centering(self) -> None:
        window = MainWindow()
        window.show()
        window.load_demo_image()
        assert window.mapper is not None
        window.add_center(*window.mapper.inches_to_pixel(10.0, 10.0))
        window.add_center(*window.mapper.inches_to_pixel(14.0, 10.0))
        window.confirm_detection()
        window.fix_overlaps()
        overlap_fixed_positions = [item.center_inches for item in window.detections]
        self.assertFalse(any(item.overlaps_cut for item in window.detections))
        self.assertFalse(window._review_centering_complete)
        window.center_cuts()
        self.assertTrue(window._review_centering_complete)
        self.assertFalse(any(item.overlaps_cut for item in window.detections))

        QTest.keyClick(
            window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        )
        self.application.processEvents()
        self.assertEqual(
            [item.center_inches for item in window.detections], overlap_fixed_positions
        )
        self.assertFalse(any(item.overlaps_cut for item in window.detections))
        self.assertFalse(window._review_centering_complete)
        self.assertTrue(window.center_cuts_button.isEnabled())

        QTest.keyClick(
            window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        )
        self.application.processEvents()
        self.assertTrue(all(item.overlaps_cut for item in window.detections))
        self.assertFalse(window._review_centering_complete)
        self.assertTrue(window.fix_overlaps_button.isEnabled())
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

    def test_grid_and_advanced_detection_are_separate_sections(self) -> None:
        window = MainWindow()

        self.assertEqual(window.panel.layout_mode_combo.currentData(), "auto")
        self.assertFalse(window.panel.advanced_detection_controls.isHidden())
        labels = [label.text() for label in window.panel.findChildren(QLabel)]
        self.assertIn("PANEL GRID", labels)
        self.assertIn("ADVANCED DETECTION SETTINGS", labels)
        self.assertNotIn("DETECTION SETTINGS", labels)
        self.assertFalse(hasattr(window.panel, "apply_grid_size_button"))
        self.assertEqual(
            window.panel.redetect_grid_button.text(), "Restore automatic grid"
        )
        window.close()

    def test_detection_requires_explicit_result_confirmation(self) -> None:
        window = MainWindow()
        window.load_demo_image()

        self.assertEqual(window._workflow_phase, "detect")
        self.assertIsNone(window.panel_grid)
        self.assertFalse(window._grid_review_complete)
        self.assertTrue(window.workflow_detect_button.isEnabled())
        window.detect_motifs()
        self.assertGreater(len(window.detections), 0)
        self.assertEqual(window._workflow_phase, "detect")
        self.assertFalse(window._detection_review_complete)
        self.assertFalse(window.workflow_review_button.isEnabled())
        self.assertTrue(window.panel.confirm_detection_button.isEnabled())
        self.assertEqual(window.panel.review_grid_button.text(), "Adjust panel grid")
        self.assertTrue(window.panel.show_layout_checkbox.isHidden())
        self.assertFalse(window.canvas._layout_review_details)

        window.confirm_detection()
        self.assertTrue(window._detection_review_complete)
        self.assertEqual(window._workflow_phase, "review")
        self.assertTrue(window.workflow_review_button.isEnabled())
        self.assertFalse(window.panel.show_layout_checkbox.isHidden())
        window.close()

    def test_reliable_grid_is_used_in_first_detection_without_manual_step(self) -> None:
        window = MainWindow()
        window.load_demo_image()

        self.assertIsNone(window.panel_grid)
        self.assertFalse(window._grid_review_complete)
        window.detect_motifs()

        self.assertGreater(len(window.detections), 0)
        self.assertIsNotNone(window.panel_grid)
        self.assertTrue(window.logical_layout.reliable)
        self.assertTrue(all(d.grid_positioned for d in window.detections))
        self.assertEqual(window._workflow_phase, "detect")
        self.assertTrue(window.panel.review_grid_button.isEnabled())
        window.close()

    def test_side_panel_is_contextual_and_canvas_is_dominant(self) -> None:
        window = MainWindow()
        window.resize(1420, 880)
        window.show()
        self.application.processEvents()

        self.assertFalse(window.panel.machine_section.isHidden())
        self.assertTrue(window.panel.grid_section.isHidden())
        self.assertGreater(window.canvas.width(), window.panel.width() * 2)
        window.load_demo_image()
        self.application.processEvents()
        self.assertTrue(window.panel.machine_section.isHidden())
        self.assertTrue(window.panel.grid_section.isHidden())
        self.assertFalse(window.panel.detection_review.isHidden())
        self.assertLess(window.panel.context_title.y(), 30)

        self.assertFalse(window.panel.advanced_toggle.isHidden())
        self.assertTrue(window.panel.advanced_section.isHidden())
        window.detect_motifs()
        self.assertTrue(window.panel.review_actions.isHidden())
        self.assertFalse(window.add_center_button.isEnabled())
        window.confirm_detection()
        self.assertFalse(window.panel.review_actions.isHidden())
        self.assertFalse(window.panel.detections_section.isHidden())
        self.assertEqual(window.add_center_button.text(), "Add cut square")
        self.assertTrue(window.add_center_button.isEnabled())
        window.add_center_button.click()
        self.assertTrue(window.add_action.isChecked())
        self.assertEqual(window.add_center_button.text(), "Cancel adding square")
        window.add_center_button.click()
        self.assertFalse(window.add_action.isChecked())
        window.close()

    def test_grid_changes_preserve_review_until_user_redetects(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        window.detect_motifs()
        original_ids = [item.id for item in window.detections]

        window.panel.review_grid_button.click()
        self.application.processEvents()
        assert window.panel_grid is not None
        window.change_grid_dimensions(window.panel_grid.columns + 1, window.panel_grid.rows)

        self.assertEqual([item.id for item in window.detections], original_ids)
        self.assertFalse(window._grid_review_complete)
        self.assertEqual(window._workflow_phase, "grid")
        window.confirm_grid()
        self.assertGreater(len(window.detections), 0)
        self.assertEqual(window._workflow_phase, "detect")
        self.assertFalse(window._detection_review_complete)
        self.assertFalse(window.workflow_review_button.isEnabled())
        window.close()

    def test_preflight_only_skips_unchecked_cuts(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        window.detect_motifs()

        window.show_preflight()

        self.assertFalse(window._preflight_complete)
        self.assertEqual(window._workflow_phase, "detect")
        window.confirm_detection()

        # Unchecking one cut is the only thing that removes it from the export.
        skipped_id = window.detections[0].id
        window.set_detection_enabled(skipped_id, False)
        window.show_preflight()

        self.assertTrue(window._preflight_complete)
        self.assertEqual(window._workflow_phase, "preflight")
        label = window.panel.verification_label.text()
        self.assertIn("EXPORT", label.upper())
        self.assertIn("Skipped (unchecked): 1", label)
        self.assertTrue(window.cut_preview_toggle.isChecked())
        window.close()

    def test_manual_grid_dimensions_and_distribution_update_canvas(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.image_bgr is not None
        height, width = window.image_bgr.shape[:2]
        window.panel_grid = PanelGrid.regular(width, height, 4, 3)
        window._sync_panel_grid_ui()

        moved = window.panel_grid.move_line("x", 1, width * 0.18)
        window.panel_grid = moved
        window.handle_grid_action("distribute_columns")

        assert window.panel_grid is not None
        self.assertEqual((window.panel_grid.columns, window.panel_grid.rows), (4, 3))
        self.assertAlmostEqual(window.panel_grid.x_lines_px[1], width / 4)
        self.assertIs(window.canvas._panel_grid, window.panel_grid)
        self.assertFalse(window.panel.grid_controls.isHidden())
        window.close()

    def test_grid_can_be_hidden_and_dimensions_apply_immediately(self) -> None:
        window = MainWindow()
        window.load_demo_image()
        assert window.image_bgr is not None
        height, width = window.image_bgr.shape[:2]
        window.panel_grid = PanelGrid.regular(width, height, 4, 3)
        window._sync_panel_grid_ui()

        window.panel.show_grid_checkbox.setChecked(False)
        self.assertFalse(window.canvas._grid_visible)
        self.assertFalse(window.canvas._grid_edit_active)
        window.panel.grid_columns_spin.setValue(5)

        assert window.panel_grid is not None
        self.assertEqual(window.panel_grid.columns, 5)
        self.assertFalse(window.canvas._grid_visible)
        window.close()

    def test_cut_can_move_while_grid_is_visible_and_editable(self) -> None:
        window = MainWindow()
        window.resize(1400, 820)
        window.load_demo_image()
        assert window.image_bgr is not None
        assert window.mapper is not None
        height, width = window.image_bgr.shape[:2]
        window.panel_grid = PanelGrid.regular(width, height, 4, 3)
        window._sync_panel_grid_ui()
        window.add_center(*window.mapper.inches_to_pixel(11.0, 11.0))
        window.clear_selection()
        window.panel.edit_grid_checkbox.setChecked(True)
        window.show()
        self.application.processEvents()

        before = window.detections[0].center_px
        start = window.canvas._pixel_to_widget(*before).toPoint()
        end = start + QPoint(24, 15)
        QTest.mousePress(window.canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(window.canvas, end)
        QTest.mouseRelease(window.canvas, Qt.MouseButton.LeftButton, pos=end)
        self.application.processEvents()

        self.assertNotEqual(window.detections[0].center_px, before)
        window.close()

    def test_grid_line_drag_updates_geometry_and_is_undoable(self) -> None:
        window = MainWindow()
        window.resize(1400, 820)
        window.load_demo_image()
        assert window.image_bgr is not None
        height, width = window.image_bgr.shape[:2]
        window.panel_grid = PanelGrid.regular(width, height, 4, 3)
        window._sync_panel_grid_ui()
        window.panel.edit_grid_checkbox.setChecked(True)
        window.show()
        self.application.processEvents()

        start = window.canvas._pixel_to_widget(width / 4, height / 6).toPoint()
        QTest.mousePress(window.canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(window.canvas, start + QPoint(18, 0))
        QTest.mouseRelease(
            window.canvas, Qt.MouseButton.LeftButton, pos=start + QPoint(18, 0)
        )
        self.application.processEvents()

        assert window.panel_grid is not None
        self.assertNotAlmostEqual(window.panel_grid.x_lines_px[1], width / 4)
        self.assertEqual(window._undo_stack[-1].label, "Edit panel grid")
        window.undo()
        assert window.panel_grid is not None
        self.assertAlmostEqual(window.panel_grid.x_lines_px[1], width / 4)
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
