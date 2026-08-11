from __future__ import annotations

import unittest

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_square import CutSquare
from app.geometry.units import (
    LengthUnit,
    area_from_square_inches,
    area_to_square_inches,
    from_inches,
    to_inches,
)


class CoordinateMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = CoordinateMapper(1800, 1200)

    def test_pixel_origin_maps_to_physical_origin(self) -> None:
        self.assertEqual(self.mapper.pixel_to_inches(0, 0), (0.0, 0.0))

    def test_image_extent_maps_to_bed_extent(self) -> None:
        self.assertEqual(self.mapper.pixel_to_inches(1800, 1200), (36.0, 24.0))

    def test_pixel_center_maps_to_bed_center(self) -> None:
        self.assertEqual(self.mapper.pixel_to_inches(900, 600), (18.0, 12.0))

    def test_inches_to_pixels_inverse(self) -> None:
        self.assertEqual(self.mapper.inches_to_pixel(18, 12), (900.0, 600.0))

    def test_pixel_round_trip(self) -> None:
        source = (1377.125, 823.75)
        reconstructed = self.mapper.inches_to_pixel(
            *self.mapper.pixel_to_inches(*source)
        )
        self.assertAlmostEqual(reconstructed[0], source[0], places=12)
        self.assertAlmostEqual(reconstructed[1], source[1], places=12)

    def test_center_square_geometry(self) -> None:
        square = CutSquare.centered_at(18, 12)
        self.assertEqual(square.as_tuple(), (15.5, 9.5, 5.0, 5.0))

    def test_square_near_edge_is_invalid(self) -> None:
        self.assertFalse(CutSquare.centered_at(1, 1).is_valid())

    def test_square_touching_edge_is_valid(self) -> None:
        self.assertTrue(CutSquare.centered_at(2.5, 2.5).is_valid())

    def test_configurable_rectangle_geometry(self) -> None:
        rectangle = CutSquare.centered_at(18, 12, 4, 6)
        self.assertEqual(rectangle.as_tuple(), (16.0, 9.0, 4, 6))

    def test_length_and_area_unit_conversion(self) -> None:
        self.assertAlmostEqual(from_inches(5, LengthUnit.MILLIMETRES), 127.0)
        self.assertAlmostEqual(to_inches(127, LengthUnit.MILLIMETRES), 5.0)
        self.assertAlmostEqual(
            area_from_square_inches(1, LengthUnit.CENTIMETRES), 6.4516
        )
        self.assertAlmostEqual(
            area_to_square_inches(6.4516, LengthUnit.CENTIMETRES), 1.0
        )

    def test_custom_bed_mapper_scales_axes_independently(self) -> None:
        mapper = CoordinateMapper(1800, 1000, 40.0, 20.0)
        self.assertEqual(mapper.pixel_to_inches(900, 500), (20.0, 10.0))
        self.assertEqual(mapper.pixels_per_unit(LengthUnit.INCHES), (45.0, 50.0))

    def test_contained_image_preserves_aspect_ratio(self) -> None:
        mapper = CoordinateMapper.contain_image(2000, 1000, 36.0, 24.0)
        self.assertEqual(mapper.image_bed_rect_inches, (0.0, 3.0, 36.0, 18.0))
        self.assertAlmostEqual(mapper.px_per_inch_x, mapper.px_per_inch_y)
        self.assertEqual(mapper.pixel_to_inches(0, 0), (0.0, 3.0))
        self.assertEqual(mapper.pixel_to_inches(2000, 1000), (36.0, 21.0))


if __name__ == "__main__":
    unittest.main()
