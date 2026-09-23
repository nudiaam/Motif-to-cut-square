"""Accessory components need corroborated ownership, not a second cut lattice."""
import json
from pathlib import Path
import unittest
from dataclasses import replace
from unittest.mock import patch

import cv2
import numpy as np

from app.imaging.detector import MotifDetector, MotifCandidate, DetectorSettings
from app.imaging.contrast_grid import infer_contrast_geometry

FIXTURE=Path(__file__).parent/'fixtures/acceptance/animal_accessories_4x3.png'
WITNESSES=(
 ((230,230),(150,300),(335,210)), ((535,240),(620,290),(665,300)),
 ((845,240),(945,155),(975,300)), ((1175,250),(1280,220),(1280,300)),
 ((210,540),(325,520),(330,595)), ((550,530),(660,530),(640,600)),
 ((850,555),(970,520),(940,610)), ((1175,540),(1290,500),(1290,590)),
 ((215,840),(320,807),(325,887)), ((560,850),(525,930),(670,895)),
 ((850,835),(970,815),(960,889)), ((1185,850),(1305,820),(1300,900)),
)


class AccessoryOwnershipTests(unittest.TestCase):
    @staticmethod
    def provisional(detector,image,settings):
        # Capture the actual pre-appearance result after fabric preparation;
        # calling _detect_layout on the uncropped photo is a different pipeline.
        captured=[]
        def retain(source,config,current,fabric_mask=None):
            captured.append(current)
            return current,False
        with patch.object(detector,'_coordinate_appearance',side_effect=retain):
            detector.detect_with_layout(image,settings)
        return captured[0]

    def test_source_groups_keep_their_two_detached_accessories_at_three_sizes(self):
        original=cv2.imread(str(FIXTURE))
        for scale in (1.,.5,1.5):
            with self.subTest(scale=scale):
                image=cv2.resize(original,None,fx=scale,fy=scale);before=image.copy()
                detector=MotifDetector();result=detector.detect_with_layout(image,DetectorSettings())
                self.assertEqual(len(result.candidates),12)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(4,3))
                owners=[]
                for points in WITNESSES:
                    hits=[i for i,c in enumerate(result.candidates)
                          if all(c.bounding_box_px[0]<=x*scale<=c.bounding_box_px[0]+c.bounding_box_px[2]
                                 and c.bounding_box_px[1]<=y*scale<=c.bounding_box_px[1]+c.bounding_box_px[3]
                                 for x,y in points)]
                    self.assertEqual(len(hits),1,(points,hits));owners.extend(hits)
                self.assertEqual(len(set(owners)),12)
                np.testing.assert_array_equal(image,before)
                json.dumps(detector.last_diagnostics)

    def test_aligned_centres_are_insufficient_if_accessories_are_discarded(self):
        image=cv2.imread(str(FIXTURE));detector=MotifDetector();settings=DetectorSettings()
        current=self.provisional(detector,image,settings)
        geometry=infer_contrast_geometry(image,channel='shared_background')
        bodies=[MotifCandidate((x+w/2,y+h/2),(round(x+w/2)-5,round(y+h/2)-5,10,10),.9,100)
                for _,_,(x,y,w,h) in geometry.grid.cells()]
        with patch('app.imaging.detector.infer_contrast_geometry',side_effect=
                   lambda image,channel='dark': geometry if channel=='shared_background' else None), \
             patch.object(detector,'detect_in_grid',return_value=bodies):
            result,recovered=detector._coordinate_appearance(image,settings,current)
        self.assertFalse(recovered);self.assertEqual(result,current)
        checks=[p for p in detector._plans if p['stage']=='appearance_ownership_recheck']
        self.assertEqual(len(checks),1)
        self.assertEqual(checks[0]['aligned_fraction'],1.)
        self.assertFalse(checks[0]['corroborated'])
        self.assertLess(checks[0]['retained_regions_fraction'],.90)

    def test_two_distinct_figures_per_cell_do_not_trigger_accessory_merging(self):
        image=cv2.imread(str(FIXTURE));detector=MotifDetector();settings=DetectorSettings()
        current=self.provisional(detector,image,settings)
        geometry=infer_contrast_geometry(image,channel='shared_background')
        regions=tuple(replace(geometry.regions[0],center_px=(x+w/2+offset,y+h/2),
                              bounding_box_px=(round(x+w/2+offset)-5,round(y+h/2)-5,10,10),area_px=100)
                      for _,_,(x,y,w,h) in geometry.grid.cells() for offset in (-30,30))
        geometry=replace(geometry,regions=regions)
        with patch('app.imaging.detector.infer_contrast_geometry',side_effect=
                   lambda image,channel='dark': geometry if channel=='shared_background' else None), \
             patch.object(detector,'detect_in_grid') as probe:
            _,recovered=detector._coordinate_appearance(image,settings,current)
        probe.assert_not_called();self.assertFalse(recovered)


if __name__=='__main__':unittest.main()
