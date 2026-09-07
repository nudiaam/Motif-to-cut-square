from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.config.bed_references import BedReferences
from app.imaging.bed_reference import locate_fabric, extend_to_fabric
from app.imaging.detector import (
    MotifDetector, MotifCandidate, DetectionResult, DetectorSettings,
    _consolidate_grid_candidates,
)
from app.imaging.logical_layout import LayoutObservation, fit_logical_layout
from app.imaging.panel_grid import PanelGrid


REFERENCE = Path(__file__).resolve().parents[1] / 'assets/references/epilog/empty_bed.png'


class BedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.reference = cv2.imread(str(REFERENCE))

    def test_black_and_multicolour_fabric_are_one_filled_piece(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                image = self.reference.copy()
                image[65:420,90:630] = (12,12,12) if dark else (230,220,210)
                if not dark:
                    image[65:420,250:420] = (40,65,100)
                    cv2.circle(image,(520,250),60,(5,5,5),-1)
                evidence = locate_fabric(image,self.reference)
                self.assertIsNotNone(evidence.mask, evidence.reason)
                self.assertGreater(np.mean(evidence.mask[70:415,95:625]>0),.99)
                self.assertLess(np.mean(evidence.mask[:50]>0),.01)

    def test_empty_bed_and_exposure_change_do_not_create_fabric(self):
        for image in (self.reference, np.clip(self.reference.astype(float)*1.08+4,0,255).astype(np.uint8)):
            evidence = locate_fabric(image,self.reference)
            self.assertIsNotNone(evidence.mask,evidence.reason)
            self.assertEqual(np.count_nonzero(evidence.mask),0)

    def test_unrelated_same_size_photo_is_not_a_reference_match(self):
        other=cv2.imread(str(REFERENCE.parents[3]/'tests/fixtures/transport_camera.png'))
        other=cv2.resize(other,(self.reference.shape[1],self.reference.shape[0]))
        self.assertIsNone(locate_fabric(other,self.reference).mask)

    def test_small_camera_shift_can_be_registered(self):
        image=self.reference.copy()
        image[90:390,140:570]=15
        image=cv2.warpAffine(image,np.float32([[1,0,3],[0,1,2]]),
                            (image.shape[1],image.shape[0]),borderMode=cv2.BORDER_REFLECT)
        evidence=locate_fabric(image,self.reference)
        self.assertIsNotNone(evidence.mask,evidence.reason)
        self.assertGreater(np.mean(evidence.mask[100:385,150:565]>0),.98)

    def test_missing_outer_rows_and_columns_extend_without_moving_lattice(self):
        for missing_axis in ('top','bottom','left','right'):
            for columns,rows in ((6,4),(4,5),(7,3)):
                with self.subTest(edge=missing_axis,columns=columns,rows=rows):
                    observations=[]
                    for r in range(rows):
                        for c in range(columns):
                            if ((missing_axis=='top' and r==0) or (missing_axis=='bottom' and r==rows-1)
                                or (missing_axis=='left' and c==0) or (missing_axis=='right' and c==columns-1)):
                                continue
                            observations.append(LayoutObservation(len(observations),(100+c*90,100+r*85)))
                    core=fit_logical_layout(observations)
                    self.assertTrue(core.reliable,core)
                    mask=np.zeros((700,900),np.uint8)
                    mask[57:round(100+(rows-.5)*85)+1,55:round(100+(columns-.5)*90)+1]=255
                    grid=extend_to_fabric(core,mask)
                    self.assertIsNotNone(grid)
                    self.assertEqual((grid.columns,grid.rows),(columns,rows))
                    np.testing.assert_allclose(grid.lattice[0],(100,100),atol=1e-6)
                    np.testing.assert_allclose(grid.lattice[1],core.column_vector_px,atol=1e-6)
                    np.testing.assert_allclose(grid.lattice[2],core.row_vector_px,atol=1e-6)

    def test_pipeline_filters_bed_and_extends_an_entire_undetected_row(self):
        image=self.reference.copy()
        image[65:420,90:630]=225
        candidates=[]
        for r in range(3):
            for c in range(6):
                x,y=135+c*90,110+r*88
                candidates.append(MotifCandidate((x,y),(x-20,y-20,40,40),.9,1000))
        candidates.append(MotifCandidate((30,30),(20,20,20,20),.9,300))
        detector=MotifDetector(); detector.bed_reference=self.reference
        with patch.object(detector,'_detect_layout',return_value=DetectionResult(tuple(candidates))):
            result=detector.detect_with_layout(image,DetectorSettings())
        self.assertEqual(len(result.candidates),18)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        self.assertEqual(result.panel_grid.source,'reference')

    def test_trusted_grid_removes_bed_artifacts_and_combines_cell_fragments(self):
        image=self.reference.copy()
        image[65:420,90:630]=225
        # Changed areas of the bed mimic stains/reflections that survive the
        # first fabric mask, as in the reported right and bottom artifacts.
        image[90:310,650:719]=35
        image[430:480,0:190]=35
        candidates=[]
        for r in range(4):
            for c in range(6):
                x,y=135+c*90,110+r*88
                candidates.append(MotifCandidate((x,y),(x-20,y-20,40,40),.8,900))
        # Two nearby pieces of one drawing occupy the same intended cell.
        candidates.append(MotifCandidate((420,290),(413,276,14,28),.7,220))
        # Three artifacts are on changed bed areas, outside the fabric grid.
        candidates.extend([
            MotifCandidate((680,180),(665,165,30,30),.8,500),
            MotifCandidate((45,455),(25,440,40,30),.8,500),
            MotifCandidate((145,455),(125,440,40,30),.8,500),
        ])
        self.assertEqual(len(candidates),28)
        detector=MotifDetector(); detector.bed_reference=self.reference
        with patch.object(detector,'_detect_layout',return_value=DetectionResult(tuple(candidates))):
            result=detector.detect_with_layout(image,DetectorSettings())
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        self.assertEqual(len(result.candidates),24)
        layout_cells={(round(c.center_px[0]),round(c.center_px[1])) for c in result.candidates}
        self.assertTrue(all(80 < x < 640 and 60 < y < 425 for x,y in layout_cells))
        merged=[c for c in result.candidates if 390 < c.center_px[0] < 450
                and 260 < c.center_px[1] < 320]
        self.assertEqual(len(merged),1)
        self.assertGreater(merged[0].area_px,900)

    def test_candidate_cleanup_requires_an_independent_reliable_grid(self):
        grid=PanelGrid.regular(600,400,6,4,confidence=.95,source='pattern')
        candidates=tuple(MotifCandidate((50+i*10,50),(45+i*10,45,10,10),.8,100)
                         for i in range(3))
        self.assertEqual(_consolidate_grid_candidates(candidates,grid),candidates)
        uncertain=PanelGrid.regular(600,400,6,4,confidence=.70,source='reference')
        self.assertEqual(_consolidate_grid_candidates(candidates,uncertain),candidates)

    def test_reference_persistence_is_per_machine_and_removable(self):
        with tempfile.TemporaryDirectory() as directory:
            store=BedReferences(directory)
            store.save('one',self.reference)
            np.testing.assert_array_equal(BedReferences(directory).load('one'),self.reference)
            self.assertIsNone(store.load('two'))
            store.disable('one'); self.assertIsNone(store.load('one'))
            store.save('one',self.reference); self.assertIsNotNone(store.load('one'))

    def test_real_detector_completes_row_without_foreground_detections(self):
        image=self.reference.copy()
        image[65:420,90:630]=225
        for r in range(3):
            for c in range(6):
                cv2.ellipse(image,(135+c*90,110+r*88),(20,26),0,0,360,(65,90,130),-1)
        detector=MotifDetector(); detector.bed_reference=self.reference
        result=detector.detect_with_layout(image,DetectorSettings(minimum_area_px=150))
        self.assertEqual(len(result.candidates),18)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))

    def test_partial_edge_and_separate_piece_do_not_extend_grid(self):
        observations=[LayoutObservation(r*6+c,(100+c*90,100+r*85))
                      for r in range(3) for c in range(6)]
        core=fit_logical_layout(observations)
        mask=np.zeros((600,900),np.uint8)
        mask[57:335,55:596]=255  # Only part of the next cell row fits.
        mask[345:470,55:596]=255  # A separate piece is not the same panel.
        result=extend_to_fabric(core,mask)
        self.assertEqual((result.columns,result.rows),(6,3))
