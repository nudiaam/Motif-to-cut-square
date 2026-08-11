"""Fixed-size physical cut-square geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinate_mapper import BED_HEIGHT_IN, BED_WIDTH_IN


CUT_SIZE_IN = 5.0


@dataclass(frozen=True, slots=True)
class CutSquare:
    x: float
    y: float
    width: float = CUT_SIZE_IN
    height: float = CUT_SIZE_IN

    @classmethod
    def centered_at(
        cls,
        center_x_in: float,
        center_y_in: float,
        width_in: float = CUT_SIZE_IN,
        height_in: float = CUT_SIZE_IN,
    ) -> "CutSquare":
        if width_in <= 0 or height_in <= 0:
            raise ValueError("Cut dimensions must be positive")
        return cls(
            center_x_in - width_in / 2.0,
            center_y_in - height_in / 2.0,
            width_in,
            height_in,
        )

    def is_valid(
        self,
        bed_width_in: float = BED_WIDTH_IN,
        bed_height_in: float = BED_HEIGHT_IN,
        tolerance: float = 1e-9,
    ) -> bool:
        return (
            self.x >= -tolerance
            and self.y >= -tolerance
            and self.x + self.width <= bed_width_in + tolerance
            and self.y + self.height <= bed_height_in + tolerance
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.width, self.height
