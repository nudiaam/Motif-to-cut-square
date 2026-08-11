"""Centralized conversion between camera-image pixels and physical bed units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .units import LengthUnit, from_inches, to_inches


BED_WIDTH_IN = 36.0
BED_HEIGHT_IN = 24.0


@dataclass(frozen=True, slots=True)
class CoordinateMapper:
    """Map a full-bed image to a configurable physical laser bed.

    DEMO_ASSUMPTION: the input image is placed linearly inside the physical bed,
    preserving its aspect ratio unless an explicit placement is supplied. The
    origin is top-left, X increases right, Y increases down, and there is no crop,
    distortion, perspective correction, or homography. This assumption must be
    validated physically on the selected machine.

    All camera-pixel <-> physical-inch transformations live in this class so a
    calibrated implementation can replace this one without changing detection,
    editing, visualization, or export code.
    """

    image_width_px: int
    image_height_px: int
    bed_width_in: float = BED_WIDTH_IN
    bed_height_in: float = BED_HEIGHT_IN
    image_x_in: float = 0.0
    image_y_in: float = 0.0
    image_width_in: float | None = None
    image_height_in: float | None = None

    def __post_init__(self) -> None:
        if self.image_width_px <= 0 or self.image_height_px <= 0:
            raise ValueError("Image dimensions must be positive")
        if self.bed_width_in <= 0 or self.bed_height_in <= 0:
            raise ValueError("Bed dimensions must be positive")
        if self.image_width_in is None:
            object.__setattr__(self, "image_width_in", self.bed_width_in)
        if self.image_height_in is None:
            object.__setattr__(self, "image_height_in", self.bed_height_in)
        assert self.image_width_in is not None and self.image_height_in is not None
        if self.image_width_in <= 0 or self.image_height_in <= 0:
            raise ValueError("Physical image dimensions must be positive")
        tolerance = 1e-9
        if (
            self.image_x_in < -tolerance
            or self.image_y_in < -tolerance
            or self.image_x_in + self.image_width_in > self.bed_width_in + tolerance
            or self.image_y_in + self.image_height_in > self.bed_height_in + tolerance
        ):
            raise ValueError("Image placement must remain inside the physical bed")

    @classmethod
    def contain_image(
        cls,
        image_width_px: int,
        image_height_px: int,
        bed_width_in: float = BED_WIDTH_IN,
        bed_height_in: float = BED_HEIGHT_IN,
    ) -> "CoordinateMapper":
        if image_width_px <= 0 or image_height_px <= 0:
            raise ValueError("Image dimensions must be positive")
        uniform_inches_per_pixel = min(
            bed_width_in / image_width_px,
            bed_height_in / image_height_px,
        )
        image_width_in = image_width_px * uniform_inches_per_pixel
        image_height_in = image_height_px * uniform_inches_per_pixel
        return cls(
            image_width_px,
            image_height_px,
            bed_width_in,
            bed_height_in,
            (bed_width_in - image_width_in) / 2.0,
            (bed_height_in - image_height_in) / 2.0,
            image_width_in,
            image_height_in,
        )

    @property
    def image_bed_rect_inches(self) -> tuple[float, float, float, float]:
        assert self.image_width_in is not None and self.image_height_in is not None
        return (
            self.image_x_in,
            self.image_y_in,
            self.image_width_in,
            self.image_height_in,
        )

    @property
    def px_per_inch_x(self) -> float:
        assert self.image_width_in is not None
        return self.image_width_px / self.image_width_in

    @property
    def px_per_inch_y(self) -> float:
        assert self.image_height_in is not None
        return self.image_height_px / self.image_height_in

    def pixels_per_unit(self, unit: LengthUnit) -> tuple[float, float]:
        return (
            self.px_per_inch_x / from_inches(1.0, unit),
            self.px_per_inch_y / from_inches(1.0, unit),
        )

    def pixel_to_inches(self, x_px: float, y_px: float) -> tuple[float, float]:
        return (
            self.image_x_in + float(x_px) / self.image_width_px * self.image_width_in,
            self.image_y_in + float(y_px) / self.image_height_px * self.image_height_in,
        )

    def inches_to_pixel(self, x_in: float, y_in: float) -> tuple[float, float]:
        return (
            (float(x_in) - self.image_x_in) / self.image_width_in * self.image_width_px,
            (float(y_in) - self.image_y_in) / self.image_height_in * self.image_height_px,
        )

    def pixel_to_unit(
        self, x_px: float, y_px: float, unit: LengthUnit
    ) -> tuple[float, float]:
        x_in, y_in = self.pixel_to_inches(x_px, y_px)
        return from_inches(x_in, unit), from_inches(y_in, unit)

    def unit_to_pixel(
        self, x_value: float, y_value: float, unit: LengthUnit
    ) -> tuple[float, float]:
        return self.inches_to_pixel(to_inches(x_value, unit), to_inches(y_value, unit))

    def pixel_rect_to_inches(
        self, rect_px: Iterable[float]
    ) -> tuple[float, float, float, float]:
        x_px, y_px, width_px, height_px = rect_px
        x_in, y_in = self.pixel_to_inches(x_px, y_px)
        right_in, bottom_in = self.pixel_to_inches(
            x_px + width_px, y_px + height_px
        )
        return x_in, y_in, right_in - x_in, bottom_in - y_in

    def inches_rect_to_pixel(
        self, rect_in: Iterable[float]
    ) -> tuple[float, float, float, float]:
        x_in, y_in, width_in, height_in = rect_in
        x_px, y_px = self.inches_to_pixel(x_in, y_in)
        right_px, bottom_px = self.inches_to_pixel(
            x_in + width_in, y_in + height_in
        )
        return x_px, y_px, right_px - x_px, bottom_px - y_px

    def round_trip_error(self, x_px: float, y_px: float) -> tuple[float, float]:
        x_in, y_in = self.pixel_to_inches(x_px, y_px)
        round_x, round_y = self.inches_to_pixel(x_in, y_in)
        return abs(round_x - x_px), abs(round_y - y_px)
