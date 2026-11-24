"""Measured print geometry must improve placement without inventing artwork."""
from dataclasses import replace
from pathlib import Path
import unittest

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector
from app.imaging.logical_layout import layout_from_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.imaging.printed_partition import infer_straight_printed_partition
from app.imaging.section_evidence import refine_artwork_sections
from app.imaging.analysis_frame import scale_grid


def uneven_print():
    xs=(40.,190.,340.,490.,640.);ys=(40.,190.,340.,490.)
    vertices=np.stack(np.meshgrid(xs,ys),axis=-1)
    for r,c,delta in ((1,1,(8,-6)),(1,2,(-7,5)),(1,3,(7,7)),
                      (2,1,(6,7)),(2,2,(-6,-7)),(2,3,(8,-5))):
        vertices[r,c]+=delta
    image=np.full((540,690,3),240,np.uint8)
    for r in range(3):
        for c in range(4):
            poly=np.array([vertices[r,c],vertices[r,c+1],vertices[r+1,c+1],vertices[r+1,c]],np.int32)
            value=170+((r+c)%2)*60
            cv2.fillConvexPoly(image,poly,(value,value,value))
            cv2.circle(image,(round(xs[c]+55),round(ys[r]+65)),15,(35,70,90),-1)
    return image,PanelGrid(xs,ys,.95,'local_contrast'),vertices


class LocalSectionAlignmentTests(unittest.TestCase):
    def test_touching_pastels_recover_divisions_with_no_cloth_outline(self):
        colours = ((155,167,172), (202,215,209), (174,191,179),
                   (207,208,197), (155,166,154), (193,186,181))
        pitch = 135
        for cols, rows in ((4, 3), (6, 4)):
            with self.subTest(cols=cols, rows=rows):
                image = np.full((rows*pitch+80, cols*pitch+95, 3), 220, np.uint8)
                for row in range(rows):
                    for col in range(cols):
                        x, y = 43+col*pitch, 36+row*pitch
                        colour = colours[(row*3+col) % len(colours)]
                        image[y:y+pitch, x:x+pitch] = colour
                        for offset in range(8, pitch, 14):
                            if (row+col) % 2:
                                cv2.line(image, (x+2, y+offset), (x+pitch-2, y+offset),
                                         tuple(value-9 for value in colour), 2)
                            else:
                                for y_offset in range(8, pitch, 20):
                                    cv2.circle(image, (x+offset, y+y_offset), 2,
                                               tuple(value+12 for value in colour), -1)
                        cv2.circle(image, (x+pitch//2, y+pitch//2), 32, (147,142,135), -1)
                panel = infer_straight_printed_partition(image)
                self.assertIsNotNone(panel)
                self.assertEqual((panel.grid.columns, panel.grid.rows), (cols, rows))
                np.testing.assert_allclose(np.asarray(panel.grid.x_lines_px)*panel.to_source[0,0],
                                           43+pitch*np.arange(cols+1), atol=6.)
                np.testing.assert_allclose(np.asarray(panel.grid.y_lines_px)*panel.to_source[1,1],
                                           36+pitch*np.arange(rows+1), atol=6.)

    def test_touching_pastel_fallback_rejects_one_axis_texture(self):
        bands = np.repeat(np.array([160, 220] * 4, dtype=np.uint8), 120)
        image = np.tile(bands[None, :, None], (640, 1, 3))
        self.assertIsNone(infer_straight_printed_partition(image))

    def test_individual_printed_corners_replace_mean_spacing(self):
        image,grid,vertices=uneven_print()
        original=image.copy()
        refined=refine_artwork_sections(image,grid)
        self.assertNotEqual(refined,grid)
        self.assertEqual((refined.columns,refined.rows),(4,3))
        polygons=np.array(refined.cell_regions_px).reshape(3,4,4,2)
        for r in (1,2):
            for c in (1,2,3):
                np.testing.assert_allclose(polygons[r,c,0],vertices[r,c],atol=1.2)
                np.testing.assert_allclose(polygons[r,c,0],polygons[r-1,c-1,2],atol=1e-8)
        # Unverified outer limits remain exactly as supplied.
        np.testing.assert_allclose(polygons[0,:,0],vertices[0,:-1],atol=1e-8)
        np.testing.assert_array_equal(image,original)
        self.assertTrue(refined.review_reasons)

    def test_manual_and_projective_guides_remain_explicit_user_geometry(self):
        image,grid,_=uneven_print()
        manual=replace(grid,source='manual')
        self.assertIs(refine_artwork_sections(image,manual),manual)
        projected=replace(grid,projection=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))
        self.assertIs(refine_artwork_sections(image,projected),projected)

    def test_boundary_measurement_survives_changes_of_input_resolution(self):
        image,grid,vertices=uneven_print()
        for scale in (.5,.75,1.5):
            with self.subTest(scale=scale):
                pixels=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
                refined=refine_artwork_sections(pixels,scale_grid(grid,scale,scale))
                polygons=np.array(refined.cell_regions_px).reshape(3,4,4,2)/scale
                for r in (1,2):
                    for c in (1,2,3):
                        np.testing.assert_allclose(polygons[r,c,0],vertices[r,c],atol=2.)

    def test_plain_cloth_and_one_axis_stripes_cannot_establish_sections(self):
        _,grid,_=uneven_print()
        blank=np.full((540,690,3),225,np.uint8)
        striped=blank.copy()
        for x in range(20,690,18):striped[:,x:x+5]=160
        for pixels in (blank,striped):
            self.assertIs(refine_artwork_sections(pixels,grid),grid)

    @unittest.skipUnless((Path(__file__).parents[1]/'Analisis_Lalikul/source.png').exists(),
                         'Private customer original is not installed')
    def test_customer_grey_panel_uses_the_observed_first_internal_crossing(self):
        import json
        root=Path(__file__).parents[1]/'Analisis_Lalikul'
        report=json.loads((root/'report.json').read_text(encoding='utf-8'))
        image=cv2.imread(str(root/'source.png'))
        detector=MotifDetector();detector.bed_reference=cv2.imread(str(root/'reference.png'))
        result=detector.detect_with_layout(image,DetectorSettings(**report['detection_run']['settings']))
        self.assertEqual(len(result.candidates),24)
        self.assertEqual((result.panel_grid.columns,result.panel_grid.rows),(6,4))
        layout=layout_from_panel_grid([],result.panel_grid)
        # Independently read at the white crossing in the original photograph.
        # The four-pixel tolerance is a manual reading, not physical calibration.
        np.testing.assert_allclose(layout.cell_polygon(1,1)[0],(466.,462.),atol=4.)
        self.assertTrue(result.panel_grid.review_reasons)


if __name__=='__main__':unittest.main()
