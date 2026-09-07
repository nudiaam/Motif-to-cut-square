# Empty-bed reference

`empty_bed.png` is the unmodified camera image supplied on 2026-09-07 as
`Epilog Bed Picture1.png`. It is the bundled default for the Epilog Fusion
Maker 36 profile. Original dimensions and pixels are preserved.

Users can replace or remove the reference in Prepare image / BED / IMAGE.
Overrides are stored per machine beside the machine settings, outside the
installation. Removing the reference disables the bundled default too.

The detector first checks framing and matching visible bed texture. Unrelated
photographs fall back to the existing detector; they are never forcibly
subtracted from this image. Mild camera movement and exposure changes are
handled in the analysis image only.

When the reference matches, a filled fabric mask excludes bed detections and
extends a reliable lattice by complete rows/columns contained in the same
physical piece. Grid spacing, phase, orientation and cut size are preserved.
Partial edge cells and disconnected pieces do not extend the lattice. Once the
grid is trusted, outside bed artifacts are removed and nearby fragments in one
cell are represented by one combined artwork observation.

Validation currently uses synthetic fabric composited on this real reference,
including black and multicolour pieces, a missing entire outer row/column,
empty bed, exposure changes, small translation and unrelated photographs.
A paired original camera capture with real fabric is still needed to validate
real cloth boundaries, folds, shadows and black fabric under actual lighting.
