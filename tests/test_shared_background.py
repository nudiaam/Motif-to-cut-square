"""Low contrast must be judged relative to background noise, not ink brightness."""
import json
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.contrast_grid import infer_contrast_geometry
from app.imaging.detector import MotifDetector,DetectorSettings


FIXTURE=Path(__file__).parent/'fixtures/acceptance/dark_leaves_5x3.png'
# Points inspected on the source image, including stems and broad leaf lobes.
WITNESSES=(
 ((230,75),(105,218),(215,355)), ((486,90),(557,233),(463,355)),
 ((730,78),(651,225),(729,353)), ((999,85),(880,190),(1001,350)),
 ((1265,90),(1205,235),(1265,350)),
 ((213,410),(118,543),(199,673)), ((438,437),(551,518),(513,655)),
 ((728,410),(654,494),(721,666)), ((999,410),(930,529),(994,669)),
 ((1254,410),(1168,550),(1255,665)),
 ((206,719),(133,879),(209,972)), ((467,719),(344,863),(462,974)),
 ((703,720),(837,854),(754,991)), ((1000,790),(916,844),(1003,974)),
 ((1251,720),(1340,817),(1231,972)),
)


class SharedBackgroundTests(unittest.TestCase):
    def test_dark_original_and_resizing_keep_unique_whole_leaf_owners(self):
        original=cv2.imread(str(FIXTURE))
        for scale in (1.,.5,1.5):
            with self.subTest(scale=scale):
                image=cv2.resize(original,None,fx=scale,fy=scale)
                unchanged=image.copy();detector=MotifDetector()
                result=detector.detect_with_layout(image,DetectorSettings())
                self.assertEqual(len(result.candidates),15)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(5,3))
                used=set()
                for points in WITNESSES:
                    owners=[i for i,c in enumerate(result.candidates)
                            if all(c.bounding_box_px[0]<=px*scale<=c.bounding_box_px[0]+c.bounding_box_px[2]
                                   and c.bounding_box_px[1]<=py*scale<=c.bounding_box_px[1]+c.bounding_box_px[3]
                                   for px,py in points)]
                    self.assertEqual(len(owners),1,(scale,points,owners))
                    self.assertNotIn(owners[0],used);used.add(owners[0])
                np.testing.assert_array_equal(image,unchanged)
                json.dumps(detector.last_diagnostics)

    def test_large_low_contrast_shapes_on_light_and_dark_shared_fabric(self):
        for luminance,cols,rows in ((60,4,3),(210,3,3)):
            with self.subTest(luminance=luminance):
                lab=np.full((rows*160+60,cols*150+60,3),(luminance,128,128),np.uint8)
                for r in range(rows):
                    for c in range(cols):
                        cv2.ellipse(lab,(105+150*c,110+160*r),(48,63),0,0,360,
                                    (luminance,140,132),-1)
                image=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
                geometry=infer_contrast_geometry(image,channel='shared_background')
                self.assertIsNotNone(geometry)
                self.assertEqual((geometry.grid.columns,geometry.grid.rows),(cols,rows))

    def test_uniform_noise_and_stripes_do_not_become_compositions(self):
        rng=np.random.default_rng(42)
        plain=np.full((480,640,3),(40,25,20),np.uint8)
        noisy=np.clip(plain.astype(float)+rng.normal(0,2,(480,640,1)),0,255).astype(np.uint8)
        stripes=plain.copy()
        for x in range(0,640,24): stripes[:,x:x+7]=(52,34,30)
        for image in (plain,noisy,stripes):
            self.assertIsNone(infer_contrast_geometry(image,channel='shared_background'))


if __name__=='__main__':unittest.main()
