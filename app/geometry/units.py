"""Physical unit conversion with inches as the canonical application unit."""

from __future__ import annotations

from enum import Enum


class LengthUnit(str, Enum):
    INCHES = "in"
    CENTIMETRES = "cm"
    MILLIMETRES = "mm"

    @property
    def display_name(self) -> str:
        return {
            LengthUnit.INCHES: "Inches",
            LengthUnit.CENTIMETRES: "Centimetres",
            LengthUnit.MILLIMETRES: "Millimetres",
        }[self]

    @property
    def singular_name(self) -> str:
        return {
            LengthUnit.INCHES: "inch",
            LengthUnit.CENTIMETRES: "centimetre",
            LengthUnit.MILLIMETRES: "millimetre",
        }[self]

    @property
    def area_suffix(self) -> str:
        return f"{self.value}²"


_UNITS_PER_INCH = {
    LengthUnit.INCHES: 1.0,
    LengthUnit.CENTIMETRES: 2.54,
    LengthUnit.MILLIMETRES: 25.4,
}


def from_inches(value_in: float, unit: LengthUnit) -> float:
    return float(value_in) * _UNITS_PER_INCH[unit]


def to_inches(value: float, unit: LengthUnit) -> float:
    return float(value) / _UNITS_PER_INCH[unit]


def area_from_square_inches(value_in2: float, unit: LengthUnit) -> float:
    factor = _UNITS_PER_INCH[unit]
    return float(value_in2) * factor * factor


def area_to_square_inches(value: float, unit: LengthUnit) -> float:
    factor = _UNITS_PER_INCH[unit]
    return float(value) / (factor * factor)


def convert_length(value: float, source: LengthUnit, target: LengthUnit) -> float:
    return from_inches(to_inches(value, source), target)


def convert_area(value: float, source: LengthUnit, target: LengthUnit) -> float:
    return area_from_square_inches(area_to_square_inches(value, source), target)
