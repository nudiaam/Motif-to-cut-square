"""Independent section landmarks, blank margins and final cut presentation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import replace
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.printed_partition import infer_printed_partition
from app.imaging.section_evidence import trim_unprinted_extensions,refine_projected_sections
from app.imaging.printed_composition import _diffuse_texture_only
from app.geometry.cut_presentation import present_cut,READY_COLOR,REVIEW_COLOR,INVALID_COLOR
from app.geometry.coordinate_mapper import CoordinateMapper
from app.imaging.panel_grid import PanelGrid
from app.imaging.detector import DetectionResult,MotifCandidate
from app.models import Detection
from app.ui.main_window import MainWindow
from app.export.svg_exporter import SVG_NAMESPACE

FIXTURES=Path(__file__).parent/'fixtures/generated'


class SectionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_white_separators_are_measured_locally_on_original_pixels(self):
        image=cv2.imread(str(FIXTURES/'printed_white_gutters_6x4.png'))
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        grid=result.panel_grid
        # Centres of white strips read independently in the original before
        # using detector output. No filename/count/landmarks enter production.
        vertical=((317.5,544.5,767.,991.5,1220.5),(315.5,544.5,768.,992.5,1220.5),
                  (314.5,544.,768.,991.5,1221.),(313.5,543.5,767.5,992.,1221.5))
        horizontal=((327.5,537.,734.),(327.5,537.,735.5),(327.5,537.,735.5),
                    (327.5,537.,735.5),(328.5,537.5,736.),(329.,539.,737.))
        errors=[]
        for row,values in enumerate(vertical):
            for col,value in enumerate(values,1):
                polygon=np.array(grid.cell_regions_px[row*6+col])
                errors.append(abs(float(polygon[[0,3],0].mean())-value))
        for col,values in enumerate(horizontal):
            for row,value in enumerate(values,1):
                polygon=np.array(grid.cell_regions_px[row*6+col])
                errors.append(abs(float(polygon[[0,1],1].mean())-value))
        self.assertLess(max(errors),1.5)
        self.assertLess(float(np.mean(errors)),.6)
        # Shared corners prevent overlapping, independently refined cells.
        for row in range(4):
            for col in range(5):
                a=np.array(grid.cell_regions_px[row*6+col]);b=np.array(grid.cell_regions_px[row*6+col+1])
                np.testing.assert_allclose(a[[1,2]],b[[0,3]],atol=1e-8)

    def test_blank_hem_is_outside_observed_print_for_all_four_sides(self):
        image=cv2.imread(str(FIXTURES/'framed_animals_blank_hem_6x4.png'))
        for transpose in (False,True):
            for flipped in (False,True):
                with self.subTest(transpose=transpose,flipped=flipped):
                    pixels=cv2.flip(image,0) if flipped else image
                    if transpose:pixels=cv2.transpose(pixels)
                    panel=infer_printed_partition(pixels)
                    self.assertIsNotNone(panel)
                    self.assertEqual((panel.grid.columns,panel.grid.rows),(4,6) if transpose else (6,4))
                    # All remaining borders must be observed; a finite-frame
                    # sequence may avoid the spurious extension altogether.
                    self.assertTrue(all(not v['estimated'] for v in panel.partition_evidence['axis_observations']))

    def test_continuing_vertical_rules_do_not_allow_removing_a_real_row(self):
        image=np.full((880,850,3),225,np.uint8)
        xs=(40.,160.,280.,400.,520.,640.,760.);ys=(20.,180.,340.,500.,660.,820.)
        for y in ys[:-1]:cv2.line(image,(40,int(y)),(760,int(y)),(40,40,40),2)
        for x in xs:cv2.line(image,(int(x),20),(int(x),820),(40,40,40),2)
        observations=[{'estimated':[]},{'estimated':[5]}]
        axes,removed=trim_unprinted_extensions(image,(xs,ys),observations)
        self.assertFalse(removed);self.assertEqual(axes,(xs,ys))
        image[665:]=225  # A closed frame and no continuing stems.
        axes,removed=trim_unprinted_extensions(image,(xs,ys),observations)
        self.assertEqual(axes[1],ys[:-1]);self.assertEqual(len(removed),1)

    def test_diffuse_weave_veto_retains_a_coherent_faint_component(self):
        ink=np.zeros((150,150),np.uint8)
        for y in range(10,145,15):
            for x in range(10,145,15):ink[y:y+2,x:x+2]=1
        self.assertTrue(_diffuse_texture_only(ink,(0,0,150,150)))
        cv2.ellipse(ink,(75,75),(25,40),0,0,360,1,1)
        self.assertFalse(_diffuse_texture_only(ink,(0,0,150,150)))

    def test_final_colours_depend_on_section_geometry_not_outline_notes(self):
        mapper=CoordinateMapper(600,600,12,12)
        d=Detection.from_pixel_center(1,(250,250),mapper,(100,100,300,300),
            cut_width_inches=2,cut_height_inches=2,artwork_extent_uncertain=True)
        d.cut_region_px=((150.,150.),(350.,150.),(350.,350.),(150.,350.))
        self.assertEqual(present_cut(d,mapper).color,READY_COLOR)
        self.assertTrue(d.review_reasons_for(mapper))
        d.set_cut_size(4.2,4.2,mapper)
        self.assertEqual(present_cut(d,mapper).color,REVIEW_COLOR)
        self.assertIn('section boundary',present_cut(d,mapper).reason)
        d.set_cut_size(20,20,mapper)
        self.assertEqual(present_cut(d,mapper).color,INVALID_COLOR)

    def test_inside_the_guide_error_band_is_green_until_the_rectangle_crosses(self):
        mapper=CoordinateMapper(600,600,12,12)
        d=Detection.from_pixel_center(1,(250,250),mapper,cut_width_inches=3.98,cut_height_inches=3.98)
        d.cut_region_px=((150.,150.),(350.,150.),(350.,350.),(150.,350.))
        d.cut_region_uncertainty_px=4.
        self.assertTrue(d.panel_boundary_review_reason(mapper))
        self.assertIsNone(d.panel_boundary_reason(mapper))
        self.assertEqual(present_cut(d,mapper).color,READY_COLOR)
        d.set_cut_size(4.02,4.02,mapper)
        self.assertTrue(d.panel_boundary_reason(mapper))
        self.assertEqual(present_cut(d,mapper).color,REVIEW_COLOR)

    def test_unobserved_grid_cell_never_becomes_an_automatic_svg_cut(self):
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(np.full((600,900,3),225,np.uint8),'empty section')
        window.change_cut_size(2,2)
        grid=PanelGrid((100.,400.,700.),(100.,300.,500.),.99,'printed')
        candidates=tuple(MotifCandidate((x,y),(x-25,y-25,50,50),.9,800,(x,y))
                         for x,y in ((250.,200.),(550.,200.),(250.,400.)))
        window._apply_detection_result(DetectionResult(candidates,grid),{})
        self.assertEqual(len(window.detections),3)
        self.assertEqual(len(window.logical_layout.missing),1)
        for size in (2.,1.,2.):
            window.change_cut_size(size,size);window._refresh()
            self.assertEqual(len(window.detections),3)
            self.assertFalse(any(d.inferred for d in window.detections))
            self.assertEqual(len(window.svg_exporter.build_tree(window.mapper,window.detections).findall(f'{{{SVG_NAMESPACE}}}rect')),3)

    def test_actual_faint_lamb_is_recovered_but_the_neighbouring_empty_position_is_not(self):
        # The original visibly contains 23 animals: an empty position in the
        # second row and a very pale lamb in the third. The old 24-cut output
        # filled both gaps without image evidence; a count alone hid the error.
        path=Path(__file__).parent/'fixtures/acceptance/batch_20260923/case_09.png'
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(path)),'actual ink versus empty cloth')
        window.panel.cut_width_spin.setValue(4.);window.detect_motifs()
        self.assertEqual(len(window.detections),23)
        self.assertFalse(any(d.inferred for d in window.detections))
        self.assertFalse(any(d.layout_cell==(2,1) for d in window.detections))
        lamb=next(d for d in window.detections if d.layout_cell==(4,2))
        x,y,w,h=lamb.bounding_box_px
        self.assertTrue(x<=1050<x+w and y<=650<y+h)
        points=[(165,225),(395,217),(618,224),(830,210),(1055,215),(1280,225),
                (165,440),(390,430),(825,440),(1055,440),(1290,440),
                (165,655),(390,650),(615,650),(830,665),(1050,650),(1280,650),
                (165,885),(390,880),(615,880),(830,880),(1055,880),(1280,885)]
        owners=[]
        for px,py in points:
            hits=[d.id for d in window.detections if d.bounding_box_px is not None
                  for bx,by,bw,bh in [d.bounding_box_px] if bx<=px<bx+bw and by<=py<by+bh]
            self.assertEqual(len(hits),1,(px,py));owners+=hits
        self.assertEqual(len(set(owners)),23)
        window._refresh();window.change_cut_size(3.8,3.8)
        self.assertEqual(len(window.detections),23)
        self.assertEqual(len(window.svg_exporter.build_tree(window.mapper,window.detections).findall(f'{{{SVG_NAMESPACE}}}rect')),23)

    def test_real_photos_export_same_requested_rectangles_and_keep_centres(self):
        for name in ('printed_white_gutters_6x4.png','framed_animals_blank_hem_6x4.png'):
            with self.subTest(source=name):
                window=MainWindow();self.addCleanup(window.close)
                window._load_image(cv2.imread(str(FIXTURES/name)),name)
                window.panel.cut_width_spin.setValue(4.);window.detect_motifs()
                self.assertEqual(len(window.detections),24)
                self.assertEqual((window.logical_layout.columns,window.logical_layout.rows),(6,4))
                self.assertTrue(all(present_cut(d,window.mapper).color==READY_COLOR for d in window.detections))
                self.assertEqual(window.panel.valid_value_label.text(),'24')
                self.assertEqual(window._cut_warning_count(),0)
                centres={d.id:d.center_px for d in window.detections}
                for size in (4.,5.,3.8):
                    window.panel.cut_width_spin.setValue(size)
                    self.assertEqual(centres,{d.id:d.center_px for d in window.detections})
                    rects=window.svg_exporter.build_tree(window.mapper,window.detections).findall(f'{{{SVG_NAMESPACE}}}rect')
                    self.assertEqual(len(rects),24)
                    for d,rect in zip(window.detections,rects):
                        for key,value in zip(('x','y','width','height'),d.square_inches.as_tuple()):
                            self.assertAlmostEqual(float(rect.attrib[key]),value,places=5)
                    if size==5.:
                        self.assertTrue(any(present_cut(d,window.mapper).color==REVIEW_COLOR for d in window.detections))
                        self.assertFalse(any(present_cut(d,window.mapper).color==INVALID_COLOR for d in window.detections))
                window.set_detection_enabled(window.detections[0].id,False)
                self.assertEqual(len(window.svg_exporter.build_tree(window.mapper,window.detections).findall(f'{{{SVG_NAMESPACE}}}rect')),23)


if __name__=='__main__':unittest.main()
