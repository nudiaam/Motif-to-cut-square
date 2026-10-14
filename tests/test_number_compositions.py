"""Nested object repetitions must not split number compositions into extra cuts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import unittest
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.hierarchical_compositions import infer_hierarchical_compositions
from app.ui.main_window import MainWindow
from tests.evaluate_accessory_columns import variants
from tests.evaluate_number_compositions import assess

SOURCE=Path(__file__).parent/'fixtures/customer_20261012/numbers_objects_5x4.png'

class NumberCompositionTests(unittest.TestCase):
    def test_source_variants_preserve_twenty_unique_number_and_object_groups(self):
        for name,pixels,transform,settings in variants(cv2.imread(str(SOURCE))):
            with self.subTest(variant=name):
                original=pixels.copy();detector=MotifDetector()
                result=detector.detect_with_layout(pixels,settings)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(5,4))
                self.assertEqual(len(result.candidates),20)
                self.assertEqual(assess(result,transform),{'whole_groups':20,'failed_groups':[]})
                self.assertFalse(any(c.source_incomplete for c in result.candidates))
                self.assertTrue(any(p['stage']=='hierarchical_compositions' for p in detector.last_diagnostics['detection_plans']))
                np.testing.assert_array_equal(pixels,original)

    def test_other_counts_keep_primary_marks_and_their_small_repeated_objects(self):
        for columns,rows in ((3,3),(4,3),(6,3)):
            image=np.full((rows*180+80,columns*240+80,3),230,np.uint8)
            witnesses=[]
            for row in range(rows):
                for col in range(columns):
                    x=40+col*240;y=40+row*180
                    cv2.rectangle(image,(x+10,y+40),(x+55,y+115),(80,100,140),-1)
                    points=[(x+30,y+80)]
                    for r in range(3):
                        for c in range(3):
                            point=(x+105+c*30,y+45+r*30)
                            cv2.circle(image,point,7,(90,150,200),-1);points.append(point)
                    witnesses.append(points)
            with self.subTest(columns=columns,rows=rows):
                grid,groups,_=infer_hierarchical_compositions(image)
                self.assertEqual((grid.columns,grid.rows),(columns,rows))
                self.assertEqual(len(groups),columns*rows)
                owners=[]
                for points in witnesses:
                    hits=[i for i,((x,y,w,h),_,_) in enumerate(groups)
                          if all(x<=px<x+w and y<=py<y+h for px,py in points)]
                    self.assertEqual(len(hits),1);owners.extend(hits)
                self.assertEqual(len(set(owners)),columns*rows)

    def test_equal_distinct_figures_and_blank_background_are_not_nested_compositions(self):
        blank=np.full((600,900,3),230,np.uint8)
        self.assertIsNone(infer_hierarchical_compositions(blank))
        separate=blank.copy()
        for y in range(60,600,80):
            for x in range(60,900,80):cv2.circle(separate,(x,y),15,(90,120,160),-1)
        self.assertIsNone(infer_hierarchical_compositions(separate))

    def test_ui_preserves_twenty_real_compositions_without_inferred_cuts(self):
        application=QApplication.instance() or QApplication([])
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(SOURCE)),'Numbers grouping regression')
        window.detect_motifs();application.processEvents()
        self.assertEqual(len(window.detections),20)
        self.assertTrue(all(d.grid_positioned and not d.inferred for d in window.detections))
        self.assertEqual(sum(d.enabled for d in window.detections),20)
        window.confirm_detection()
        self.assertEqual(len(window.detections),20)

if __name__=='__main__':unittest.main()
