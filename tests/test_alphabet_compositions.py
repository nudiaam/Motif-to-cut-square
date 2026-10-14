"""A correct count cannot conceal detached letters or an incorrect ownership grid."""
from pathlib import Path
import unittest
import cv2
import numpy as np
from app.imaging.detector import MotifDetector, DetectorSettings
from app.imaging.logical_layout import layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from tests.evaluate_alphabet import assess
from tests.evaluate_accessory_columns import variants

class AlphabetCompositionTests(unittest.TestCase):
    def test_photographic_variants_keep_all_letters_with_their_illustrations(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/customer_20261012/alphabet_detached_6x4.png'))
        for name,pixels,transform,settings in variants(image):
            with self.subTest(variant=name):
                original=pixels.copy()
                detector=MotifDetector();result=detector.detect_with_layout(pixels,settings)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
                self.assertEqual(len(result.candidates),24)
                self.assertEqual(assess(result,transform),{'whole_groups':24,'failed_groups':[]})
                self.assertFalse(any(c.source_incomplete for c in result.candidates))
                np.testing.assert_array_equal(pixels,original)
                layout=layout_from_panel_grid([],result.panel_grid)
                for candidate in result.candidates:
                    col,row=layout.coordinates(*candidate.layout_center_px)
                    self.assertAlmostEqual(col,round(col),places=6)
                    self.assertAlmostEqual(row,round(row),places=6)

    def test_shared_background_recheck_respects_requested_cells(self):
        image=np.full((400,600,3),230,np.uint8)
        for y in (100,300):
            for x in (100,300,500):
                cv2.rectangle(image,(x-45,y-40),(x-25,y-15),(30,30,30),-1)
                cv2.circle(image,(x+15,y+10),28,(90,120,180),-1)
        grid=PanelGrid.regular(600,400,3,2,confidence=1,source='manual')
        colour=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)[0,0].tolist()
        result=MotifDetector().detect_in_grid(image,DetectorSettings(),grid,
                    background_model=(colour,[3,1,1]),cell_filter={(1,0)})
        self.assertEqual(len(result),1)
        x,y,w,h=result[0].bounding_box_px
        self.assertLessEqual(x,255);self.assertGreaterEqual(x+w,343)
        self.assertLessEqual(y,60);self.assertGreaterEqual(y+h,138)

if __name__=='__main__':unittest.main()
