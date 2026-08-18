# Lalikul Cut Prep

<p align="center">
  <img src="app/assets/lalikul-cut-prep.png" alt="Lalikul Cut Prep logo" width="180">
</p>

A local Windows demo that converts an image of a laser cutter bed into motif centres and cut squares or rectangles that can be exported as SVG.

The initial configuration uses an **Epilog Fusion Maker 36**, a **36 x 24 in** bed, and a global cut size of **5 x 5 in**. You can also create custom machine profiles, change working units, and adjust the cut size.

> **Project status:** functional validation prototype. It does not control the laser cutter, start cutting jobs, or configure power, speed, frequency, focus, or materials.

## Documentation for users and developers

The documentation is split so that non-technical users do not have to read development details:

- This `README.md` explains what the app does, how to install it, and how to use it. It is also the project homepage on GitHub.
- The complete user manual is available in both languages:
  - [English user manual](docs/Lalikul_Cut_Prep_User_Manual_EN.docx)
  - [Spanish user manual](docs/Lalikul_Cut_Prep_Manual_de_usuario_ES.docx)
  Both editions include detailed instructions, screenshots, states, settings,
  navigation controls, automatic overlap correction, and troubleshooting guidance.
- The [developer guide](docs/DEVELOPER_GUIDE.md) describes the architecture, virtual environment, tests, and technical decisions.

## Quick start for Windows users

### 1. Download and extract

On GitHub, select **Code -> Download ZIP**. Extract the entire ZIP to a normal folder before continuing. Do not run the application from inside the ZIP file.

### 2. Install Python

Install [Python for Windows](https://www.python.org/downloads/windows/) 3.10 or later. During installation, enable **Add python.exe to PATH**.

### 3. Set up the application once

Double-click `setup.bat` and wait for the `Setup complete` message.

The setup script creates `.venv`, a private Python environment for this application, and installs PySide6, OpenCV, and NumPy. It does not install Node.js or create a web server.

### 4. Open the app without a terminal

Double-click **`Lalikul Cut Prep.lnk`**, which `setup.bat` creates automatically in the main folder.

This is the recommended launcher. It displays the Lalikul Cut Prep icon and opens the interface through `pythonw.exe`, without leaving a terminal window visible or using Python's generic icon.

Alternative launchers are also available:

- `Lalikul Cut Prep.vbs` starts the app without a terminal if the shortcut is unavailable, although Windows Explorer displays a generic VBS icon for the file.
- `run.bat` delegates to the same hidden launcher and closes immediately. Windows may briefly flash a console because `.bat` files run through `cmd`.
- `run_console.bat` deliberately keeps the terminal open to display technical errors. Use it only for troubleshooting.

## Typical workflow

1. In **Prepare image**, select the machine, units, and global cut size.
2. Load an image using **Paste Image**, `Ctrl+V`, **Open Image**, or **Demo Image**.
3. If necessary, clear **Lock image placement** to move the image or scale it from
   its corners without distorting it. Lock it again when finished.
4. Select **Detect figures**. The first pass always uses the image freely, without
   imposing a panel grid.
5. Compare every detected cut with the image. The application stays in **Detect and
   check** and does not advance automatically. If the result is right, select
   **Detection is correct — continue**.
6. If the free result misses or merges figures, select **Improve with panel grid**,
   correct the estimated rows, columns, or guides, and choose **Use this grid and
   detect again**. Check the new result and confirm it explicitly as well.
7. In **Review cuts**, select false positives or use `Shift+click` to select several,
   then choose **Delete selected** or press `Delete`. Add missing cuts when needed.
8. Resolve orange cuts with **Fix overlaps**. This establishes a collision-free
   layout before any final centring.
9. Use **Center drawings**. Automatic cuts use stricter, stable
   artwork bounds so printed panel marks do not pull the square away from the
   drawing. Centring is constrained by the current layout: it approaches the
   true artwork centre without recreating avoidable collisions. If a drawing is
   genuinely larger than the configured cut, that size conflict remains visible.
10. Select **Check output**. The preflight reports ready cuts, cuts with warnings
   (overlapping, clipped, or outside the bed), and cuts skipped because they are unchecked.
11. Select **Export SVG**. Every checked cut is saved; if any carries a warning the
    application asks for confirmation and then exports it anyway.

## Zooming and panning like Illustrator

The canvas is not a fixed view. Open **Navigation controls** in the bottom-left
corner of the workspace to see these controls at any time. The compact guide
floats over the canvas, so opening it never moves or resizes the bed. It opens only
when selected and is never shown automatically when the pointer is idle.

You can zoom into the workspace and pan without changing any physical coordinates:

| Action | Windows control |
|---|---|
| Temporary Hand tool | Hold `Space` and drag |
| Hand tool | Press `H` and drag |
| Alternative pan | Drag with the middle mouse button |
| Zoom tool | Press `Z` and click |
| Zoom out with the Zoom tool | `Alt + click` |
| Zoom at the pointer | `Ctrl + mouse wheel` |
| Zoom in / out | `Ctrl + =` / `Ctrl + -` |
| Fit the entire bed | `Ctrl + 0` |
| Return to normal editing | `V` or `Esc` |

The mouse wheel without `Ctrl` pans vertically; `Shift + mouse wheel` pans horizontally. Zooming is centred on the pointer so that the area being inspected stays in view.

These controls follow the main navigation shortcuts in [Adobe Illustrator](https://helpx.adobe.com/illustrator/using/default-keyboard-shortcuts.html), adapted to this application's physical bed.

## Epilog Copy Background Image

The demo **does not connect directly to Epilog cameras**. It is designed to reuse the image that Epilog Dashboard copies to the Windows clipboard:

**Epilog Dashboard -> Copy Background Image -> Windows clipboard -> Lalikul Cut Prep -> Ctrl+V -> detection -> cut shapes -> SVG**

Epilog explains that **Copy Background Image** uses the IRIS camera system to capture the bed so the image can then be pasted into another application. In this workflow, Lalikul Cut Prep is that receiving application. See [Epilog's official explanation](https://support.epiloglaser.com/laser-machine/fusion-galvo/usage-and-operation/how-and-when-to-use-the-copy-background-image-feature/).

## Colour meanings

| Colour | State | Action |
|---|---|---|
| Green | Ready | Ready for export. |
| Bright cyan | Selected cut | Inspect, move, or delete it. |
| Orange | Overlap | Separate the cuts or exclude one of them. |
| Red | Outside the bed | Move the centre or reduce the cut size. |
| Grey | Excluded | Not included in the SVG. |

Two enabled cuts are considered to overlap if they cross or if their edges touch
exactly. Both change to `OVERLAP`. This is a warning state, not a filter: a
checked cut is still exported, so resolve or uncheck the ones you do not want.

After the centring step, **Fix Overlaps** is enabled when at least one collision
exists. It keeps each complete drawing inside its cut, leaves
collision-free cuts in place, and shares the minimum required movement between
colliding cuts. This keeps the complete arrangement as close as possible to the
original motifs instead of arbitrarily pinning one cut and moving another. If
there is not enough free space on the bed, the remaining cuts stay orange and can
be dragged manually or disabled. Automatic placement never prevents later manual
editing.

The horizontal **WORKFLOW** above the canvas has five user goals: Prepare image,
Detect + check, Review cuts, Check output, and Export SVG. The canvas keeps the main
working area, while the narrower right panel shows only controls belonging to the
current goal. Review commands such as Add cut square, Delete selected, Fix overlaps,
Center drawings, and Clear all appear together in the contextual review panel.
Detecting and accepting a result are deliberately separate: Review cuts remains
locked until the user confirms that every intended figure was detected exactly once.

The top toolbar contains only image loading and the global **Undo** command.
**Preview cuts** remains over the canvas.

## Main controls

### Machine / Work Area

- **Machine** selects the profile that defines the physical bed.
- The built-in **Epilog Fusion Maker 36** profile uses the manufacturer's stated
  maximum engraving area of **36 x 24 in** (approximately 915 x 610 mm), as listed
  in the [official Epilog 17000 Series manual](https://www.epiloglaser.com/es/assets/downloads/manuals/17000-series_manual.pdf).
- **Add machine...** saves custom profiles with a name, width, height, and unit.
- **Working units** changes visible measurements between inches, centimetres, and millimetres.
- The origin is at the top-left corner. X increases to the right and Y increases downwards.

### Bed / Image

- The image is loaded centred and contained within the bed while preserving its aspect ratio.
- **Lock image placement** protects the image while cut shapes are being edited.
- When unlocked, drag inside the image to move it or drag a corner to scale it.
- **IMAGE SCALE** shows how many pixels represent one physical unit horizontally and vertically.
- **Preview Cuts** dims everything outside enabled, valid, collision-free cut
  rectangles. It changes only the display and never modifies export geometry.
- A motif centre is calculated from robust high-confidence visual extents. Weak
  extreme fragments and fabric specks are trimmed, while the extent midpoint
  prevents dense lower areas from pulling the centre towards the ink mass.
- Cut centring deliberately uses a separate reference: the full detected bounding
  box. The overlap solver constrains later movement to positions that continue to
  contain that box whenever the configured cut is large enough.
- A cut that cannot contain its full detected drawing is marked **CLIPPED**. This
  is a warning, not an exclusion: the cut still exports while checked. Increase the
  global cut size or correct the detection, or uncheck the cut to leave it out.

### Global Cut Size

- The default value is **5 x 5 in**.
- With **Keep cut square** enabled, you can edit either Width or Height; the other measurement updates automatically.
- Disable it to create freely sized rectangles.

### Panel Grid

- The first detection runs without a grid. The grid is an optional second pass for
  images where free detection misses, merges, or duplicates figures.
- Select **Improve with panel grid** after the first result to estimate the panel
  boundaries. Choose **Use a panel grid** to enter them manually, or **No grid** to
  return to a free composition.
- **Show grid** controls only the guide overlay. **Edit grid lines** unlocks the
  guides for dragging and reveals **Space columns evenly** and **Space rows evenly**.
- Row and column changes update the guides immediately but preserve the current cut
  review. **Use this grid and detect again** replaces the old result; the replacement
  can be undone and must be checked and confirmed before Review cuts unlocks.
- **Restore automatic grid** discards manual guide adjustments and estimates the
  panel boundaries again. It does not restart the complete workflow.

### Advanced Detection Settings

- **Join separated parts** keeps detached details belonging to one figure together.
- Sensitivity, area, cleanup, and merge distance are technical overrides. Double-click
  a control to restore its default.

## Manual editing

- Click a centre or cut shape to select it; selected cuts use a high-contrast
  cyan border, cyan centre, and translucent cyan fill on the cut square itself.
- Hold `Shift` while clicking the canvas or detection list to add or remove cuts
  from a multiple selection.
- Clicking empty canvas space preserves the current selection. Selecting another
  cut, toggling cuts with `Shift`, deleting, or clearing changes it explicitly.
- **Center drawings** and **Fix overlaps** leave no cut selected, preventing an
  accidental Delete from removing the last cuts moved by the program.
- If cuts collide, either select **Fix Overlaps** or continue arranging them manually.
- Enable **Add cut square** and click on the bed to create a manual cut area.
- Press **Delete** to remove all selected cuts together.
- Use **Clear all** in the contextual review panel to remove every cut area.
- Press `Ctrl+Z` or use **Undo** to restore the previous edit. The app keeps the
  latest 50 geometry operations, including deletion, clearing, movement, cut-size
  changes, centring, and overlap correction.
- Use **Include in SVG** to exclude a cut without deleting it.

## Export and verification

The SVG contains every **checked** (enabled) cut, even if it overlaps, is clipped,
or lies outside the bed. Those states raise a warning at export time but do not
remove the cut. The only cuts left out are the ones you uncheck in the list.

It does not include the photograph, text, centres, labels, or detection bounding boxes.

By default, **Export units** uses the same unit as **Working units**. The app displays a warning if you choose a different unit. Always verify the bed size in the receiving software.

**Check output** runs the geometry verification, enables the visual cut preview, and
states how many cuts are ready, how many carry warnings (overlapping, clipped, or
outside the bed), and how many are skipped because they are unchecked. **Export SVG**
is unlocked only after this preflight has been reviewed; if any checked cut carries a
warning, the app asks for confirmation and then exports it anyway.

The internal debug JSON option is hidden and disabled by default for normal users.

## In-app help

- Select the small circular information icons to open explanations in English.
- Keep the pointer still over a top-toolbar button for approximately 1.3 seconds to display its help text.

## Troubleshooting

### The application reports a missing or broken environment

Run `setup.bat` again. If Python has been uninstalled, reinstall it first.

### Ctrl+V does not load the image

Return to Epilog Dashboard, select **Copy Background Image**, and paste immediately. You can also use **Open Image** with a PNG, JPG, JPEG, or BMP file.

### The application does not open and the hidden launcher gives no reason

Run `run_console.bat`. The terminal will remain open and display the technical error.

### The imported SVG has the wrong size

Match **Export units** to **Working units** and verify the page size during import.

## Current limitations

- There is no direct connection to the cameras, Epilog Dashboard, PrintAPI, or laser cutter.
- The detector uses OpenCV, not YOLO or a trained model.
- Repeated patchworks are detected from broad seam/fabric changes and then
  validated against the candidate layout. Each panel receives its own background
  analysis and at most one automatic figure. Free compositions retain the normal
  component detector. Extremely low
  contrast, severe perspective, occlusion, or multiple intended motifs in one
  panel still require manual review.
- There is no perspective or homography correction.
- The image-to-bed relationship, origin, and SVG must be physically validated before production use.
- The default profile is Epilog Fusion Maker 36, but additional machines can be added.

## Development and testing

Technical information is kept outside this main guide so that the page remains useful to non-technical users. See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for PowerShell environment setup, code structure, and test instructions.

## Release status

Before distributing a production release publicly, the project should add a signed installer, an explicit licence, versioning, and a release section. This folder currently contains a local validation demo, not a certified production package.
