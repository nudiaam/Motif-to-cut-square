"""Independent checks for cuts crossing their assigned printed region."""
import copy
import json
import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.export.svg_exporter import SVGExporter, SVG_NAMESPACE
from app.export.verifier import verify_export_geometry
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_region import fit_center_in_region, rectangle_inside_region
from app.imaging.detector import DetectionResult, MotifCandidate
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.imaging.grid_guidance import restrict_grid_to_fabric
from app.imaging.visual_grid import refine_printed_boundaries
from app.models import Detection, apply_logical_layout
from app.ui.main_window import MainWindow


class CutRegionTests(unittest.TestCase):
    def setUp(self):
        self.mapper = CoordinateMapper(3600,2400)

    def scene(self,width=1.10):
        grid = PanelGrid((40.,152.,264.,376.),(44.,156.,268.),.95,'visual',
                         ((100.,100.),(112.,0.),(8.,112.)))
        points = [(100.+112*c+8*r,100.+112*r) for r in range(2) for c in range(3)]
        detections = [Detection.from_pixel_center(i,p,self.mapper,
            (round(p[0]-20),round(p[1]-20),40,40),cut_width_inches=width,cut_height_inches=width)
            for i,p in enumerate(points,1)]
        layout = layout_from_panel_grid([LayoutObservation(d.id,d.center_px,d.bounding_box_px)
                                        for d in detections],grid)
        apply_logical_layout(detections,self.mapper,layout)
        return detections,layout

    def test_sheared_cuts_warn_but_remain_in_verification_and_export(self):
        detections,_ = self.scene()
        self.assertTrue(all(not d.valid_cut for d in detections))
        self.assertTrue(all('panel boundary' in d.cut_warning_reason(self.mapper) for d in detections))
        self.assertTrue(all(d.enabled for d in detections))
        self.assertEqual(len(verify_export_geometry(self.mapper,detections).overlay_rectangles_px),6)
        self.assertEqual(len(SVGExporter().build_tree(self.mapper,detections).findall(f'{{{SVG_NAMESPACE}}}rect')),6)

    def test_smaller_cuts_preserve_size_and_every_corner_has_physical_clearance(self):
        detections,_ = self.scene(1.)
        for d in detections:
            self.assertTrue(d.exportable)
            polygon = np.asarray(d.cut_region_px,np.float32)
            x,y = d.center_px
            # Independent signed-distance oracle, not the implementation's planes.
            for dx,dy in ((-50,-50),(50,-50),(50,50),(-50,50)):
                self.assertGreaterEqual(cv2.pointPolygonTest(polygon,(x+dx,y+dy),True),.99999)
            self.assertEqual((d.cut_width_inches,d.cut_height_inches),(1.,1.))
        self.assertEqual(len(SVGExporter().build_tree(self.mapper,detections).findall(f'{{{SVG_NAMESPACE}}}rect')),6)

    def test_manual_movement_stays_in_the_original_panel(self):
        detections,_ = self.scene(1.)
        first = detections[0]
        region = first.cut_region_px
        for point in ((105.,100.),(300.,250.),(0.,0.)):
            first.move_to_pixel(point,self.mapper)
            self.assertEqual(first.cut_region_px,region)
            self.assertTrue(first.manual)
            x,y,w,h = self.mapper.inches_rect_to_pixel(first.square_inches.as_tuple())
            polygon = np.asarray(region,np.float32)
            for corner in ((x,y),(x+w,y),(x+w,y+h),(x,y+h)):
                self.assertGreaterEqual(cv2.pointPolygonTest(polygon,corner,True),-1e-4)
            self.assertIsNone(first.cut_hard_block_reason(self.mapper))
        self.assertEqual((first.cut_width_inches,first.cut_height_inches),(1.,1.))
        self.assertEqual(len(SVGExporter().build_tree(self.mapper,detections).findall(f'{{{SVG_NAMESPACE}}}rect')),6)

    def test_uneven_guides_keep_exact_centres_edges_and_inverse_coordinates(self):
        grid = PanelGrid((100.,210.,330.,460.),(100.,210.,330.),1.,'manual')
        layout = layout_from_panel_grid([],grid)
        for r,y in enumerate((155.,270.)):
            for c,x in enumerate((155.,270.,395.)):
                self.assertEqual(layout.position(c,r),(x,y))
                np.testing.assert_allclose(layout.coordinates(x,y),(c,r),atol=1e-10)
                self.assertEqual(layout.cell_polygon(c,r),
                    ((grid.x_lines_px[c],grid.y_lines_px[r]),
                     (grid.x_lines_px[c+1],grid.y_lines_px[r]),
                     (grid.x_lines_px[c+1],grid.y_lines_px[r+1]),
                     (grid.x_lines_px[c],grid.y_lines_px[r+1])))

    def test_nearest_safe_placement_repositions_without_resizing(self):
        polygon = ((0.,0.),(10.,0.),(10.,10.),(0.,10.))
        np.testing.assert_allclose(fit_center_in_region((1.,5.),(4.,4.),polygon,.1),(2.1,5.),atol=1e-10)
        self.assertIsNone(fit_center_in_region((5.,5.),(10.,10.),polygon,.1))
        self.assertTrue(rectangle_inside_region((5.,5.),(9.,9.),polygon,.1))

    def test_inconsistent_layout_centre_is_warned_without_silent_repositioning(self):
        from app.imaging.logical_layout import LogicalLayout, LayoutMatch
        region = ((100.,100.),(200.5,100.),(200.5,200.5),(100.,200.5))
        detection = Detection.from_pixel_center(1,(195.,151.),self.mapper,
            cut_width_inches=1.,cut_height_inches=1.)
        layout = LogicalLayout(columns=1,rows=1,origin_px=(195.,151.),
            column_vector_px=(102.,0.),row_vector_px=(0.,102.),confidence=1.,
            matches=(LayoutMatch(1,(195.,151.),(195.,151.),0,0,0.,'matched'),),
            cell_regions_px=(region,))
        apply_logical_layout([detection],self.mapper,layout)
        self.assertIsNone(detection.cut_hard_block_reason(self.mapper))
        self.assertEqual((detection.cut_width_inches,detection.cut_height_inches),(1.,1.))
        self.assertEqual(detection.center_px,(195.,151.))
        self.assertIsNotNone(detection.panel_boundary_reason(self.mapper))

    def test_invalid_or_concave_regions_do_not_certify_cuts(self):
        for polygon in ((),((0.,0.),(0.,0.),(1.,1.)),
                        ((0.,0.),(10.,0.),(4.,4.),(10.,10.),(0.,10.))):
            self.assertFalse(rectangle_inside_region((5.,5.),(1.,1.),polygon))
            self.assertIsNone(fit_center_in_region((5.,5.),(1.,1.),polygon))

    def test_mapper_and_size_changes_recheck_current_geometry(self):
        detections,_ = self.scene(1.)
        first = detections[0]
        first.set_cut_size(1.10,1.10,self.mapper)
        self.assertIsNotNone(first.cut_block_reason(self.mapper))
        first.set_cut_size(1.,1.,self.mapper)
        self.assertIsNone(first.cut_block_reason(self.mapper))
        magnified = CoordinateMapper(3600,2400,image_width_in=18.,image_height_in=12.)
        first.recalculate_for_mapper(magnified)
        self.assertIsNotNone(first.cut_block_reason(magnified))

    def test_cells_that_do_not_fit_remain_enabled_with_warnings(self):
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(np.full((600,900,3),230,np.uint8),'region test')
        window.change_cut_size(5.,5.)
        grid = PanelGrid.regular(900,600,3,2,bounds_px=(200,150,500,350),confidence=.99,source='visual')
        candidates = tuple(MotifCandidate((250.+c*100,200.+r*100),(240+c*100,190+r*100,20,20),.9,400)
                           for r in range(2) for c in range(3))
        window._apply_detection_result(DetectionResult(candidates,grid),{})
        self.assertEqual(len(window.detections),6)
        # A 5in cut in a ~4in cell stays enabled with a warning.
        self.assertTrue(all(d.enabled and not d.auto_blocked and d.cut_region_px is not None
                            and d.cut_block_reason(window.mapper) for d in window.detections))
        window._refresh()
        self.assertEqual(len(window.detections),6)
        self.assertTrue(all(d.enabled for d in window.detections))
        window.change_cut_size(2.,2.)
        # A cut that fits clears the warning and stays enabled.
        self.assertTrue(all(d.enabled and not d.cut_block_reason(window.mapper)
                            for d in window.detections))
        first = window.detections[0]
        window.set_detection_enabled(first.id,False)
        window.change_cut_size(5.,5.)
        window.change_cut_size(2.,2.)
        self.assertFalse(first.enabled)  # Manual exclusions must never revive.
        self.assertTrue(all(d.enabled for d in window.detections[1:]))
        app.processEvents()

    def test_uncertain_inside_border_needs_review_but_only_crossings_are_red(self):
        mapper = CoordinateMapper(3600,2400)  # 100 px per inch
        region = ((100.,100.),(202.,100.),(202.,202.),(100.,202.))  # 1.02 in panel
        for size,uncertainty,flagged in ((1.,0.,False),(1.019,0.,False),
                                        (1.,.2,False),(1.,5.,False),(1.03,0.,True)):
            with self.subTest(size=size,uncertainty=uncertainty):
                d = Detection.from_pixel_center(1,(151.,151.),mapper,cut_width_inches=size,
                    cut_height_inches=size,cut_region_uncertainty_px=uncertainty)
                d.cut_region_px = region
                d.cut_region_required = True
                d.recalculate_for_mapper(mapper)
                self.assertEqual(bool(d.cut_block_reason(mapper)),flagged)
                self.assertIsNone(d.cut_hard_block_reason(mapper))
                self.assertEqual(d.valid_cut,not flagged)
                self.assertEqual(bool(d.panel_boundary_review_reason(mapper)),uncertainty==5.)

    def test_panel_crossings_are_purple_checkable_visible_and_exportable(self):
        import tempfile
        import xml.etree.ElementTree as ET
        from unittest import mock
        from PySide6.QtWidgets import QMessageBox, QFileDialog
        from PySide6.QtGui import QImage, QPainter, QColor
        from app.ui.cut_status import REVIEW_COLOR
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(np.full((600,900,3),230,np.uint8),'panel warning ui')
        window.change_cut_size(5.,5.)
        grid = PanelGrid.regular(900,600,3,2,bounds_px=(200,150,500,350),confidence=.99,source='visual')
        candidates = tuple(MotifCandidate((250.+c*100,200.+r*100),(240+c*100,190+r*100,20,20),.9,400)
                           for r in range(2) for c in range(3))
        window._apply_detection_result(DetectionResult(candidates,grid),{})
        self.assertTrue(all(d.enabled for d in window.detections))
        self.assertEqual(window.panel.disabled_value_label.text(),'0')
        self.assertEqual(window.panel.invalid_value_label.text(),'6')
        self.assertIn('Section crossing',window.panel.review_breakdown_label.text())
        self.assertNotIn('blocked',window.panel.review_breakdown_label.text().lower())
        for index in range(window.panel.detection_list.count()):
            item = window.panel.detection_list.item(index)
            self.assertIn('SECTION CROSSING',item.text())
            self.assertEqual(item.foreground().color().name(),REVIEW_COLOR)
        first = window.detections[0]
        window.panel._selected_id = first.id
        window.panel._update_details()
        self.assertTrue(window.panel.include_checkbox.isEnabled())
        self.assertTrue(window.panel.include_checkbox.isChecked())
        self.assertIn('included in the SVG',window.panel.detail_label.text())
        self.assertEqual(len(verify_export_geometry(window.mapper,window.detections).overlay_rectangles_px),6)
        # Every square remains drawn, including overlapping warning cuts.
        image = QImage(1000,700,QImage.Format.Format_ARGB32)
        image.fill(QColor('white'))
        painter = QPainter(image)
        try:
            with mock.patch.object(QPainter,'drawRect',wraps=painter.drawRect) as draw:
                window.canvas._paint_detections(painter)
            self.assertEqual(draw.call_count,6)  # Final cut squares; artwork boxes are optional details.
        finally:
            painter.end()
        window.canvas.set_cut_preview(True)
        image.fill(QColor('white'))
        painter = QPainter(image)
        try:
            window.canvas._paint_cut_preview(painter,window.canvas._bed_rect())
        finally:
            painter.end()
        a,b=window.detections[:2]
        overlap=window.canvas._inches_rect_to_widget(a.square_inches.as_tuple()).intersected(
            window.canvas._inches_rect_to_widget(b.square_inches.as_tuple()))
        self.assertFalse(overlap.isEmpty())
        self.assertEqual(image.pixelColor(overlap.center().toPoint()).name(),'#ffffff')
        window.confirm_detection()
        self.assertTrue(window.workflow_export_button.isEnabled())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'all-warnings.svg'
            with mock.patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Cancel), \
                 mock.patch.object(QFileDialog,'getSaveFileName') as save:
                window.export_svg()
                save.assert_not_called()
            with mock.patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Yes) as warning, \
                 mock.patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'SVG')), \
                 mock.patch.object(QMessageBox,'information'):
                window.export_svg()
            self.assertEqual(warning.call_args.args[1],'Some cuts have warnings')
            self.assertEqual(len(ET.parse(path).getroot().findall(f'{{{SVG_NAMESPACE}}}rect')),6)
        # Old automatic exclusions are restored, manual exclusions stay off.
        first.enabled=False;first.auto_blocked=True
        window._refresh()
        self.assertTrue(first.enabled)
        self.assertFalse(first.auto_blocked)
        window.set_detection_enabled(first.id,False)
        window._refresh()
        self.assertFalse(first.enabled)
        self.assertEqual(len(window.svg_exporter.build_tree(window.mapper,window.detections).findall(f'{{{SVG_NAMESPACE}}}rect')),5)
        app.processEvents()

    def test_peripheral_bed_column_is_removed_but_partial_cloth_column_is_retained(self):
        mask = np.zeros((300,500),np.uint8)
        mask[30:230,50:350] = 255
        grid = PanelGrid.regular(500,300,4,2,bounds_px=(50,30,450,230),confidence=.95,source='visual')
        restricted = restrict_grid_to_fabric(grid,(),mask)
        self.assertEqual((restricted.columns,restricted.rows),(3,2))
        self.assertEqual(restricted.bounds_px,(50.,30.,350.,230.))
        mask[30:230,350:380] = 255
        self.assertEqual(restrict_grid_to_fabric(grid,(),mask),grid)
        self.assertEqual(restrict_grid_to_fabric(grid,(),None),grid)
        manual = copy.copy(grid)
        from dataclasses import replace
        manual = replace(manual,source='manual')
        self.assertEqual(restrict_grid_to_fabric(manual,(),mask),manual)

    def test_sustained_visible_seams_replace_average_boundaries_without_changing_count(self):
        image = np.full((400,550,3),235,np.uint8)
        xs,ys = (40,150,280,390,510),(40,140,250,360)
        colors = ((170,210,230),(210,170,230),(220,230,165))
        for r in range(3):
            for c in range(4):
                image[ys[r]:ys[r+1],xs[c]:xs[c+1]] = colors[(c+r)%3]
        approximate = PanelGrid.regular(550,400,4,3,bounds_px=(40,40,510,360),confidence=.95,source='visual')
        refined = refine_printed_boundaries(image,approximate)
        self.assertEqual((refined.columns,refined.rows),(4,3))
        np.testing.assert_allclose(refined.x_lines_px,xs,atol=2)
        np.testing.assert_allclose(refined.y_lines_px,ys,atol=2)
        self.assertEqual(refine_printed_boundaries(np.full_like(image,235),approximate),approximate)

    def test_print_seams_override_axis_aligned_artwork_phase_but_not_rotated_or_manual_guides(self):
        from dataclasses import replace
        image = np.full((400,550,3),235,np.uint8)
        xs,ys = (40,150,280,390,510),(40,140,250,360)
        colors = ((170,210,230),(210,170,230),(220,230,165))
        for row in range(3):
            for col in range(4):
                image[ys[row]:ys[row+1],xs[col]:xs[col+1]] = colors[(col+row)%3]
        lattice = PanelGrid.regular(550,400,4,3,bounds_px=(40,35,510,355),confidence=.95,source='pattern')
        lattice = replace(lattice,lattice=((98.75,88.33),(117.5,.01),(.01,106.67)))
        refined = refine_printed_boundaries(image,lattice)
        self.assertEqual((refined.columns,refined.rows),(4,3))
        self.assertEqual(refined.source,'visual')
        self.assertIsNone(refined.lattice)
        np.testing.assert_allclose(refined.x_lines_px,xs,atol=2)
        np.testing.assert_allclose(refined.y_lines_px,ys,atol=2)
        self.assertEqual(refine_printed_boundaries(np.full_like(image,235),lattice),lattice)
        rotated = replace(lattice,lattice=(lattice.lattice[0],(117.5,20.),(15.,106.67)))
        self.assertEqual(refine_printed_boundaries(image,rotated),rotated)
        manual = replace(lattice,source='manual')
        self.assertEqual(refine_printed_boundaries(image,manual),manual)

    def test_real_controls_respect_independently_annotated_print_not_the_cloth_border(self):
        from app.imaging.detector import MotifDetector,DetectorSettings
        root = Path(__file__).parent/'fixtures/generated/straight'
        manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        app = QApplication.instance() or QApplication([])
        for name in ('hearts_6x4.png','dogs_6x4.png','pastel_6x4.png'):
            with self.subTest(source=name):
                truth = next(c for c in manifest['cases'] if c['file']==name)
                image = cv2.imread(str(root/name))
                window = MainWindow();self.addCleanup(window.close)
                window._load_image(image,'independent print boundaries')
                detector = MotifDetector()
                result = detector.detect_with_layout(image,DetectorSettings())
                window._apply_detection_result(result,detector.last_diagnostics)
                self.assertEqual(len(window.detections),truth['expected_compositions'])
                self.assertGreaterEqual(sum(d.enabled for d in window.detections),12)
                def check_corners():
                    # These generated-photo annotations explicitly declare
                    # approximate manual geometry. Require a section conflict
                    # beyond their six-pixel tolerance; SVG rounding is checked
                    # independently at subpixel precision below.
                    for d in window.detections:
                        if not d.enabled:continue
                        tol = .001  # Floating point / SVG rounding only.
                        x,y,w,h = window.mapper.inches_rect_to_pixel(d.square_inches.as_tuple())
                        col = int(np.searchsorted(truth['x_lines_px'],x+w/2)-1)
                        row = int(np.searchsorted(truth['y_lines_px'],y+h/2)-1)
                        annotation_tol = 6.
                        crosses=(x<truth['x_lines_px'][col]-annotation_tol or y<truth['y_lines_px'][row]-annotation_tol
                            or x+w>truth['x_lines_px'][col+1]+annotation_tol or y+h>truth['y_lines_px'][row+1]+annotation_tol)
                        if crosses:
                            self.assertTrue(d.cut_warning_reason(window.mapper)
                                            or d.panel_boundary_review_reason(window.mapper),d.id)
                            item=next(window.panel.detection_list.item(i) for i in range(window.panel.detection_list.count())
                                if window.panel.detection_list.item(i).data(Qt.ItemDataRole.UserRole)==d.id)
                            self.assertNotIn('READY',item.text())
                    # Independently check the serialized SVG, including its
                    # rounding, against every assigned cell polygon.
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(ET.tostring(window.svg_exporter.build_tree(
                        window.mapper,window.detections).getroot()))
                    active = [d for d in window.detections if d.enabled]
                    rectangles = root.findall(f'{{{SVG_NAMESPACE}}}rect')
                    self.assertEqual(len(rectangles),len(active))
                    for d,rect in zip(active,rectangles):
                        if d.panel_boundary_reason(window.mapper):continue
                        values = tuple(float(rect.attrib[key]) for key in ('x','y','width','height'))
                        x,y,w,h = window.mapper.inches_rect_to_pixel(values)
                        polygon = np.asarray(d.cut_region_px,np.float32)
                        for point in ((x,y),(x+w,y),(x+w,y+h),(x,y+h)):
                            self.assertGreaterEqual(cv2.pointPolygonTest(polygon,point,True),-.001)
                check_corners()
                if name.startswith('hearts'):
                    window.change_cut_size(4.8,4.8)
                    self.assertEqual(sum(d.enabled for d in window.detections),24)
                    check_corners()
                app.processEvents()


if __name__ == '__main__':
    unittest.main()
