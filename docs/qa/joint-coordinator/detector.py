"""Classical OpenCV motif detection for the prototype."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import cv2
import numpy as np

from .panel_grid import PanelGrid
from .visual_grid import infer_printed_panel_grid
from .pattern_grid import infer_repeated_artwork
from .camera_panel import infer_camera_panel, source_grid, project_points
from .grid_validation import contradicts_artwork
from .grid_guidance import extend_visual_grid, preserve_spanning_artwork
from .analysis_frame import fabric_analysis_bounds, translate_grid
from .extent_review import review_extents
from .scene_profile import POLICY, profile_scene, illumination_view
from .detection_plan import choose_grid, plan_zones, stable_artwork_grid
from .region_analysis import segment_zone
from .contrast_grid import infer_contrast_geometry


DETECTOR_REVISION = "2026-09-22-local-contrast-consensus"


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    sensitivity: int = 65
    minimum_area_px: int = 500
    morphological_cleanup: float = 0.25
    merge_distance_px_x: float = 14.0
    merge_distance_px_y: float = 14.0
    layout_mode: str = "auto"
    adaptive_planning: bool = True


@dataclass(frozen=True, slots=True)
class MotifCandidate:
    center_px: tuple[float, float]
    bounding_box_px: tuple[int, int, int, int]
    score: float
    area_px: int
    layout_center_px: tuple[float, float] | None = None
    review_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DetectionResult:
    candidates: tuple[MotifCandidate, ...]
    panel_grid: PanelGrid | None = None


def _inside_fabric(candidate: MotifCandidate, mask: np.ndarray | None) -> bool:
    if mask is None:
        return True
    x, y = candidate.center_px
    h, w = mask.shape
    return 0 <= x < w and 0 <= y < h and bool(mask[int(y), int(x)])


def _consolidate_grid_candidates(
    candidates: tuple[MotifCandidate, ...], panel_grid: PanelGrid,
) -> tuple[MotifCandidate, ...]:
    """Combine nearby fragments without hiding distinct artwork in one cell.

    All reliable grid sources share the same ownership rules. A grid boundary
    is not evidence that unexplained marks outside it are disposable.
    """
    if panel_grid.confidence < .78 and panel_grid.source != "manual":
        return candidates
    from .logical_layout import LayoutObservation, layout_from_panel_grid

    observations = [
        LayoutObservation(
            index,
            (x + width / 2., y + height / 2.),
            candidate.bounding_box_px,
            candidate.layout_center_px,
        )
        for index, candidate in enumerate(candidates)
        for x, y, width, height in [candidate.bounding_box_px]
    ]
    layout = layout_from_panel_grid(observations, panel_grid)
    matches = {match.detection_id: match for match in layout.matches}
    grouped: dict[tuple[int, int], list[int]] = {}
    unresolved = []
    for index in range(len(candidates)):
        match = matches[index]
        if match.column is None or match.row is None or match.status == "outlier":
            # A fabric outline establishes where the cloth ends, but not where
            # all printed cells end. Preserve unexplained in-fabric artwork.
            unresolved.append(replace(candidates[index], review_reasons=tuple(dict.fromkeys(
                (*candidates[index].review_reasons, "Artwork outside the proposed printed grid")))))
            continue
        grouped.setdefault((match.column, match.row), []).append(index)

    spacing = min(
        np.linalg.norm(layout.column_vector_px),
        np.linalg.norm(layout.row_vector_px),
    )
    consolidated = []
    for cell, indexes in grouped.items():
        primary_index = max(indexes, key=lambda index: candidates[index].area_px)
        primary = candidates[primary_index]
        merged = [primary]
        for index in indexes:
            if index == primary_index:
                continue
            candidate = candidates[index]
            distance = np.linalg.norm(
                np.asarray(candidate.center_px) - primary.center_px
            )
            ax, ay, aw, ah = primary.bounding_box_px
            bx, by, bw, bh = candidate.bounding_box_px
            overlaps = (
                min(ax + aw, bx + bw) >= max(ax, bx)
                and min(ay + ah, by + bh) >= max(ay, by)
            )
            gap = np.hypot(max(ax-bx-bw, bx-ax-aw, 0), max(ay-by-bh, by-ay-ah, 0))
            accessory = (candidate.area_px <= primary.area_px*.25 and gap <= spacing*.20)
            if overlaps or distance <= spacing * .24 or accessory:
                merged.append(candidate)
            else:
                unresolved.append(candidate)
        left = min(item.bounding_box_px[0] for item in merged)
        top = min(item.bounding_box_px[1] for item in merged)
        right = max(item.bounding_box_px[0] + item.bounding_box_px[2] for item in merged)
        bottom = max(item.bounding_box_px[1] + item.bounding_box_px[3] for item in merged)
        # A distant mark in the same cell must not enlarge the artwork extent.
        if right - left > spacing * 1.15 or bottom - top > spacing * 1.15:
            unresolved.extend(merged[1:])
            merged = [primary]
            left, top, width, height = primary.bounding_box_px
            right, bottom = left + width, top + height
        if len(merged) == 1:
            consolidated.append(primary)
            continue
        consolidated.append(MotifCandidate(
            ((left + right) / 2., (top + bottom) / 2.),
            (left, top, right - left, bottom - top),
            max(item.score for item in merged),
            sum(item.area_px for item in merged),
            primary.layout_center_px,
            tuple(dict.fromkeys(reason for item in merged for reason in item.review_reasons)),
        ))
    return tuple(sorted(consolidated + unresolved, key=lambda item: (
        item.center_px[1], item.center_px[0],
    )))


@dataclass(frozen=True, slots=True)
class _RawComponent:
    bounding_box_px: tuple[int, int, int, int]
    area_px: int
    contrast: float
    label_id: int = 0


class MotifDetector:
    """Locate visually distinct connected regions without classifying them."""

    def __init__(self):
        self.bed_reference = None
        self.reference_status = "No empty-bed reference"
        self.last_diagnostics = {}
        self._grid_notes = []
        self._plans = []

    def detect_with_layout(self, image_bgr, settings):
        from .bed_reference import locate_fabric, locate_bright_fabric, extend_to_fabric
        from .logical_layout import LayoutObservation, fit_logical_layout, layout_from_panel_grid
        self._validate_image(image_bgr)
        self._grid_notes = []
        self._plans = []
        scene = profile_scene(image_bgr) if settings.adaptive_planning else None
        evidence = (locate_fabric(image_bgr, self.bed_reference)
                    if self.bed_reference is not None else None)
        self.reference_status = evidence.reason if evidence else "No empty-bed reference"
        matched_reference = evidence is not None and evidence.mask is not None
        if not matched_reference:
            evidence = locate_bright_fabric(image_bgr) if settings.layout_mode == "auto" else None
        mask = evidence.mask if evidence is not None else None
        detection_image = image_bgr
        illumination = None
        if settings.adaptive_planning and settings.layout_mode == 'auto' and not matched_reference:
            alternate = illumination_view(image_bgr, mask)
            if alternate is not None:
                detection_image, illumination = alternate
                expanded = locate_bright_fabric(detection_image)
                if expanded.mask is not None:
                    # A shadow can make the original support incomplete. Keep
                    # either view's evidence, never intersect away dark artwork.
                    mask = cv2.bitwise_or(mask, expanded.mask)
        analysis_bounds = None
        if mask is not None and not np.any(mask):
            result = DetectionResult(())
        elif matched_reference:
            analysis = image_bgr.copy()
            analysis[mask == 0] = np.median(image_bgr[mask > 0], axis=0)
            result = self._detect_layout(analysis, settings)
        else:
            # Preserve the original camera/seam evidence. Only the segmentation
            # candidates are masked; source pixels and calibration never change.
            if mask is not None and settings.layout_mode == "auto":
                left, top, right, bottom = fabric_analysis_bounds(mask)
                analysis_bounds = [left, top, right, bottom]
                local = self._detect_layout(detection_image[top:bottom, left:right], settings,
                                            fabric_mask=mask[top:bottom, left:right])
                candidates = tuple(replace(c,
                    center_px=(c.center_px[0]+left, c.center_px[1]+top),
                    bounding_box_px=(c.bounding_box_px[0]+left, c.bounding_box_px[1]+top,
                                     *c.bounding_box_px[2:]),
                    layout_center_px=((c.layout_center_px[0]+left, c.layout_center_px[1]+top)
                                      if c.layout_center_px is not None else None),
                ) for c in local.candidates)
                result = DetectionResult(candidates, translate_grid(local.panel_grid, left, top))
            else:
                result = self._detect_layout(detection_image, settings, fabric_mask=mask)
        if settings.adaptive_planning and settings.layout_mode == 'auto' and not matched_reference:
            # Geometry must be recoverable before a global foreground mask or a
            # bright-fabric boundary succeeds. No transformed pixels become cuts.
            geometry = infer_contrast_geometry(image_bgr)
            if geometry is not None:
                proposal = geometry.grid
                previous = result.panel_grid
                same = (previous is not None and
                        (previous.columns,previous.rows) == (proposal.columns,proposal.rows) and
                        max(np.max(np.abs(np.array(previous.x_lines_px)-proposal.x_lines_px)),
                            np.max(np.abs(np.array(previous.y_lines_px)-proposal.y_lines_px)))
                        < min(np.median(np.diff(proposal.x_lines_px)),
                              np.median(np.diff(proposal.y_lines_px)))*.15)
                # An established complete-composition lattice remains authoritative,
                # including artwork legitimately spanning more than one cell.
                established = (previous is not None and previous.source in ('pattern','observations')
                               and previous.confidence >= .90)
                incomplete = (geometry.diagnostics['occupancy'] >
                              sum(_inside_fabric(c,mask) for c in result.candidates)/
                              (proposal.columns*proposal.rows)+.02)
                accepted = False
                if (not same or incomplete) and not established:
                    local = self.detect_in_grid(image_bgr, settings, proposal)
                    if len(local) >= proposal.columns*proposal.rows*.85:
                        result = DetectionResult(tuple(local), proposal)
                        # The rejected bright support must not erase recovered
                        # shadowed cells. Original whole-cell review still runs.
                        mask = None
                        analysis_bounds = None
                        accepted = True
                        self._grid_notes.append('Local contrast agrees across scales and thresholds; original pixels analysed by cell')
                self._plans.append({'stage':'contrast_geometry',**geometry.diagnostics,
                                    'columns':proposal.columns,'rows':proposal.rows,
                                    'accepted':accepted,'existing_geometry_agrees':bool(same),
                                    'established_compositions_preserved':established})
            else:
                self._plans.append({'stage':'contrast_geometry','accepted':False,
                                    'reason':'No agreement across contrast scales and thresholds'})
        candidates = tuple(c for c in result.candidates if _inside_fabric(c, mask))
        observations = [LayoutObservation(i, (x+bw/2, y+bh/2), c.bounding_box_px,
                                          c.layout_center_px)
                        for i, c in enumerate(candidates)
                        for x, y, bw, bh in [c.bounding_box_px]]
        grid = result.panel_grid
        layout = (layout_from_panel_grid(observations, grid) if grid and grid.confidence >= .78
                  else fit_logical_layout(observations))
        extended = (extend_to_fabric(layout, mask)
                    if matched_reference and settings.layout_mode == "auto" else None)
        if mask is not None and grid is None and layout.reliable and settings.layout_mode == "auto":
            # An unregistered bright boundary is sufficient to remove bed
            # marks, but not to fill blank fabric margins with extra rows.
            # Keep exactly the artwork-supported extent for consolidation.
            origin, col, row = layout.origin_px, layout.column_vector_px, layout.row_vector_px
            if extended is None:
                extended = PanelGrid(
                    tuple(origin[0] + (c-.5)*col[0] + row[0]*(layout.rows-1)/2
                          for c in range(layout.columns+1)),
                    tuple(origin[1] + (r-.5)*row[1] + col[1]*(layout.columns-1)/2
                          for r in range(layout.rows+1)),
                    layout.confidence, "fabric", (origin, col, row), layout.projection,
                )
        final_grid = extended or grid
        candidates = self.finalize_compositions(image_bgr, candidates, final_grid)
        if illumination is not None:
            first,last=illumination['affected_y_px']
            candidates=tuple(replace(c,review_reasons=tuple(dict.fromkeys((*c.review_reasons,
                'Illumination compensation used; check artwork in the shadowed band'))))
                if c.bounding_box_px[1] <= last and c.bounding_box_px[1]+c.bounding_box_px[3] >= first else c
                for c in candidates)
        if settings.layout_mode == "auto" and final_grid is None:
            candidates = tuple(replace(c, review_reasons=tuple(dict.fromkeys(
                (*c.review_reasons, "No reliable panel layout; check which regions form each composition"))))
                for c in candidates)
        self.last_diagnostics = {
            "detector_revision": DETECTOR_REVISION,
            "image_size_px": [image_bgr.shape[1], image_bgr.shape[0]],
            "settings": asdict(settings),
            "reference_status": self.reference_status,
            "reference_applied": matched_reference,
            "fabric_status": evidence.reason if evidence is not None else "No fabric mask",
            "analysis_bounds_px": analysis_bounds,
            "grid": asdict(final_grid) if final_grid is not None else None,
            "grid_notes": list(self._grid_notes),
            "scene_profile": scene,
            "illumination": illumination,
            "analysis_policy": asdict(POLICY) if settings.adaptive_planning else None,
            "detection_plans": self._plans,
            "candidates_before_cleanup": len(result.candidates),
            "candidates_after_cleanup": len(candidates),
            "compositions_needing_extent_review": sum(bool(c.review_reasons) for c in candidates),
        }
        return DetectionResult(candidates, final_grid)

    def finalize_compositions(self, image_bgr, candidates, grid):
        """Every automatic/manual grid uses one ownership and review contract."""
        candidates = tuple(candidates)
        if grid is not None:
            candidates = _consolidate_grid_candidates(candidates, grid)
            issues = grid.review_reasons
            if grid.confidence < .78 and grid.source != "manual":
                issues = (*issues, "Panel layout is uncertain; check composition ownership")
            if issues:
                candidates = tuple(replace(c, review_reasons=tuple(dict.fromkeys(
                    (*c.review_reasons, *issues)))) for c in candidates)
        return review_extents(image_bgr, candidates, grid)

    def detect(
        self, image_bgr: np.ndarray, settings: DetectorSettings
    ) -> list[MotifCandidate]:
        return list(self.detect_with_layout(image_bgr, settings).candidates)

    def _detect_layout(
        self, image_bgr: np.ndarray, settings: DetectorSettings,
        *, fabric_mask: np.ndarray | None = None,
    ) -> DetectionResult:
        self._validate_image(image_bgr)
        primary = [c for c in self._detect_once(image_bgr, settings) if _inside_fabric(c, fabric_mask)]
        height, width = image_bgr.shape[:2]

        layout_mode = settings.layout_mode if settings.layout_mode in {
            "auto",
            "panels",
            "free",
        } else "auto"
        pattern = (infer_repeated_artwork(image_bgr, settings.sensitivity, settings.minimum_area_px)
                   if layout_mode == "auto" else None)
        camera = infer_camera_panel(image_bgr) if layout_mode == "auto" else None
        preferred = None
        artwork_grid = None
        if layout_mode != "free":
            panel_grid = infer_panel_grid(image_bgr, primary)
            # A frame-sized proposal is weaker than independently visible
            # printed divisions. Do not let its early return hide that evidence.
            if panel_grid is not None and panel_grid.source == "automatic" and camera is not None:
                panel_grid = None
            if panel_grid is not None and pattern is not None and contradicts_artwork(panel_grid, pattern):
                self._grid_notes.append(
                    f"Rejected {panel_grid.columns}x{panel_grid.rows} panel grid: "
                    f"stable artwork supports {pattern.grid.columns}x{pattern.grid.rows}."
                )
                panel_grid = None
            if settings.adaptive_planning and layout_mode == 'auto':
                regular = _infer_regular_tile_grid(primary,width,height)
                regular_proposal = (PanelGrid.regular(width,height,*regular,confidence=.8,source='automatic')
                                    if regular is not None else None)
                if pattern is None and regular is None and 6 <= len(primary) <= 300:
                    passes = [primary]
                    for offset in (-10,10):
                        passes.append([c for c in self._detect_once(image_bgr, replace(
                            settings, sensitivity=int(np.clip(settings.sensitivity+offset,0,100))))
                            if _inside_fabric(c,fabric_mask)])
                    artwork_grid = stable_artwork_grid(passes)
                preferred, hypotheses = choose_grid(image_bgr, [
                    ('panels', panel_grid),
                    ('pattern', pattern.grid if pattern is not None else None),
                    ('regular', regular_proposal),
                    ('observations', artwork_grid),
                    ('camera', source_grid(camera) if camera is not None else None),
                ], primary, stable_routes=('pattern','observations'))
                self._plans.append({'stage':'grid','selected_route':preferred,'hypotheses':hypotheses})
                eligible_routes = {h['route'] for h in hypotheses if h['eligible']}
                if 'panels' not in eligible_routes: panel_grid = None
                if 'camera' not in eligible_routes: camera = None
                if 'pattern' not in eligible_routes: pattern = None
                if preferred == 'observations':
                    self._grid_notes.append('Artwork spacing and phase agree across three thresholds; retained complete compositions')
                    return DetectionResult(tuple(primary), artwork_grid)
                if preferred in ('pattern','camera','regular'):
                    if panel_grid is not None:
                        self._grid_notes.append('Grid planner preferred '+preferred+' evidence over the panel proposal')
                    panel_grid = None
            if panel_grid is not None and (panel_grid.confidence >= 0.78 or layout_mode == "panels"):
                strict = []
                if layout_mode == "auto":
                    strict = [c for c in self._detect_once(image_bgr, replace(
                        settings, sensitivity=max(0, settings.sensitivity-10),
                    )) if _inside_fabric(c, fabric_mask)]
                    checked = extend_visual_grid(panel_grid, primary, strict, image_bgr.shape, fabric_mask)
                    if checked != panel_grid:
                        self._grid_notes.append(
                            f"Extended {panel_grid.columns}x{panel_grid.rows} visual grid to "
                            f"{checked.columns}x{checked.rows}: multiple stable outer motifs."
                        )
                    panel_grid = checked
                panel_candidates = self.detect_in_grid(
                    image_bgr, settings, panel_grid
                )
                if layout_mode == "auto":
                    complete = self.reconcile_grid_artwork(
                        image_bgr, settings, panel_grid, panel_candidates, whole=primary,
                    )
                    if len(complete) < len(panel_candidates):
                        self._grid_notes.append("Preserved whole artwork spanning adjacent cells.")
                    panel_candidates = complete
                coverage = len(panel_candidates) / max(
                    1, panel_grid.columns * panel_grid.rows
                )
                if layout_mode == "panels" or panel_grid.source == "visual" or coverage >= 0.35:
                    return DetectionResult(tuple(panel_candidates), panel_grid)

        if layout_mode == "auto":
            if pattern is not None and preferred not in ('camera','regular'):
                if settings.adaptive_planning:
                    self._plans.append({'stage':'zones','execution':'whole_compositions',
                        'image_size_px':[width,height],
                        'zones':[asdict(z) for z in plan_zones(image_bgr,pattern.grid)]})
                # Keep complete regions, including artwork crossing a cell boundary.
                # Detecting independently in each cell here would split such artwork.
                candidates = tuple(MotifCandidate((x + w / 2., y + h / 2.),
                                                   region.bounding_box_px,
                                                   region.score, region.area_px,
                                                   region.center_px)
                                   for region in pattern.regions
                                   for x, y, w, h in [region.bounding_box_px])
                return DetectionResult(tuple(sorted(candidates, key=lambda c: (c.center_px[1], c.center_px[0]))),
                                       pattern.grid)

        if layout_mode == "auto" and preferred != 'regular' and (preferred == 'camera' or _infer_regular_tile_grid(primary, width, height) is None):
            panel = camera
            if panel is not None:
                # Normalize the photographed fabric for analysis, not the displayed
                # image or calibration. Weak ink is separated by a local colour
                # model rather than a fixed global contrast threshold.
                corners = project_points([(0,0), (panel.image.shape[1],0),
                                          (panel.image.shape[1],panel.image.shape[0]),
                                          (0,panel.image.shape[0])], panel.to_source)
                area_scale = panel.image.shape[0]*panel.image.shape[1] / cv2.contourArea(corners.astype(np.float32))
                local_settings = replace(settings, minimum_area_px=max(1, int(settings.minimum_area_px*area_scale)))
                local = self.detect_in_grid(panel.image, local_settings, panel.grid, region_segmentation=True)
                if len(local) >= panel.grid.columns * panel.grid.rows * .70:
                    mapped = []
                    for item in local:
                        x, y, w, h = item.bounding_box_px
                        bounds = project_points([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], panel.to_source)
                        left, top = np.floor(bounds.min(axis=0)).astype(int)
                        right, bottom = np.ceil(bounds.max(axis=0)).astype(int)
                        center = project_points([item.center_px], panel.to_source)[0]
                        mapped.append(MotifCandidate(tuple(float(v) for v in center),
                                                     (int(left),int(top),int(right-left),int(bottom-top)),
                                                     item.score, int(item.area_px/area_scale),
                                                     review_reasons=item.review_reasons))
                    return DetectionResult(tuple(sorted(mapped, key=lambda c: (c.center_px[1],c.center_px[0]))),
                                           source_grid(panel))

        if settings.adaptive_planning and layout_mode == 'auto' and preferred is None:
            return DetectionResult(tuple(primary))
        regular_grid = _infer_regular_tile_grid(primary, width, height)
        if regular_grid is None:
            return DetectionResult(
                tuple(sorted(primary, key=lambda item: (item.center_px[1], item.center_px[0])))
            )

        columns, rows = regular_grid
        expected_count = columns * rows
        tile_width = width / columns
        tile_height = height / rows

        # Detection and artwork extent need different evidence. A permissive
        # threshold is useful for finding pale motifs, but its outermost pixels
        # often include printed dots, seams, or shadows. Compare a family of
        # thresholds: one pass establishes that a panel is occupied, while the
        # strictest stable pass supplies the artwork bounds used for centring.
        # This is driven by inferred layout, never fixed coordinates or counts.
        sensitivity = int(np.clip(settings.sensitivity, 0, 100))
        passes: list[tuple[int, list[MotifCandidate]]] = [(sensitivity, primary)]
        for offset in (-30, -20, -15, -10, -5, 5, 10, 15, 20):
            pass_sensitivity = int(np.clip(sensitivity + offset, 0, 100))
            if any(existing == pass_sensitivity for existing, _items in passes):
                continue
            pass_settings = DetectorSettings(
                sensitivity=pass_sensitivity,
                minimum_area_px=settings.minimum_area_px,
                morphological_cleanup=settings.morphological_cleanup,
                merge_distance_px_x=settings.merge_distance_px_x,
                merge_distance_px_y=settings.merge_distance_px_y,
            )
            passes.append(
                (pass_sensitivity, [c for c in self._detect_once(image_bgr, pass_settings)
                                    if _inside_fabric(c, fabric_mask)])
            )

        def pass_quality(
            pass_entry: tuple[int, list[MotifCandidate]],
        ) -> tuple[int, int, int]:
            pass_sensitivity, pass_candidates = pass_entry
            occupied = len(
                _candidates_by_tile(
                    pass_candidates, columns, rows, width, height
                )
            )
            return (
                occupied,
                -abs(len(pass_candidates) - expected_count),
                -abs(pass_sensitivity - sensitivity),
            )

        _chosen_sensitivity, chosen = max(passes, key=pass_quality)
        chosen_cells = _candidates_by_tile(chosen, columns, rows, width, height)
        cells_by_sensitivity = {
            pass_sensitivity: _candidates_by_tile(
                pass_candidates, columns, rows, width, height
            )
            for pass_sensitivity, pass_candidates in passes
        }
        primary_cells = cells_by_sensitivity[sensitivity]

        # If the best single threshold still misses a panel, borrow that panel
        # from the nearest pass in which it was visible.
        for row in range(rows):
            for column in range(columns):
                cell = column, row
                if cell in chosen_cells:
                    continue
                alternatives = [
                    (abs(pass_sensitivity - sensitivity), pass_cells[cell])
                    for pass_sensitivity, pass_cells in cells_by_sensitivity.items()
                    if pass_cells.get(cell)
                ]
                if alternatives:
                    chosen_cells[cell] = min(alternatives, key=lambda item: item[0])[1]

        refined: list[MotifCandidate] = []
        for cell, layout_candidates in chosen_cells.items():
            layout_candidate = _consolidate_tile_candidates(
                layout_candidates, tile_width, tile_height
            )
            anchor_candidates = primary_cells.get(cell, layout_candidates)
            anchor_candidate = _consolidate_tile_candidates(
                anchor_candidates, tile_width, tile_height
            )
            reference_area = max(anchor_candidate.area_px, layout_candidate.area_px)
            _anchor_x, _anchor_y, anchor_width, anchor_height = (
                anchor_candidate.bounding_box_px
            )
            extent_options: list[tuple[int, MotifCandidate]] = []
            for pass_sensitivity, pass_cells in cells_by_sensitivity.items():
                if pass_sensitivity > sensitivity or cell not in pass_cells:
                    continue
                extent_candidate = _consolidate_tile_candidates(
                    pass_cells[cell], tile_width, tile_height
                )
                _extent_x, _extent_y, extent_width, extent_height = (
                    extent_candidate.bounding_box_px
                )
                if (
                    extent_candidate.area_px >= reference_area * 0.40
                    and extent_width >= anchor_width * 0.65
                    and extent_height >= anchor_height * 0.65
                ):
                    extent_options.append((pass_sensitivity, extent_candidate))
            extent_candidate = (
                min(extent_options, key=lambda item: item[0])[1]
                if extent_options
                else anchor_candidate
            )
            refined.append(
                MotifCandidate(
                    center_px=anchor_candidate.center_px,
                    bounding_box_px=extent_candidate.bounding_box_px,
                    score=anchor_candidate.score,
                    area_px=extent_candidate.area_px,
                )
            )
        return DetectionResult(
            tuple(sorted(refined, key=lambda item: (item.center_px[1], item.center_px[0])))
        )

    def reconcile_grid_artwork(self, image_bgr, settings, grid, candidates, *, whole=None):
        """Check cell crops against whole-image evidence without moving guides."""
        if grid.confidence < .78 or grid.lattice is not None or grid.projection is not None:
            return candidates
        whole = self._detect_once(image_bgr, settings) if whole is None else whole
        dx = float(np.median(np.diff(grid.x_lines_px)))
        dy = float(np.median(np.diff(grid.y_lines_px)))
        possible_spans = [c for c in whole
                          if (1.35*dy < c.bounding_box_px[3] < 2.4*dy and c.bounding_box_px[2] < .95*dx)
                          or (1.35*dx < c.bounding_box_px[2] < 2.4*dx and c.bounding_box_px[3] < .95*dy)]
        connected = self._detect_once(image_bgr, replace(
            settings, sensitivity=max(0, settings.sensitivity-10),
            merge_distance_px_x=0., merge_distance_px_y=0.,
        )) if possible_spans else []
        return preserve_spanning_artwork(candidates, possible_spans, connected, grid)

    def detect_in_grid(
        self,
        image_bgr: np.ndarray,
        settings: DetectorSettings,
        panel_grid: PanelGrid,
        *,
        region_segmentation: bool = False,
    ) -> list[MotifCandidate]:
        """Detect at most one locally separated motif inside each panel."""

        self._validate_image(image_bgr)
        image_height, image_width = image_bgr.shape[:2]
        results: list[MotifCandidate] = []
        zones = {(z.column,z.row):z for z in plan_zones(image_bgr,panel_grid)} if settings.adaptive_planning else {}
        plan_log={'stage':'zones','image_size_px':[image_width,image_height],
                  'zones':[asdict(z) for z in zones.values()]}
        if zones:self._plans.append(plan_log)
        base_sensitivity = int(np.clip(settings.sensitivity, 0, 100))
        sensitivities = tuple(
            dict.fromkeys(
                int(np.clip(base_sensitivity + offset, 0, 100))
                for offset in (0, 10, -10, 20, -20)
            )
        )

        for _column, _row, (cell_x, cell_y, cell_width, cell_height) in panel_grid.cells():
            left = min(max(cell_x, 0), image_width - 1)
            top = min(max(cell_y, 0), image_height - 1)
            right = min(max(cell_x + cell_width, left + 1), image_width)
            bottom = min(max(cell_y + cell_height, top + 1), image_height)
            # Guides define ownership, not an irreversible foreground crop.
            # Keep surrounding pixels available when ink approaches a seam.
            context = POLICY.context_fraction if settings.adaptive_planning else .10
            padding_x = max(3, int(round((right-left)*context)))
            padding_y = max(3, int(round((bottom-top)*context)))
            crop_left, crop_top = max(0, left-padding_x), max(0, top-padding_y)
            crop_right, crop_bottom = min(image_width, right+padding_x), min(image_height, bottom+padding_y)
            crop = image_bgr[crop_top:crop_bottom, crop_left:crop_right]
            if crop.shape[0] < 8 or crop.shape[1] < 8:
                continue

            zone=zones.get((_column,_row))
            if zone is not None and zone.strategy == 'local_palette':
                analysed=segment_zone(crop,settings.minimum_area_px,
                    (left-crop_left,top-crop_top,right-crop_left,bottom-crop_top),
                    shadow_gain=zone.shadow_gain)
                if analysed is not None:
                    x,y,w,h=analysed['box']
                    cx,cy=x+w/2+crop_left,y+h/2+crop_top
                    if left <= cx < right and top <= cy < bottom:
                        results.append(MotifCandidate((cx,cy),(x+crop_left,y+crop_top,w,h),
                            analysed['score'],analysed['area'],review_reasons=analysed['issues']))
                        continue
            if region_segmentation and not settings.adaptive_planning:
                region = self._local_colour_region(crop, settings.minimum_area_px,
                    core_bounds=(left-crop_left, top-crop_top, right-crop_left, bottom-crop_top))
                if region is not None and (left <= region.center_px[0]+crop_left < right
                                           and top <= region.center_px[1]+crop_top < bottom):
                    x, y, w, h = region.bounding_box_px
                    results.append(MotifCandidate((region.center_px[0]+crop_left, region.center_px[1]+crop_top),
                                                   (x+crop_left,y+crop_top,w,h), region.score, region.area_px,
                                                   review_reasons=region.review_reasons))
                    continue

            options: list[tuple[float, int, MotifCandidate]] = []
            for pass_sensitivity in sensitivities:
                pass_settings = DetectorSettings(
                    sensitivity=pass_sensitivity,
                    minimum_area_px=settings.minimum_area_px,
                    morphological_cleanup=0. if zone is not None and zone.preserve_detail else settings.morphological_cleanup,
                    merge_distance_px_x=settings.merge_distance_px_x,
                    merge_distance_px_y=settings.merge_distance_px_y,
                    layout_mode="free",
                    adaptive_planning=settings.adaptive_planning,
                )
                local_candidates = self._detect_once(crop, pass_settings, local_context=True) if settings.adaptive_planning else self._detect_once(crop, pass_settings)
                for candidate in local_candidates:
                    # Overlapping windows must not claim their neighbour's core.
                    cx, cy = candidate.center_px[0]+crop_left, candidate.center_px[1]+crop_top
                    if not (left <= cx < right and top <= cy < bottom):
                        continue
                    rank = _panel_candidate_rank(
                        candidate, crop.shape[1], crop.shape[0]
                    )
                    if rank is None:
                        continue
                    x, y, width, height = candidate.bounding_box_px
                    translated = MotifCandidate(
                        center_px=(
                            candidate.center_px[0] + crop_left,
                            candidate.center_px[1] + crop_top,
                        ),
                        bounding_box_px=(
                            x + crop_left,
                            y + crop_top,
                            width,
                            height,
                        ),
                        score=candidate.score,
                        area_px=candidate.area_px,
                        review_reasons=candidate.review_reasons,
                    )
                    options.append(
                        (rank, -abs(pass_sensitivity - base_sensitivity), translated)
                    )
            if options:
                results.append(max(options, key=lambda item: (item[0], item[1]))[2])

        return sorted(results, key=lambda item: (item.center_px[1], item.center_px[0]))

    @staticmethod
    def _local_colour_region(image: np.ndarray, minimum_area: int,
                             core_bounds=None) -> MotifCandidate | None:
        """Separate coherent artwork from the cell border; never seed fixed foreground."""
        h, w = image.shape[:2]
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
        if core_bounds is None:
            sample = lab
        else:
            left, top, right, bottom = core_bounds
            # Sample this panel's background, not the neighbouring panels in
            # the expanded window. This changes seeds, never available pixels.
            inset = max(1, round(min(right-left, bottom-top)*.035))
            sample = lab[top+inset:bottom-inset, left+inset:right-inset]
        border = np.concatenate([sample[0], sample[-1], sample[:,0], sample[:,-1]])
        background_colour = np.median(border, axis=0)
        distance = np.linalg.norm(lab-background_colour, axis=2)
        border_distance = np.linalg.norm(border-background_colour, axis=1)
        threshold = max(10., float(np.percentile(border_distance, 65)))
        mask = np.full((h,w), cv2.GC_PR_BGD, np.uint8)
        mask[distance > threshold] = cv2.GC_PR_FGD
        if core_bounds is not None:
            outside = np.ones((h,w), bool)
            outside[top:bottom, left:right] = False
            mask[outside] = cv2.GC_PR_BGD
        # Only border pixels that agree with the sampled background are fixed.
        # Everything else remains revisable, including artwork near an edge.
        rim = np.zeros((h,w), bool)
        rim[[0,-1],:] = True
        rim[:,[0,-1]] = True
        sure_background = rim & (distance <= max(3., float(np.percentile(border_distance, 25))))
        mask[sure_background] = cv2.GC_BGD
        if not np.any(sure_background) or np.count_nonzero(mask == cv2.GC_PR_FGD) < minimum_area:
            return None
        background, foreground = np.zeros((1,65), np.float64), np.zeros((1,65), np.float64)
        cv2.setRNGSeed(0)
        cv2.grabCut(image, mask, None, background, foreground, 4, cv2.GC_INIT_WITH_MASK)
        selected = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD])
        ys, xs = np.nonzero(selected)
        area = len(xs)
        if area < minimum_area or area > w*h*.60:
            return None
        x, y, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)
        contrast = float(np.linalg.norm(lab[selected].mean(axis=0)-lab[~selected].mean(axis=0)))
        score = float(.72*np.clip(contrast/80, 0, 1) + .28*min(1,area/max(1,minimum_area*8)))
        issues = (("Foreground reaches the analysis boundary",)
                  if np.any(selected[rim]) else ())
        return MotifCandidate(((x+right)/2,(y+bottom)/2),(x,y,right-x,bottom-y),score,area,
                              review_reasons=issues)

    def _detect_once(
        self, image_bgr: np.ndarray, settings: DetectorSettings, *, local_context: bool = False
    ) -> list[MotifCandidate]:
        sensitivity = int(np.clip(settings.sensitivity, 0, 100))
        cleanup = float(np.clip(settings.morphological_cleanup, 0.0, 1.0))

        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        background_lab = self._estimate_background(lab)

        # Color distance is intentionally generic: the detector asks only whether
        # a region differs from the locally estimated fabric color.  A background
        # image, rather than one color sampled from the border, is important for
        # camera captures: the bed surround may be dark and illumination across
        # the fabric is rarely uniform.
        delta = lab - background_lab
        distance = np.sqrt(
            0.35 * np.square(delta[:, :, 0])
            + np.square(delta[:, :, 1])
            + np.square(delta[:, :, 2])
        )
        # Gaussian background estimation creates a faint inverse halo around a
        # high-contrast motif.  Pixels that still match the typical fabric color
        # are background, even if that local halo is present.  This small gate
        # preserves real shadows (which do not match the global fabric color).
        typical_fabric_lab = self._estimate_typical_fabric(lab)
        global_delta = lab - typical_fabric_lab.reshape(1, 1, 3)
        global_distance = np.sqrt(
            0.35 * np.square(global_delta[:, :, 0])
            + np.square(global_delta[:, :, 1])
            + np.square(global_delta[:, :, 2])
        )
        distance[global_distance < 6.0] = 0.0
        distance_u8 = np.clip(distance, 0, 255).astype(np.uint8)
        distance_u8 = cv2.GaussianBlur(distance_u8, (5, 5), 0)

        # Local illumination correction reduces the measured distance compared
        # with a single global reference, so its useful threshold range is lower.
        threshold = int(round(np.interp(sensitivity, [0, 100], [60, 6])))
        _, mask = cv2.threshold(distance_u8, threshold, 255, cv2.THRESH_BINARY)

        if cleanup > 0:
            open_size = _odd_size(1.0 + cleanup * 8.0)
            close_size = _odd_size(3.0 + cleanup * 16.0)
            open_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (open_size, open_size)
            )
            close_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (close_size, close_size)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

        if not local_context:
            mask = self._remove_camera_surround(mask)

        candidates = self._components(
            mask,
            distance,
            max(1, int(settings.minimum_area_px)),
            image_bgr.shape[1] * image_bgr.shape[0],
            threshold,
            max(0.0, float(settings.merge_distance_px_x)),
            max(0.0, float(settings.merge_distance_px_y)),
            center_strength=distance_u8,
        )
        return sorted(candidates, key=lambda item: (item.center_px[1], item.center_px[0]))

    @staticmethod
    def _validate_image(image_bgr: np.ndarray) -> None:
        if not isinstance(image_bgr, np.ndarray):
            raise TypeError("image_bgr must be a NumPy array")
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError("image_bgr must have shape (height, width, 3)")
        if image_bgr.size == 0:
            raise ValueError("image_bgr cannot be empty")

    @staticmethod
    def _estimate_background(lab: np.ndarray) -> np.ndarray:
        """Return a smooth local fabric estimate that follows light and shadow."""
        height, width = lab.shape[:2]
        sigma = max(9.0, min(height, width) * 0.075)
        return cv2.GaussianBlur(
            lab,
            (0, 0),
            sigmaX=sigma,
            sigmaY=sigma,
            borderType=cv2.BORDER_REFLECT,
        )

    @staticmethod
    def _estimate_typical_fabric(lab: np.ndarray) -> np.ndarray:
        """Estimate the common fabric color without trusting the camera border."""
        height, width = lab.shape[:2]
        inset_y = int(round(height * 0.08))
        inset_x = int(round(width * 0.08))
        interior = lab[
            inset_y : max(inset_y + 1, height - inset_y),
            inset_x : max(inset_x + 1, width - inset_x),
        ]
        return np.median(interior.reshape(-1, 3), axis=0)

    @staticmethod
    def _remove_camera_surround(mask: np.ndarray) -> np.ndarray:
        """Remove broad foreground regions connected to the camera frame.

        A dark laser bed around lighter fabric is deliberately foreground in the
        color-distance mask.  It must not be allowed to surround and merge every
        motif.  Small clipped motifs are retained; only components spanning a
        substantial part of an image dimension are treated as camera surround.
        """
        height, width = mask.shape
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        cleaned = mask.copy()
        for label in range(1, count):
            x, y, component_width, component_height, _area = (
                int(value) for value in stats[label]
            )
            touches_border = (
                x == 0
                or y == 0
                or x + component_width == width
                or y + component_height == height
            )
            spans_frame = (
                component_width >= width * 0.25
                or component_height >= height * 0.25
            )
            if touches_border and spans_frame:
                cleaned[labels == label] = 0
        return cleaned

    @staticmethod
    def _components(
        mask: np.ndarray,
        distance: np.ndarray,
        minimum_area_px: int,
        total_area_px: int,
        threshold: int,
        merge_distance_px_x: float,
        merge_distance_px_y: float,
        center_strength: np.ndarray | None = None,
    ) -> list[MotifCandidate]:
        count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        components: list[_RawComponent] = []
        maximum_area = total_area_px * 0.30
        fragment_floor = max(4, int(round(minimum_area_px * 0.04)))
        for label in range(1, count):
            x, y, width, height, area = (int(value) for value in stats[label])
            if area < fragment_floor or area > maximum_area:
                continue
            component_values = distance[labels == label]
            contrast = float(component_values.mean()) if component_values.size else 0.0
            components.append(
                _RawComponent(
                    (x, y, width, height),
                    area,
                    contrast,
                    label,
                )
            )

        groups = _group_nearby_components(
            components,
            merge_distance_px_x,
            merge_distance_px_y,
            core_area_px=max(fragment_floor, int(round(minimum_area_px * 0.5))),
        )
        groups = _attach_orphan_groups(
            groups,
            minimum_area_px,
            merge_distance_px_x,
            merge_distance_px_y,
        )
        result: list[MotifCandidate] = []
        for group in groups:
            area = sum(item.area_px for item in group)
            if area < minimum_area_px or area > maximum_area:
                continue
            x = min(item.bounding_box_px[0] for item in group)
            y = min(item.bounding_box_px[1] for item in group)
            right = max(
                item.bounding_box_px[0] + item.bounding_box_px[2] for item in group
            )
            bottom = max(
                item.bounding_box_px[1] + item.bounding_box_px[3] for item in group
            )
            # Detection remains permissive so pale or separated artwork is not
            # lost.  Centering uses a stronger subset and trimmed extents so one
            # speck, fabric mark, or weak merged fragment cannot pull the cut away
            # from the motif's visual core.  Unlike an ink centroid, the midpoint
            # of the robust extents does not favor visually dense lower sections.
            center = MotifDetector._robust_group_center(
                labels,
                group,
                (x, y, right, bottom),
                center_strength,
                threshold,
            )
            contrast = sum(item.contrast * item.area_px for item in group) / area
            contrast_score = np.clip((contrast - threshold) / 80.0, 0.0, 1.0)
            area_score = np.clip(area / max(minimum_area_px * 8.0, 1.0), 0.0, 1.0)
            score = float(0.72 * contrast_score + 0.28 * area_score)
            result.append(
                MotifCandidate(center, (x, y, right - x, bottom - y), score, area)
            )
        return result

    @staticmethod
    def _robust_group_center(
        labels: np.ndarray,
        group: list[_RawComponent],
        extent: tuple[int, int, int, int],
        center_strength: np.ndarray | None,
        threshold: int,
    ) -> tuple[float, float]:
        """Center a group on high-confidence pixels after trimming weak extremes."""
        x, y, right, bottom = extent
        fallback = ((x + right) / 2.0, (y + bottom) / 2.0)
        label_ids = [
            component.label_id for component in group if component.label_id > 0
        ]
        if center_strength is None or not label_ids:
            return fallback

        group_mask = np.isin(labels[y:bottom, x:right], label_ids)
        strength = center_strength[y:bottom, x:right]
        strong_mask = group_mask & (strength >= min(255, threshold + 6))
        minimum_strong_area = max(
            20,
            int(round(sum(component.area_px for component in group) * 0.10)),
        )
        center_mask = (
            strong_mask
            if int(np.count_nonzero(strong_mask)) >= minimum_strong_area
            else group_mask
        )
        rows, columns = np.nonzero(center_mask)
        if columns.size == 0:
            return fallback

        left = float(np.quantile(columns, 0.10))
        robust_right = float(np.quantile(columns, 0.90))
        top = float(np.quantile(rows, 0.10))
        robust_bottom = float(np.quantile(rows, 0.90))
        return (
            x + (left + robust_right) / 2.0,
            y + (top + robust_bottom) / 2.0,
        )


def _odd_size(value: float) -> int:
    rounded = max(1, int(round(value)))
    return rounded if rounded % 2 == 1 else rounded + 1


def infer_panel_grid(
    image_bgr: np.ndarray,
    candidates: list[MotifCandidate] | None = None,
) -> PanelGrid | None:
    """Infer repeated panel boundaries from seams and broad fabric changes.

    Candidate centres only validate a visual grid proposal; they never create the
    proposal. This keeps the panel structure independent from motif detection.
    """

    printed = infer_printed_panel_grid(image_bgr)
    if printed is not None:
        return printed
    height, width = image_bgr.shape[:2]
    if width < 80 or height < 80:
        return None
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    softened = cv2.GaussianBlur(lab, (5, 5), 0)
    vertical_difference = np.linalg.norm(
        softened[:, 1:, :] - softened[:, :-1, :], axis=2
    )
    horizontal_difference = np.linalg.norm(
        softened[1:, :, :] - softened[:-1, :, :], axis=2
    )
    vertical_profile = np.percentile(vertical_difference, 72, axis=0)
    horizontal_profile = np.percentile(horizontal_difference, 72, axis=1)
    vertical_profile = cv2.GaussianBlur(
        vertical_profile.reshape(1, -1), (0, 0), sigmaX=2.0
    ).reshape(-1)
    horizontal_profile = cv2.GaussianBlur(
        horizontal_profile.reshape(-1, 1), (0, 0), sigmaX=0.0, sigmaY=2.0
    ).reshape(-1)

    x_fits = {
        count: _fit_regular_boundaries(vertical_profile, width, count)
        for count in range(2, 13)
    }
    y_fits = {
        count: _fit_regular_boundaries(horizontal_profile, height, count)
        for count in range(2, 11)
    }
    choices: list[tuple[float, float, int, int, tuple[float, ...], tuple[float, ...]]] = []
    candidate_count = len(candidates or [])
    candidate_grid = (
        _infer_regular_tile_grid(candidates, width, height) if candidates else None
    )
    for columns, x_fit in x_fits.items():
        if x_fit is None:
            continue
        x_score, x_lines = x_fit
        for rows, y_fit in y_fits.items():
            if y_fit is None:
                continue
            y_score, y_lines = y_fit
            tile_aspect = (width / columns) / (height / rows)
            if not 0.65 <= tile_aspect <= 1.50:
                continue
            layout_score = 0.52 * x_score + 0.48 * y_score
            occupancy = 0.0
            duplicates = 0.0
            if candidates:
                occupied = _candidate_cells_for_lines(candidates, x_lines, y_lines)
                expected = columns * rows
                occupancy = len(occupied) / expected
                duplicates = max(0, candidate_count - len(occupied)) / candidate_count
                layout_score += 0.35 * occupancy - 0.40 * duplicates
                layout_score -= 1.20 * abs(candidate_count - expected) / max(
                    candidate_count, expected
                )
                if candidate_grid == (columns, rows):
                    layout_score += 0.75
                elif candidate_grid is not None:
                    layout_score -= 0.08 * (
                        abs(candidate_grid[0] - columns)
                        + abs(candidate_grid[1] - rows)
                    )
            layout_score -= 0.035 * abs(float(np.log(tile_aspect)))
            # Reward grids supported along both axes rather than one excellent
            # projection hiding a weak or absent perpendicular structure.
            support = min(x_score, y_score)
            choices.append(
                (
                    layout_score,
                    support,
                    columns,
                    rows,
                    x_lines,
                    y_lines,
                )
            )
    if not choices:
        return None
    choices.sort(reverse=True)
    best_score, support, columns, rows, x_lines, y_lines = choices[0]
    runner_up = choices[1][0] if len(choices) > 1 else 0.0
    candidate_supported = candidate_grid == (columns, rows)
    if (support < 0.22 and not candidate_supported) or best_score < 0.34:
        return None
    regular_deviation = _grid_regular_deviation(x_lines, width, y_lines, height)
    if regular_deviation > 0.055:
        return None
    # A uniform image can contain motifs arranged in rows without being a
    # patchwork. Require broad fabric change on at least one axis before a
    # centre-supported proposal switches the detector into panel mode.
    if candidate_supported:
        broad_contrast = _broad_grid_contrast(lab, x_lines, y_lines)
        if broad_contrast < 4.0:
            return None
    separation = max(0.0, best_score - runner_up)
    confidence = float(
        np.clip(
            0.42
            + support * 0.35
            + separation * 1.8
            + (0.24 if candidate_supported else 0.0),
            0.0,
            0.98,
        )
    )
    return PanelGrid(
        x_lines_px=x_lines,
        y_lines_px=y_lines,
        confidence=confidence,
        source="automatic",
    )


def _broad_grid_contrast(
    lab: np.ndarray,
    x_lines: tuple[float, ...],
    y_lines: tuple[float, ...],
) -> float:
    height, width = lab.shape[:2]
    sample = max(2, int(round(min(width, height) * 0.006)))
    values: list[float] = []
    for position in x_lines[1:-1]:
        x = int(round(position))
        if x - sample - 1 < 0 or x + sample + 1 > width:
            continue
        left = np.median(lab[:, x - sample - 1 : x - 1, :], axis=1)
        right = np.median(lab[:, x + 1 : x + sample + 1, :], axis=1)
        values.append(float(np.median(np.linalg.norm(left - right, axis=1))))
    for position in y_lines[1:-1]:
        y = int(round(position))
        if y - sample - 1 < 0 or y + sample + 1 > height:
            continue
        top = np.median(lab[y - sample - 1 : y - 1, :, :], axis=0)
        bottom = np.median(lab[y + 1 : y + sample + 1, :, :], axis=0)
        values.append(float(np.median(np.linalg.norm(top - bottom, axis=1))))
    return max(values, default=0.0)


def _grid_regular_deviation(
    x_lines: tuple[float, ...],
    width: int,
    y_lines: tuple[float, ...],
    height: int,
) -> float:
    deviations: list[float] = []
    for index, position in enumerate(x_lines[1:-1], 1):
        step = width / (len(x_lines) - 1)
        deviations.append(abs(position - index * step) / max(step, 1.0))
    for index, position in enumerate(y_lines[1:-1], 1):
        step = height / (len(y_lines) - 1)
        deviations.append(abs(position - index * step) / max(step, 1.0))
    return float(np.mean(deviations)) if deviations else 0.0


def _fit_regular_boundaries(
    profile: np.ndarray, image_length: int, count: int
) -> tuple[float, tuple[float, ...]] | None:
    if profile.size < 4 or count < 2:
        return None
    baseline = float(np.median(profile))
    high = float(np.percentile(profile, 96))
    scale = high - baseline
    if scale <= 1e-6:
        return None
    step = image_length / count
    radius = max(2, int(round(step * 0.13)))
    selected: list[float] = []
    strengths: list[float] = []
    regularity: list[float] = []
    for index in range(1, count):
        expected = index * step
        center = int(round(expected)) - 1
        start = max(0, center - radius)
        stop = min(profile.size, center + radius + 1)
        if stop <= start:
            return None
        local = profile[start:stop]
        offsets = np.arange(start, stop, dtype=np.float32) + 1.0
        normalized = np.clip((local - baseline) / scale, 0.0, 1.5)
        displacement = np.abs(offsets - expected) / max(radius, 1)
        objective = normalized - 0.20 * displacement
        chosen_offset = int(np.argmax(objective))
        position = float(offsets[chosen_offset])
        selected.append(position)
        strengths.append(float(normalized[chosen_offset]))
        regularity.append(float(displacement[chosen_offset]))
    if not strengths:
        return None
    lower_quartile = float(np.quantile(strengths, 0.25))
    score = (
        0.58 * float(np.mean(strengths))
        + 0.32 * lower_quartile
        - 0.10 * float(np.mean(regularity))
    )
    return score, (0.0, *selected, float(image_length))


def _candidate_cells_for_lines(
    candidates: list[MotifCandidate],
    x_lines: tuple[float, ...],
    y_lines: tuple[float, ...],
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for candidate in candidates:
        column = int(np.searchsorted(x_lines, candidate.center_px[0], side="right") - 1)
        row = int(np.searchsorted(y_lines, candidate.center_px[1], side="right") - 1)
        column = min(max(column, 0), len(x_lines) - 2)
        row = min(max(row, 0), len(y_lines) - 2)
        occupied.add((column, row))
    return occupied


def _panel_candidate_rank(
    candidate: MotifCandidate, panel_width: int, panel_height: int
) -> float | None:
    x, y, width, height = candidate.bounding_box_px
    if width <= 0 or height <= 0:
        return None
    width_ratio = width / panel_width
    height_ratio = height / panel_height
    if (width_ratio > 0.86 and height_ratio < 0.10) or (
        height_ratio > 0.86 and width_ratio < 0.10
    ):
        return None
    center_x = candidate.center_px[0] / panel_width
    center_y = candidate.center_px[1] / panel_height
    center_distance = float(np.hypot(center_x - 0.5, center_y - 0.5)) / 0.7072
    centrality = np.clip(1.0 - center_distance, 0.0, 1.0)
    area_ratio = candidate.area_px / max(1, panel_width * panel_height)
    useful_area = np.clip(area_ratio / 0.08, 0.0, 1.0)
    oversized_penalty = np.clip((area_ratio - 0.48) / 0.32, 0.0, 1.0)
    edge_penalty = 0.0
    if x <= 1 or y <= 1 or x + width >= panel_width - 1 or y + height >= panel_height - 1:
        edge_penalty = 0.14
    return float(
        0.44 * candidate.score
        + 0.38 * centrality
        + 0.18 * useful_area
        - 0.26 * oversized_penalty
        - edge_penalty
    )


def _infer_regular_tile_grid(
    candidates: list[MotifCandidate],
    image_width: int,
    image_height: int,
) -> tuple[int, int] | None:
    """Infer an approximately square repeated-panel layout from candidate centers.

    The inference is deliberately conservative. It requires most panels to be
    occupied, centers to sit near regularly spaced panel centers, and the best
    row/column hypothesis to beat alternatives. Free-form layouts therefore keep
    the normal single-threshold behavior.
    """
    count = len(candidates)
    if count < 8 or image_width <= 0 or image_height <= 0:
        return None

    choices: list[tuple[float, int, int, float, float]] = []
    for rows in range(2, 11):
        for columns in range(2, 13):
            expected_count = rows * columns
            if expected_count < count * 0.82 or expected_count > count * 1.22:
                continue
            tile_aspect = (image_width / columns) / (image_height / rows)
            if not 0.72 <= tile_aspect <= 1.38:
                continue
            cells = _candidates_by_tile(
                candidates, columns, rows, image_width, image_height
            )
            offsets: list[float] = []
            for candidate in candidates:
                normalized_x = candidate.center_px[0] * columns / image_width
                normalized_y = candidate.center_px[1] * rows / image_height
                cell_x = min(columns - 1, max(0, int(normalized_x)))
                cell_y = min(rows - 1, max(0, int(normalized_y)))
                offsets.append(
                    abs(normalized_x - cell_x - 0.5)
                    + abs(normalized_y - cell_y - 0.5)
                )
            occupancy = len(cells) / expected_count
            duplicates = (count - len(cells)) / count
            alignment = float(np.median(offsets))
            score = (
                occupancy
                - 0.45 * duplicates
                - 0.28 * alignment
                - 0.10 * abs(float(np.log(tile_aspect)))
            )
            choices.append((score, columns, rows, occupancy, alignment))

    if not choices:
        return None
    choices.sort(reverse=True)
    best_score, columns, rows, occupancy, alignment = choices[0]
    runner_up_score = choices[1][0] if len(choices) > 1 else float("-inf")
    if (
        best_score < 0.82
        or occupancy < 0.82
        or alignment > 0.26
        or best_score - runner_up_score < 0.01
    ):
        return None
    return columns, rows


def _candidates_by_tile(
    candidates: list[MotifCandidate],
    columns: int,
    rows: int,
    image_width: int,
    image_height: int,
) -> dict[tuple[int, int], list[MotifCandidate]]:
    grouped: dict[tuple[int, int], list[MotifCandidate]] = {}
    for candidate in candidates:
        column = min(
            columns - 1,
            max(0, int(candidate.center_px[0] * columns / image_width)),
        )
        row = min(
            rows - 1,
            max(0, int(candidate.center_px[1] * rows / image_height)),
        )
        grouped.setdefault((column, row), []).append(candidate)
    return grouped


def _consolidate_tile_candidates(
    candidates: list[MotifCandidate],
    tile_width: float | None = None,
    tile_height: float | None = None,
) -> MotifCandidate:
    """Return one artwork extent without absorbing thin panel seams or marks."""
    if len(candidates) == 1:
        return candidates[0]
    ordered = sorted(candidates, key=lambda item: item.area_px, reverse=True)
    main = ordered[0]
    retained = [main]
    for candidate in ordered[1:]:
        if tile_width is None or tile_height is None:
            retained.append(candidate)
            continue
        _x, _y, width, height = candidate.bounding_box_px
        area_ratio = candidate.area_px / max(1, main.area_px)
        minimum_dimension_ratio = min(width / tile_width, height / tile_height)
        gap_x, gap_y = _bounding_box_gap(
            main.bounding_box_px, candidate.bounding_box_px
        )
        close_to_main = gap_x <= tile_width * 0.10 and gap_y <= tile_height * 0.10
        # Legitimate detached details have useful area or two-dimensional shape.
        # A long one-pixel-wide seam has neither and must never enlarge artwork.
        substantial = area_ratio >= 0.12 or minimum_dimension_ratio >= 0.08
        if close_to_main and substantial:
            retained.append(candidate)

    left = min(candidate.bounding_box_px[0] for candidate in retained)
    top = min(candidate.bounding_box_px[1] for candidate in retained)
    right = max(
        candidate.bounding_box_px[0] + candidate.bounding_box_px[2]
        for candidate in retained
    )
    bottom = max(
        candidate.bounding_box_px[1] + candidate.bounding_box_px[3]
        for candidate in retained
    )
    return MotifCandidate(
        center_px=main.center_px,
        bounding_box_px=(left, top, right - left, bottom - top),
        score=main.score,
        area_px=sum(candidate.area_px for candidate in retained),
    )


def _group_nearby_components(
    components: list[_RawComponent],
    merge_distance_px_x: float,
    merge_distance_px_y: float,
    core_area_px: int = 1,
) -> list[list[_RawComponent]]:
    """Group nearby components without letting texture specks bridge motifs.

    Substantial components may form a group directly. Small fragments are then
    assigned to their nearest substantial component, but never act as links
    between two groups. This prevents a chain of dots or printed background marks
    from merging adjacent motifs across several quilt cells.
    """
    if not components:
        return []
    parents = list(range(len(components)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            parents[root_second] = root_first

    core_indices = [
        index
        for index, component in enumerate(components)
        if component.area_px >= core_area_px
    ]
    core_index_set = set(core_indices)
    fragment_indices = [
        index for index in range(len(components)) if index not in core_index_set
    ]

    for offset, first in enumerate(core_indices):
        for second in core_indices[offset + 1 :]:
            if _components_are_near(
                components[first],
                components[second],
                merge_distance_px_x,
                merge_distance_px_y,
            ):
                union(first, second)

    grouped: dict[int, list[_RawComponent]] = {}
    for index in core_indices:
        grouped.setdefault(find(index), []).append(components[index])

    unassigned_fragments: list[int] = []
    for fragment_index in fragment_indices:
        nearest: tuple[float, int] | None = None
        for core_index in core_indices:
            distance = _normalized_component_distance(
                components[fragment_index],
                components[core_index],
                merge_distance_px_x,
                merge_distance_px_y,
            )
            if distance <= 1.0 and (nearest is None or distance < nearest[0]):
                nearest = distance, core_index
        if nearest is None:
            unassigned_fragments.append(fragment_index)
        else:
            grouped.setdefault(find(nearest[1]), []).append(
                components[fragment_index]
            )

    # Preserve motifs made exclusively from small nearby pieces, while keeping
    # them isolated from the already-established core groups.
    for offset, first in enumerate(unassigned_fragments):
        for second in unassigned_fragments[offset + 1 :]:
            if _components_are_near(
                components[first],
                components[second],
                merge_distance_px_x,
                merge_distance_px_y,
            ):
                union(first, second)
    for index in unassigned_fragments:
        grouped.setdefault(find(index), []).append(components[index])
    return list(grouped.values())


def _components_are_near(
    first: _RawComponent,
    second: _RawComponent,
    merge_distance_px_x: float,
    merge_distance_px_y: float,
) -> bool:
    return (
        _normalized_component_distance(
            first,
            second,
            merge_distance_px_x,
            merge_distance_px_y,
        )
        <= 1.0
    )


def _attach_orphan_groups(
    groups: list[list[_RawComponent]],
    minimum_area_px: int,
    merge_distance_px_x: float,
    merge_distance_px_y: float,
) -> list[list[_RawComponent]]:
    """Attach one small detached detail to its single obvious parent motif.

    A cherry, antenna, or flag can sit slightly beyond the normal merge radius.
    Only groups under three minimum areas qualify, and their parent must be at
    least three times larger. Choosing exactly one nearest parent avoids restoring
    the texture-bridge problem prevented by the core/fragment grouping pass.
    """
    if len(groups) < 2:
        return groups

    merged = [list(group) for group in groups]
    removed: set[int] = set()
    maximum_orphan_area = minimum_area_px * 3
    for orphan_index, orphan in enumerate(merged):
        if orphan_index in removed:
            continue
        orphan_area = sum(component.area_px for component in orphan)
        if orphan_area > maximum_orphan_area:
            continue
        orphan_box = _group_bounding_box(orphan)
        synthetic_orphan = _RawComponent(orphan_box, orphan_area, 0.0)
        candidates: list[tuple[float, int]] = []
        for parent_index, parent in enumerate(merged):
            if parent_index == orphan_index or parent_index in removed:
                continue
            parent_area = sum(component.area_px for component in parent)
            if parent_area < orphan_area * 3:
                continue
            synthetic_parent = _RawComponent(
                _group_bounding_box(parent), parent_area, 0.0
            )
            distance = _normalized_component_distance(
                synthetic_orphan,
                synthetic_parent,
                merge_distance_px_x * 2.0,
                merge_distance_px_y * 2.0,
            )
            if distance <= 1.0:
                candidates.append((distance, parent_index))
        if not candidates:
            continue
        candidates.sort()
        # An orphan midway between two similarly near motifs is ambiguous and
        # must remain independent for manual review.
        if len(candidates) > 1 and candidates[1][0] <= candidates[0][0] * 1.25 + 0.05:
            continue
        parent_index = candidates[0][1]
        merged[parent_index].extend(orphan)
        removed.add(orphan_index)
    return [group for index, group in enumerate(merged) if index not in removed]


def _group_bounding_box(
    group: list[_RawComponent],
) -> tuple[int, int, int, int]:
    left = min(component.bounding_box_px[0] for component in group)
    top = min(component.bounding_box_px[1] for component in group)
    right = max(
        component.bounding_box_px[0] + component.bounding_box_px[2]
        for component in group
    )
    bottom = max(
        component.bounding_box_px[1] + component.bounding_box_px[3]
        for component in group
    )
    return left, top, right - left, bottom - top


def _normalized_component_distance(
    first: _RawComponent,
    second: _RawComponent,
    merge_distance_px_x: float,
    merge_distance_px_y: float,
) -> float:
    gap_x, gap_y = _bounding_box_gap(
        first.bounding_box_px, second.bounding_box_px
    )
    if gap_x == 0.0 and gap_y == 0.0:
        return 0.0
    if merge_distance_px_x <= 0.0 or merge_distance_px_y <= 0.0:
        return float("inf")
    return (
        (gap_x / merge_distance_px_x) ** 2
        + (gap_y / merge_distance_px_y) ** 2
    )


def _bounding_box_gap(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> tuple[float, float]:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    gap_x = max(
        first_x - (second_x + second_width),
        second_x - (first_x + first_width),
        0,
    )
    gap_y = max(
        first_y - (second_y + second_height),
        second_y - (first_y + first_height),
        0,
    )
    return float(gap_x), float(gap_y)
