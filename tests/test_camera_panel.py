from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.camera_panel import infer_camera_panel, project_points, source_grid
from app.imaging.detector import DetectorSettings, MotifDetector
from app.imaging.logical_layout import LayoutObservation, layout_from_panel_grid, fit_logical_layout

PATCHWORK_FIXTURE = Path(__file__).parent / 'fixtures' / 'patchwork_camera.png'


def photographed_patchwork(columns, rows):
    size = 160
    fabric = np.full((rows*size, columns*size, 3), 230, np.uint8)
    colors = [(225,205,228), (207,225,206), (229,218,205), (206,216,237)]
    for r in range(rows):
        for c in range(columns):
            x, y = c*size, r*size
            fabric[y:y+size, x:x+size] = colors[(c+r)%len(colors)]
            cv2.ellipse(fabric, (x+size//2,y+size//2), (25,35), 0,0,360,(80,100,140),-1)
    h, w = fabric.shape[:2]
    source = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    quad = np.float32([[75,65],[w+35,45],[w+65,h+70],[40,h+45]])
    return cv2.warpPerspective(fabric,cv2.getPerspectiveTransform(source,quad),(w+120,h+120),borderValue=(25,25,25))


class CameraPanelTests(unittest.TestCase):
    def test_camera_fallback_does_not_replace_a_supported_existing_layout(self):
        image = cv2.imread(str(PATCHWORK_FIXTURE.parent / 'vehicles_panels.png'))
        result = MotifDetector().detect_with_layout(image, DetectorSettings())
        self.assertEqual(len(result.candidates),24)
        layout = fit_logical_layout([LayoutObservation(i,c.center_px) for i,c in enumerate(result.candidates)])
        self.assertEqual((layout.columns,layout.rows),(6,4))
        self.assertTrue(layout.reliable)

    def test_real_camera_grid_does_not_depend_on_the_six_initial_detections(self):
        image = cv2.imread(str(PATCHWORK_FIXTURE))
        original = image.copy()
        detector = MotifDetector()
        self.assertLess(len(detector._detect_once(image, DetectorSettings())), 10)
        result = detector.detect_with_layout(image, DetectorSettings())
        np.testing.assert_array_equal(image, original)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows), (6,4))
        self.assertEqual(result.panel_grid.source, 'camera')
        self.assertEqual(len(result.candidates),22)
        layout = layout_from_panel_grid([LayoutObservation(i,c.center_px,c.bounding_box_px)
                                        for i,c in enumerate(result.candidates)],result.panel_grid)
        self.assertTrue(layout.reliable)
        self.assertEqual([(p.column,p.row,p.review_state) for p in layout.missing],
                         [(3,1,'proposed'),(1,3,'proposed')])
        self.assertTrue(all(m.status == 'matched' for m in layout.matches))

    def test_global_projection_preserves_cell_positions_and_straight_grid_lines(self):
        panel = infer_camera_panel(cv2.imread(str(PATCHWORK_FIXTURE)))
        grid = source_grid(panel)
        layout = layout_from_panel_grid([],grid)
        for row in range(grid.rows):
            for col in range(grid.columns):
                rectified_center = ((col+.5)*panel.image.shape[1]/grid.columns,
                                    (row+.5)*panel.image.shape[0]/grid.rows)
                expected = project_points([rectified_center],panel.to_source)[0]
                np.testing.assert_allclose(layout.position(col,row),expected,atol=1e-8)
            points = np.array([layout.position(c,row) for c in range(grid.columns)])
            self.assertLess(np.linalg.svd(np.column_stack([points,np.ones(len(points))]))[1][-1],1e-8)
        self.assertIsNone(grid.move_line('x',1,grid.x_lines_px[1]+5).projection)
        self.assertIsNone(grid.distribute('y').projection)

    def test_other_dimensions_and_camera_angles(self):
        for columns,rows in [(3,2),(4,5),(7,3)]:
            with self.subTest(columns=columns,rows=rows):
                panel = infer_camera_panel(photographed_patchwork(columns,rows))
                self.assertIsNotNone(panel)
                self.assertEqual((panel.grid.columns,panel.grid.rows),(columns,rows))

    def test_plain_cloth_does_not_create_a_grid_or_a_foreground_region(self):
        image = np.full((600,800,3),230,np.uint8)
        self.assertIsNone(infer_camera_panel(image))
        self.assertIsNone(MotifDetector._local_colour_region(image[:160,:160],500))
