"""Independent review counts: one cut may need more than one kind of attention."""
from collections import Counter


LABELS = {'overlap': 'Overlapping cuts', 'outside_bed': 'Outside bed',
          'artwork_clipped': 'Artwork exceeds cut', 'possible_clipping': 'Possible artwork clipping — inspect outline',
          'layout_review': 'Layout / ownership review',
          'extent_review': 'Artwork detail review', 'inferred': 'No artwork detected',
          'partial_image': 'Partial image panels'}


def review_counts(detections, mapper, layout=None):
    counts = Counter({key: 0 for key in LABELS})
    matches = {m.detection_id: m for m in layout.matches} if layout else {}
    for d in detections:
        if not d.enabled:
            continue
        counts['overlap'] += bool(d.overlaps_cut)
        counts['outside_bed'] += bool(mapper and not d.square_inches.is_valid(mapper.bed_width_in, mapper.bed_height_in))
        clipped=bool(d.artwork_clipped or (mapper and not d.contains_supported_artwork(mapper)))
        counts['artwork_clipped'] += bool(clipped and not d.artwork_extent_uncertain)
        counts['possible_clipping'] += bool(clipped and d.artwork_extent_uncertain)
        counts['inferred'] += bool(d.inferred)
        match = matches.get(d.id)
        reasons = ' '.join(d.review_reasons).lower()
        counts['layout_review'] += bool((match and (match.status != 'matched' or match.review_reason))
                                       or (mapper and d.panel_boundary_review_reason(mapper))
                                       or (d.cut_region_required and d.cut_region_px is None)
                                       or any(s in reasons for s in ('layout', 'ownership', 'outside the proposed printed grid')))
        counts['partial_image'] += bool('partly inside' in reasons or 'source-image boundary' in reasons)
        counts['extent_review'] += bool(d.artwork_extent_uncertain or (mapper and d.artwork_edge_review_reason(mapper)) or any(not any(s in r.lower() for s in (
            'layout', 'ownership', 'outside the proposed printed grid',
            'partly inside', 'source-image boundary', 'no artwork detected')) for r in d.review_reasons))
    return dict(counts)


def physical_spacing(mapper, layout, cut_width, cut_height):
    """Report nearest projected spacings in physical units, without resizing cuts."""
    if mapper is None or layout is None or not layout.reliable:
        return None
    horizontal, vertical = [], []
    for row in range(layout.rows):
        for col in range(layout.columns):
            here = mapper.pixel_to_inches(*layout.position(col, row))
            if col+1 < layout.columns:
                other = mapper.pixel_to_inches(*layout.position(col+1, row))
                horizontal.append(abs(other[0]-here[0]))
            if row+1 < layout.rows:
                other = mapper.pixel_to_inches(*layout.position(col, row+1))
                vertical.append(abs(other[1]-here[1]))
    return {'column_pitch_inches': min(horizontal) if horizontal else None,
            'row_pitch_inches': min(vertical) if vertical else None,
            'cut_width_inches': cut_width, 'cut_height_inches': cut_height,
            'note': 'Estimated from image placement; verify against a known physical measurement.'}
