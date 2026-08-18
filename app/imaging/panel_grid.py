"""Panel-grid geometry shared by detection and the user interface."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class PanelGrid:
    """Axis-aligned panel boundaries expressed in source-image pixels."""

    x_lines_px: tuple[float, ...]
    y_lines_px: tuple[float, ...]
    confidence: float = 0.0
    source: str = "automatic"

    def __post_init__(self) -> None:
        if len(self.x_lines_px) < 3 or len(self.y_lines_px) < 3:
            raise ValueError("A panel grid needs at least two columns and two rows")
        if any(b <= a for a, b in zip(self.x_lines_px, self.x_lines_px[1:])):
            raise ValueError("Vertical grid lines must be strictly increasing")
        if any(b <= a for a, b in zip(self.y_lines_px, self.y_lines_px[1:])):
            raise ValueError("Horizontal grid lines must be strictly increasing")

    @property
    def columns(self) -> int:
        return len(self.x_lines_px) - 1

    @property
    def rows(self) -> int:
        return len(self.y_lines_px) - 1

    @classmethod
    def regular(
        cls,
        image_width: int,
        image_height: int,
        columns: int,
        rows: int,
        *,
        bounds_px: tuple[float, float, float, float] | None = None,
        confidence: float = 0.0,
        source: str = "manual",
    ) -> "PanelGrid":
        columns = max(2, int(columns))
        rows = max(2, int(rows))
        if bounds_px is None:
            left, top, right, bottom = 0.0, 0.0, float(image_width), float(image_height)
        else:
            left, top, right, bottom = (float(value) for value in bounds_px)
        x_step = (right - left) / columns
        y_step = (bottom - top) / rows
        return cls(
            tuple(left + index * x_step for index in range(columns + 1)),
            tuple(top + index * y_step for index in range(rows + 1)),
            confidence=confidence,
            source=source,
        )

    @property
    def bounds_px(self) -> tuple[float, float, float, float]:
        return (
            self.x_lines_px[0],
            self.y_lines_px[0],
            self.x_lines_px[-1],
            self.y_lines_px[-1],
        )

    def with_dimensions(
        self, image_width: int, image_height: int, columns: int, rows: int
    ) -> "PanelGrid":
        return PanelGrid.regular(
            image_width,
            image_height,
            columns,
            rows,
            bounds_px=self.bounds_px,
            confidence=0.0,
            source="manual",
        )

    def move_line(
        self,
        axis: str,
        index: int,
        value_px: float,
        *,
        minimum_gap_px: float = 2.0,
    ) -> "PanelGrid":
        lines = list(self.x_lines_px if axis == "x" else self.y_lines_px)
        if not 0 <= index < len(lines):
            return self
        lower = lines[index - 1] + minimum_gap_px if index > 0 else 0.0
        if index + 1 < len(lines):
            upper = lines[index + 1] - minimum_gap_px
        else:
            upper = max(lines[-1], float(value_px))
        lines[index] = min(max(float(value_px), lower), upper)
        if axis == "x":
            return replace(
                self,
                x_lines_px=tuple(lines),
                confidence=0.0,
                source="manual",
            )
        return replace(
            self,
            y_lines_px=tuple(lines),
            confidence=0.0,
            source="manual",
        )

    def distribute(self, axis: str) -> "PanelGrid":
        """Evenly distribute internal lines between the two outer boundaries."""

        lines = self.x_lines_px if axis == "x" else self.y_lines_px
        count = len(lines) - 1
        step = (lines[-1] - lines[0]) / count
        distributed = tuple(lines[0] + index * step for index in range(count + 1))
        if axis == "x":
            return replace(
                self,
                x_lines_px=distributed,
                confidence=0.0,
                source="manual",
            )
        return replace(
            self,
            y_lines_px=distributed,
            confidence=0.0,
            source="manual",
        )

    def cells(self) -> list[tuple[int, int, tuple[int, int, int, int]]]:
        result: list[tuple[int, int, tuple[int, int, int, int]]] = []
        for row in range(self.rows):
            top = int(round(self.y_lines_px[row]))
            bottom = int(round(self.y_lines_px[row + 1]))
            for column in range(self.columns):
                left = int(round(self.x_lines_px[column]))
                right = int(round(self.x_lines_px[column + 1]))
                result.append(
                    (column, row, (left, top, max(1, right - left), max(1, bottom - top)))
                )
        return result
