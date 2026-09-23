# Release verification — 23 September 2026

Scope: publish accumulated adaptive detection work, restore grid recovery after
zero detections, verify the empty-bed path and validate Windows installation.
No further dark-background tuning was made; this remains a known limitation.

## Empty-result recovery

- Adjust panel grid depends on a loaded image, rather than the presence of cuts.
- The grid screen no longer refuses zero detections.
- Restore automatic grid remains available with an image even when no grid exists.
- A UI regression exercises zero results, unavailable automatic geometry,
  manually entered dimensions and a successful guided retry. Confirm detection
  remains disabled for an empty result.

## Bed reference

All reference tests pass, including registration under a small camera shift,
unrelated-photo rejection, empty-bed exposure changes, outside-fabric filtering,
row extension and reference persistence. In the extracted installation, the
actual bundled bed image produced zero detections with `reference_applied=true`
and the grid recovery button enabled. See `clean-install-smoke.json` and
`empty-detection.png`. These checks do not imply every client photo registers.

## Clean installation

A candidate ZIP was extracted outside the source checkout. No old `.venv`,
bundled `.runtime` or globally installed packages were copied into it. Windows
setup selected its installed Python 3.12.10, created its own environment and
installed the declared dependencies. The installed application's own import
path is recorded in `clean-install-smoke.json`.

The initial deep-directory trial reproduced a genuine Windows long-path error
inside Qt. Essentials alone still contains the affected file, so omitting Addons
reduces download size but is not the complete fix. Setup now rejects installation
roots longer than 70 characters before package installation and gives relocation
instructions; `long-path-guard.txt` records that check. The clean short-folder
installation, including an accented character, completes successfully.

Setup verifies dependency consistency, application imports and required assets
before declaring success. The shortcut is generated for the new installation.
Qt Essentials and OpenCV are pinned; NumPy is pinned for Python 3.12+.
Python 3.10–3.14 satisfies the GUI dependency's declared range; only Windows
Python 3.12 was exercised here. This is not a guarantee for every client machine.

User ZIP exports omit regression fixtures and QA artifacts via `.gitattributes`;
these remain in the Git repository for developer review. Runtime environments
and machine-specific shortcuts remain excluded by `.gitignore`.

## Evidence

All 205 tests pass in the source environment (325.690 seconds) and with the
freshly installed environment (311.199 seconds). Repeating the final setup in
the installed folder also succeeds, including dependency and asset verification.

- `unittest.txt`: full source-checkout suite.
- `clean-setup-verified.txt`: successful fresh setup and exact installed versions.
- `clean-environment-tests.txt`: full suite using the fresh environment.
- `repeat-setup.txt`: successful repeat with the final setup script.
- `package-files.json`: hashes of files in the clean-install candidate.
- `clean-install-smoke.json`: actual package import path, bed reference and recovery.
- `long-path-guard.txt`: explicit early rejection and actionable instructions.

The first two installation logs are retained as failure evidence, not successful
release checks. This report distinguishes successful fixture tests from the
user-reported unresolved dark-background behaviour.
