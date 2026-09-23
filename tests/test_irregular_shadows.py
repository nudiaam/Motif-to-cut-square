"""Shadow geometry, original-pixel extent witnesses and unsupported-grid rejection."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.imaging.contrast_grid import infer_contrast_geometry
from app.imaging.detection_plan import choose_grid
from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.panel_grid import PanelGrid
from tests.diagnose_irregular_shadows import shadow_field


FIXTURES = Path(__file__).parent/'fixtures'
# Hand-inspected ink points in the user's original, not detector-generated boxes.
# Include thin extremities (flags, antennae, propellers, ladders) as well as bodies.
TRANSPORT_WITNESSES = (
    ((1,1), ((209,161),(183,263),(281,184))),
    ((2,1), ((420,136),(510,241),(399,246))),
    ((3,1), ((682,163),(715,252),(622,250))),
    ((4,1), ((831,179),(909,142),(931,215))),
    ((5,1), ((1107,153),(1041,246),(1144,252))),
    ((6,1), ((1238,178),(1385,239),(1346,245))),
    ((1,2), ((158,397),(291,410),(225,434))),
    ((2,2), ((388,390),(517,372),(416,451))),
    ((3,2), ((602,355),(695,369),(720,456))),
    ((4,2), ((854,360),(843,461),(942,430))),
    ((5,2), ((1040,343),(1162,461),(1060,470))),
    ((6,2), ((1240,397),(1397,441),(1281,459))),
    ((1,3), ((151,576),(291,590),(210,657))),
    ((2,3), ((377,555),(510,651),(401,662))),
    ((3,3), ((637,550),(719,662),(590,634))),
    ((4,3), ((822,648),(944,647),(853,566))),
    ((5,3), ((1025,627),(1167,645),(1102,580))),
    ((6,3), ((1253,549),(1282,675),(1388,653))),
    ((1,4), ((139,832),(278,859),(202,764))),
    ((2,4), ((505,744),(382,884),(419,803))),
    ((3,4), ((710,774),(610,851),(712,858))),
    ((4,4), ((827,754),(945,754),(926,875))),
    ((5,4), ((1060,750),(1165,852),(1040,858))),
    ((6,4), ((1355,756),(1245,810),(1383,882))),
)


class IrregularShadowTests(unittest.TestCase):
    def test_original_shadowed_transport_preserves_distinct_complete_motifs(self):
        image = cv2.imread(str(FIXTURES/'transport_irregular_shadows.png'))
        original = image.copy()
        detector = MotifDetector()
        result = detector.detect_with_layout(image, DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        grid = result.panel_grid
        self.assertEqual((grid.columns,grid.rows),(6,4))
        used = set()
        for (col,row),points in TRANSPORT_WITNESSES:
            cx = (grid.x_lines_px[col-1]+grid.x_lines_px[col])/2
            cy = (grid.y_lines_px[row-1]+grid.y_lines_px[row])/2
            i,c = min(enumerate(result.candidates),key=lambda ic:(ic[1].center_px[0]-cx)**2+(ic[1].center_px[1]-cy)**2)
            self.assertNotIn(i,used); used.add(i)
            x,y,w,h = c.bounding_box_px
            for px,py in points:
                self.assertTrue(x <= px <= x+w and y <= py <= y+h, ((col,row),(px,py),c.bounding_box_px))
            self.assertLess(w,(grid.x_lines_px[col]-grid.x_lines_px[col-1])*1.2)
            self.assertLess(h,(grid.y_lines_px[row]-grid.y_lines_px[row-1])*1.2)
        np.testing.assert_array_equal(image,original)
        # Debug exports must remain serializable, including NumPy comparisons.
        json.dumps(detector.last_diagnostics)

    def test_shadow_fields_across_three_collections(self):
        for name,path in (('transport','transport_dashed_shared.png'),
                          ('dogs','generated/straight/dogs_6x4.png'),
                          ('hearts','generated/straight/hearts_6x4.png')):
            image = cv2.imread(str(FIXTURES/path))
            for kind in ('horizontal','vertical','diagonal','patches'):
                with self.subTest(collection=name,shadow=kind):
                    shadowed = (image.astype(np.float32)*shadow_field(image,kind)[...,None]).astype(np.uint8)
                    result = MotifDetector().detect_with_layout(shadowed,DetectorSettings())
                    self.assertEqual(len(result.candidates),24)
                    self.assertIsNotNone(result.panel_grid)
                    self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))

    def test_geometry_accepts_different_row_and_column_counts(self):
        from tests.test_visual_grid import printed_fabric
        for columns,rows in ((4,3),(7,4),(3,5)):
            with self.subTest(columns=columns,rows=rows):
                image = printed_fabric(columns,rows)
                y,x = np.mgrid[:image.shape[0],:image.shape[1]]
                gain = 1-.5*np.exp(-((x/image.shape[1]-y/image.shape[0]*.6-.1)/.15)**2)
                shadowed = (image*gain[...,None]).astype(np.uint8)
                geometry = infer_contrast_geometry(shadowed)
                self.assertIsNotNone(geometry)
                self.assertEqual((geometry.grid.columns,geometry.grid.rows),(columns,rows))

    def test_blank_or_striped_background_cannot_supply_a_grid(self):
        image = np.full((480,640,3),200,np.uint8)
        self.assertIsNone(infer_contrast_geometry(image))
        image[:,::10] = 60
        self.assertIsNone(infer_contrast_geometry(image))

    def test_resized_shadowed_original_keeps_geometry_and_extent(self):
        original = cv2.imread(str(FIXTURES/'transport_irregular_shadows.png'))
        for scale in (.5,1.5):
            with self.subTest(scale=scale):
                image = cv2.resize(original,None,fx=scale,fy=scale)
                result = MotifDetector().detect_with_layout(image,DetectorSettings())
                self.assertEqual(len(result.candidates),24)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
                for _,points in TRANSPORT_WITNESSES:
                    for px,py in points:
                        self.assertTrue(any(x <= px*scale <= x+w and y <= py*scale <= y+h
                                            for x,y,w,h in (c.bounding_box_px for c in result.candidates)))

    def test_coarse_grid_is_rejected_even_without_an_alternative(self):
        image = np.full((400,600,3),200,np.uint8)
        candidates = [MotifCandidate((50+c*100,50+r*100),(35+c*100,35+r*100,30,30),.9,900)
                      for r in range(4) for c in range(6)]
        coarse = PanelGrid.regular(600,400,3,2,confidence=.95,source='automatic')
        route,rows = choose_grid(image,[('panels',coarse)],candidates)
        self.assertIsNone(route)
        self.assertFalse(rows[0]['eligible'])
        with patch('app.imaging.detector.infer_panel_grid',return_value=coarse), \
             patch('app.imaging.detector.infer_camera_panel',return_value=None), \
             patch('app.imaging.detector.infer_repeated_artwork',return_value=None), \
             patch('app.imaging.detector._infer_regular_tile_grid',return_value=None), \
             patch('app.imaging.detector.stable_artwork_grid',return_value=None), \
             patch.object(MotifDetector,'_detect_once',return_value=candidates):
            result = MotifDetector()._detect_layout(image,DetectorSettings())
        self.assertIsNone(result.panel_grid)
        self.assertEqual(len(result.candidates),24)


if __name__ == '__main__': unittest.main()
