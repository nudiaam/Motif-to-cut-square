# Camera regression fixture

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
