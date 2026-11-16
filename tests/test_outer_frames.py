"""A corrected interior cannot leave an unverified, displaced outer frame."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from dataclasses import replace
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from PySide6.QtWidgets import QApplication

from app.imaging.visual_grid import refine_printed_boundaries, _observed_outer_frame
from app.imaging.panel_grid import PanelGrid
from app.geometry.units import LengthUnit
from app.ui.main_window import MainWindow
from app.export.svg_exporter import SVG_NAMESPACE

PHOTO = Path(__file__).parent/'fixtures/generated/framed_animals_6x4.png'


class OuterFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def sheet(with_outer=True):
        image = np.full((760,1000,3),20,np.uint8)
        image[15:745,20:980] = 225
        xs = (80.,220.,360.,500.,640.,780.,920.)
        ys = (60.,200.,340.,480.,620.)
        for y in ys if with_outer else ys[1:-1]:
            cv2.line(image,(80,int(y)),(920,int(y)),(70,70,70),2)
        for x in xs:
            cv2.line(image,(int(x),60),(int(x),620),(70,70,70),2)
        proposal = PanelGrid(xs,(92.,220.,360.,500.,640.),.92,'visual')
        return image, proposal, ys

    @staticmethod
    def received_proposal():
        # Recorded pre-refinement proposal that reproduced the received report.
        # The expected frame positions below are independently read on the photo.
        return PanelGrid((217.1135584415586,404.39903896103914,591.6845194805196,
            778.97,966.2554805194807,1153.540961038961,1340.8264415584415),
            (99.61677272727263,279.86986363636356,460.1229545454545,
             640.3760454545455,820.6291363636363),.9078989422308701,'visual')

    def test_displaced_exterior_recovers_observed_frame_on_all_four_sides(self):
        image=cv2.imread(str(PHOTO));grid=self.received_proposal()
        ys=(60.,250.,439.,615.,809.)
        for transpose in (False,True):
            for flipped in (False,True):
                with self.subTest(transpose=transpose,flipped=flipped):
                    im=image.copy();g=grid;expected=ys
                    if flipped:
                        im=cv2.flip(im,0)
                        expected=tuple(im.shape[0]-1-y for y in reversed(ys))
                        g=replace(g,y_lines_px=tuple(im.shape[0]-1-y for y in reversed(g.y_lines_px)))
                    if transpose:
                        im=cv2.transpose(im)
                        g=replace(g,x_lines_px=g.y_lines_px,y_lines_px=g.x_lines_px)
                    refined=refine_printed_boundaries(im,g)
                    found=refined.x_lines_px if transpose else refined.y_lines_px
                    np.testing.assert_allclose(found,expected,atol=4.)
                    edge=-1 if flipped else 0
                    self.assertAlmostEqual(found[edge],expected[edge],delta=1.)
                    self.assertFalse(refined.review_reasons)

    def test_missing_outer_stroke_is_not_replaced_by_spacing_prediction(self):
        blank=np.full((350,400,3),225,np.uint8)
        self.assertIsNone(_observed_outer_frame(blank,0,60.,140.,(0.,350.)))
        image=cv2.imread(str(PHOTO));grid=self.received_proposal()
        with patch('app.imaging.visual_grid._observed_outer_frame',return_value=None):
            refined=refine_printed_boundaries(image,grid)
        self.assertEqual(refined.y_lines_px[0],grid.y_lines_px[0])
        self.assertTrue(any('could not be confirmed' in r for r in refined.review_reasons))

    def test_one_dark_stroke_has_one_centre_and_two_competing_strokes_abstain(self):
        for width in (1,3,5):
            with self.subTest(width=width):
                im=np.full((350,400,3),225,np.uint8)
                cv2.line(im,(0,60),(399,60),(65,65,65),width)
                result=_observed_outer_frame(im,0,68.,140.,(0.,350.))
                self.assertIsNotNone(result)
                self.assertAlmostEqual(result[0],60.,delta=1.)
        cv2.line(im,(0,82),(399,82),(65,65,65),5)
        self.assertIsNone(_observed_outer_frame(im,0,70.,140.,(0.,350.)))

    def test_manual_and_projected_guides_are_unchanged(self):
        image,grid,_=self.sheet()
        for protected in (replace(grid,source='manual'),replace(grid,
                projection=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)))):
            self.assertEqual(refine_printed_boundaries(image,protected),protected)

    def test_received_photo_centres_corners_sizes_and_svg(self):
        window=MainWindow();self.addCleanup(window.close)
        window._load_image(cv2.imread(str(PHOTO)),'framed animal sections')
        window.change_cut_size(4.,4.)
        window.detect_motifs()
        self.assertEqual(len(window.detections),24)
        self.assertEqual((window.logical_layout.columns,window.logical_layout.rows),(6,4))
        # Horizontal printed frames read on the original, independent of the
        # detector. Small variations along the slightly tilted frame are kept
        # within a four-pixel measurement tolerance, not a changed cut size.
        ys=(60.,250.,439.,615.,809.)
        for d in window.detections:
            row=d.layout_cell[1]
            self.assertAlmostEqual(d.center_px[1],(ys[row]+ys[row+1])/2,delta=4.)
            x,y,w,h=window.mapper.inches_rect_to_pixel(d.square_inches.as_tuple())
            self.assertGreaterEqual(y,ys[row]-4.)
            self.assertLessEqual(y+h,ys[row+1]+4.)
            self.assertFalse(d.panel_boundary_reason(window.mapper))
        centres={d.id:d.center_px for d in window.detections}
        def serialized():
            import xml.etree.ElementTree as ET
            return ET.tostring(window.svg_exporter.build_tree(window.mapper,
                window.detections,LengthUnit.INCHES).getroot())
        for size in (3.8,4.,4.3):
            window.change_cut_size(size,size)
            self.assertEqual({d.id:d.center_px for d in window.detections},centres)
            self.assertTrue(all(d.cut_width_inches==size and d.cut_height_inches==size
                                for d in window.detections))
            tree=window.svg_exporter.build_tree(window.mapper,window.detections)
            rects=tree.findall(f'{{{SVG_NAMESPACE}}}rect')
            self.assertEqual(len(rects),24)
            for d,rect in zip(window.detections,rects):
                for key,value in zip(('x','y','width','height'),d.square_inches.as_tuple()):
                    self.assertAlmostEqual(float(rect.attrib[key]),value,places=5)
        initial=serialized()
        window.canvas.set_view_scale(2.)
        window.canvas.center_view_on_bed_inches(18.,12.)
        self.assertEqual(serialized(),initial)


if __name__=='__main__':unittest.main()
