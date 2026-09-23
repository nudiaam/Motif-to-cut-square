# Change log

## 2026-09-23 — Keep grid recovery available and verify Windows setup

- Allow an image with zero detected figures to open grid adjustment, retry
  automatic geometry or enter rows and columns manually. Empty detection still
  cannot be confirmed for cutting.
- Retain empty-bed registration, fabric-boundary support and clear reporting
  when the reference cannot be applied to the current image.
- Verify dependency consistency, application imports and required assets during
  setup; reject overly long Windows installation paths with recovery instructions.
- Use Qt Essentials and tested dependency versions. Validate fresh installation
  and repeated setup with Windows Python 3.12.10, including the bundled reference
  and zero-detection recovery. All 205 tests pass in both environments.
- Publish update instructions and preserve regression evidence in Git while
  excluding it from the user-facing source ZIP. Dark backgrounds remain a known
  limitation; this release makes no claim that every collection is resolved.

See [update instructions](docs/ACTUALIZACION_2026-09-23.md) and
[release verification](docs/qa/release-20260923/README.md).

## 2026-09-23 — Corroborate groups with detached accessories

- Recheck disputed repeated-appearance proposals locally before treating nearby
  accessory components as independent cuts. Compare recovered ownership against
  all available appearance evidence, including the shared background when needed.
- Reject a probed partition that loses independently visible components even if
  its extracted centres are aligned. Reuse corroborated local results.
- Recover 12 groups in the supplied original instead of 20 misplaced regions;
  preserve all 36 animal/accessory witnesses at three resolutions.
- Preserve exact boxes, centres and review reasons in 29 controls, including the
  other nine images in the user's new batch. All 202 automated tests pass.
- Keep physical cut sizes and clipping warnings unchanged.

See [diagnosis, evidence and limits](docs/qa/accessory-groups/README.md).

## 2026-09-23 — Recover low-contrast artwork on shared backgrounds

- Compare broad, faint artwork with a spatially supported background colour and
  its measured variation. Corroborate the resulting alignment across scales and
  thresholds, then reanalyse original pixels with the same background evidence.
- Allow independently observed compositions to challenge a filled but provisional
  coarse grid. Preserve thin connected stems that local segmentation can discard.
- Recover 15 leaves in the supplied dark-on-dark original, at half and 1.5×
  resolution and with extra surround. Verify 45 source points per variant.
- Preserve exact boxes and centres in 19 prior collection controls. All 199
  automated tests pass. Preserve physical size and overlap warnings: the default
  5-inch cuts are too small for these leaves at the current image scale.

See [diagnosis, evidence and limits](docs/qa/dark-leaves/README.md).

## 2026-09-23 — Corroborate disputed grids before rejecting them

- Do not let sparse global fragments alone veto a strongly supported printed
  grid. Reuse the existing local analysis to check occupancy, alignment and
  distinct ownership, then resubmit its evidence to the common coordinator.
- Recover 24 motifs in the supplied mixed-background original, including
  half-resolution and added-surround probes. Preserve exact boxes and centres
  in all 18 controls from the preceding update. All 196 automated tests pass.
- Preserve protection against coarse grids that group distinct observations,
  artwork extent warnings and physical overlap checks.

See [diagnosis, evidence and limits](docs/qa/mixed-icons/README.md).

## 2026-09-23 — Coordinate artwork, grid and appearance evidence

- Preserve each proposal's artwork evidence and compare competing grids against
  independently supported compositions, including coverage outside a tentative grid.
- Add colour-seam proposals corroborated by local artwork, and bounded light and
  chromatic contrast alternatives for unresolved scenes. Recheck only missing zones
  when geometry agrees but provisional fabric support discards artwork.
- Recover 20 patchwork animals, 16 pastel animals, 15 space motifs and 12 grouped
  compositions in the supplied originals. Keep existing extent and collision checks.
- Pass 194 automated tests, including the previous shadow and spanning-artwork
  checks. Preserve exact candidate boxes and centres in the eleven previous
  collection controls and the original transport with irregular shadows.

See [verification and remaining limits](docs/qa/joint-coordinator/README.md) and
[ten fabric-image test prompts](docs/qa/joint-coordinator/10-pruebas-telas.md).

## 2026-09-22 — Recover geometry under irregular shadows

- Add bounded local-relative-contrast geometry proposals, independent of a valid
  bright-fabric mask. Require agreement across scales and thresholds, then segment
  and review complete compositions against original pixels.
- Preserve established composition grids and prevent a shadow-fragmented fabric
  mask from dropping independently supported cells. Reject coarse, poorly aligned
  proposals even without an alternative; honour rejection in fallback paths.
- Recover 24 compositions in the new shadowed transport original, its resized
  variants and twelve controlled shadow cases across three collections. Preserve
  all eleven previous collection counts. All 188 automated tests pass.
- Keep artwork-review warnings and physical collision checks. In the new synthetic
  scene mapped to 36×24 inches, 5-inch squares still overlap because row spacing
  is approximately 4.74 inches. Default cut dimensions remain unchanged.

See [implementation and verification](docs/qa/shadow-recovery/README.md).

## 2026-09-22 — Preserve independently stable artwork grids

- Reproduce the transport original's 24-regions-to-12-cuts failure. Add the affine
  artwork layout to grid selection before the camera fallback can replace it.
- Require geometry agreement across three foreground thresholds; retain image
  framing independence and tolerate extra permissive-pass fragments only when
  the same layout remains supported.
- Reject grids that group stable distinct centres and align them substantially
  worse. The transport original now yields 24 cuts in 6×4, including added-margin
  and half-resolution probes. At 5 inches, two artwork warnings remain and there
  are no overlaps.

See [confirmed cause and results](docs/qa/transport-shared/README.md).

## 2026-09-22 — Distinct artwork-review colours and grid diagnosis

- Reserve orange for overlapping cuts; use violet for artwork/layout review in
  both canvas and cut list, with a visible legend and shared colour priority.
- Verify the rendered states and 50 diagnostic/UI tests. Add ten controlled
  patterned-background cases and a reproducible isolated grid-ranking probe.
- Document competing decorative/artwork periodicities and generated-image test
  prompts. The customer's annotated screenshot is not used as detector input;
  its exact failing route remains unconfirmed. Detection selection is unchanged
  in this update.

See [colours and typology diagnosis](docs/qa/grid-typology/README.md).

## 2026-09-22 — Adaptive scene and cell analysis

- Analyse scene appearance and compare grid hypotheses using common evidence.
  Record per-cell background palettes, contrast, detail and illumination plans.
- Seed local segmentation inside its owning panel; retain revisable context and
  avoid treating local artwork as camera surround. Inspect the whole owning cell
  during extent review, including parts far beyond an incomplete detected box.
- Recover coherent horizontal shadow bands through a bounded alternative view;
  preserve original pixels, physical calibration and explicit review reasons.
- Keep the same user workflow and dependencies. All 176 tests pass. Eleven image
  cases and four shadow probes are recorded, including timing and process memory.
  Two very pale patchwork motifs remain unconfirmed; full silhouette accuracy is
  not established for every collection.

See [adaptive analysis results](docs/qa/adaptive-planning/README.md).

## 2026-09-21 — Shared composition rules and artwork extent review

- Apply the same grouping rules to every reliable panel grid; preserve unexplained
  outliers with review reasons instead of deleting them solely by grid position.
- Normalize analysis to the observed fabric and fit camera-grid spacing and origin
  from internal seams. Preserve source calibration and flag uncertain print extents.
- Use overlapping cell windows and mask-initialized GrabCut with revisable context,
  sampling background within the owning panel rather than neighbouring panels.
- Check original image evidence outside candidate boxes. Propagate uncertainty to
  cut colours, list/detail states, preflight and diagnostic JSON; flag inferred cells.
- Validation: 166 tests pass. All three frontal generated fixtures have 24 unique
  occupied cells. Full artwork segmentation still has omissions and background
  contamination; no claim of complete or universal detection accuracy.

See [implementation results and limits](docs/qa/global-rework/README.md).

## 2026-09-21 — Whole-image guidance and generated regression fixtures

- Extend a visual grid by an adjacent row/column only when multiple distinct
  motifs survive stricter foreground extraction; retain the existing lines.
- Reconcile cell crops with whole-image evidence to preserve narrow artwork
  spanning two cells, including confirmed-guide redetection. Require a stable
  region without proximity merging before combining the two local detections.
- Do not materialize covered cells as extra cuts through spanning artwork.
  Preserve explicit manual choices and retain clipping/assignment warnings.
- Add three unchanged AI-generated textile fixtures with saved prompts and
  documented expectations. They are development cases, not a production accuracy
  benchmark. Keep the existing OpenCV/NumPy dependencies.

See `docs/DETECTION_GUIDANCE_2026-09-21.md` for results and limitations.

Validation: all 158 tests passed, including eight new guidance/UI regressions.
The existing transport UI expectation now correctly requires 19 cuts rather
than 20. Manually inspected rendered UI results for all three generated inputs.

## 2026-09-20 — Grid validation and detection diagnostics

- Cross-check automatic panel proposals against artwork layouts supported by
  multiple segmentation thresholds. Reject a proposal when the alternative
  explains substantially more distinct drawings, including missing rows/columns.
- Run trusted-grid cleanup even when an empty-bed reference is missing or rejected.
  Merge nearby fragments while preserving separated artwork for review.
- Use a conservative visible boundary fallback for one light piece on a dark bed.
  Ambiguous boundaries, full-frame fabric and multiple pieces retain the previous
  path; the fallback does not invent rows in blank fabric margins.
- Show whether the last detection applied the empty-bed reference, and why it did
  not. Advanced settings can save a detection report before accepting any cuts.
  The report includes detector revision, settings, reference status, grid decisions,
  positions and clipping. Undo restores the matching report.
- Show duplicate, outside-grid, spanning-artwork and clipped-artwork warnings
  before confirmation. Include these warnings in counts and output preflight.
  Cut sizes, shared grid positions and checked-cut SVG export remain unchanged.

Validation: 150 automated tests passed (16 new), including existing original
camera fixtures plus controlled grid-alias,
border-artifact, ambiguous-fabric, clipping, report and undo regressions. The six
new customer screenshots are not unannotated source photographs; their exact
production results still need validation with the originals and saved reports.

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
