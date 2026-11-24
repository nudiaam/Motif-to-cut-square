"""Uncertain outlines must not manufacture red clipping errors or green claims."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog
from app.models import Detection
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_presentation import present_cut
from app.geometry.review_summary import review_counts
from app.imaging.detector import MotifDetector,MotifCandidate,DetectionResult,_scale_candidate,_consolidate_grid_candidates
from app.imaging.panel_grid import PanelGrid
from app.export.svg_exporter import SVGExporter,SVG_NAMESPACE
from app.ui.cut_status import cut_status_color,REVIEW_COLOR,INVALID_COLOR,READY_COLOR
from app.ui.main_window import MainWindow


class ArtworkEvidenceTests(unittest.TestCase):
    def scene(self):
        mapper=CoordinateMapper(1000,800,10,8)
        d=Detection.from_pixel_center(1,(250,250),mapper,(100,100,300,300),
            cut_width_inches=2,cut_height_inches=2,artwork_extent_uncertain=True,
            artwork_support_boxes_px=((210,210,80,80),))
        d.cut_region_px=((100.,100.),(400.,100.),(400.,400.),(100.,400.))
        d.place_on_grid((250.,250.),(0,0),mapper)
        return mapper,d

    def test_uncertain_context_is_a_note_not_a_section_conflict(self):
        mapper,d=self.scene()
        self.assertFalse(d.contains_artwork(mapper))  # The broad context is retained.
        self.assertTrue(d.contains_supported_artwork(mapper))
        self.assertFalse(d.artwork_clipped)
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertTrue(d.review_reasons_for(mapper))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)
        counts=review_counts([d],mapper)
        self.assertEqual(counts['artwork_clipped'],0)
        self.assertEqual(counts['extent_review'],1)

    def test_resolved_ink_clipping_is_detailed_without_changing_section_colour(self):
        mapper,d=self.scene();position=d.center_px
        d.artwork_extent_uncertain=False;d.review_reasons=()
        d.set_cut_size(.5,.5,mapper)
        self.assertEqual(d.center_px,position)
        self.assertTrue(d.artwork_clipped)
        self.assertIsNotNone(d.cut_warning_reason(mapper))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)
        rect=SVGExporter().build_tree(mapper,[d]).find(f'{{{SVG_NAMESPACE}}}rect')
        self.assertEqual(tuple(float(rect.attrib[k]) for k in ('x','y','width','height')),(2.25,2.25,.5,.5))

    def test_supported_detached_part_outside_the_box_keeps_its_clipping_note(self):
        mapper,d=self.scene();d.bounding_box_px=(225,225,50,50)
        d.artwork_extent_uncertain=False;d.review_reasons=()
        d.artwork_support_boxes_px=((225,225,50,50),(360,250,10,10))
        d.recalculate_for_mapper(mapper)
        self.assertTrue(d.contains_artwork(mapper))
        self.assertFalse(d.contains_supported_artwork(mapper))
        self.assertTrue(d.artwork_clipped)
        self.assertIsNotNone(d.cut_warning_reason(mapper))
        self.assertEqual(d.center_px,(250.,250.))

    def test_uncertain_clipped_ink_is_explained_review_not_a_red_verdict(self):
        mapper,d=self.scene();d.set_cut_size(.5,.5,mapper)
        self.assertTrue(d.artwork_clipped)
        self.assertFalse(d.confirmed_artwork_clipped)
        self.assertTrue(d.valid_cut)
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertTrue(any('Possible artwork clipping' in reason for reason in d.review_reasons_for(mapper)))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)
        counts=review_counts([d],mapper)
        self.assertEqual(counts['artwork_clipped'],0)
        self.assertEqual(counts['possible_clipping'],1)
        self.assertEqual(d.bounding_box_px,(100,100,300,300))
        self.assertEqual(d.center_px,(250.,250.))

    def test_missing_assignment_keeps_its_note_without_claiming_a_section_crossing(self):
        mapper,d=self.scene();d.cut_region_px=None;d.cut_region_required=True
        d.recalculate_for_mapper(mapper)
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertTrue(any('assignment is uncertain' in r for r in d.review_reasons_for(mapper)))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)

    def test_uncertain_artwork_cannot_hide_an_actual_section_crossing(self):
        mapper,d=self.scene();d.set_cut_size(3.5,3.5,mapper)
        self.assertIn('panel boundary',d.cut_warning_reason(mapper))
        self.assertEqual(cut_status_color(d,mapper=mapper),REVIEW_COLOR)

    def test_measured_crossing_is_purple_even_with_guide_uncertainty(self):
        mapper,d=self.scene();d.set_cut_size(3.02,3.02,mapper)
        d.cut_region_uncertainty_px=3.;d.recalculate_for_mapper(mapper)
        self.assertIsNotNone(d.panel_boundary_reason(mapper))
        self.assertIsNone(d.confirmed_panel_boundary_reason(mapper))
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertIn('Possible section crossing',d.panel_boundary_review_reason(mapper))
        self.assertEqual(present_cut(d,mapper).state, 'POSSIBLE CROSSING')
        self.assertEqual(cut_status_color(d,mapper=mapper),REVIEW_COLOR)
        # Explicitly confirmed guides have no error band. The identical
        # geometry is then a measured crossing, still checked and exportable.
        before=ET.tostring(SVGExporter().build_tree(mapper,[d]).getroot())
        d.cut_region_uncertainty_px=0.;d.recalculate_for_mapper(mapper)
        self.assertIn('panel boundary',d.cut_warning_reason(mapper))
        self.assertEqual(before,ET.tostring(SVGExporter().build_tree(mapper,[d]).getroot()))
        self.assertEqual(present_cut(d,mapper).state, 'SECTION CROSSING')

    def test_section_crossing_beyond_the_measured_error_remains_a_conflict(self):
        mapper,d=self.scene();d.cut_region_uncertainty_px=3.
        d.set_cut_size(3.2,3.2,mapper)
        self.assertIn('panel boundary',d.cut_warning_reason(mapper))
        self.assertIsNone(d.panel_boundary_review_reason(mapper))

    def test_unresolved_edge_remains_in_notes_when_core_fits(self):
        mapper,d=self.scene();d.artwork_extent_uncertain=False;d.review_reasons=()
        d.recalculate_for_mapper(mapper)
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertTrue(d.artwork_edge_review_reason(mapper))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)

    def test_unverified_ink_is_not_a_measured_section_crossing(self):
        mapper,d=self.scene();d.artwork_support_boxes_px=()
        d.recalculate_for_mapper(mapper)
        self.assertIsNone(d.cut_warning_reason(mapper))
        self.assertTrue(d.review_reasons_for(mapper))
        self.assertEqual(cut_status_color(d,mapper=mapper),READY_COLOR)

    def test_changing_outline_confidence_cannot_change_svg_coordinates(self):
        mapper,d=self.scene();exporter=SVGExporter()
        before=ET.tostring(exporter.build_tree(mapper,[d]).getroot())
        d.artwork_extent_uncertain=False;d.artwork_support_boxes_px=();d.review_reasons=();d.recalculate_for_mapper(mapper)
        self.assertTrue(d.artwork_clipped)
        self.assertIsNotNone(d.cut_warning_reason(mapper))
        self.assertEqual(before,ET.tostring(exporter.build_tree(mapper,[d]).getroot()))

    def test_support_is_scaled_with_the_source_image(self):
        c=MotifCandidate((50,60),(10,20,80,90),.9,100,
            artwork_extent_uncertain=True,artwork_support_boxes_px=((20,30,10,15),))
        scaled=_scale_candidate(c,2.,3.,1000,1000)
        self.assertEqual(scaled.artwork_support_boxes_px,((40,90,20,45),))
        self.assertTrue(scaled.artwork_extent_uncertain)

    def test_merging_keeps_supported_accessories_and_uncertain_context_distinct(self):
        grid=PanelGrid((0.,300.,600.),(0.,300.,600.),1.,'manual')
        a=MotifCandidate((150,150),(100,100,100,100),.9,100,(150,150),
            artwork_extent_uncertain=True,artwork_support_boxes_px=((130,130,30,30),))
        b=MotifCandidate((195,145),(190,130,20,20),.8,40,(150,150))
        result=_consolidate_grid_candidates((a,b),grid)
        self.assertEqual(len(result),1)
        self.assertTrue(result[0].artwork_extent_uncertain)
        self.assertEqual(set(result[0].artwork_support_boxes_px),{(130,130,30,30),(190,130,20,20)})

    def test_confirmed_guides_use_the_same_evidence_without_changing_extraction(self):
        import cv2
        image=np.full((360,360,3),225,np.uint8)
        grid=PanelGrid((20.,180.,340.),(20.,180.,340.),1.,'manual')
        candidates=[]
        for i,(x,y) in enumerate(((100,100),(260,100),(100,260),(260,260))):
            cv2.circle(image,(x,y),28,(80,130,180),-1)
            candidates.append(MotifCandidate((x,y),(x-70,y-70,140,140),.9,2000,(x,y)))
        source=image.copy();detector=MotifDetector()
        result=detector.finalize_compositions(image,candidates,grid)
        self.assertEqual([c.bounding_box_px for c in result],[c.bounding_box_px for c in candidates])
        self.assertEqual([c.layout_center_px for c in result],[c.layout_center_px for c in candidates])
        self.assertTrue(all(c.artwork_extent_uncertain for c in result))
        self.assertTrue(all(c.artwork_support_boxes_px for c in result))
        np.testing.assert_array_equal(image,source)


class ArtworkEvidenceUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_review_is_distinct_from_error_and_checked_review_still_exports(self):
        w=MainWindow();self.addCleanup(w.close)
        w._load_image(np.full((600,600,3),225,np.uint8),'outline confidence')
        w.change_cut_size(2,2)
        grid=PanelGrid((100.,300.,500.),(100.,300.,500.),1.,'manual')
        candidates=[]
        for i,(x,y) in enumerate(((200,200),(400,200),(200,400),(400,400))):
            candidates.append(MotifCandidate((x,y),(x-100,y-100,200,200) if i==0 else (x-10,y-10,20,20),.9,400,
                (x,y),artwork_extent_uncertain=i==0,artwork_support_boxes_px=((x-10,y-10,20,20),)))
        w._apply_detection_result(DetectionResult(tuple(candidates),grid),{})
        d=w.detections[0];position=d.center_px
        self.assertIsNone(d.cut_warning_reason(w.mapper))
        item=w.panel.detection_list.item(0)
        self.assertIn('READY',item.text());self.assertNotIn('WARNING',item.text())
        self.assertEqual(item.foreground().color().name(),READY_COLOR)
        self.assertEqual(w.panel.valid_value_label.text(),'4')
        self.assertIn('4 inside measured sections; 0 crossing',w.panel.review_breakdown_label.text())
        w.confirm_detection();w.show_preflight()
        self.assertNotIn('TO REVIEW',w.panel.verification_label.text())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'review.svg'
            with patch.object(QMessageBox,'warning',return_value=QMessageBox.StandardButton.Yes) as message, \
                 patch.object(QFileDialog,'getSaveFileName',return_value=(str(path),'SVG')), \
                 patch.object(QMessageBox,'information'):
                w.export_svg()
            message.assert_not_called()
            self.assertEqual(len(ET.parse(path).getroot().findall(f'{{{SVG_NAMESPACE}}}rect')),4)
        w.change_cut_size(.5,.5)
        self.assertEqual(d.center_px,position)
        self.assertIsNone(d.cut_warning_reason(w.mapper))
        self.assertIn('READY',w.panel.detection_list.item(0).text())
        self.assertIn('Possible artwork clipping',w.panel.detection_list.item(0).toolTip())
        d.artwork_extent_uncertain=False;d.review_reasons=();d.recalculate_for_mapper(w.mapper);w._refresh()
        self.assertIsNotNone(d.cut_warning_reason(w.mapper))
        self.assertIn('READY',w.panel.detection_list.item(0).text())


if __name__=='__main__':unittest.main()
