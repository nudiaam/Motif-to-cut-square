"""Independent fixture witnesses and general evidence-coordination contracts."""
import json
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.contrast_grid import infer_contrast_geometry
from app.imaging.detection_plan import choose_grid
from app.imaging.detector import MotifCandidate, MotifDetector, DetectorSettings
from app.imaging.panel_grid import PanelGrid
from app.imaging.seam_grid import infer_seam_grid


FIXTURES=Path(__file__).parent/'fixtures/acceptance'
# Inspected points on the source pictures, not predicted centres or extents.
CASES={
    'patchwork_animals_5x4':(20,5,4,[200,480,765,1040,1325],[160,390,625,865]),
    'pastel_4x4':(16,4,4,[380,635,890,1160],[180,410,640,870]),
    'space_dark_3x5':(15,3,5,[485,760,1050],[145,320,495,680,875]),
    'groups_4x3':(12,4,3,[250,600,930,1300],[235,535,815]),
    'thin_7x3':(21,7,3,None,None),
    'spanning_5x4':(19,5,4,None,None),
}


class JointCoordinatorTests(unittest.TestCase):
    def test_originals_have_distinct_owners_and_preserve_witnesses(self):
        for name,(count,cols,rows,xs,ys) in CASES.items():
            with self.subTest(image=name):
                image=cv2.imread(str(FIXTURES/(name+'.png')))
                original=image.copy();detector=MotifDetector()
                result=detector.detect_with_layout(image,DetectorSettings())
                self.assertEqual(len(result.candidates),count)
                self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(cols,rows))
                if xs:
                    owners=set()
                    for y in ys:
                        for x in xs:
                            matches=[i for i,c in enumerate(result.candidates)
                                     if c.bounding_box_px[0]<=x<=c.bounding_box_px[0]+c.bounding_box_px[2]
                                     and c.bounding_box_px[1]<=y<=c.bounding_box_px[1]+c.bounding_box_px[3]]
                            self.assertEqual(len(matches),1,(name,x,y,matches))
                            self.assertNotIn(matches[0],owners)
                            owners.add(matches[0])
                np.testing.assert_array_equal(image,original)
                json.dumps(detector.last_diagnostics)

    def test_accessories_remain_with_their_compositions(self):
        image=cv2.imread(str(FIXTURES/'groups_4x3.png'))
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        # Fox + butterfly; elephant + star; deer + butterfly; owl + moon.
        for body,accessory in [((250,240),(364,180)),((600,240),(695,274)),
                               ((1265,240),(1370,185)),((1250,540),(1380,552))]:
            self.assertTrue(any(all(x<=px<=x+w and y<=py<=y+h for px,py in (body,accessory))
                                for x,y,w,h in (c.bounding_box_px for c in result.candidates)))

    def test_dark_ink_on_dark_fabric_can_use_colour_at_equal_luminance(self):
        lab=np.full((540,740,3),(65,125,135),np.uint8)
        for row in range(3):
            for col in range(4):
                cv2.ellipse(lab,(100+180*col,100+170*row),(25,35),0,0,360,(65,150,110),-1)
        image=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
        geometry=infer_contrast_geometry(image,channel='chroma')
        self.assertIsNotNone(geometry)
        self.assertEqual((geometry.grid.columns,geometry.grid.rows),(4,3))
        result=MotifDetector().detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),12)

    def test_blank_and_stripes_do_not_become_light_or_colour_artwork(self):
        image=np.full((480,640,3),(45,30,30),np.uint8)
        for patterned in (False,True):
            if patterned:
                for x in range(0,640,20): image[:,x:x+6]=(65,35,50)
            for channel in ('light','chroma'):
                self.assertIsNone(infer_contrast_geometry(image,channel=channel))
            self.assertIsNone(infer_seam_grid(image))

    def test_complete_evidence_is_not_replaced_by_a_fragment_count(self):
        image=np.full((400,600,3),200,np.uint8)
        correct=PanelGrid.regular(600,400,6,4,confidence=.95)
        wrong=PanelGrid.regular(600,400,2,2,confidence=.98)
        whole=[MotifCandidate((50+100*c,50+100*r),(30+100*c,25+100*r,40,50),.9,2000)
               for r in range(4) for c in range(6)]
        selected,rows=choose_grid(image,[('coarse',wrong),('pattern',correct)],whole[:4],
                                 stable_routes=('pattern',),route_evidence={'pattern':whole})
        self.assertEqual(selected,'pattern')
        self.assertFalse(rows[0]['eligible'])

    def test_seams_keep_spacing_after_resizing_and_adding_surround(self):
        image=cv2.imread(str(FIXTURES/'patchwork_animals_5x4.png'))
        for scale in (.5,1.):
            small=cv2.resize(image,None,fx=scale,fy=scale)
            padded=cv2.copyMakeBorder(small,20,20,20,20,cv2.BORDER_CONSTANT,value=(90,90,90))
            grid=infer_seam_grid(padded)
            self.assertIsNotNone(grid)
            self.assertEqual((grid.columns,grid.rows),(5,4))


if __name__=='__main__':unittest.main()
