"""Stable motif spacing must participate before a camera grid can merge cells."""
from dataclasses import replace
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.detection_plan import stable_artwork_grid
from tests.diagnose_grid_typology import competing_periods


class StableArtworkGridTests(unittest.TestCase):
    def test_added_margin_and_resizing_preserve_transport_grid(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/transport_dashed_shared.png'))
        for altered in (cv2.copyMakeBorder(image,80,80,80,80,cv2.BORDER_CONSTANT,value=(20,20,20)),
                        cv2.resize(image,None,fx=.5,fy=.5)):
            result=MotifDetector().detect_with_layout(altered,DetectorSettings())
            self.assertEqual(len(result.candidates),24)
            self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))

    def test_original_transport_keeps_twenty_four_distinct_compositions(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/transport_dashed_shared.png'))
        detector=MotifDetector()
        result=detector.detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        self.assertEqual(result.panel_grid.source,'observations')
        chosen=next(p for p in detector.last_diagnostics['detection_plans'] if p['stage']=='grid')
        camera=next(p for p in chosen['hypotheses'] if p['route']=='camera')
        self.assertFalse(camera['eligible'])
        cells=set()
        for candidate in result.candidates:
            cx,cy=candidate.center_px
            col=int(np.argmin(abs((np.array(result.panel_grid.x_lines_px[:-1])+result.panel_grid.x_lines_px[1:])/2-cx)))
            row=int(np.argmin(abs((np.array(result.panel_grid.y_lines_px[:-1])+result.panel_grid.y_lines_px[1:])/2-cy)))
            cells.add((col,row))
        self.assertEqual(len(cells),24)

    def test_camera_margins_do_not_define_artwork_spacing(self):
        for columns,rows in ((4,3),(7,4),(3,5)):
            candidates=[MotifCandidate((190+c*105,170+r*95),(170+c*105,145+r*95,40,50),.9,1300)
                        for r in range(rows) for c in range(columns)]
            shifted=[replace(c,center_px=(c.center_px[0]+1,c.center_px[1]-1)) for c in candidates]
            grid=stable_artwork_grid([candidates,shifted,candidates])
            self.assertIsNotNone(grid)
            self.assertEqual((grid.columns,grid.rows),(columns,rows))
            np.testing.assert_allclose(grid.lattice[0],(190,170),atol=2)

    def test_unstable_fragment_positions_cannot_veto_panel_geometry(self):
        candidates=[MotifCandidate((100+c*100,100+r*100),(80+c*100,80+r*100,40,40),.9,1300)
                    for r in range(3) for c in range(4)]
        shifted=[replace(c,center_px=(c.center_px[0]+35,c.center_px[1])) for c in candidates]
        self.assertIsNone(stable_artwork_grid([candidates,candidates,shifted]))

    def test_strong_decoration_cannot_group_independently_supported_motifs(self):
        _,diagnosis=competing_periods()
        self.assertEqual(diagnosis['chosen'],'compositions')
        rejected=next(m for m in diagnosis['measurements'] if m['route']=='decorative')
        self.assertFalse(rejected['eligible'])


if __name__=='__main__':unittest.main()
