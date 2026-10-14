"""Whole ownership and common cut centring across luminance/colour routes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import replace
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from app.imaging.detector import MotifDetector,DetectorSettings,MotifCandidate
from app.imaging.content_preservation import foreground_mask,preservation
from app.imaging.logical_layout import LayoutObservation,layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.geometry.composition_phase import contain_automatic_compositions
from app.geometry.coordinate_mapper import CoordinateMapper
from app.models import Detection
from app.ui.main_window import MainWindow
from tests.evaluate_composition_groups import POINTS,assess
from tests.evaluate_accessory_columns import variants

FIXTURES=Path(__file__).parent/'fixtures/customer_20261012'

class CompositionContentTests(unittest.TestCase):
    def test_mixed_colour_and_monochrome_groups_survive_photographic_variations(self):
        for name,shape in (('cocktails',(6,3)),('quotes',(4,4))):
            for variant,pixels,transform,settings in variants(cv2.imread(str(FIXTURES/f'{name}_groups.png'))):
                with self.subTest(source=name,variant=variant):
                    original=pixels.copy();d=MotifDetector();r=d.detect_with_layout(pixels,settings)
                    self.assertEqual((r.panel_grid.columns,r.panel_grid.rows),shape)
                    self.assertEqual(len(r.candidates),len(POINTS[name]))
                    self.assertEqual(assess(r,transform,name),{'whole_groups':len(POINTS[name]),'failed_groups':[]})
                    # A correct count must not hide text or ingredients from the
                    # neighbouring composition inside a result's source limits.
                    for points in POINTS[name]:
                        group=cv2.perspectiveTransform(np.asarray(points,float).reshape(-1,1,2),transform).reshape(-1,2)
                        owner=next(c for c in r.candidates if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in group))
                        for other in POINTS[name]:
                            if other is points:continue
                            x,y=cv2.perspectiveTransform(np.asarray([other[0]],float).reshape(-1,1,2),transform).reshape(-1,2)[0]
                            bx,by,bw,bh=owner.bounding_box_px
                            self.assertFalse(bx<=x<bx+bw and by<=y<by+bh)
                    np.testing.assert_array_equal(pixels,original)

    def test_one_reference_cannot_be_certified_by_separate_text_and_decoration_boxes(self):
        image=np.full((240,320,3),230,np.uint8)
        cv2.rectangle(image,(55,50),(120,75),(20,20,20),-1)
        cv2.circle(image,(130,130),16,(100,180,220),-1)
        reference=MotifCandidate((100,90),(50,45,105,105),.9,2500)
        text=MotifCandidate((88,63),(50,45,75,35),.9,1700)
        colour=MotifCandidate((130,130),(110,110,40,40),.9,800)
        mask=foreground_mask(image);self.assertIsNotNone(mask)
        self.assertFalse(preservation([reference],[colour],mask)['approved'])
        self.assertFalse(preservation([reference],[text,colour],mask)['approved'])
        self.assertTrue(preservation([reference],[reference],mask)['approved'])

    def test_source_edge_fragment_is_not_discarded_by_an_empty_cloth_mask(self):
        c=MotifCandidate((60,195),(45,180,30,20),.9,300)
        other=MotifCandidate((60,150),(45,135,30,30),.9,500)
        verdict=preservation([c],[other],np.zeros((200,200),bool))
        self.assertFalse(verdict['approved'])

    def test_ui_keeps_whole_groups_and_reports_insufficient_cut_size(self):
        app=QApplication.instance() or QApplication([])
        for name in POINTS:
            with self.subTest(source=name):
                window=MainWindow();self.addCleanup(window.close)
                window._load_image(cv2.imread(str(FIXTURES/f'{name}_groups.png')),name)
                window.change_cut_size(4,4);window.detect_motifs();app.processEvents()
                self.assertEqual(len(window.detections),len(POINTS[name]))
                self.assertTrue(all(d.grid_positioned and not d.inferred for d in window.detections))
                self.assertTrue(any(d.artwork_clipped for d in window.detections))
                positions=[d.center_px for d in window.detections]
                window.confirm_detection()
                self.assertEqual([d.center_px for d in window.detections],positions)

class CommonCompositionPhaseTests(unittest.TestCase):
    def scene(self):
        mapper=CoordinateMapper(220,220,22,22)
        grid=PanelGrid.regular(220,220,2,2,bounds_px=(0,0,160,160),confidence=.99,source='pattern')
        detections=[];observations=[]
        for i,(x,y) in enumerate(((40,40),(120,40),(40,120),(120,120)),1):
            box=(x+14,y-10,20,20)
            d=Detection.from_pixel_center(i,(x,y),mapper,box,cut_width_inches=4,cut_height_inches=4)
            detections.append(d);observations.append(LayoutObservation(i,(x+24,y),box,(x,y)))
        return mapper,detections,layout_from_panel_grid(observations,grid)

    def test_common_translation_contains_bounds_without_deforming_rows_or_columns(self):
        mapper,detections,layout=self.scene()
        shifted=contain_automatic_compositions(layout,detections,mapper,4,4)
        self.assertEqual(shifted.column_vector_px,layout.column_vector_px)
        self.assertEqual(shifted.row_vector_px,layout.row_vector_px)
        self.assertNotEqual(shifted.origin_px,layout.origin_px)
        for d,m in zip(detections,sorted(shifted.matches,key=lambda m:m.detection_id)):
            d.place_on_grid(shifted.position(m.column,m.row),(m.column,m.row),mapper)
            self.assertTrue(d.contains_artwork(mapper));self.assertTrue(d.valid_cut)

    def test_impossible_size_or_manual_guides_keep_the_layout(self):
        mapper,detections,layout=self.scene()
        self.assertEqual(contain_automatic_compositions(layout,detections,mapper,1,1),layout)
        self.assertEqual(contain_automatic_compositions(replace(layout,source='manual'),detections,mapper,4,4),replace(layout,source='manual'))
        detections[0].manual=True
        self.assertEqual(contain_automatic_compositions(layout,detections,mapper,4,4),layout)

    def test_conflicting_containment_intervals_do_not_move_cuts_independently(self):
        mapper,detections,layout=self.scene()
        detections[1].bounding_box_px=(86,30,20,20)
        self.assertEqual(contain_automatic_compositions(layout,detections,mapper,4,4),layout)

if __name__=='__main__':unittest.main()
