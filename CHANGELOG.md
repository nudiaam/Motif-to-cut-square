# Change log

## 2026-09-07 — Automatic fabric extent and grid cleanup

- Added an empty-bed camera reference for each machine in **Prepare image**.
- Grouped each machine's dimensions and empty-bed photograph in one visual profile.
- Included the supplied Epilog empty-bed image as the default reference for the
  Epilog Fusion Maker 36 profile.
- Detects the physical fabric by comparing colour and bed texture while tolerating
  small camera shifts and exposure changes.
- Extends reliable grid geometry to complete rows and columns inside the fabric,
  including an entirely undetected outer row or column.
- Preserves exact common grid centres through cut review, resizing, overlap checks,
  output verification, and SVG export.
- Creates missing grid cells as ordinary deletable squares without an additional
  user decision or review list.
- Removes bed artifacts outside independently established grids and combines nearby
  fragments assigned to the same cell.
- Keeps the previous detector when the empty-bed reference does not match the input.
- Retains automatic support for varied row and column counts, continuous fabric,
  visible printed panels, perspective, missing artwork, and spanning artwork.

Validation: 134 automated tests on Windows, including real supplied photographs and
controlled light, dark, multicolour, shifted, incomplete, and unrelated inputs.
