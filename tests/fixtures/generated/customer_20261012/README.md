# Synthetic collection controls — 12 October 2026

Generated with the built-in `image_gen` tool, following the user's request for
Alfabeto and Navidad test images. Exact prompts are in `prompts.json`.

- `alphabet_6x4.png`: 1536×1024, 24 cells containing A–X and detached illustrations
  on a shared dotted background. The letter and illustration form one composition.
- `christmas_6x4.png`: 1536×1024, 24 Christmas compositions on mixed patterned
  backgrounds, including paired characters, thin details and a snowflake.

These are generated clean inputs, not reconstructions of the client's camera
files, and have no independently calibrated physical dimensions. Both were
visually inspected. The generator produced all 24 requested cells in each.

`tests/test_customer_diagnostics.py` checks independent source witness points for
letters, artwork and a detached bow. It also preserves a known limitation: the
snowflake's faint tips are not all segmented. The new review must flag that
composition instead of claiming its small central region is complete.

At the default 36×24-inch image placement, estimated row spacing is below the
default 5-inch square size. The UI therefore correctly reports overlaps. Cut sizes
were not reduced to make these synthetic examples green.

Evaluation and real UI screenshots: `docs/qa/customer-improvements/`.
