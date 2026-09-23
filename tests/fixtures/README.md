# Camera regression fixture

`acceptance/animal_accessories_4x3.png` preserves the original supplied on
23 September at 11:10:14: twelve animal compositions, each with two detached
accessories. Its regression checks 36 source points at three resolutions.
The remaining nine images from the same 11:10 batch are preserved under
`acceptance/batch_20260923/`, with original paths and SHA-256 hashes in its
manifest. See `tests/test_accessory_ownership.py` and `docs/qa/accessory-groups/`.

`acceptance/dark_leaves_5x3.png` is the byte-identical original supplied on
23 September as `Imagen de Codex 23 sept 2026, 10_09_15-4.png`. It contains
15 low-contrast leaf compositions on navy fabric. Counts, arrangement and 45
manually inspected source points are test expectations only. See
`tests/test_shared_background.py` and `docs/qa/dark-leaves/` for source-relative
colour evidence, thin-stem checks and the remaining physical cut-size warnings.

`acceptance/mixed_icons_6x4.png` preserves the clean clipboard original supplied
on 23 September (ladybird, daisy, rabbit and other motifs on varied backgrounds).
It exercises sparse global fragments wrongly vetoing a supported 6×4 camera grid.
See `tests/test_disputed_grid.py` and `docs/qa/mixed-icons/`.

`acceptance/` preserves six byte-identical originals supplied on 23 September:
`pastel_4x4`, `space_dark_3x5`, `thin_7x3`, `groups_4x3`, `spanning_5x4`
(00:16:17 through 00:16:43) and `patchwork_animals_5x4` (00:38:25).
The expected counts and manually inspected witness points live only in tests,
not detector code. See `docs/qa/joint-coordinator/` for before/after results,
source hashes and limits. Screenshot overlays are not used as detector inputs.

`transport_irregular_shadows.png` is the byte-identical image supplied by the user
on 2026-09-22 as `Imagen de Codex 22 sept 2026, 11_54_06-7.png`. It contains 24
vehicle compositions in a 6×4 arrangement, irregular diagonal shadows, a shared
blue patterned background and a dark exterior. Its automatic diagnostic baseline
is 15 candidates without an accepted grid. It is a separate generated scene,
not a pixel-aligned shadow variant of `transport_dashed_shared.png`. Counts and
manually supplied diagnostic bounds are never production detector inputs. See
`docs/qa/irregular-shadows/` for controlled shadow tests and unresolved failures.

`transport_dashed_shared.png` is the unmodified original supplied by the user on
2026-09-22, from `Imagen de Codex 22 sept 2026, 11_25_03-5.png`. It contains 24
compositions arranged 6×4 on a shared blue/star background with dashed frames.
The previous selector found 24 initial regions but replaced their layout with a
4×3 camera hypothesis, producing 12 cuts. Dimensions are regression expectations,
never detector inputs. See `docs/qa/transport-shared/` for the exact reproduction.

`pastel_panels_camera.png` is the unmodified photograph supplied by the user on
2026-09-03: a pastel fabric collection on a dark laser bed, with blank margins,
uneven illumination and mild perspective. It contains six columns and four rows
of illustrations. These counts are expected test results, never detector inputs.

The synthetic cases in `test_visual_grid.py` exercise other inferred dimensions
and missing artwork. The original image is retained at full resolution so the
regression includes the same background and fine texture as the reported failure.

`transport_camera.png` is the unmodified second user photograph supplied on the
same date. It has a continuous background and a 5-column, 4-row arrangement of
19 illustrations: one giraffe spans two rows. Counts are test expectations only.
The fixture reproduces the previous 25-fragment / low-confidence-grid failure.

`patchwork_camera.png` is the pale touching-panel photograph from the user's
third failure screenshot, matched to the original downloaded image. It contains
6×4 cells in perspective, with a moon and a lamb too faint for the local detector;
their two grid squares are materialized automatically without extra UI.

`vehicles_panels.png` is the existing strongly coloured vehicle collection used
to ensure a camera fallback does not replace a supported 24-illustration result.

`floral_patchwork_recovered.png` is an unmodified user-provided image recovered
from the August conversation history on 2026-09-21 (audit ID I19). It shows a 6×4
panel of floral-filled silhouettes over varied pale patterned backgrounds, with
no UI or detection overlays. Its photographic versus synthetic origin is not
certified. The initial, untuned run returns 24 candidates and four extent/layout
reviews. Full-contour accuracy is not annotated. Provenance and the measured
baseline are in `docs/qa/image-audit/`; this image is not yet a regression test.
