"""Printed ownership, weak details and machine-bed omissions across layouts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import replace
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from app.imaging.printed_partition import infer_printed_partition,include_faint_ink,_read_truncated_axis,_profiles,_read_axis,_combine_axis_votes
from app.imaging.camera_panel import CameraPanel,source_grid,project_points
from app.imaging.panel_grid import PanelGrid
from app.imaging.logical_layout import LayoutObservation,layout_from_panel_grid
from app.imaging.analysis_frame import scale_grid,translate_grid
from app.imaging.grid_guidance import _trim_unsupported_strips
from app.imaging.detector import MotifDetector,DetectorSettings,DetectionResult,MotifCandidate
from app.geometry.coordinate_mapper import CoordinateMapper
from app.models import Detection,apply_logical_layout
from app.ui.main_window import MainWindow
from app.export.svg_exporter import SVGExporter,SVG_NAMESPACE
from app.export.verifier import verify_export_geometry

PHOTOS=Path(__file__).parents[1]/'docs/qa/customer-20261115/originals'


class PrintedPartitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_plain_weave_and_one_axis_stripes_do_not_establish_panels(self):
        for mode in ('plain','weave','stripes'):
            with self.subTest(mode=mode):
                image=np.full((500,760,3),24,np.uint8)
                image[30:470,30:730]=225
                if mode=='stripes':
                    for y in range(40,460,45):image[y:y+12,30:730]=180
                if mode=='weave':
                    image[30:470:3,30:730]=215;image[30:470,30:730:4]=218
                self.assertIsNone(infer_printed_partition(image))

    def test_partial_photo_keeps_measured_seams_instead_of_redistributing_rows(self):
        profile=np.zeros(380,float)
        for y,weight in ((8,4.),(108,10.),(210,9.),(311,10.)):
            profile+=weight*np.exp(-.5*((np.arange(380)-y)/3)**2)
        result=_read_truncated_axis(profile,False,True)
        self.assertIsNotNone(result)
        np.testing.assert_allclose(result[0],(8,108,210,311,412.5),atol=1)
        self.assertIsNone(_read_truncated_axis(profile,False,False))

    def test_smoothed_divisions_use_their_centres_not_a_filter_plateau_edge(self):
        image=np.full((600,900,3),220,np.uint8)
        xs=np.arange(30,871,140);ys=np.arange(40,561,130)
        for row in range(4):
            for col in range(6):
                image[ys[row]:ys[row+1],xs[col]:xs[col+1]]=(
                    (130,190,230) if (col+row)%2 else (220,190,120))
        for scale in (2.5,3.5):
            profiles=_profiles(image,'colour',scale)
            for profile,expected in zip(profiles,(xs,ys)):
                observed=_read_axis(profile)
                self.assertIsNotNone(observed)
                # The raster colour transition has a half-pixel centre. The
                # previous fit drifted by up to six pixels at the outer edge.
                np.testing.assert_allclose(observed[0],expected,atol=.75)

    def test_dark_analysis_crop_cannot_replace_the_printed_outer_frame(self):
        image=np.full((646,1000,3),230,np.uint8)
        image[:3]=15;image[-3:]=15
        xs=(20,182,340,499,658,818,979);ys=(20,179,336,484,630)
        for y in ys:cv2.line(image,(20,y),(979,y),(150,150,150),1)
        for x in xs:cv2.line(image,(x,20),(x,630),(150,150,150),1)
        for scale in (.5,.8):
            for profile,expected in zip(_profiles(image,'frames',scale),(xs,ys)):
                result=_read_axis(profile)
                self.assertIsNotNone(result)
                np.testing.assert_allclose(result[0],expected,atol=.75)

    def test_automatic_centre_is_invariant_to_size_and_artwork_bounds(self):
        mapper=CoordinateMapper(1000,800,10,8)
        grid=PanelGrid((100.,400.,700.),(100.,400.,700.),1.,'printed')
        d=Detection.from_pixel_center(1,(300,270),mapper,(170,170,70,70))
        layout=layout_from_panel_grid([LayoutObservation(1,(250,250),d.bounding_box_px,(250,250))],grid)
        for box in ((170,170,70,70),(310,200,50,90),(90,190,300,80)):
            d.bounding_box_px=box
            for size in (1.,2.,3.5):
                d.set_cut_size(size,size,mapper)
                apply_logical_layout([d],mapper,layout)
                self.assertEqual(d.center_px,(250.,250.))
                self.assertEqual((d.cut_width_inches,d.cut_height_inches),(size,size))
                self.assertTrue(d.enabled)

    def test_repeated_motif_edge_cannot_shorten_the_first_printed_row(self):
        profile=np.zeros(638,float)
        for y,weight in ((7,4.),(44,8.),(168,10.),(322,10.),(473,10.),(630,5.)):
            profile+=weight*np.exp(-.5*((np.arange(638)-y)/3)**2)
        read=_read_axis(profile)
        self.assertIsNotNone(read)
        np.testing.assert_allclose(read[0],(7,168,322,473,630),atol=1.)

    def test_outer_disagreement_cannot_pass_on_internal_agreement_alone(self):
        first=((8.,108.,208.,308.),.9,{'observed':(True,)*4})
        second=((35.,108.,208.,308.),.9,{'observed':(True,)*4})
        self.assertIsNone(_combine_axis_votes(first,second))
        lines,evidence=_combine_axis_votes(first,second,allow_outer_estimate=True)
        self.assertEqual(lines,(8.,108.,208.,308.))
        self.assertEqual(evidence['disputed'],[0])
        self.assertEqual(evidence['estimated'],[0])
        self.assertGreaterEqual(evidence['spread_px'],27.)

    def test_observed_edge_wins_over_inward_spacing_prior_with_explicit_review(self):
        first=((8.,108.,208.,308.),.9,{'observed':(True,)*4})
        second=((25.,108.,208.,308.),.9,{'observed':(False,True,True,True)})
        lines,evidence=_combine_axis_votes(first,second)
        self.assertEqual(lines,(8.,108.,208.,308.))
        self.assertEqual(evidence['single_scale'],[0])
        self.assertGreaterEqual(evidence['spread_px'],8.5)

    def test_unsupported_divisions_remain_estimates_not_confirmed_edges(self):
        vote=((8.,108.,208.,308.),.9,{'observed':(False,True,True,False)})
        _lines,evidence=_combine_axis_votes(vote,vote)
        self.assertEqual(evidence['estimated'],[0,3])

    @unittest.skipUnless((PHOTOS.parents[1]/'square-contract-20261115/originals/hearts_flowers_6x4.png').exists(),
                         'Private photographic QA original not installed')
    def test_patterned_hearts_keep_outer_seams_and_do_not_create_row_overlaps(self):
        photo=PHOTOS.parents[1]/'square-contract-20261115/originals/hearts_flowers_6x4.png'
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(photo)),'patterned hearts');window.detect_motifs()
        self.assertEqual(len(window.detections),24)
        self.assertEqual((window.logical_layout.columns,window.logical_layout.rows),(6,4))
        for row,expected_y in enumerate((170.,400.,626.,857.)):
            # Independently measured printed seams, not motif/extent centres.
            self.assertLess(abs(window.logical_layout.position(2,row)[1]-expected_y),6.)
        self.assertFalse(any(d.overlaps_cut for d in window.detections))
        self.assertFalse(any(d.panel_boundary_reason(window.mapper) for d in window.detections))

    def test_generated_pastel_uses_visible_outer_edge_and_keeps_independent_centres(self):
        path=Path(__file__).parent/'fixtures/generated/pastel_animals_6x4.png'
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(path)),'pastel printed divisions');window.detect_motifs()
        self.assertEqual(len(window.detections),24)
        # Read on the original source, with labelled pixel rulers, before using
        # detector output. These are the four central printed sections; the
        # six-pixel tolerance belongs to manual measurement, not to cut size.
        # Central transitions read at y=57,285,501,715,963 in source pixels.
        centres=((656.5,171.),(656.,393.),(654.,608.),(651.,839.))
        for row,expected in enumerate(centres):
            np.testing.assert_allclose(window.logical_layout.position(2,row),expected,atol=6.)
        self.assertFalse(any(d.overlaps_cut for d in window.detections))
        self.assertTrue(window.panel_grid.review_reasons)
        for d in window.detections:
            self.assertTrue(d.review_reasons_for(window.mapper))
        exported=SVGExporter().build_tree(window.mapper,window.detections)
        self.assertEqual(len(exported.findall(f'{{{SVG_NAMESPACE}}}rect')),24)

    def test_generated_outer_edge_regressions_keep_centres_at_two_smaller_resolutions(self):
        cases=((Path(__file__).parent/'fixtures/generated/pastel_animals_6x4.png',(171.,393.,608.,839.)),
               (PHOTOS.parents[1]/'square-contract-20261115/originals/hearts_flowers_6x4.png',(170.,400.,626.,857.)))
        for path,expected in cases:
            if not path.exists():continue  # The first case is always installed.
            image=cv2.imread(str(path))
            for scale in (.5,.75):
                with self.subTest(source=path.name,scale=scale):
                    r=MotifDetector().detect_with_layout(cv2.resize(image,None,fx=scale,fy=scale),DetectorSettings())
                    self.assertEqual((r.panel_grid.columns,r.panel_grid.rows),(6,4))
                    self.assertEqual(len(r.candidates),24)
                    layout=layout_from_panel_grid([],r.panel_grid)
                    for row,y in enumerate(expected):
                        self.assertLess(abs(layout.position(2,row)[1]/scale-y),6.)

    @unittest.skipUnless((PHOTOS/'partial.png').exists(),'Private photographic QA original not installed')
    def test_cropped_last_row_preserves_centres_of_complete_rows(self):
        image=cv2.imread(str(PHOTOS/'partial.png'))
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        layout=layout_from_panel_grid([],result.panel_grid)
        # Measured from printed horizontal divisions in the original, not from
        # artwork or from the detector's proposed partition.
        for row,y in enumerate((227.,504.,765.)):
            self.assertLess(abs(layout.position(2,row)[1]-y),12.)
        self.assertLess(abs(layout.position(0,0)[0]-164.),12.)

    def test_measured_uneven_camera_cells_survive_projection_scale_translation_and_trim(self):
        g=PanelGrid((10.,100.,215.,310.),(20.,110.,220.),.95,'printed')
        matrix=np.array([[1.1,.05,30.],[.02,.9,40.],[.0002,.0001,1.]])
        projected=source_grid(CameraPanel(np.zeros((250,340,3),np.uint8),g,matrix))
        layout=layout_from_panel_grid([],projected)
        for r in range(2):
            for c in range(3):
                corners=[(g.x_lines_px[c],g.y_lines_px[r]),(g.x_lines_px[c+1],g.y_lines_px[r]),
                         (g.x_lines_px[c+1],g.y_lines_px[r+1]),(g.x_lines_px[c],g.y_lines_px[r+1])]
                np.testing.assert_allclose(layout.cell_polygon(c,r),project_points(corners,matrix),atol=1e-8)
                center=((g.x_lines_px[c]+g.x_lines_px[c+1])/2,(g.y_lines_px[r]+g.y_lines_px[r+1])/2)
                np.testing.assert_allclose(layout.position(c,r),project_points([center],matrix)[0],atol=1e-8)
        moved=translate_grid(scale_grid(projected,2.,3.),11.,17.)
        np.testing.assert_allclose(moved.cell_regions_px,np.array(projected.cell_regions_px)*[2,3]+[11,17])
        trimmed=_trim_unsupported_strips(projected,np.array([[False,True,True],[False,True,True]]))
        self.assertEqual(trimmed.cell_regions_px[0],projected.cell_regions_px[1])
        self.assertFalse(projected.move_line('x',1,100.).cell_regions_px)
        self.assertFalse(projected.distribute('y').cell_centers_px)

    def test_faint_connected_ear_and_detached_detail_extend_a_strong_body_box(self):
        image=np.full((180,180,3),225,np.uint8)
        cv2.ellipse(image,(90,110),(35,40),0,0,360,(180,180,180),-1)
        cv2.ellipse(image,(75,55),(8,35),-12,0,360,(216,216,216),-1)
        cv2.circle(image,(145,55),9,(214,214,214),-1)
        x,y,w,h=include_faint_ink(image,(55,70,70,80))
        self.assertLessEqual(y,28)
        self.assertGreaterEqual(x+w,150)
        self.assertGreaterEqual(y+h,150)

    def test_printed_frame_and_weave_do_not_expand_a_clear_composition(self):
        from app.imaging.printed_composition import segment_printed_composition
        noise=np.random.default_rng(17).normal(0,2,(200,200,1))
        image=np.clip(np.full((200,200,3),220)+noise,0,255).astype(np.uint8)
        cv2.rectangle(image,(10,10),(189,189),(180,180,180),2)
        cv2.circle(image,(85,95),35,(80,130,180),-1)
        cv2.circle(image,(145,120),9,(75,120,160),-1)
        result=segment_printed_composition(image,(10,10,190,190))
        self.assertIsNotNone(result)
        x,y,w,h=result['box']
        self.assertGreater(x,30);self.assertGreater(y,35)
        self.assertLess(x+w,175);self.assertLess(y+h,160)
        self.assertLessEqual(x,50);self.assertGreaterEqual(x+w,154)

    def test_colour_separation_is_not_mistaken_for_weak_monochrome_artwork(self):
        from app.imaging.printed_composition import segment_printed_composition
        image=np.full((200,200,3),(150,210,220),np.uint8)
        cv2.rectangle(image,(10,10),(189,189),(140,190,205),2)
        # These colours have similar luminance but distinct chroma.
        cv2.circle(image,(90,100),32,(90,175,255),-1)
        result=segment_printed_composition(image,(10,10,190,190))
        self.assertIsNotNone(result)
        x,y,w,h=result['box']
        self.assertGreater(x,40);self.assertGreater(y,45)
        self.assertLess(x+w,145);self.assertLess(y+h,155)
        self.assertFalse(result['issues'])

    def test_offcentre_artwork_cannot_pull_cut_away_from_cell_centre(self):
        mapper=CoordinateMapper(1000,800,10,8)
        grid=PanelGrid((100.,400.,700.),(100.,400.,700.),1.,'manual')
        d=Detection.from_pixel_center(1,(250,250),mapper,(310,200,50,90),
                                     cut_width_inches=2,cut_height_inches=2)
        layout=layout_from_panel_grid([LayoutObservation(1,(335,245),d.bounding_box_px)],grid)
        apply_logical_layout([d],mapper,layout)
        self.assertEqual(d.center_px,(250.,250.))
        self.assertFalse(d.contains_artwork(mapper))
        self.assertIsNotNone(d.cut_warning_reason(mapper))
        self.assertEqual(d.cut_width_inches,2.)
        d.set_cut_size(4,4,mapper)
        self.assertEqual(d.center_px,(250.,250.))
        self.assertTrue(d.enabled)
        self.assertIsNotNone(d.cut_warning_reason(mapper))

    def test_off_bed_grid_row_does_not_return_on_refresh_resize_or_svg_round_trip(self):
        w=MainWindow();self.addCleanup(w.close)
        w._load_image(np.full((600,900,3),225,np.uint8),'bed edge')
        w.change_cut_size(2,2)
        grid=PanelGrid.regular(900,600,3,3,bounds_px=(150,100,750,850),confidence=.99,source='visual')
        candidates=tuple(MotifCandidate((250+c*200,225+r*250),(240+c*200,215+r*250,20,20),.9,400)
                         for r in range(3) for c in range(3))
        w._apply_detection_result(DetectionResult(candidates,grid),{})
        self.assertEqual(len(w.detections),6)
        for _ in range(2):w._refresh()
        w.change_cut_size(1,1)
        self.assertEqual(len(w.detections),6)
        self.assertEqual(len(w.canvas._detections),6)
        self.assertEqual(w.panel.detection_list.count(),6)
        self.assertEqual(len(verify_export_geometry(w.mapper,w.detections).overlay_rectangles_px),6)
        self.assertEqual(len(SVGExporter().build_tree(w.mapper,w.detections)
                             .findall(f'{{{SVG_NAMESPACE}}}rect')),6)

    @unittest.skipUnless((PHOTOS/'beige.png').exists(),'Private photographic QA originals not installed')
    def test_real_customer_and_new_photographic_layouts(self):
        # Expectations and witnesses inspected on originals, never supplied as
        # detector input. New generated layouts have different dimensions.
        cases={'beige':(6,4),'shadow':(6,4),'faint':(6,4),'accessories':(4,3),
               'holdout_pale_5x4':(5,4),'holdout_accessories_4x3':(4,3),'holdout_birds_7x3':(7,3)}
        witnesses={'faint':[[(436,108),(420,270)],[(432,765),(420,927)],[(625,555),(700,705)]],
                   'accessories':[[(160,260),(330,205),(330,330)],[(550,250),(690,190),(690,320)],
                                  [(910,810),(1060,765),(1050,890)]]}
        for name,(cols,rows) in cases.items():
            with self.subTest(name=name):
                image=cv2.imread(str(PHOTOS/(name+'.png')));original=image.copy()
                detector=MotifDetector();result=detector.detect_with_layout(image,DetectorSettings())
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(cols,rows))
                self.assertEqual(len(result.candidates),cols*rows)
                self.assertFalse(any(c.source_incomplete for c in result.candidates))
                layout=layout_from_panel_grid([LayoutObservation(i,c.center_px,c.bounding_box_px,c.layout_center_px)
                                               for i,c in enumerate(result.candidates)],result.panel_grid)
                self.assertTrue(all(m.status=='matched' for m in layout.matches))
                for points in witnesses.get(name,[]):
                    self.assertEqual(sum(all(x<=px<x+bw and y<=py<y+bh for px,py in points)
                        for c in result.candidates for x,y,bw,bh in [c.bounding_box_px]),1,points)
                np.testing.assert_array_equal(image,original)

    @unittest.skipUnless((PHOTOS/'holdout_birds_7x3.png').exists(),'Private photographic QA original not installed')
    def test_perspective_keeps_birds_with_their_flowers_despite_a_bed_highlight(self):
        image=cv2.imread(str(PHOTOS/'holdout_birds_7x3.png'))
        h,w=image.shape[:2]
        transform=cv2.getPerspectiveTransform(np.float32([[0,0],[w,0],[w,h],[0,h]]),
            np.float32([[40,30],[w-50,10],[w-10,h-20],[20,h-45]]))
        altered=cv2.warpPerspective(image,transform,(w,h),borderValue=(24,24,24))
        result=MotifDetector().detect_with_layout(altered,DetectorSettings())
        self.assertEqual(len(result.candidates),21)
        # Heads plus flowers/branches, selected on the original photograph.
        # A count-only assertion missed the yellow bird's absent lower flowers.
        heads=[(178,258),(386,264),(610,256),(810,270),(961,270),(1211,269),(1385,268),
               (191,457),(394,450),(609,466),(765,452),(1007,478),(1213,459),(1412,459),
               (195,657),(415,670),(614,658),(803,675),(1043,658),(1186,668),(1396,697)]
        flowers=[(235,311),(433,330),(616,367),(792,364),(972,368),(1240,365),(1370,376),
                 (202,564),(340,551),(582,591),(806,552),(1036,558),(1150,554),(1414,584),
                 (168,786),(369,799),(527,781),(756,813),(1004,795),(1258,802),(1465,781)]
        owners=[]
        for a,b in zip(heads,flowers):
            points=cv2.perspectiveTransform(np.asarray([a,b],float).reshape(-1,1,2),transform).reshape(-1,2)
            hits=[i for i,c in enumerate(result.candidates) if all(
                x<=px<x+bw and y<=py<y+bh for px,py in points for x,y,bw,bh in [c.bounding_box_px])]
            self.assertEqual(len(hits),1,(a,b))
            owners.extend(hits)
        self.assertEqual(len(set(owners)),21)

    @unittest.skipUnless((PHOTOS/'holdout_pale_5x4.png').exists(),'Private photographic QA original not installed')
    def test_downsampling_cannot_leave_only_a_head_on_a_shadowed_pale_body(self):
        image=cv2.imread(str(PHOTOS/'holdout_pale_5x4.png'))
        small=cv2.resize(image,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
        result=MotifDetector().detect_with_layout(small,DetectorSettings(minimum_area_px=125,
            merge_distance_px_x=7,merge_distance_px_y=7))
        owners=[]
        # Body pixels inspected on the source, including a faint flank below
        # the brighter head. Counts alone accepted two incomplete silhouettes.
        for px,py in ((242.,610.),(1284.,858.)):
            hits=[i for i,c in enumerate(result.candidates) if all((
                c.bounding_box_px[0]<=px*.5<c.bounding_box_px[0]+c.bounding_box_px[2],
                c.bounding_box_px[1]<=py*.5<c.bounding_box_px[1]+c.bounding_box_px[3]))]
            self.assertEqual(len(hits),1,(px,py))
            owners.extend(hits)
        self.assertEqual(len(set(owners)),2)


if __name__=='__main__':unittest.main()
