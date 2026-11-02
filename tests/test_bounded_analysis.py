"""Resolution, source-coordinate and cache contracts, independent of motif count."""
from dataclasses import replace
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from app.imaging.analysis_frame import scale_grid
from app.imaging.detector import DetectionResult,DetectorSettings,MotifCandidate,MotifDetector
from app.imaging.logical_layout import layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.imaging.run_diagnostics import image_identity
from app.imaging.scene_profile import POLICY


class BoundedAnalysisTests(unittest.TestCase):
    def test_large_input_is_bounded_and_public_geometry_settings_identity_are_source_based(self):
        image = np.full((1200,2400,3),230,np.uint8)
        original = image.copy()
        detector = MotifDetector()
        settings = DetectorSettings(minimum_area_px=1000,merge_distance_px_x=20,merge_distance_px_y=30)
        def analyse(work,effective):
            self.assertEqual(work.shape[:2],(768,1536))
            self.assertEqual(effective.minimum_area_px,410)
            self.assertAlmostEqual(effective.merge_distance_px_x,12.8)
            self.assertAlmostEqual(effective.merge_distance_px_y,19.2)
            detector.last_diagnostics = {'timings_seconds':{'total':.01},'illumination':None}
            grid = PanelGrid.regular(1536,768,3,2,bounds_px=(0.,0.,1536.,768.),confidence=.95,source='visual')
            return DetectionResult((MotifCandidate((100.,200.),(90,180,20,40),.9,800,(101.,201.)),),grid)
        with patch.object(detector,'_detect_at_analysis_resolution',side_effect=analyse), \
             patch('app.imaging.detector.review_extents',side_effect=lambda image,candidates,grid:candidates):
            result = detector.detect_with_layout(image,settings)
        np.testing.assert_array_equal(image,original)
        self.assertEqual(result.candidates[0].center_px,(156.25,312.5))
        self.assertEqual(result.candidates[0].bounding_box_px,(140,281,32,63))
        self.assertEqual(result.panel_grid.x_lines_px,(0.,800.,1600.,2400.))
        self.assertEqual(detector.last_diagnostics['identity']['image'],image_identity(image))
        self.assertEqual(detector.last_diagnostics['settings']['minimum_area_px'],1000)
        self.assertEqual(detector.last_diagnostics['analysis_frame']['public_geometry'],'source_pixels')
        self.assertIsNone(detector._contrast_cache)

    def test_projection_and_lattice_scale_together_in_both_directions(self):
        grid = PanelGrid((10.,110.,210.),(20.,120.,220.),.9,'camera',
            ((60.,70.),(100.,2.),(3.,100.)),((100.,3.,60.),(2.,100.,70.),(.001,.002,1.)))
        scaled = scale_grid(grid,2.,3.)
        before,after = layout_from_panel_grid([],grid),layout_from_panel_grid([],scaled)
        for c,r in ((0,0),(1,0),(0,1),(1,1),(.5,.5)):
            x,y = before.position(c,r)
            np.testing.assert_allclose(after.position(c,r),(2*x,3*y),atol=1e-10)
        restored = scale_grid(scaled,.5,1/3)
        np.testing.assert_allclose(restored.projection,grid.projection)

    def test_sensitivity_passes_share_fields_but_do_not_modify_cached_data(self):
        detector = MotifDetector()
        detector._contrast_cache = {}
        image = np.full((500,600,3),230,np.uint8)
        cv2.circle(image,(250,250),50,(30,40,50),-1)
        with patch.object(detector,'_contrast_fields',wraps=detector._contrast_fields) as fields:
            first = detector._detect_once(image,DetectorSettings())
            detector._detect_once(image,replace(DetectorSettings(),sensitivity=75))
            again = detector._detect_once(image,DetectorSettings())
            self.assertEqual(fields.call_count,1)
            self.assertEqual(first,again)

    def test_cache_is_released_after_processing_failure(self):
        detector = MotifDetector()
        def fail(*args):
            detector._contrast_cache = {'owned':'temporary'}
            raise ValueError('controlled failure')
        with patch.object(detector,'_detect_at_analysis_resolution',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'controlled failure'):
                detector.detect_with_layout(np.zeros((100,100,3),np.uint8),DetectorSettings())
        self.assertIsNone(detector._contrast_cache)


if __name__ == '__main__':
    unittest.main()
