"""Unseen customer originals: full ownership, neighbours and alignment."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import unittest
import cv2,numpy as np
from app.imaging.detector import MotifDetector,DetectorSettings
from tests.holdout_group_truth import CASES
from tests.evaluate_accessory_columns import variants

ROOT=Path(__file__).parents[1]/'docs/qa/holdout-20261014'

def assess(result,transform,points):
    mapped=[cv2.perspectiveTransform(np.asarray(ps,float).reshape(-1,1,2),transform).reshape(-1,2) for ps in points]
    owners=[];failed=[]
    for i,group in enumerate(mapped):
        hits=[j for j,c in enumerate(result.candidates) if all(c.bounding_box_px[0]-2<=x<c.bounding_box_px[0]+c.bounding_box_px[2]+2 and c.bounding_box_px[1]-2<=y<c.bounding_box_px[1]+c.bounding_box_px[3]+2 for x,y in group)]
        if len(hits)!=1:failed.append(i+1);continue
        owners.append(hits[0]);x,y,w,h=result.candidates[hits[0]].bounding_box_px
        if any(x<=ps[0][0]<x+w and y<=ps[0][1]<y+h for k,ps in enumerate(mapped) if k!=i):failed.append(i+1)
    return len(set(owners)),sorted(set(failed))

class HoldoutGroupTests(unittest.TestCase):
    def test_actual_workflow_separates_artwork_groups_from_cut_size_warnings(self):
        from PySide6.QtWidgets import QApplication
        from app.ui.main_window import MainWindow
        app=QApplication.instance() or QApplication([])
        for name,(shape,points) in CASES.items():
            with self.subTest(source=name):
                window=MainWindow();self.addCleanup(window.close)
                window._load_image(cv2.imread(str(ROOT/f'{name}.png')),name)
                window.detect_motifs();app.processEvents()
                self.assertEqual(len(window.detections),len(points))
                self.assertTrue(all(d.grid_positioned and not d.inferred for d in window.detections))
                for d in window.detections:
                    np.testing.assert_allclose(d.center_px,window.logical_layout.position(*d.layout_cell),atol=1e-6)
                self.assertIn('Dashed cyan',window.panel.review_breakdown_label.text())
                if any(d.artwork_clipped for d in window.detections):
                    self.assertIn('do not contain',window.panel.review_breakdown_label.text())
    def test_native_originals_keep_each_complete_group_exactly_once(self):
        for name,(shape,points) in CASES.items():
            with self.subTest(source=name):
                image=cv2.imread(str(ROOT/f'{name}.png'));source=image.copy()
                r=MotifDetector().detect_with_layout(image,DetectorSettings())
                self.assertEqual(len(r.candidates),len(points))
                self.assertEqual((r.panel_grid.columns,r.panel_grid.rows),shape)
                self.assertEqual(assess(r,np.eye(3),points),(len(points),[]))
                np.testing.assert_array_equal(image,source)

    def test_source_groups_under_scale_and_illumination_changes(self):
        for name,(shape,points) in CASES.items():
            for variant,image,transform,settings in variants(cv2.imread(str(ROOT/f'{name}.png'))):
                if variant not in ('resize_0.5','dim','warm','diagonal_shadow'):continue
                with self.subTest(source=name,variant=variant):
                    r=MotifDetector().detect_with_layout(image,settings)
                    self.assertEqual(len(r.candidates),len(points))
                    self.assertEqual((r.panel_grid.columns,r.panel_grid.rows),shape)
                    self.assertEqual(assess(r,transform,points),(len(points),[]))

if __name__=='__main__':unittest.main()
