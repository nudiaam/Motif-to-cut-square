"""Conditional compound recovery, neighbour ownership and independent figures."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import replace
import unittest
import cv2,numpy as np
from PySide6.QtWidgets import QApplication
from app.imaging.compound_grid import infer_compound_grid
from app.imaging.detector import MotifDetector,DetectorSettings,MotifCandidate,DetectionResult
from app.imaging.panel_grid import PanelGrid
from app.ui.main_window import MainWindow
from tests.evaluate_accessory_columns import variants
import runpy

SOURCE=Path(__file__).parent/'fixtures/customer_20261012/numbers_compact_5x4.png'
POINTS=runpy.run_path(str(Path(__file__).parents[1]/'docs/qa/numbers-audit/audit_alternating_columns.py'))['POINTS']

def assess(result,transform):
    owners=[];failed=[]
    mapped=[cv2.perspectiveTransform(np.asarray(points,float).reshape(-1,1,2),transform).reshape(-1,2) for points in POINTS]
    for i,points in enumerate(mapped):
        hits=[j for j,c in enumerate(result.candidates) if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in points)]
        if len(hits)!=1:failed.append(i+1)
        else:
            owners.append(hits[0]);bx,by,bw,bh=result.candidates[hits[0]].bounding_box_px
            for j,other in enumerate(mapped):
                if j!=i and any(bx<=x<bx+bw and by<=y<by+bh for x,y in other):failed.append(i+1)
    return len(set(owners)),sorted(set(failed))

class CompoundGridTests(unittest.TestCase):
    def test_compact_number_groups_across_photographic_variations(self):
        for name,image,transform,settings in variants(cv2.imread(str(SOURCE))):
            with self.subTest(variant=name):
                original=image.copy();d=MotifDetector();r=d.detect_with_layout(image,settings)
                self.assertEqual((r.panel_grid.columns,r.panel_grid.rows),(5,4))
                self.assertEqual(len(r.candidates),20)
                self.assertEqual(assess(r,transform),(20,[]))
                self.assertFalse(any(c.source_incomplete for c in r.candidates))
                np.testing.assert_array_equal(image,original)

    def independent_scene(self,cluster=True):
        image=np.full((650,980,3),230,np.uint8);candidates=[]
        for row in range(4):
            for col in range(6):
                cx=100+col*150;cy=100+row*150
                if col%2==0:
                    box=(cx-25,cy-40,50,80);cv2.rectangle(image,(cx-25,cy-40),(cx+25,cy+40),(50,110,190),-1)
                elif cluster:
                    box=(cx-25,cy-25,50,50)
                    for dy in (-18,0,18):
                        for dx in (-18,0,18):cv2.circle(image,(cx+dx,cy+dy),6,(60,170,80),-1)
                else:
                    box=(cx-15,cy-15,30,30);cv2.circle(image,(cx,cy),15,(60,170,80),-1)
                candidates.append(MotifCandidate((cx,cy),box,.95,2000))
        grid=PanelGrid.regular(980,650,6,4,bounds_px=(25,25,925,625),confidence=.99,source='pattern')
        return image,DetectionResult(tuple(candidates),grid)

    def test_equal_spacing_does_not_join_independent_large_figures_and_clusters(self):
        image,current=self.independent_scene()
        self.assertIsNone(infer_compound_grid(image,current))

    def test_other_counts_preserve_complete_primary_and_cluster_groups(self):
        for columns in (3,4,6):
            with self.subTest(columns=columns):
                image=np.full((520,columns*200+100,3),230,np.uint8);candidates=[];points=[]
                for row in range(3):
                    for column in range(columns):
                        x=100+column*200;y=100+row*150
                        cv2.rectangle(image,(x-20,y-40),(x+20,y+40),(50,110,190),-1)
                        candidates.append(MotifCandidate((x,y),(x-20,y-40,40,80),.95,3200))
                        for dx in (-18,0,18):
                            for dy in (-18,0,18):cv2.circle(image,(x+70+dx,y+dy),6,(60,170,80),-1)
                        candidates.append(MotifCandidate((x+70,y),(x+46,y-24,48,48),.95,1000))
                        points.append([(x,y),(x+52,y-18),(x+88,y+18)])
                grid=PanelGrid.regular(image.shape[1],image.shape[0],columns*2,3,bounds_px=(50,25,50+columns*200,475),confidence=.99,source='pattern')
                proposal=infer_compound_grid(image,DetectionResult(tuple(candidates),grid))
                self.assertIsNotNone(proposal)
                self.assertEqual((proposal[0].columns,proposal[0].rows),(columns,3))
                self.assertEqual(len(proposal[1]),columns*3)
                owners=[]
                for group in points:
                    hits=[i for i,((x,y,w,h),_,_) in enumerate(proposal[1]) if all(x<=px<x+w and y<=py<y+h for px,py in group)]
                    self.assertEqual(len(hits),1);owners.extend(hits)
                self.assertEqual(len(set(owners)),len(points))

    def test_large_and_one_small_figure_are_not_a_compound_pattern(self):
        image,current=self.independent_scene(cluster=False)
        self.assertIsNone(infer_compound_grid(image,current))

    def test_independent_butterflies_and_flowers_keep_their_own_cuts(self):
        image=np.full((650,980,3),230,np.uint8)
        for row in range(4):
            for col in range(6):
                x=100+col*150;y=100+row*150
                if col%2==0:
                    for dx in (-15,15):
                        for dy in (-13,13):cv2.ellipse(image,(x+dx,y+dy),(16,13),0,0,360,(90,140,190),-1)
                    cv2.line(image,(x,y-20),(x,y+25),(35,35,35),3)
                    cv2.line(image,(x,y-20),(x-12,y-35),(35,35,35),1)
                    cv2.line(image,(x,y-20),(x+12,y-35),(35,35,35),1)
                else:
                    for angle in np.linspace(0,2*np.pi,6)[:-1]:
                        cv2.circle(image,(round(x+15*np.cos(angle)),round(y-12+15*np.sin(angle))),11,(100,170,220),-1)
                    cv2.line(image,(x,y),(x,y+35),(70,140,60),3)
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        for row in range(4):
            for col in range(6):
                x=100+col*150;y=100+row*150
                self.assertEqual(sum(bx<=x<bx+bw and by<=y<by+bh for bx,by,bw,bh in (c.bounding_box_px for c in result.candidates)),1)

    def test_confirmed_guides_and_incomplete_ink_are_protected(self):
        image,current=self.independent_scene()
        for source in ('manual','visual','camera','reference'):
            self.assertIsNone(infer_compound_grid(image,replace(current,panel_grid=replace(current.panel_grid,source=source))))
        partial=replace(current,candidates=(replace(current.candidates[0],source_incomplete=True),*current.candidates[1:]))
        self.assertIsNone(infer_compound_grid(image,partial))

    def test_ui_keeps_twenty_groups_and_reports_small_cut_size(self):
        app=QApplication.instance() or QApplication([]);window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(SOURCE)),'Compact number groups')
        window.change_cut_size(3,3);window.detect_motifs();app.processEvents()
        self.assertEqual(len(window.detections),20)
        self.assertTrue(all(d.grid_positioned and not d.inferred for d in window.detections))
        self.assertTrue(any(d.artwork_clipped for d in window.detections))
        positions=[d.center_px for d in window.detections];window.confirm_detection()
        self.assertEqual([d.center_px for d in window.detections],positions)

    def test_partial_source_groups_stay_excluded_after_resizing_cuts(self):
        app=QApplication.instance() or QApplication([]);window=MainWindow();self.addCleanup(window.close)
        image=cv2.imread(str(SOURCE))[:815].copy()
        window._load_image(image,'Partial compact number groups');window.detect_motifs();app.processEvents()
        partial=[d.id for d in window.detections if d.source_incomplete]
        self.assertGreaterEqual(len(partial),5)
        self.assertFalse(any(d.enabled for d in window.detections if d.id in partial))
        window.change_cut_size(1,1);app.processEvents()
        self.assertTrue(all(d.source_incomplete and not d.enabled for d in window.detections if d.id in partial))

if __name__=='__main__':unittest.main()
