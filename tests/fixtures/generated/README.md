# Generated textile development fixtures — 2026-09-21

Created with the built-in `image_gen` tool at the user's request. These are
synthetic photographs, not scans of original designs or customer camera inputs.
The unchanged PNGs are 1536 × 1024. Exact generation prompts are in
[prompts.json](prompts.json). No model, image service or new dependency is used
by the application to process them.

Visually inspected expectations (never passed to production detection):

| File | Compositions | Layout | Intended difficulty |
| --- | ---: | --- | --- |
| [pastel_animals_6x4.png](pastel_animals_6x4.png) | 24 | 6 × 4 | Pale animals, different printed backgrounds, accessories; bear and penguin together are one composition |
| [transport_spanning_5x4.png](transport_spanning_5x4.png) | 19 | 5 × 4, one merged pair of cells | Giraffe occupies column 5, rows 2–3; vehicles with smoke, fish, flags and other detached details |
| [folk_floral_6x4.png](folk_floral_6x4.png) | 24 | 6 × 4 | Continuous patterned background, fine floral details, two pale motifs, no printed grid |

Before this change the detector returned 18 / 20 / 20 candidates respectively.
After the guidance changes it returns 24 / 19 / 24. Tests also check cell
coverage, a complete giraffe extent, and that UI redetection does not add a
second cut through it. These checks do not establish accurate motif masks,
containment of every decorative detail, physical calibration, or production
accuracy. The images were used during development, so they are not a held-out
evaluation set.

Run `python -m unittest tests.test_grid_guidance` from the project root.
Use the PNGs directly in **Open Image** for manual review. The images have no
known physical scale: a 5-inch square can overlap or clip artwork depending on
the machine mapping. A matching detection count does not mean all cuts are ready.

The geometric negative tests separately cover blank borders, isolated marks,
multiple fragments in one cell, unsupported extrapolation, manual guides and
distinct neighbouring motifs. Future evaluation should include new collections
that have not been used to adjust the rules, then actual camera inputs when available.
