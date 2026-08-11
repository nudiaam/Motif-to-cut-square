"""Generate a repeatable fabric-and-motifs image without external files."""

from __future__ import annotations

import cv2
import numpy as np

from app.geometry.coordinate_mapper import CoordinateMapper


def create_demo_image(width_px: int = 1350, height_px: int = 900) -> np.ndarray:
    """Return a BGR image containing 12 visually distinct, separated motifs."""
    if width_px <= 0 or height_px <= 0:
        raise ValueError("Demo image dimensions must be positive")

    rng = np.random.default_rng(20250314)
    y_grid, x_grid = np.mgrid[0:height_px, 0:width_px]
    weave = 2.1 * np.sin(x_grid / 7.0) + 1.5 * np.cos(y_grid / 9.0)
    noise = rng.normal(0.0, 1.4, (height_px, width_px))
    texture = weave + noise
    base_bgr = np.array([218.0, 226.0, 232.0], dtype=np.float32)
    image = np.empty((height_px, width_px, 3), dtype=np.float32)
    image[:, :, 0] = base_bgr[0] + texture * 0.75
    image[:, :, 1] = base_bgr[1] + texture * 0.90
    image[:, :, 2] = base_bgr[2] + texture
    image = np.clip(image, 0, 255).astype(np.uint8)

    mapper = CoordinateMapper(width_px, height_px)
    motifs = [
        ((3.0, 3.1), (2.1, 1.8), (76, 67, 201), 0),
        ((9.3, 3.8), (2.8, 1.6), (180, 72, 53), 1),
        ((16.0, 3.2), (1.7, 2.2), (41, 151, 235), 2),
        ((23.2, 4.0), (2.5, 1.9), (71, 171, 74), 3),
        # Close to the top/right edges, but the fixed 5 inch cut still fits.
        ((32.8, 2.8), (1.8, 1.4), (177, 73, 176), 4),
        ((5.4, 10.3), (2.4, 2.4), (40, 137, 194), 5),
        ((12.5, 10.0), (2.0, 1.7), (193, 121, 47), 0),
        ((19.2, 10.8), (2.8, 2.0), (73, 80, 210), 1),
        ((27.2, 10.2), (2.1, 2.5), (50, 166, 158), 2),
        # Intentionally outside the valid 5 x 5 cut region.
        ((35.0, 15.2), (1.4, 2.0), (36, 80, 222), 3),
        ((9.1, 19.4), (2.7, 1.8), (152, 77, 202), 4),
        ((21.8, 19.3), (2.3, 2.1), (45, 151, 88), 5),
    ]
    for center_in, size_in, color, style in motifs:
        center_px = mapper.inches_to_pixel(*center_in)
        size_px = mapper.inches_rect_to_pixel((0.0, 0.0, *size_in))[2:]
        _draw_motif(image, center_px, size_px, color, style)

    return image


def _draw_motif(
    image: np.ndarray,
    center_px: tuple[float, float],
    size_px: tuple[float, float],
    color: tuple[int, int, int],
    style: int,
) -> None:
    cx, cy = (int(round(value)) for value in center_px)
    width, height = (max(12, int(round(value))) for value in size_px)
    dark = tuple(max(0, channel - 48) for channel in color)
    light = tuple(min(255, channel + 45) for channel in color)

    if style == 0:  # flower, overlapping petals form one connected component
        radius_x, radius_y = width // 4, height // 4
        for angle in range(0, 360, 60):
            radians = np.deg2rad(angle)
            px = cx + int(np.cos(radians) * width * 0.25)
            py = cy + int(np.sin(radians) * height * 0.25)
            cv2.ellipse(image, (px, py), (radius_x, radius_y), angle, 0, 360, color, -1)
        cv2.circle(image, (cx, cy), max(5, min(width, height) // 6), dark, -1)
    elif style == 1:  # rounded capsule
        radius = max(5, min(width, height) // 3)
        x1, y1 = cx - width // 2, cy - height // 2
        x2, y2 = cx + width // 2, cy + height // 2
        cv2.rectangle(image, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(image, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for corner in ((x1 + radius, y1 + radius), (x2 - radius, y1 + radius),
                       (x1 + radius, y2 - radius), (x2 - radius, y2 - radius)):
            cv2.circle(image, corner, radius, color, -1)
        cv2.line(image, (cx - width // 3, cy), (cx + width // 3, cy), light, 4)
    elif style == 2:  # oval with a connected contrasting center
        cv2.ellipse(image, (cx, cy), (width // 2, height // 2), 18, 0, 360, color, -1)
        cv2.ellipse(image, (cx, cy), (width // 5, height // 3), -18, 0, 360, dark, -1)
    elif style == 3:  # irregular organic polygon
        points = np.array(
            [
                (cx - width // 2, cy - height // 8),
                (cx - width // 4, cy - height // 2),
                (cx + width // 4, cy - height // 3),
                (cx + width // 2, cy),
                (cx + width // 5, cy + height // 2),
                (cx - width // 3, cy + height // 3),
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(image, [points], color)
        cv2.circle(image, (cx, cy), max(5, min(width, height) // 7), light, -1)
    elif style == 4:  # diamond
        points = np.array(
            [
                (cx, cy - height // 2),
                (cx + width // 2, cy),
                (cx, cy + height // 2),
                (cx - width // 2, cy),
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(image, [points], color)
        cv2.line(image, (cx, cy - height // 3), (cx, cy + height // 3), dark, 5)
    else:  # butterfly-like silhouette
        cv2.ellipse(image, (cx - width // 5, cy), (width // 3, height // 2), -24, 0, 360, color, -1)
        cv2.ellipse(image, (cx + width // 5, cy), (width // 3, height // 2), 24, 0, 360, color, -1)
        cv2.rectangle(image, (cx - 4, cy - height // 3), (cx + 4, cy + height // 3), dark, -1)
