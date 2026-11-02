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

    def test_sheared_cuts_are_flagged_red_but_never_withheld_from_export(self):
        detections,_ = self.scene()
        # A cut that crosses its panel is flagged red (a warning), never a hard
        # block: it stays enabled, the verifier includes it and export emits it.
        self.assertTrue(all(not d.valid_cut for d in detections))
        self.assertTrue(all('panel boundary' in d.cut_block_reason(self.mapper) for d in detections))
        self.assertTrue(all(d.enabled for d in detections))
        self.assertEqual(len(verify_export_geometry(self.mapper,detections).overlay_rectangles_px),
                         len(detections))
        rects = SVGExporter().build_tree(self.mapper,detections).findall(f'{{{SVG_NAMESPACE}}}rect')
        self.assertEqual(len(rects),len(detections))

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

    def test_manual_move_across_panel_warns_in_red_but_still_exports(self):
        detections,_ = self.scene(1.)
        first = detections[0]
        region = first.cut_region_px
        first.move_to_pixel((105.,100.),self.mapper)
        self.assertEqual(first.cut_region_px,region)
        # Moving the cut across its panel keeps the region and flags it red, but
        # export is never prevented: every enabled cut is emitted.
        self.assertIn('panel boundary',first.cut_block_reason(self.mapper))
        self.assertTrue(first.manual)
        rects = SVGExporter().build_tree(self.mapper,detections).findall(f'{{{SVG_NAMESPACE}}}rect')
        self.assertEqual(len(rects),len(detections))

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

    def test_cells_that_do_not_fit_stay_red_but_enabled_and_toggleable(self):
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
        # The 5in cut does not fit the ~4in cell: flagged red, never auto-disabled.
        self.assertTrue(all(d.enabled and d.cut_region_px is not None
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

    def test_real_controls_respect_independently_annotated_print_not_the_cloth_border(self):
        from app.imaging.detector import MotifDetector,DetectorSettings
        root = Path(__file__).parent/'fixtures/generated/straight'
        manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        app = QApplication.instance() or QApplication([])
        for name in ('hearts_6x4.png','dogs_6x4.png'):
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
                    # A cut that does not fit is now flagged red (cut_block_reason)
                    # instead of being disabled; only the cuts that do fit must
                    # keep every corner inside their printed panel.
                    for d in window.detections:
                        if not d.enabled or d.cut_block_reason(window.mapper):continue
                        x,y,w,h = window.mapper.inches_rect_to_pixel(d.square_inches.as_tuple())
                        col = int(np.searchsorted(truth['x_lines_px'],x+w/2)-1)
                        row = int(np.searchsorted(truth['y_lines_px'],y+h/2)-1)
                        self.assertGreaterEqual(x,truth['x_lines_px'][col])
                        self.assertGreaterEqual(y,truth['y_lines_px'][row])
                        self.assertLessEqual(x+w,truth['x_lines_px'][col+1])
                        self.assertLessEqual(y+h,truth['y_lines_px'][row+1])
                check_corners()
                if name.startswith('hearts'):
                    window.change_cut_size(4.8,4.8)
                    self.assertEqual(sum(d.enabled for d in window.detections),24)
                    check_corners()
                app.processEvents()


if __name__ == '__main__':
    unittest.main()
