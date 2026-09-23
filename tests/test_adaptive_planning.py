"""General mechanisms: backgrounds, neighbouring panels, shadows and lost extent."""
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.detection_plan import plan_zones
from app.imaging.extent_review import review_extents
from app.imaging.panel_grid import PanelGrid
from app.imaging.region_analysis import segment_zone
from app.imaging.scene_profile import illumination_view
from app.imaging.bed_reference import locate_bright_fabric


class AdaptivePlanningTests(unittest.TestCase):
    def test_strong_lower_shadow_keeps_the_fourth_row(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/generated/straight/dogs_6x4.png'))
        shadow=image.copy()
        shadow[730:]=(shadow[730:].astype(np.float32)*.45).astype(np.uint8)
        original=shadow.copy()
        detector=MotifDetector()
        result=detector.detect_with_layout(shadow,DetectorSettings())
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        self.assertEqual(len(result.candidates),24)
        self.assertIsNotNone(detector.last_diagnostics['illumination'])
        self.assertTrue(any('shadowed band' in reason for c in result.candidates for reason in c.review_reasons))
        np.testing.assert_array_equal(shadow,original)

    def test_global_shadow_analysis_preserves_a_coloured_printed_band(self):
        from tests.test_visual_grid import printed_fabric
        image=printed_fabric(6,4)
        image[380:470,60:700]=(100,45,25)
        self.assertIsNone(illumination_view(image,locate_bright_fabric(image).mask))

    def test_recovered_floral_panel_keeps_all_compositions(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/floral_patchwork_recovered.png'))
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))

    def test_different_neighbour_background_does_not_prevent_full_body(self):
        image=np.full((240,240,3),(120,175,210),np.uint8)
        image[20:220,20:220]=(235,235,235)
        cv2.circle(image,(120,83),22,(30,50,80),-1)
        cv2.rectangle(image,(107,92),(133,185),(160,170,180),-1)
        result=segment_zone(image,150,(20,20,220,220))
        self.assertIsNotNone(result)
        x,y,w,h=result['box']
        self.assertGreaterEqual(y+h,185)
        self.assertGreaterEqual(x,95)
        self.assertLessEqual(x+w,145)

    def test_patterned_background_is_not_an_extension_of_complete_artwork(self):
        image=np.full((200,200,3),225,np.uint8)
        for x in range(0,200,16):image[:,x:x+5]=195
        cv2.ellipse(image,(100,100),(30,48),0,0,360,(50,90,120),-1)
        candidate=MotifCandidate((100,100),(70,52,61,97),.9,4000)
        self.assertFalse(review_extents(image,(candidate,))[0].review_reasons)

    def test_full_cell_review_finds_body_far_beyond_head(self):
        image=np.full((400,400,3),235,np.uint8)
        cv2.circle(image,(100,50),20,(30,60,90),-1)
        cv2.rectangle(image,(87,55),(113,174),(130,150,170),-1)
        head=MotifCandidate((100,50),(80,30,41,41),.9,1200)
        grid=PanelGrid.regular(400,400,2,2,confidence=.95)
        reviewed=review_extents(image,(head,),grid)[0]
        self.assertTrue(reviewed.review_reasons)
        self.assertEqual(reviewed.bounding_box_px,head.bounding_box_px)

    def test_blank_pattern_does_not_become_a_motif(self):
        image=np.full((160,160,3),225,np.uint8)
        for x in range(0,160,16):image[:,x:x+5]=195
        self.assertIsNone(segment_zone(image,120,(0,0,160,160)))

    def test_row_shadow_requires_agreement_across_columns(self):
        image=np.full((400,600,3),230,np.uint8)
        grid=PanelGrid.regular(600,400,6,4,confidence=.95)
        image[300:]=155
        zones=plan_zones(image,grid)
        self.assertTrue(all(z.shadow_gain > 1 for z in zones if z.row==3))
        self.assertTrue(all(z.shadow_gain==1 for z in zones if z.row!=3))
        image[:]=230;image[300:,:100]=(90,90,90)
        self.assertTrue(all(z.shadow_gain==1 for z in plan_zones(image,grid)))

    def test_coloured_printed_row_is_not_a_neutral_shadow(self):
        image=np.full((400,600,3),230,np.uint8)
        image[300:]=(140,70,30)
        grid=PanelGrid.regular(600,400,6,4,confidence=.95)
        self.assertTrue(all(z.shadow_gain==1 for z in plan_zones(image,grid)))

    def test_plans_are_exportable_and_original_pixels_unchanged(self):
        from tests.test_visual_grid import printed_fabric
        import json
        image=printed_fabric(4,3);original=image.copy()
        detector=MotifDetector()
        result=detector.detect_with_layout(image,DetectorSettings(minimum_area_px=150))
        self.assertEqual(len(result.candidates),12)
        self.assertTrue(detector.last_diagnostics['detection_plans'])
        json.dumps(detector.last_diagnostics)
        np.testing.assert_array_equal(image,original)


if __name__=='__main__':unittest.main()
