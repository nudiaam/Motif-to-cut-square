"""Regression inputs supplied by the customer and hard cut boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import unittest
import cv2
from PySide6.QtWidgets import QApplication
from app.imaging.detector import DetectorSettings, MotifDetector
from app.imaging.detector import MotifCandidate
from app.imaging.detector import DetectionResult
from app.imaging.extent_review import review_extents
from app.imaging.panel_grid import PanelGrid
from app.ui.main_window import MainWindow
from app.export.svg_exporter import SVG_NAMESPACE

ROOT = Path(__file__).parent / 'fixtures'

class CustomerCutBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_animals_keep_all_twelve_animals_with_their_accessories(self):
        image = cv2.imread(str(ROOT / 'customer_20261012/animals_accessories_4x3.png'))
        detector = MotifDetector()
        result = detector.detect_with_layout(image, DetectorSettings())
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (4, 3))
        self.assertEqual(len(result.candidates), 12)
        # Witnesses chosen on the original, one animal and its two detached objects.
        groups = [[(290,200),(180,134),(380,250)],[(610,205),(495,250),(710,260)],
                  [(940,200),(840,134),(1050,250)],[(1290,210),(1180,233),(1380,247)],
                  [(220,480),(150,395),(365,540)],[(595,490),(490,485),(700,540)],
                  [(950,480),(835,525),(1060,545)],[(1300,480),(1185,533),(1420,550)],
                  [(240,800),(140,717),(334,836)],[(600,800),(475,821),(715,856)],
                  [(955,800),(842,701),(1064,854)],[(1335,800),(1205,800),(1440,800)]]
        owners = []
        for points in groups:
            owning = [i for i,c in enumerate(result.candidates)
                      if all(c.bounding_box_px[0] <= x < c.bounding_box_px[0]+c.bounding_box_px[2]
                             and c.bounding_box_px[1] <= y < c.bounding_box_px[1]+c.bounding_box_px[3]
                             for x,y in points)]
            self.assertEqual(len(owning), 1, points)
            owners.extend(owning)
        self.assertEqual(len(set(owners)), 12)
        self.assertFalse(any(c.source_incomplete for c in result.candidates))
        checks = [p for p in detector.last_diagnostics['detection_plans']
                  if p['stage'] == 'appearance_ownership_recheck']
        self.assertTrue(any(p['corroborated'] for p in checks))

    def test_partial_row_stays_excluded_even_with_a_small_cut_or_manual_move(self):
        image = cv2.imread(str(ROOT / 'generated/customer_20261012/alphabet_6x4.png'))[:860]
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(image, 'cropped source regression')
        window.detect_motifs()
        incomplete = [d for d in window.detections if d.source_incomplete]
        self.assertEqual(len(incomplete), 6)
        self.assertTrue(all(not d.enabled for d in incomplete))
        window.change_cut_size(1, 1)
        for d in incomplete:
            window.set_detection_enabled(d.id, True)
            self.assertFalse(d.enabled)
        first = incomplete[0]
        window.move_detection(first.id, 500, 400)
        window.set_detection_enabled(first.id, True)
        self.assertFalse(first.enabled)
        window._refresh()
        self.assertEqual(len(window.detections), 24)  # No replacement grid cuts.
        self.assertEqual(sum(d.enabled for d in window.detections), 18)
        tree = window.svg_exporter.build_tree(window.mapper, window.detections)
        self.assertEqual(len(tree.findall(f'{{{SVG_NAMESPACE}}}rect')), 18)
        self.assertIn('incomplete image: 6', window.panel.review_breakdown_label.text())

    def test_outside_cut_is_excluded_and_can_be_enabled_only_after_moving_inside(self):
        import numpy as np
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(np.full((600,900,3),230,np.uint8), 'boundary test')
        window.add_center(10, 10)
        d = window.detections[0]
        self.assertFalse(d.enabled)
        window.set_detection_enabled(d.id, True)
        self.assertFalse(d.enabled)
        window.move_detection(d.id, 450, 300)
        window.set_detection_enabled(d.id, True)
        self.assertTrue(d.enabled)
        self.assertIsNone(d.cut_block_reason(window.mapper))
        self.assertEqual(d.cut_width_inches, 5)

    def test_customer_birds_keep_eighteen_complete_and_exclude_six_partial(self):
        image = cv2.imread(str(ROOT / 'customer_20261012/birds_partial_6x4.png'))
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(image, 'customer birds')
        window.detect_motifs()
        self.assertEqual(len(window.detections), 24)
        self.assertEqual(sum(d.source_incomplete for d in window.detections), 6)
        self.assertEqual(sum(d.enabled for d in window.detections), 18)
        self.assertEqual({d.layout_cell for d in window.detections if d.source_incomplete},
                         {(column, 3) for column in range(6)})
        self.assertTrue(all(d.bounding_box_px[1]+d.bounding_box_px[3] == image.shape[0]
                            for d in window.detections if d.source_incomplete))
        window.change_cut_size(1, 1)
        self.assertEqual(sum(d.enabled for d in window.detections), 18)
        tree = window.svg_exporter.build_tree(window.mapper, window.detections)
        self.assertEqual(len(tree.findall(f'{{{SVG_NAMESPACE}}}rect')), 18)

    def test_partial_cells_are_blocked_on_every_image_edge(self):
        import numpy as np
        image = np.full((200,200,3),230,np.uint8)
        cases = [((-40,0,200,200),(20,50)), ((0,0,240,200),(180,50)),
                 ((0,-40,200,200),(50,20)), ((0,0,200,240),(50,180))]
        for bounds, (x,y) in cases:
            with self.subTest(bounds=bounds):
                grid = PanelGrid.regular(200,200,2,2,bounds_px=bounds,confidence=.9)
                c = MotifCandidate((x,y),(x-5,y-5,10,10),.9,100)
                checked = review_extents(image,[c],grid)[0]
                self.assertTrue(checked.source_incomplete)
                self.assertEqual(checked.bounding_box_px,c.bounding_box_px)

    def test_missing_partial_grid_cells_cannot_become_enabled_inferred_cuts(self):
        import numpy as np
        window = MainWindow()
        self.addCleanup(window.close)
        window._load_image(np.full((600,900,3),230,np.uint8), 'partial inferred row')
        window.change_cut_size(1, 1)
        grid = PanelGrid.regular(900,600,3,3,bounds_px=(100,60,700,660),confidence=.95)
        candidates = tuple(MotifCandidate((x,y),(x-15,y-15,30,30),.9,900)
                           for y in (160,360) for x in (200,400,600))
        window._apply_detection_result(DetectionResult(candidates,grid), {})
        self.assertEqual(len(window.detections), 9)
        partial = [d for d in window.detections if d.source_incomplete]
        self.assertEqual(len(partial), 3)
        self.assertTrue(all(d.inferred and not d.enabled for d in partial))
        window._refresh()
        self.assertEqual(sum(d.enabled for d in window.detections), 6)

if __name__ == '__main__':
    unittest.main()
