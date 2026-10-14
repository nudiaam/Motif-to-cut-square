import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import cv2
import numpy as np

from app.export.debug_exporter import export_detection_bundle
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.review_summary import review_counts
from app.imaging.detection_plan import choose_grid, grid_distance, grid_evidence, seam_profiles
from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.extent_review import review_extents
from app.imaging.panel_grid import PanelGrid
from app.imaging.run_diagnostics import compare_reports, image_identity, run_identity
from app.models import Detection


class CustomerDiagnosticsTests(unittest.TestCase):
    def test_repeat_identity_and_changed_pixel_settings_guides(self):
        image = np.full((80,100,3),200,np.uint8)
        settings = asdict(DetectorSettings())
        a = run_identity(image,None,settings)
        self.assertEqual(a, run_identity(image.copy(),None,settings))
        altered=image.copy(); altered[0,0,0] = 199
        b = run_identity(altered,None,settings)
        self.assertNotEqual(a['input_sha256'],b['input_sha256'])
        report = lambda identity: {'detection_run': {'identity':identity, 'result_sha256':'same'}}
        self.assertEqual(compare_reports(report(a),report(b))['changed_inputs'],['image'])
        c = run_identity(image,None,settings,'confirmed_guides',{'rows':4})
        self.assertIn('confirmed_guides',compare_reports(report(a),report(c))['changed_inputs'])
        self.assertFalse(compare_reports({}, {})['comparable'])

    def test_bundle_preserves_pixels_and_rejects_mismatched_input(self):
        image = np.full((80,100,3),(190,200,210),np.uint8)
        reference = np.zeros_like(image)
        run = {'identity':run_identity(image,reference,asdict(DetectorSettings()))}
        mapper = CoordinateMapper(100,80)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'case.zip'
            export_detection_bundle(path,image,reference,mapper,[],detection_run=run)
            with zipfile.ZipFile(path) as bundle:
                decoded = cv2.imdecode(np.frombuffer(bundle.read('source.png'),np.uint8),cv2.IMREAD_COLOR)
                np.testing.assert_array_equal(decoded,image)
                self.assertIn('reference.png',bundle.namelist())
                self.assertEqual(json.loads(bundle.read('report.json'))['detection_run'],run)
            before=path.read_bytes()
            with self.assertRaises(ValueError):
                export_detection_bundle(path,image+1,reference,mapper,[],detection_run=run)
            self.assertEqual(path.read_bytes(),before)
            export_detection_bundle(path,image,reference+1,mapper,[],detection_run=run)
            with zipfile.ZipFile(path) as bundle:
                self.assertNotIn('reference.png',bundle.namelist())
                self.assertIn(b'no longer loaded',bundle.read('README.txt'))

    def test_image_profiles_reused_without_changing_evidence(self):
        image = np.random.default_rng(2).integers(0,255,(150,200,3),dtype=np.uint8)
        grid = PanelGrid.regular(200,150,4,3)
        candidates = [MotifCandidate((25,25),(10,10,30,30),.9,900)]
        self.assertEqual(grid_evidence(image,grid,candidates),
                         grid_evidence(image,grid,candidates,profiles=seam_profiles(image)))

    def test_same_count_different_phase_near_tie_is_exposed(self):
        image = np.full((300,400,3),230,np.uint8)
        good = PanelGrid.regular(400,300,4,3,confidence=.9)
        shifted = PanelGrid.regular(400,300,4,3,bounds_px=(30,30,430,330),confidence=.9)
        measures={'score':.8,'unique_assignment_fraction':1.,'aligned_fraction':1.,
                  'occupied_fraction':1.,'outside_fraction':0.}
        with patch('app.imaging.detection_plan.grid_evidence',return_value=measures):
            selected, rows=choose_grid(image,[('a',good),('b',shifted)],[])
        self.assertEqual(selected,'a')
        self.assertEqual(rows[0]['competing_routes'],['b'])
        self.assertGreater(grid_distance(good,shifted),.15)
        with patch('app.imaging.detection_plan.grid_evidence',return_value=measures):
            _, rows=choose_grid(image,[('a',good),('b',good)],[])
        self.assertEqual(rows[0]['competing_routes'],[])

    def test_partial_panel_is_not_silently_complete(self):
        image=np.full((200,300,3),230,np.uint8)
        cv2.circle(image,(225,175),15,(20,60,100),-1)
        grid=PanelGrid.regular(300,200,3,2,bounds_px=(0,0,300,240),confidence=.9)
        c=MotifCandidate((225,175),(210,160,31,31),.9,700)
        reviewed=review_extents(image,[c],grid)[0]
        self.assertTrue(any('partly inside' in r for r in reviewed.review_reasons))
        self.assertEqual(reviewed.bounding_box_px,c.bounding_box_px)
        self.assertTrue(reviewed.source_incomplete)

    def test_warning_counts_do_not_hide_multiple_causes_or_excluded_cuts(self):
        mapper=CoordinateMapper(600,400)
        d=Detection.from_pixel_center(1,(10,10),mapper,review_reasons=('Panel is only partly inside the source image',))
        d.overlaps_cut=True
        counts=review_counts([d],mapper)
        self.assertEqual(counts['overlap'],1)
        self.assertEqual(counts['outside_bed'],1)
        self.assertEqual(counts['partial_image'],1)
        d.enabled=False
        self.assertFalse(any(review_counts([d],mapper).values()))

    def test_generated_compositions_keep_letters_and_expose_missed_detail(self):
        root=Path(__file__).parent/'fixtures/generated/customer_20261012'
        alphabet=MotifDetector().detect_with_layout(cv2.imread(str(root/'alphabet_6x4.png')),DetectorSettings())
        self.assertEqual(len(alphabet.candidates),24)
        # Independent source witnesses, not predicted centres: letter and artwork
        # in each of four distant cells, including the violin's detached bow.
        groups=[[(170,140),(220,220)],[(600,550),(655,615)],
                [(820,765),(865,835),(920,840)],[(1267,757),(1350,847)]]
        owners=[]
        for points in groups:
            owning=[i for i,c in enumerate(alphabet.candidates)
                    if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2]
                           and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3]
                           for x,y in points)]
            self.assertEqual(len(owning),1,points)
            owners+=owning
        self.assertEqual(len(set(owners)),len(groups))
        # Resizing must scale pixel-valued settings as well as the input pixels.
        original=cv2.imread(str(root/'alphabet_6x4.png'))
        half=cv2.resize(original,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
        resized=MotifDetector().detect_with_layout(half,DetectorSettings(
            minimum_area_px=125,merge_distance_px_x=7,merge_distance_px_y=7))
        self.assertEqual(len(resized.candidates),24)
        christmas=MotifDetector().detect_with_layout(cv2.imread(str(root/'christmas_6x4.png')),DetectorSettings())
        self.assertEqual(len(christmas.candidates),24)
        snowflake=min(christmas.candidates,key=lambda c:np.linalg.norm(np.array(c.center_px)-(455,390)))
        # Count is correct but the original detector misses faint extremities.
        # Until corroborated recovery exists this composition must require review.
        self.assertTrue(snowflake.review_reasons)
        self.assertTrue(any('textured panel' in r for r in snowflake.review_reasons))
        # Cropping away the bottom of the last row must not certify that row.
        cropped=MotifDetector().detect_with_layout(original[:860].copy(),DetectorSettings())
        self.assertEqual(sum(any('partly inside' in r for r in c.review_reasons)
                             for c in cropped.candidates),6)


if __name__ == '__main__':
    unittest.main()
