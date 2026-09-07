"""Fit an affine lattice that defines cut centres from artwork observations.

This module never detects artwork or creates cuts. Pixel geometry only; panel
seams, calibration, physical cut sizes and export policy are independent.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .panel_grid import PanelGrid


@dataclass(frozen=True, slots=True)
class LayoutObservation:
    detection_id: int
    center_px: tuple[float, float]
    bounding_box_px: tuple[int, int, int, int] | None = None
    edge_anchor_px: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class LayoutMatch:
    detection_id: int
    observed_px: tuple[float, float]
    proposed_px: tuple[float, float] | None
    column: int | None
    row: int | None
    residual_px: float | None
    status: str  # matched, outlier, duplicate
    review_reason: str = ""


@dataclass(frozen=True, slots=True)
class MissingPosition:
    column: int
    row: int
    center_px: tuple[float, float]
    source: str = "inferred"  # No image evidence; never an exportable detection.
    review_state: str = "proposed"  # Internal evidence class; never a UI step.
    reason: str = ""


@dataclass(frozen=True, slots=True)
class LogicalLayout:
    columns: int = 0
    rows: int = 0
    origin_px: tuple[float, float] = (0.0, 0.0)
    column_vector_px: tuple[float, float] = (0.0, 0.0)
    row_vector_px: tuple[float, float] = (0.0, 0.0)
    confidence: float = 0.0
    mean_residual_px: float = 0.0
    occupancy: float = 0.0
    matches: tuple[LayoutMatch, ...] = ()
    missing: tuple[MissingPosition, ...] = ()
    reason: str = "At least six automatic artwork detections are needed."
    source: str = "observations"
    projection: tuple[tuple[float, float, float], ...] | None = None

    @property
    def reliable(self) -> bool:
        return self.confidence >= 0.78

    def position(self, column: int, row: int) -> tuple[float, float]:
        if self.projection is not None:
            x, y, z = (line[0]*column + line[1]*row + line[2] for line in self.projection)
            return x/z, y/z
        return tuple(self.origin_px[i] + column * self.column_vector_px[i]
                     + row * self.row_vector_px[i] for i in (0, 1))


def layout_from_panel_grid(observations: list[LayoutObservation], grid: PanelGrid) -> LogicalLayout:
    """Assign artwork to an independently established grid, never refit to artwork.

    Only call for a reliable automatic grid or an explicitly confirmed manual
    grid. Guides being edited are not evidence until detection is rerun.
    """
    axes = []
    for lines in (grid.x_lines_px, grid.y_lines_px):
        centers = (np.asarray(lines[:-1]) + lines[1:]) / 2
        axes.append(np.linalg.lstsq(
            np.column_stack([np.ones(len(centers)), np.arange(len(centers))]),
            centers, rcond=None,
        )[0])
    (ox, dx), (oy, dy) = axes
    confidence = 1.0 if grid.source == "manual" else grid.confidence
    layout = LogicalLayout(columns=grid.columns, rows=grid.rows,
                           origin_px=(float(ox), float(oy)),
                           column_vector_px=(float(dx), 0.), row_vector_px=(0., float(dy)),
                           confidence=confidence, source=grid.source)
    if grid.lattice is not None:
        layout = replace(layout, origin_px=grid.lattice[0], column_vector_px=grid.lattice[1],
                         row_vector_px=grid.lattice[2], projection=grid.projection)
    inverse = np.linalg.inv(np.column_stack([layout.column_vector_px, layout.row_vector_px]))
    inverse_projection = np.linalg.inv(np.asarray(grid.projection)) if grid.projection is not None else None
    assignments = []
    spanning = {}
    covered = set()
    for item in observations:
        # A trimmed visual centre is useful for assigning an asymmetric motif
        # to an already established cell.  It must never define or refit the
        # shared grid geometry.
        x, y = item.edge_anchor_px or item.center_px
        large = False
        if item.bounding_box_px is not None:
            bx, by, bw, bh = item.bounding_box_px
            large = (bw > np.linalg.norm(layout.column_vector_px) * 1.35
                     or bh > np.linalg.norm(layout.row_vector_px) * 1.35)
            # A multi-cell illustration needs a stable whole-extent assignment
            # (for example a giraffe spanning two rows). Normal illustrations
            # use their trimmed visual core so a tail or smoke cannot move them
            # into a neighbouring cell.
            if large:
                x, y = bx + bw / 2.0, by + bh / 2.0
        col = int(np.searchsorted(grid.x_lines_px, x, side="right") - 1)
        row = int(np.searchsorted(grid.y_lines_px, y, side="right") - 1)
        if grid.lattice is not None:
            col, row = (int(v) for v in np.rint(inverse @ (np.array([x, y]) - layout.origin_px)))
        if inverse_projection is not None:
            pc, pr, pz = inverse_projection @ [x, y, 1.]
            col, row = int(round(pc/pz)), int(round(pr/pz))
        if item.bounding_box_px is not None:
            bx, by, bw, bh = item.bounding_box_px
            cells = {(c, r) for r in range(layout.rows) for c in range(layout.columns)
                     if bx <= layout.position(c, r)[0] <= bx+bw
                     and by <= layout.position(c, r)[1] <= by+bh}
            if large and len(cells) > 1:
                spanning[item.detection_id] = "Artwork spans multiple cells; review its cut assignment."
                covered.update(cells)
        inside = 0 <= col < grid.columns and 0 <= row < grid.rows
        position = layout.position(col, row)
        residual = float(np.linalg.norm(np.array(position) - (x, y)))
        assignments.append((residual, item, col, row, inside))
    occupied = set()
    matches = []
    for residual, item, col, row, inside in sorted(assignments, key=lambda a: a[0]):
        status = "outlier" if not inside else "duplicate" if (col, row) in occupied else "matched"
        if status == "matched":
            occupied.add((col, row))
        matches.append(LayoutMatch(item.detection_id, item.center_px,
                                   layout.position(col, row) if inside else None,
                                   col if inside else None, row if inside else None,
                                   residual, status, spanning.get(item.detection_id, "")))
    missing = tuple(MissingPosition(col, row, layout.position(col, row),
                                   review_state="proposed" if confidence >= .86 and (col, row) not in covered else "pending",
                                   reason="Covered by artwork assigned to another cell; review before adding a cut."
                                   if (col, row) in covered else "")
                    for row in range(grid.rows) for col in range(grid.columns)
                    if (col, row) not in occupied)
    return replace(layout, matches=tuple(sorted(matches, key=lambda m: m.detection_id)),
                   missing=missing, occupancy=len(occupied) / (grid.columns * grid.rows),
                   mean_residual_px=float(np.mean([m.residual_px for m in matches
                                                   if m.status == "matched"])) if occupied else 0.,
                   reason="Cut centres follow the panel grid; artwork is assigned to its cells.")


def _axis_fit(values: np.ndarray, spacing: float) -> tuple[float, float] | None:
    """Cluster repeated coordinates, then fit integer-spaced line centres.

    Artwork bounding-box centres are observations *inside* a cell, not direct
    measurements of the cell centre.  A tall giraffe, a wide train, and a
    compact bear can therefore have visibly different offsets while still
    belonging to a perfectly regular panel.  Keep the line clustering wider
    than the final regression consensus so those offsets do not split one
    physical row or column into several weak groups.
    """
    groups: list[list[float]] = []
    for value in sorted(values):
        if not groups or value - np.median(groups[-1]) > spacing * 0.40:
            groups.append([float(value)])
        else:
            groups[-1].append(float(value))
    supported = [group for group in groups if len(group) >= 2]
    if len(supported) < 2:
        return None
    centers = np.array([np.median(group) for group in supported])
    weights = np.array([len(group) for group in supported])
    gaps = np.diff(centers)
    best = None
    # Divided gaps allow an entirely missing interior row/column. A hole penalty
    # prevents arbitrarily fine lattices from explaining every observation.
    for step in np.unique(np.concatenate([gaps / k for k in (1, 2, 3)])):
        if not spacing * 0.55 <= step <= spacing * 1.8:
            continue
        for origin in centers:
            indices = np.rint((centers - origin) / step)
            keep = np.abs(centers - origin - indices * step) <= step * 0.30
            if keep.sum() < 2 or len(np.unique(indices[keep])) != keep.sum():
                continue
            design = np.column_stack([np.ones(keep.sum()), indices[keep]])
            intercept, fitted_step = np.linalg.lstsq(design, centers[keep], rcond=None)[0]
            if fitted_step <= 0:
                continue
            residual = np.abs(centers - intercept - indices * fitted_step) / fitted_step
            keep &= residual <= 0.30
            if keep.sum() < 2:
                continue
            holes = int(np.ptp(indices[keep])) + 1 - keep.sum()
            # Prefer repeated evidence with few holes.  Squared residuals keep
            # small motif-dependent offsets cheap while still rejecting a
            # phase that only loosely explains the observations.
            score = float(np.sum(weights[keep] * (1 - residual[keep] ** 2))) - holes * 0.8
            if best is None or score > best[0]:
                best = score, float(intercept), float(fitted_step)
    return None if best is None else (best[1], best[2])


def fit_logical_layout(observations: list[LayoutObservation]) -> LogicalLayout:
    """Infer rows/columns from observed centres, tolerating small rotation/shear.

    Deterministic nearest-neighbour directions + 1D clustering initialise the
    lattice. RANSAC and robust regression reject false positives before scoring
    support, occupancy, residuals and evidence per row/column. Sparse, one-row,
    and ambiguous layouts deliberately remain uncorrected.
    """
    if len(observations) < 6:
        return LogicalLayout()
    points = np.asarray([item.center_px for item in observations], dtype=float)
    if not np.isfinite(points).all():
        return LogicalLayout(reason="Non-finite observation coordinates.")
    if len(points) > 600:
        return LogicalLayout(reason="Too many candidates for a reliable panel layout; review detection.")
    delta = points[None, :, :] - points[:, None, :]
    directions = []
    spacings = []
    for axis in (0, 1):
        along, across = np.abs(delta[:, :, axis]), np.abs(delta[:, :, 1 - axis])
        distance = np.where((along > 1e-6) & (across < along * 0.45), along, np.inf)
        nearest = np.argmin(distance, axis=1)
        valid = np.isfinite(distance[np.arange(len(points)), nearest])
        if valid.sum() < 4:
            return LogicalLayout(reason="No repeated rows and columns found.")
        vectors = delta[np.arange(len(points))[valid], nearest[valid]]
        directions.append(float(np.median(vectors[:, 1 - axis] / vectors[:, axis])))
        spacings.append(float(np.median(np.abs(vectors[:, axis]))))
    basis = np.array([[1.0, directions[1]], [directions[0], 1.0]])
    projected = points @ np.linalg.inv(basis).T
    axes = [_axis_fit(projected[:, i], spacings[i]) for i in (0, 1)]
    if any(axis is None for axis in axes):
        return LogicalLayout(reason="No stable repeated spacing found.")
    origins = np.array([axis[0] for axis in axes])
    steps = np.array([axis[1] for axis in axes])
    cells = np.rint((projected - origins) / steps).astype(int)
    design = np.column_stack([np.ones(len(points)), cells])
    initial = np.vstack([basis @ origins, (basis @ np.diag(steps)).T])

    def residuals(model: np.ndarray) -> np.ndarray:
        return np.linalg.norm((points - design @ model) @ np.linalg.inv(basis).T / steps, axis=1)

    best_model = initial
    best_score = -1.0
    rng = np.random.default_rng(0)
    samples = [rng.choice(len(points), 3, replace=False) for _ in range(160)]
    for sample in [None, *samples]:
        if sample is None:
            model = initial
        else:
            if np.linalg.matrix_rank(design[sample]) < 3:
                continue
            model = np.linalg.solve(design[sample], points[sample])
        if (np.any(np.linalg.norm(model[1:] - initial[1:], axis=1) > steps * 0.25)):
            continue
        error = residuals(model)
        score = float(np.maximum(0, 1 - (error / 0.20) ** 2).sum())
        if score > best_score:
            best_model, best_score = model, score

    model = best_model
    # Unique cells and repeated support are required: duplicates never increase
    # confidence and a lone false positive cannot extend the grid boundary.
    # A point may sit roughly a quarter-cell away from the fitted cell centre
    # solely because its artwork is asymmetric.  Consensus is still strict in
    # two dimensions and additionally requires repeated row and column support,
    # so increasing this observation tolerance does not authorize arbitrary
    # point clouds as grids.
    consensus_limit = 0.30

    def inliers(error: np.ndarray) -> np.ndarray:
        keep = error < consensus_limit
        occupied = set()
        for index in np.argsort(error, kind="stable"):
            cell = tuple(cells[index])
            if cell in occupied:
                keep[index] = False
            elif keep[index]:
                occupied.add(cell)
        while True:
            previous_count = int(keep.sum())
            for axis in (0, 1):
                for value in np.unique(cells[keep, axis]):
                    if np.sum(keep & (cells[:, axis] == value)) < 2:
                        keep[cells[:, axis] == value] = False
            if int(keep.sum()) == previous_count:
                break
        return keep

    for _ in range(6):
        error = residuals(model)
        keep = inliers(error)
        if keep.sum() < 6 or np.linalg.matrix_rank(design[keep]) < 3:
            return LogicalLayout(reason="Insufficient independent support for a grid.")
        # Cauchy-like weights prevent a valid but off-centre illustration from
        # pulling the common geometry, without removing its row/column vote.
        weights = 1.0 / np.sqrt(1.0 + (error[keep] / 0.12) ** 2)
        model = np.linalg.lstsq(design[keep] * weights[:, None],
                                points[keep] * weights[:, None], rcond=None)[0]
    error = residuals(model)
    keep = inliers(error)
    if keep.sum() < 6:
        return LogicalLayout(reason="Insufficient independent support for a grid.")

    # Optional robust centres are deliberately isolated from the global fit.
    # They may confirm that a single asymmetric illustration belongs to the
    # immediately adjacent outer row/column, but cannot move any grid line.
    edge_points = np.asarray([
        item.edge_anchor_px or item.center_px for item in observations
    ], dtype=float)
    lattice_coordinates = (edge_points - model[0]) @ np.linalg.inv(model[1:])
    edge_cells = np.rint(lattice_coordinates).astype(int)
    edge_design = np.column_stack([np.ones(len(points)), edge_cells])
    edge_error = np.linalg.norm(
        (edge_points - edge_design @ model) @ np.linalg.inv(basis).T / steps,
        axis=1,
    )

    # A regular inner block can establish both lattice vectors even when the
    # detector sees only one illustration in an outer row/column.  The normal
    # repeated-line rule intentionally removes that singleton, but discarding
    # it also collapses a real 6x4 panel to 6x3.  Re-admit a singleton solely as
    # evidence of one immediately adjacent edge line when the core is already
    # dense, at least 3x3, and the point lies very close to the extrapolated
    # lattice.  It does not participate in refitting, so it cannot pull or
    # rotate the shared geometry.
    core_minimum = cells[keep].min(axis=0)
    core_maximum = cells[keep].max(axis=0)
    core_size = core_maximum - core_minimum + 1
    core_occupancy = keep.sum() / float(np.prod(core_size))
    core_mean_error = float(error[keep].mean())
    if (np.all(core_size >= 3) and keep.sum() >= 12
            and core_occupancy >= 0.82 and core_mean_error <= 0.14):
        occupied_core = {tuple(cell) for cell in cells[keep]}
        edge_limit = 0.16
        singleton_edge_limit = 0.10
        admitted: set[int] = set()
        for axis in (0, 1):
            other = 1 - axis
            for boundary in (core_minimum[axis] - 1, core_maximum[axis] + 1):
                eligible = [
                    index for index in range(len(points))
                    if not keep[index]
                    and edge_error[index] < edge_limit
                    and edge_cells[index, axis] == boundary
                    and core_minimum[other] <= edge_cells[index, other] <= core_maximum[other]
                    and tuple(edge_cells[index]) not in occupied_core
                ]
                # One best observation per cell is enough to confirm the edge;
                # duplicates remain outliers and never increase confidence.
                by_cell: dict[tuple[int, int], int] = {}
                for index in sorted(eligible, key=lambda item: edge_error[item]):
                    by_cell.setdefault(tuple(edge_cells[index]), index)
                if len(by_cell) >= 2:
                    admitted.update(by_cell.values())
                elif len(by_cell) == 1 and core_size[other] >= 4:
                    # A lone edge anchor is only persuasive when it is
                    # bracketed by several established perpendicular lines.
                    # This rejects isolated corner/bed fragments while still
                    # allowing the motorcycle-like case in a dense 6x3 core.
                    index = next(iter(by_cell.values()))
                    coordinate = edge_cells[index, other]
                    if (edge_error[index] < singleton_edge_limit
                            and core_minimum[other] < coordinate < core_maximum[other]):
                        admitted.add(index)
        for index in admitted:
            # The observation joins the already fitted lattice at the robustly
            # assigned cell.  The model itself remains exactly unchanged.
            cells[index] = edge_cells[index]
            design[index] = edge_design[index]
            error[index] = edge_error[index]
            keep[index] = True

    minimum = cells[keep].min(axis=0)
    maximum = cells[keep].max(axis=0)
    columns, rows = (int(value) for value in maximum - minimum + 1)
    if columns < 2 or rows < 2 or columns * rows > 900:
        return LogicalLayout(reason="Layout dimensions are insufficient or too sparse.")
    occupancy = float(keep.sum() / (columns * rows))
    mean_error = float(error[keep].mean())
    support = float(keep.sum() / len(points))
    evidence = min(1.0, float(keep.sum()) / 10.0)
    # Confidence describes how well a repeated lattice explains the scene.
    # Outliers must not deform the model, but multiplying directly by inlier
    # ratio made a sound 23-cell grid fail merely because five detector
    # fragments also existed.  Occupancy and repeated line support already
    # guard against sparse accidental grids, so outliers receive a bounded
    # penalty.  Squared residual quality reflects normal bbox-centre variation
    # while dropping rapidly for genuinely loose geometry.
    outlier_quality = 0.65 + 0.35 * support
    residual_quality = max(0.0, 1.0 - (mean_error / 0.38) ** 2)
    confidence = float(np.clip(outlier_quality * occupancy ** 0.75 * evidence
                              * residual_quality, 0, 1))
    origin = model[0] + minimum @ model[1:]
    occupied = {tuple(cell) for cell in cells[keep]}
    matches = []
    for index, observation in enumerate(observations):
        proposed = design[index] @ model
        status = "matched" if keep[index] else (
            "duplicate" if error[index] < 0.20 and tuple(cells[index]) in occupied else "outlier")
        matches.append(LayoutMatch(
            observation.detection_id, observation.center_px,
            tuple(float(v) for v in proposed) if status == "matched" else None,
            int(cells[index, 0] - minimum[0]) if status == "matched" else None,
            int(cells[index, 1] - minimum[1]) if status == "matched" else None,
            float(np.linalg.norm(points[index] - proposed)), status,
        ))
    missing = []
    for row in range(rows):
        for column in range(columns):
            cell = minimum + (column, row)
            if tuple(cell) in occupied:
                continue
            supported = all(np.sum(cells[keep, axis] == cell[axis]) >= 2 for axis in (0, 1))
            state = "proposed" if confidence >= 0.86 and occupancy >= 0.80 and supported else "pending"
            location = origin + np.array([column, row]) @ model[1:]
            missing.append(MissingPosition(
                column, row, tuple(float(v) for v in location), review_state=state,
            ))
    return LogicalLayout(
        columns, rows, tuple(float(v) for v in origin),
        tuple(float(v) for v in model[1]), tuple(float(v) for v in model[2]),
        confidence, float(np.linalg.norm(points[keep] - design[keep] @ model, axis=1).mean()),
        occupancy, tuple(matches), tuple(missing),
        "Cut centres determined by the fitted grid." if confidence >= 0.78
        else "Low confidence — individual cut positions are provisional.",
    )
