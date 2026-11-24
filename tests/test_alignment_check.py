import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from app.export.alignment_check import export_alignment_check
from app.export.svg_exporter import SVG_NAMESPACE, SVGExporter
from app.export.verifier import verify_export_geometry
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit
from app.models import Detection


class AlignmentCheckTests(unittest.TestCase):
    def test_reference_page_centres_and_measurement_sheet_use_known_physical_dimensions(self):
        for unit,factor in ((LengthUnit.INCHES,1.),(LengthUnit.MILLIMETRES,25.4)):
            with self.subTest(unit=unit),tempfile.TemporaryDirectory() as directory:
                result=export_alignment_check(Path(directory)/'check.svg',36.,24.,unit)
                root=ET.parse(result.svg_path).getroot()
                self.assertEqual(root.attrib['viewBox'],f'0 0 {36*factor:g} {24*factor:g}')
                rects=root.findall(f'{{{SVG_NAMESPACE}}}rect')
                self.assertEqual(len(rects),5)
                for rect,expected in zip(rects,((1.,1.),(33.,1.),(1.,21.),(33.,21.),(17.,11.))):
                    self.assertAlmostEqual(float(rect.attrib['x']),expected[0]*factor)
                    self.assertAlmostEqual(float(rect.attrib['y']),expected[1]*factor)
                    self.assertAlmostEqual(float(rect.attrib['width']),2*factor)
                    self.assertAlmostEqual(float(rect.attrib['height']),2*factor)
                with result.measurements_path.open(encoding='utf-8',newline='') as stream:
                    rows=list(csv.DictReader(stream))
                self.assertEqual(len(rows),5)
                self.assertEqual(float(rows[-1]['expected_centre_x_mm']),457.2)
                self.assertEqual(float(rows[-1]['expected_centre_y_mm']),304.8)
                self.assertTrue(all(not row['measured_centre_x_mm'] for row in rows))
                self.assertTrue(result.instructions_path.exists())

    def test_small_custom_beds_keep_all_reference_squares_in_the_bed(self):
        with tempfile.TemporaryDirectory() as directory:
            result=export_alignment_check(Path(directory)/'small.svg',4.,3.)
            for rect in ET.parse(result.svg_path).getroot().findall(f'{{{SVG_NAMESPACE}}}rect'):
                x,y,w,h=(float(rect.attrib[k]) for k in ('x','y','width','height'))
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+w,4);self.assertLessEqual(y+h,3)

    def test_existing_measurements_are_preserved_before_any_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'check.svg'
            result=export_alignment_check(path,36.,24.)
            result.measurements_path.write_text('Recorded workshop measurements',encoding='utf-8')
            svg=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'preserve recorded measurements'):
                export_alignment_check(path,40.,20.)
            self.assertEqual(result.measurements_path.read_text(encoding='utf-8'),'Recorded workshop measurements')
            self.assertEqual(path.read_bytes(),svg)

    def test_verifier_detects_serialized_position_and_dimension_errors(self):
        mapper=CoordinateMapper(2340,1560)
        cut=Detection.from_pixel_center(1,(876.125,654.375),mapper)
        original=SVGExporter.build_tree
        def corrupted(exporter,*args,**kwargs):
            tree=original(exporter,*args,**kwargs)
            rect=tree.getroot().find(f'{{{SVG_NAMESPACE}}}rect')
            rect.set('x',str(float(rect.attrib['x'])+.25))
            rect.set('height',str(float(rect.attrib['height'])+.5))
            return tree
        with patch.object(SVGExporter,'build_tree',corrupted):
            check=verify_export_geometry(mapper,[cut])
        self.assertAlmostEqual(check.maximum_error_x_px,16.25)
        self.assertAlmostEqual(check.maximum_error_y_px,32.5)
        check=verify_export_geometry(mapper,[cut])
        self.assertLess(check.maximum_error_x_px,1e-8)
        self.assertLess(check.maximum_error_y_px,1e-8)

    def test_verifier_rejects_changed_svg_page_size_or_origin(self):
        mapper=CoordinateMapper(2340,1560)
        original=SVGExporter.build_tree
        for attribute,value in (('width','35in'),('viewBox','1 0 36 24')):
            def corrupted(exporter,*args,**kwargs):
                tree=original(exporter,*args,**kwargs)
                tree.getroot().set(attribute,value)
                return tree
            with self.subTest(attribute=attribute),patch.object(SVGExporter,'build_tree',corrupted):
                with self.assertRaisesRegex(ValueError,'page size or origin'):
                    verify_export_geometry(mapper,[])


if __name__=='__main__':unittest.main()
