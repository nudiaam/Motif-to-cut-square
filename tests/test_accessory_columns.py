"""Repeated accessory columns must not become a second set of panels."""
from pathlib import Path
import unittest
import cv2
from app.imaging.detector import MotifDetector
from tests.evaluate_accessory_columns import variants, assess

class AccessoryColumnTests(unittest.TestCase):
    def test_photographic_variants_preserve_twelve_whole_compositions(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/customer_20261012/animals_accessories_columns_4x3.png'))
        for name,pixels,transform,settings in variants(image):
            with self.subTest(variant=name):
                detector=MotifDetector()
                result=detector.detect_with_layout(pixels,settings)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(4,3))
                self.assertEqual(len(result.candidates),12)
                self.assertEqual(assess(result,transform),{'whole_groups':12,'failed_groups':[]})
                self.assertFalse(any(c.source_incomplete for c in result.candidates))
                evidence=[p for p in detector.last_diagnostics['detection_plans'] if p['stage']=='camera_partition']
                self.assertTrue(evidence)
                self.assertTrue(all(p['agreeing_views']>=4 for p in evidence))
                if name=='diagonal_shadow':
                    self.assertTrue(any(p['stage']=='original_pixel_geometry' for p in detector.last_diagnostics['detection_plans']))

if __name__=='__main__':
    unittest.main()
