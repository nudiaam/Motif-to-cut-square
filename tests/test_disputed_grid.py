"""Sparse fragments cannot veto a grid without checking its local pixels."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.imaging.detector import MotifDetector, MotifCandidate, DetectorSettings
from app.imaging.panel_grid import PanelGrid


class DisputedGridTests(unittest.TestCase):
    def test_varied_background_original_preserves_24_distinct_motifs(self):
        path=Path(__file__).parent/'fixtures/acceptance/mixed_icons_6x4.png'
        image=cv2.imread(str(path));original=image.copy()
        detector=MotifDetector();result=detector.detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        # Hand-inspected body points, independent of the inferred grid.
        owners=set()
        for y in (190,385,605,830):
            for x in (195,420,650,880,1110,1340):
                hits=[i for i,c in enumerate(result.candidates)
                      if c.bounding_box_px[0]<=x<=c.bounding_box_px[0]+c.bounding_box_px[2]
                      and c.bounding_box_px[1]<=y<=c.bounding_box_px[1]+c.bounding_box_px[3]]
                self.assertEqual(len(hits),1,(x,y,hits))
                self.assertNotIn(hits[0],owners);owners.add(hits[0])
        rechecks=[s for s in detector.last_diagnostics['detection_plans']
                  if s['stage']=='disputed_grid_recheck']
        self.assertEqual(len(rechecks),1)
        self.assertTrue(rechecks[0]['corroborated'])
        self.assertGreaterEqual(rechecks[0]['aligned_fraction'],.90)
        self.assertEqual(rechecks[0]['unique_assignment_fraction'],1.)
        self.assertLess(rechecks[0]['initial_evidence_count'],24)
        np.testing.assert_array_equal(image,original)
        json.dumps(detector.last_diagnostics)

    def test_local_probe_cannot_justify_grouping_many_distinct_figures(self):
        image=np.full((400,600,3),200,np.uint8)
        candidates=[MotifCandidate((50+c*100,50+r*100),(35+c*100,35+r*100,30,30),.9,900)
                    for r in range(4) for c in range(6)]
        coarse=PanelGrid.regular(600,400,3,2,confidence=.95,source='camera')
        detector=MotifDetector()
        with patch('app.imaging.detector.infer_panel_grid',return_value=None), \
             patch('app.imaging.detector.infer_camera_panel',return_value=SimpleNamespace(grid=coarse)), \
             patch('app.imaging.detector.source_grid',return_value=coarse), \
             patch('app.imaging.detector.infer_repeated_artwork',return_value=None), \
             patch('app.imaging.detector.infer_seam_grid',return_value=None), \
             patch('app.imaging.detector._infer_regular_tile_grid',return_value=None), \
             patch('app.imaging.detector.stable_artwork_grid',return_value=None), \
             patch.object(detector,'_detect_once',return_value=candidates), \
             patch.object(detector,'_camera_candidates') as probe:
            result=detector._detect_layout(image,DetectorSettings())
        probe.assert_not_called()
        self.assertIsNone(result.panel_grid)
        self.assertEqual(len(result.candidates),24)


if __name__=='__main__':unittest.main()
