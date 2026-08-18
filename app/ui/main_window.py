"""Main window coordinating the image, domain logic, and exporters."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.config.machines import (
    EPILOG_FUSION_MAKER_36,
    MachineProfile,
    MachineRepository,
)
from app.demo.demo_image import create_demo_image
from app.export.debug_exporter import export_debug_json
from app.export.svg_exporter import SVGExporter
from app.export.verifier import verify_export_geometry
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit
from app.imaging.detector import MotifDetector, infer_panel_grid
from app.imaging.panel_grid import PanelGrid
from app.models import (
    Detection,
    center_cuts_on_visual_anchors,
    recalculate_cut_overlaps,
    resolve_cut_overlaps,
)
from app.ui.canvas import BedCanvas
from app.ui.help_widgets import DelayedHelpToolBar
from app.ui.machine_dialog import AddMachineDialog
from app.ui.side_panel import SidePanel


TOOLBAR_HELP = {
    "demo": (
        "Generate a self-contained full-bed test image with twelve different "
        "printed motifs, including one intentionally invalid edge case."
    ),
    "paste": (
        "Paste a full-bed image from the Windows clipboard. Use this after Copy "
        "Background Image in Epilog Dashboard. Shortcut: Ctrl+V."
    ),
    "open": "Open a full-bed PNG, JPG, JPEG, or BMP image from this computer.",
    "detect": (
        "Detect figures without imposing a grid, then check the result explicitly. "
        "A panel grid can be added afterwards when the free result needs improvement."
    ),
    "undo": "Undo the last edit, deletion, centering, or overlap fix. Shortcut: Ctrl+Z.",
    "fix": (
        "Establish a collision-free layout by moving cut "
        "shapes to the nearest feasible positions. Cut sizes are preserved."
    ),
    "center": (
        "Centre every cut on its detected artwork while "
        "preserving the collision-free layout whenever geometry allows it."
    ),
    "preview": (
        "Preview the exported cut areas at normal brightness while dimming the "
        "rest of the bed. Invalid, colliding, and disabled cuts stay dimmed."
    ),
    "add": (
        "Toggle manual cut-square placement. While active, click anywhere on the bed "
        "to create a new square using the current global width and height."
    ),
    "delete": "Delete every selected cut area. Shortcut: Delete.",
    "clear": "Remove all automatic and manual detections from the current image.",
    "verify": (
        "Reconstruct the exportable SVG geometry back into image pixels, draw it "
        "as a purple overlay, and report the maximum round-trip error."
    ),
    "export": (
        "Save only enabled, valid cuts in an SVG sized to the selected machine bed. "
        "The background image is never included. Shortcut: Ctrl+E."
    ),
}


@dataclass(slots=True)
class _HistorySnapshot:
    label: str
    detections: list[Detection]
    mapper: CoordinateMapper | None
    selected_ids: set[int]
    primary_id: int | None
    cut_width_inches: float
    cut_height_inches: float
    centering_complete: bool
    panel_grid: PanelGrid | None
    grid_review_complete: bool
    detection_review_complete: bool


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lalikul Cut Prep — Laser Bed Prototype")
        self.resize(1420, 880)
        self.setMinimumSize(1080, 700)

        self.image_bgr: np.ndarray | None = None
        self.mapper: CoordinateMapper | None = None
        self.detections: list[Detection] = []
        self.panel_grid: PanelGrid | None = None
        self.selected_id: int | None = None
        self.selected_ids: set[int] = set()
        self.detector = MotifDetector()
        self.svg_exporter = SVGExporter()
        self.machine_repository = MachineRepository()
        self.machine_profiles = self.machine_repository.all_profiles()
        self.current_machine = EPILOG_FUSION_MAKER_36
        self.working_unit = LengthUnit.INCHES
        self.cut_width_inches = 5.0
        self.cut_height_inches = 5.0
        self._review_centering_complete = False
        self._grid_review_complete = False
        self._detection_review_complete = False
        self._workflow_phase = "setup"
        self._preflight_complete = False
        self._undo_stack: list[_HistorySnapshot] = []
        self._restoring_history = False

        self.canvas = BedCanvas()
        self.panel = SidePanel()
        self.panel.set_machine_profiles(
            self.machine_profiles, self.current_machine.id
        )
        self.panel.set_machine(self.current_machine)
        self.panel.set_cut_size_inches(
            self.cut_width_inches, self.cut_height_inches
        )
        self._build_toolbar()
        self._build_central_widget()
        self._build_review_shortcuts()
        self._connect_signals()
        self._update_review_controls()
        self.statusBar().showMessage("Ready — choose Demo Image to start")

    def _build_toolbar(self) -> None:
        toolbar = DelayedHelpToolBar("Main tools")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        self.demo_action = self._action("Demo Image", self.load_demo_image)
        self.paste_action = self._action(
            "Paste Image", self.paste_image, QKeySequence.StandardKey.Paste
        )
        self.open_action = self._action("Open Image", self.open_image)
        self.detect_action = self._action("Detect", self.detect_motifs)
        self.undo_action = self._action("Undo", self.undo)
        self.undo_action.setEnabled(False)
        self.add_action = self._action("Add cut square", self._toggle_add_mode)
        self.add_action.setCheckable(True)
        self.delete_action = self._action("Delete", self.delete_selected)
        self.verify_action = self._action("Verify Export", self.verify_export)
        self.export_action = self._action(
            "Export SVG", self.export_svg, QKeySequence("Ctrl+E")
        )

        for action in (
            self.demo_action,
            self.paste_action,
            self.open_action,
        ):
            toolbar.addAction(action)
        toolbar.addAction(self.undo_action)

        for action, help_text in (
            (self.demo_action, TOOLBAR_HELP["demo"]),
            (self.paste_action, TOOLBAR_HELP["paste"]),
            (self.open_action, TOOLBAR_HELP["open"]),
            (self.detect_action, TOOLBAR_HELP["detect"]),
            (self.undo_action, TOOLBAR_HELP["undo"]),
        ):
            toolbar.register_action_help(action, help_text)
        self.addAction(self.delete_action)
        self.addAction(self.export_action)

    def _build_central_widget(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.review_strip = self._build_workflow_panel()

        workspace = QWidget()
        workspace.setObjectName("workspaceColumn")
        workspace_layout = QGridLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.addWidget(self.canvas, 0, 0)
        self.navigation_help = self._build_navigation_help()
        workspace_layout.addWidget(
            self.navigation_help,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
        )
        self.cut_preview_toggle = QToolButton()
        self.cut_preview_toggle.setObjectName("cutPreviewToggle")
        self.cut_preview_toggle.setText("Preview cuts")
        self.cut_preview_toggle.setCheckable(True)
        self.cut_preview_toggle.setEnabled(False)
        self.cut_preview_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cut_preview_toggle.setToolTip(TOOLBAR_HELP["preview"])
        self.cut_preview_toggle.setAccessibleDescription(TOOLBAR_HELP["preview"])
        self.cut_preview_toggle.toggled.connect(self.canvas.set_cut_preview)
        workspace_layout.addWidget(
            self.cut_preview_toggle,
            0,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        content_layout.addWidget(workspace, 1)
        content_layout.addWidget(self.panel)
        outer.addWidget(self.review_strip)
        outer.addWidget(content, 1)
        self.setCentralWidget(central)

    def _build_workflow_panel(self) -> QFrame:
        strip = QFrame()
        strip.setObjectName("reviewWorkflow")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        heading = QWidget()
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 8, 0)
        heading_layout.setSpacing(2)
        title = QLabel("WORKFLOW")
        title.setObjectName("reviewTitle")
        heading_layout.addWidget(title)

        self.review_guidance = QLabel()
        self.review_guidance.setObjectName("reviewGuidance")
        self.review_guidance.setWordWrap(True)
        self.review_guidance.setMinimumWidth(210)
        self.review_guidance.setMaximumWidth(280)
        heading_layout.addWidget(self.review_guidance)
        layout.addWidget(heading)

        self.workflow_grid_button = QPushButton("1  Prepare image")
        self.workflow_grid_button.setObjectName("reviewAction")
        self.workflow_grid_button.setToolTip(
            "Choose the machine, image placement, units, and cut size."
        )
        self.workflow_grid_button.clicked.connect(
            lambda: self._set_workflow_phase("setup")
        )
        layout.addWidget(self.workflow_grid_button, 1)

        self.workflow_detect_button = QPushButton("2  Detect + check")
        self.workflow_detect_button.setObjectName("reviewAction")
        self.workflow_detect_button.setToolTip(TOOLBAR_HELP["detect"])
        self.workflow_detect_button.clicked.connect(self.detect_motifs)
        layout.addWidget(self.workflow_detect_button, 1)

        self.workflow_review_button = QPushButton("3  Review cuts")
        self.workflow_review_button.setObjectName("reviewAction")
        self.workflow_review_button.clicked.connect(
            lambda: self._set_workflow_phase("review")
        )
        layout.addWidget(self.workflow_review_button, 1)

        self.workflow_check_button = QPushButton("4  Check output")
        self.workflow_check_button.setObjectName("reviewAction")
        self.workflow_check_button.clicked.connect(self.show_preflight)
        layout.addWidget(self.workflow_check_button, 1)

        self.workflow_export_button = QPushButton("5  Export SVG")
        self.workflow_export_button.setObjectName("reviewAction")
        self.workflow_export_button.clicked.connect(self.export_svg)
        layout.addWidget(self.workflow_export_button, 1)

        self.add_center_button = QToolButton()
        self.add_center_button.setDefaultAction(self.add_action)
        self.add_center_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.add_center_button.setObjectName("reviewSecondaryAction")
        self.panel.add_review_action(self.add_center_button)

        self.remove_detection_button = QPushButton("Delete selected")
        self.remove_detection_button.setObjectName("reviewAction")
        self.remove_detection_button.setToolTip(
            "Select incorrect cuts on the canvas. Shift+click selects several."
        )
        self.remove_detection_button.clicked.connect(self.delete_selected)
        self.panel.add_review_action(self.remove_detection_button)

        self.fix_overlaps_button = QPushButton("Fix overlaps")
        self.fix_overlaps_button.setObjectName("reviewAction")
        self.fix_overlaps_button.setToolTip(TOOLBAR_HELP["fix"])
        self.fix_overlaps_button.clicked.connect(self.fix_overlaps)
        self.panel.add_review_action(self.fix_overlaps_button)

        self.center_cuts_button = QPushButton("Center drawings")
        self.center_cuts_button.setObjectName("reviewAction")
        self.center_cuts_button.setToolTip(TOOLBAR_HELP["center"])
        self.center_cuts_button.clicked.connect(self.center_cuts)
        self.panel.add_review_action(self.center_cuts_button)

        self.clear_detections_button = QPushButton("Clear all")
        self.clear_detections_button.setObjectName("reviewSecondaryAction")
        self.clear_detections_button.setToolTip(TOOLBAR_HELP["clear"])
        self.clear_detections_button.clicked.connect(self.clear_detections)
        self.panel.add_review_action(self.clear_detections_button)
        return strip

    def _build_review_shortcuts(self) -> None:
        """Bind global editing shortcuts without hijacking numeric input."""
        self.delete_key_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Delete), self
        )
        self.delete_key_shortcut.activated.connect(self.delete_selected)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self.undo)
        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._update_review_shortcuts)

    def _update_review_shortcuts(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Leave unmodified number keys available while editing numeric fields."""
        editing_value = isinstance(new, (QLineEdit, QAbstractSpinBox, QComboBox))
        for shortcut in (
            self.delete_key_shortcut,
            self.undo_shortcut,
        ):
            shortcut.setEnabled(not editing_value)

    def _build_navigation_help(self) -> QFrame:
        container = QFrame()
        container.setObjectName("navigationHelp")
        container.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum
        )
        container.setMaximumWidth(440)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 5, 10, 7)
        layout.setSpacing(3)

        self.navigation_toggle = QToolButton()
        self.navigation_toggle.setObjectName("navigationToggle")
        self.navigation_toggle.setText("Navigation controls")
        self.navigation_toggle.setCheckable(True)
        self.navigation_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.navigation_toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.navigation_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.navigation_toggle.toggled.connect(self._toggle_navigation_help)
        layout.addWidget(
            self.navigation_toggle, 0, Qt.AlignmentFlag.AlignLeft
        )

        self.navigation_details = QWidget()
        self.navigation_details.setObjectName("navigationDetails")
        details_layout = QVBoxLayout(self.navigation_details)
        details_layout.setContentsMargins(10, 8, 10, 8)
        controls = QLabel(
            "<b>Pan</b>&nbsp;&nbsp; Space + drag / H + drag / middle-button drag"
            "<br><b>Zoom</b>&nbsp;&nbsp; Z + click / Alt + click out / Ctrl + wheel"
            "<br><b>Fit bed</b>&nbsp;&nbsp; Ctrl + 0"
            "<br><b>Edit mode</b>&nbsp;&nbsp; V or Esc"
        )
        controls.setObjectName("navigationText")
        controls.setTextFormat(Qt.TextFormat.RichText)
        details_layout.addWidget(controls)
        self.navigation_details.setVisible(False)
        layout.addWidget(
            self.navigation_details, 0, Qt.AlignmentFlag.AlignLeft
        )
        return container

    def _toggle_navigation_help(self, expanded: bool) -> None:
        self.navigation_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.navigation_details.setVisible(expanded)

    def _set_workflow_phase(self, phase: str) -> None:
        """Navigate between user goals without changing job geometry."""
        if phase == "review" and (
            not self.detections or not self._detection_review_complete
        ):
            phase = "detect"
        self._workflow_phase = phase
        panel_phase = "export" if phase in {"preflight", "export"} else phase
        self.panel.set_phase(panel_phase)
        self._update_review_controls()

    def show_preflight(self) -> None:
        """Present an explicit export summary instead of silently dropping cuts."""
        if not self._detection_review_complete:
            self._set_workflow_phase("detect")
            self.statusBar().showMessage(
                "Confirm that the detection is correct before checking the output",
                6000,
            )
            return
        if not self.detections or self.mapper is None:
            self.statusBar().showMessage(
                "Detect and review at least one cut before checking the output", 5000
            )
            return
        recalculate_cut_overlaps(self.detections)
        exported = sum(item.enabled for item in self.detections)
        collisions = sum(
            item.enabled and item.overlaps_cut for item in self.detections
        )
        clipped = sum(
            item.enabled and not item.valid_cut for item in self.detections
        )
        skipped = sum(not item.enabled for item in self.detections)
        warnings = sum(
            item.enabled and not item.exportable for item in self.detections
        )
        result = verify_export_geometry(
            self.mapper, self.detections, self.panel.export_unit()
        )
        self.canvas.set_verification_rectangles(result.overlay_rectangles_px)
        self.cut_preview_toggle.setChecked(True)
        headline = (
            f"READY TO EXPORT: {exported} CUTS"
            if warnings == 0
            else f"EXPORTING {exported} CUTS · {warnings} WITH WARNINGS"
        )
        self.panel.verification_label.setText(
            f"{headline}\n"
            f"Collisions: {collisions} · Clipped/outside: {clipped} · "
            f"Skipped (unchecked): {skipped}\n"
            f"Geometry check: maximum error "
            f"{max(result.maximum_error_x_px, result.maximum_error_y_px):.6g} px"
        )
        self._preflight_complete = True
        self._set_workflow_phase("preflight")
        self.statusBar().showMessage(
            f"Preflight complete — {exported} cuts will be saved; "
            f"{skipped} unchecked cuts skipped",
            8000,
        )

    def _connect_signals(self) -> None:
        self.canvas.detection_selected.connect(self.select_detection)
        self.canvas.empty_selected.connect(self.clear_selection)
        self.canvas.edit_started.connect(self._begin_canvas_edit)
        self.canvas.center_moved.connect(
            lambda detection_id, x_px, y_px: self.move_detection(
                detection_id, x_px, y_px, record_history=False
            )
        )
        self.canvas.add_center_requested.connect(self.add_center)
        self.panel.detection_selection_changed.connect(
            self._apply_panel_selection
        )
        self.panel.enabled_changed.connect(self.set_detection_enabled)
        self.panel.machine_changed.connect(self.change_machine)
        self.panel.add_machine_requested.connect(self.add_machine)
        self.panel.working_unit_changed.connect(self.change_working_unit)
        self.panel.cut_size_changed.connect(self.change_cut_size)
        self.panel.image_lock_changed.connect(self.canvas.set_image_locked)
        self.canvas.image_placement_changed.connect(
            lambda x_in, y_in, width_in, height_in: self.change_image_placement(
                x_in, y_in, width_in, height_in, record_history=False
            )
        )
        self.panel.grid_edit_toggled.connect(self.canvas.set_grid_edit_active)
        self.panel.grid_edit_toggled.connect(
            lambda _active: self._update_review_controls()
        )
        self.panel.grid_visibility_changed.connect(self.canvas.set_grid_visible)
        self.panel.layout_mode_changed.connect(
            self.change_layout_mode
        )
        self.panel.grid_dimensions_changed.connect(self.change_grid_dimensions)
        self.panel.grid_action_requested.connect(self.handle_grid_action)
        self.canvas.grid_line_moved.connect(self.move_grid_line)
        self.canvas.grid_edit_started.connect(
            lambda: self._push_history("Edit panel grid")
        )
        self.canvas.grid_edit_finished.connect(self.finish_grid_edit)
        self.panel.grid_confirmation_requested.connect(self.confirm_grid)
        self.panel.detection_confirmation_requested.connect(
            self.confirm_detection
        )
        self.panel.grid_review_requested.connect(self.activate_grid_step)
        self.panel.detection_settings_changed.connect(
            self.mark_detection_settings_dirty
        )

    def _apply_panel_selection(self, payload: object) -> None:
        selected_ids, primary_id = payload  # type: ignore[misc]
        self.selected_ids = set(selected_ids)
        self.selected_id = primary_id
        self.canvas.set_selected_ids(self.selected_ids)
        self._update_review_controls()

    def _action(
        self,
        text: str,
        callback,
        shortcut: QKeySequence | QKeySequence.StandardKey | None = None,
    ) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        if shortcut is not None:
            action.setShortcut(shortcut)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        return action

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if (
            event.key() == Qt.Key.Key_Z
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.undo()
            event.accept()
            return
        super().keyPressEvent(event)

    def _push_history(self, label: str) -> None:
        if self._restoring_history:
            return
        self._undo_stack.append(
            _HistorySnapshot(
                label=label,
                detections=copy.deepcopy(self.detections),
                mapper=copy.deepcopy(self.mapper),
                selected_ids=set(self.selected_ids),
                primary_id=self.selected_id,
                cut_width_inches=self.cut_width_inches,
                cut_height_inches=self.cut_height_inches,
                centering_complete=self._review_centering_complete,
                panel_grid=copy.deepcopy(self.panel_grid),
                grid_review_complete=self._grid_review_complete,
                detection_review_complete=self._detection_review_complete,
            )
        )
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self.undo_action.setEnabled(True)

    def _begin_canvas_edit(self, label: str) -> None:
        self._push_history(label)

    def undo(self) -> None:
        if not self._undo_stack:
            self.statusBar().showMessage("Nothing to undo", 3000)
            return
        snapshot = self._undo_stack.pop()
        self._restoring_history = True
        try:
            self.detections = snapshot.detections
            self.mapper = snapshot.mapper
            self.selected_ids = set(snapshot.selected_ids)
            self.selected_id = snapshot.primary_id
            self.cut_width_inches = snapshot.cut_width_inches
            self.cut_height_inches = snapshot.cut_height_inches
            self._review_centering_complete = snapshot.centering_complete
            self.panel_grid = snapshot.panel_grid
            self._grid_review_complete = snapshot.grid_review_complete
            self._detection_review_complete = snapshot.detection_review_complete
            self.panel.set_cut_size_inches(
                self.cut_width_inches, self.cut_height_inches
            )
            if self.image_bgr is not None and self.mapper is not None:
                self.canvas.set_scene(
                    self._bgr_to_qimage(self.image_bgr),
                    self.mapper,
                    self.detections,
                )
            self.panel.set_image_info(self.mapper)
            self._sync_panel_grid_ui()
            self._refresh()
            self._set_workflow_phase(
                "review"
                if self.detections and self._detection_review_complete
                else "detect"
                if self.image_bgr is not None
                else "setup"
            )
        finally:
            self._restoring_history = False
        self.undo_action.setEnabled(bool(self._undo_stack))
        self.statusBar().showMessage(f"Undid: {snapshot.label}", 5000)

    def load_demo_image(self) -> None:
        if not self._confirm_image_replacement():
            return
        self._apply_machine(EPILOG_FUSION_MAKER_36, select_in_panel=True)
        self._load_image(create_demo_image(), "Generated demo image loaded")

    def paste_image(self) -> None:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if not mime.hasImage():
            QMessageBox.warning(
                self,
                "Paste Image",
                "The clipboard does not contain an image. In Epilog Dashboard, "
                "use Copy Background Image and then press Ctrl+V here.",
            )
            return
        qimage = clipboard.image()
        if qimage.isNull():
            QMessageBox.warning(self, "Paste Image", "The clipboard image is empty.")
            return
        if not self._confirm_image_replacement():
            return
        self._load_image(self._qimage_to_bgr(qimage), "Clipboard image loaded")

    def open_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open full-bed image",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not filename:
            return
        try:
            data = np.fromfile(filename, dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except (OSError, ValueError):
            image = None
        if image is None:
            QMessageBox.critical(self, "Open Image", "The selected image could not be read.")
            return
        if not self._confirm_image_replacement():
            return
        self._load_image(image, f"Loaded {Path(filename).name}")

    def _confirm_image_replacement(self) -> bool:
        if self.image_bgr is None:
            return True
        answer = QMessageBox.question(
            self,
            "Replace current job?",
            "Loading another image will replace the current grid, detections, and "
            "undo history. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _load_image(self, image_bgr: np.ndarray, message: str) -> None:
        height, width = image_bgr.shape[:2]
        self.image_bgr = np.ascontiguousarray(image_bgr)
        self.mapper = CoordinateMapper.contain_image(
            width,
            height,
            self.current_machine.bed_width_in,
            self.current_machine.bed_height_in,
        )
        self.detections = []
        self.panel_grid = None
        self.selected_id = None
        self.selected_ids = set()
        self._review_centering_complete = False
        self._grid_review_complete = False
        self._detection_review_complete = False
        self._preflight_complete = False
        self._undo_stack.clear()
        self.undo_action.setEnabled(False)
        self.cut_preview_toggle.setChecked(False)
        self.cut_preview_toggle.setEnabled(False)
        self.canvas.set_scene(
            self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
        )
        self.canvas.reset_view()
        self.canvas.set_image_locked(self.panel.image_locked())
        self.panel.set_image_info(self.mapper)
        self.panel.set_detections(
            self.detections, self.selected_ids, self.selected_id
        )
        self._sync_panel_grid_ui()
        self._set_workflow_phase("detect")
        self.panel.verification_label.setText("Round-trip verification not run")
        self.statusBar().showMessage(f"{message} — {width} × {height} px", 6000)

    def detect_motifs(self, replace_confirmed: bool = False) -> None:
        if self.image_bgr is None or self.mapper is None:
            self._request_image()
            return
        if (
            self.detections
            and not replace_confirmed
            and not self._confirm_redetection()
        ):
            return
        if self.panel_grid is not None and self._grid_review_complete:
            self._push_history("Detect figures")
            self.detect_in_current_grid()
            self._set_workflow_phase("detect")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            settings = replace(
                self.panel.detector_settings(self.mapper), layout_mode="free"
            )
            result = self.detector.detect_with_layout(
                self.image_bgr, settings
            )
            candidates = list(result.candidates)
        except Exception as exc:  # present processing failures as UI errors
            QMessageBox.critical(self, "Detection failed", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._push_history("Detect motifs")
        self.panel_grid = result.panel_grid
        self.detections = [
            Detection.from_pixel_center(
                index,
                candidate.center_px,
                self.mapper,
                candidate.bounding_box_px,
                candidate.score,
                cut_width_inches=self.cut_width_inches,
                cut_height_inches=self.cut_height_inches,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        self._review_centering_complete = False
        self._detection_review_complete = False
        self._preflight_complete = False
        # Detection is a generation step, not a selection command. Starting
        # with an empty selection also prevents an accidental Delete press
        # from removing the first result.
        self.selected_id = None
        self.selected_ids = set()
        self._refresh()
        self._sync_panel_grid_ui()
        self._set_workflow_phase("detect")
        valid = sum(item.exportable for item in self.detections)
        detection_summary = (
            f"Detected {len(self.detections)} figures in "
            f"{self.panel_grid.columns} × {self.panel_grid.rows} panels"
            if self.panel_grid is not None
            else f"Detected {len(self.detections)} figures — {valid} ready cuts"
        )
        self.statusBar().showMessage(
            f"{detection_summary} — check the result before continuing",
            7000,
        )

    def activate_grid_step(self) -> None:
        """Offer panel boundaries only after a free detection has been reviewed."""
        if self.image_bgr is None:
            self._set_workflow_phase("setup")
            self._request_image()
            return
        if not self.detections:
            self._detection_review_complete = False
            self._set_workflow_phase("detect")
            self.statusBar().showMessage(
                "Run the first detection before deciding whether a grid is needed",
                6000,
            )
            return
        if self.panel_grid is None:
            self.estimate_panel_grid()
        self._set_workflow_phase("grid")
        if self.panel_grid is not None:
            self.panel.show_grid_checkbox.setChecked(True)
        self.canvas.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.statusBar().showMessage(
            "Adjust the divisions, then use this grid to detect again",
            6000,
        )

    def estimate_panel_grid(self) -> None:
        """Estimate panel divisions without committing to figure detection."""
        if self.image_bgr is None or self.mapper is None:
            return
        if self.panel.layout_mode_combo.currentData() == "free":
            self.panel_grid = None
            self._grid_review_complete = False
            self._sync_panel_grid_ui()
            self._update_review_controls()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            settings = replace(
                self.panel.detector_settings(self.mapper), layout_mode="free"
            )
            primary = self.detector.detect(self.image_bgr, settings)
            self.panel_grid = infer_panel_grid(self.image_bgr, primary)
        finally:
            QApplication.restoreOverrideCursor()
        self._grid_review_complete = False
        self._sync_panel_grid_ui()
        self._update_review_controls()

    def confirm_grid(self) -> None:
        """Apply the chosen layout and re-detect without advancing the workflow."""
        if self.image_bgr is None:
            self._request_image()
            return
        if (
            self.panel.layout_mode_combo.currentData() == "panels"
            and self.panel_grid is None
        ):
            self.statusBar().showMessage(
                "Create the intended rows and columns before confirming", 6000
            )
            return
        self._grid_review_complete = self.panel_grid is not None
        self.panel.edit_grid_checkbox.setChecked(False)
        self._set_workflow_phase("detect")
        self.detect_motifs(replace_confirmed=True)

    def confirm_detection(self) -> None:
        """Advance only after the user explicitly accepts the detected figures."""
        if not self.detections:
            self.statusBar().showMessage(
                "Run detection before confirming its result", 5000
            )
            return
        self._detection_review_complete = True
        self._set_workflow_phase("review")
        self.statusBar().showMessage(
            "Detection confirmed — review and adjust the cut areas", 6000
        )

    def change_layout_mode(self, mode: str) -> None:
        if self.image_bgr is None:
            self.canvas.set_panel_grid(self.panel_grid)
            return
        self._grid_review_complete = False
        self._preflight_complete = False
        if mode == "free":
            self.panel_grid = None
        elif mode == "panels" and self.panel_grid is None:
            height, width = self.image_bgr.shape[:2]
            self.panel_grid = PanelGrid.regular(width, height, 2, 2)
        elif mode == "auto":
            self.estimate_panel_grid()
        self._sync_panel_grid_ui()
        self._set_workflow_phase("grid")

    def finish_grid_edit(self) -> None:
        self._grid_review_complete = False
        self._preflight_complete = False
        self._sync_panel_grid_ui()
        self._set_workflow_phase("grid")
        self.statusBar().showMessage(
            "Grid changed — confirm the divisions before detecting again", 7000
        )

    def _confirm_redetection(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Re-detect figures?",
            "Re-detection replaces the current automatic and manual cut review. "
            "You can undo the replacement afterwards. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def mark_detection_settings_dirty(self) -> None:
        if not self.detections:
            return
        self._detection_review_complete = False
        self._preflight_complete = False
        self._set_workflow_phase("detect")
        self.statusBar().showMessage(
            "Detection settings changed — run Detect + check to apply them",
            7000,
        )

    def detect_in_current_grid(self) -> None:
        if self.image_bgr is None or self.mapper is None or self.panel_grid is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            candidates = self.detector.detect_in_grid(
                self.image_bgr,
                self.panel.detector_settings(self.mapper),
                self.panel_grid,
            )
        finally:
            QApplication.restoreOverrideCursor()
        self.detections = [
            Detection.from_pixel_center(
                index,
                candidate.center_px,
                self.mapper,
                candidate.bounding_box_px,
                candidate.score,
                cut_width_inches=self.cut_width_inches,
                cut_height_inches=self.cut_height_inches,
            )
            for index, candidate in enumerate(candidates, start=1)
        ]
        self.selected_id = None
        self.selected_ids = set()
        self._review_centering_complete = False
        self._detection_review_complete = False
        self._preflight_complete = False
        self._refresh()
        self._sync_panel_grid_ui()
        empty = self.panel_grid.columns * self.panel_grid.rows - len(self.detections)
        self.statusBar().showMessage(
            f"Grid detection updated · {len(self.detections)} figures · "
            f"{empty} empty cells · check the result before continuing",
            7000,
        )

    def change_grid_dimensions(self, columns: int, rows: int) -> None:
        if self.image_bgr is None:
            return
        height, width = self.image_bgr.shape[:2]
        if (
            self.panel_grid is not None
            and self.panel_grid.columns == columns
            and self.panel_grid.rows == rows
        ):
            return
        self._push_history("Change panel grid")
        self._grid_review_complete = False
        self._preflight_complete = False
        if self.panel_grid is None:
            self.panel_grid = PanelGrid.regular(width, height, columns, rows)
        else:
            self.panel_grid = self.panel_grid.with_dimensions(
                width, height, columns, rows
            )
        self._sync_panel_grid_ui()
        self._set_workflow_phase("grid")

    def move_grid_line(self, axis: str, index: int, value_px: float) -> None:
        if self.panel_grid is None:
            return
        self.panel_grid = self.panel_grid.move_line(axis, index, value_px)
        self._grid_review_complete = False
        self._preflight_complete = False
        self.canvas.set_panel_grid(self.panel_grid)
        self.panel.set_grid_info(
            self.panel_grid.columns,
            self.panel_grid.rows,
            self.panel_grid.confidence,
            self.panel_grid.source,
            len(self.detections),
        )

    def handle_grid_action(self, action: str) -> None:
        if self.image_bgr is None or self.mapper is None:
            return
        if action == "redetect":
            settings = replace(
                self.panel.detector_settings(self.mapper), layout_mode="free"
            )
            primary = self.detector.detect(self.image_bgr, settings)
            detected = infer_panel_grid(self.image_bgr, primary)
            if detected is None:
                self.statusBar().showMessage(
                    "No reliable panel grid found · enter rows and columns to create one",
                    7000,
                )
                return
            self._push_history("Detect panel grid")
            self.panel_grid = detected
        elif self.panel_grid is not None and action in {
            "distribute_columns",
            "distribute_rows",
        }:
            self._push_history("Distribute panel grid")
            self.panel_grid = self.panel_grid.distribute(
                "x" if action == "distribute_columns" else "y"
            )
        else:
            return
        self._grid_review_complete = False
        self._preflight_complete = False
        self._sync_panel_grid_ui()
        self._set_workflow_phase("grid")

    def _sync_panel_grid_ui(self) -> None:
        self.canvas.set_panel_grid(self.panel_grid)
        if self.panel_grid is None:
            self.panel.set_grid_info(None, None)
            free_mode = self.panel.layout_mode_combo.currentData() == "free"
            self.panel.set_grid_confirmation_state(
                self.image_bgr is not None and free_mode,
                self._grid_review_complete,
                False,
            )
            return
        self.panel.set_grid_info(
            self.panel_grid.columns,
            self.panel_grid.rows,
            self.panel_grid.confidence,
            self.panel_grid.source,
            len(self.detections),
        )
        self.panel.set_grid_confirmation_state(
            self.image_bgr is not None,
            self._grid_review_complete,
            True,
        )

    def _toggle_add_mode(self, active: bool) -> None:
        if active:
            self.panel.set_image_locked(True)
        self.canvas.set_add_mode(active)
        self.add_action.setText(
            "Cancel adding square" if active else "Add cut square"
        )
        if active:
            self.statusBar().showMessage(
                "Add cut square active — click anywhere on the bed"
            )
        else:
            self.statusBar().showMessage("Add cut square off", 3000)

    def add_center(self, x_px: float, y_px: float) -> None:
        if self.mapper is None:
            return
        self._push_history("Add cut square")
        next_id = max((item.id for item in self.detections), default=0) + 1
        detection = Detection.from_pixel_center(
            next_id,
            (x_px, y_px),
            self.mapper,
            bounding_box_px=None,
            score=1.0,
            manual=True,
            cut_width_inches=self.cut_width_inches,
            cut_height_inches=self.cut_height_inches,
        )
        self.detections.append(detection)
        self._review_centering_complete = False
        self.selected_id = detection.id
        self.selected_ids = {detection.id}
        self._refresh()
        self.statusBar().showMessage(f"Added cut square #{next_id:02d}", 4000)

    def move_detection(
        self,
        detection_id: int,
        x_px: float,
        y_px: float,
        record_history: bool = True,
    ) -> None:
        if self.mapper is None:
            return
        detection = self._find_detection(detection_id)
        if detection is None:
            return
        if record_history:
            self._push_history("Move cut")
        detection.move_to_pixel((x_px, y_px), self.mapper)
        self.selected_id = detection_id
        self.selected_ids = {detection_id}
        self.canvas.set_verification_rectangles({})
        self.panel.verification_label.setText("Round-trip verification not run")
        self._refresh()

    def select_detection(self, detection_id: int, additive: bool = False) -> None:
        if self._detection_review_complete:
            self._set_workflow_phase("review")
        if detection_id in self.selected_ids:
            # A second click is always a toggle-off. In a multi-selection it
            # removes just this square and preserves the other prepared cuts.
            self.selected_ids.remove(detection_id)
        elif additive:
            self.selected_ids.add(detection_id)
        else:
            self.selected_ids = {detection_id}
        self.selected_id = (
            detection_id
            if detection_id in self.selected_ids
            else next(iter(self.selected_ids), None)
        )
        self.canvas.set_selected_ids(self.selected_ids)
        self.panel.set_selected_ids(self.selected_ids, self.selected_id)
        self._update_review_controls()

    def clear_selection(self) -> None:
        self.selected_ids = set()
        self.selected_id = None
        self.canvas.set_selected_ids(set())
        self.panel.set_selected_ids(set())
        self._update_review_controls()

    def set_detection_enabled(self, detection_id: int, enabled: bool) -> None:
        detection = self._find_detection(detection_id)
        if detection is None or detection.enabled == enabled:
            return
        self._push_history("Change export inclusion")
        detection.enabled = enabled
        self._refresh()

    def delete_selected(self) -> None:
        if not self.selected_ids:
            self.panel.edit_grid_checkbox.setChecked(False)
            self.canvas.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.statusBar().showMessage(
                "Selection active — click a cut; Shift+click selects several",
                5000,
            )
            return
        deleted_ids = set(self.selected_ids)
        self._push_history(
            "Delete detection" if len(deleted_ids) == 1 else f"Delete {len(deleted_ids)} detections"
        )
        self.detections = [item for item in self.detections if item.id not in deleted_ids]
        self.selected_id = None
        self.selected_ids = set()
        self._refresh()
        if not self.detections:
            self._set_workflow_phase("detect")
        self.statusBar().showMessage(
            f"Deleted {len(deleted_ids)} detection"
            f"{'s' if len(deleted_ids) != 1 else ''} — Ctrl+Z to undo",
            5000,
        )

    def clear_detections(self) -> None:
        if not self.detections:
            return
        self._push_history("Clear all detections")
        self.detections = []
        self.selected_id = None
        self.selected_ids = set()
        self._review_centering_complete = False
        self._detection_review_complete = False
        self._refresh()
        self._set_workflow_phase("detect")
        self.statusBar().showMessage("Detections cleared", 4000)

    def fix_overlaps(self) -> None:
        """Finish review by separating cuts without cropping their artwork."""
        if self.mapper is None:
            self._request_image()
            return
        if not any(
            detection.enabled and detection.overlaps_cut
            for detection in self.detections
        ):
            self.statusBar().showMessage("No overlaps to fix", 4000)
            return
        self._push_history("Fix overlaps")
        self.selected_id = None
        self.selected_ids = set()
        moved_ids, unresolved_ids = resolve_cut_overlaps(
            self.detections, self.mapper
        )
        self._refresh()
        if unresolved_ids:
            self.statusBar().showMessage(
                f"Moved {len(moved_ids)} cuts automatically — "
                f"{len(unresolved_ids)} still collide; drag them manually or disable one",
                10000,
            )
        elif moved_ids:
            self.statusBar().showMessage(
                f"Fixed all overlaps by moving {len(moved_ids)} cuts — "
                "all moved squares still contain their drawings",
                8000,
            )
        else:
            self.statusBar().showMessage("No overlaps to fix", 4000)

    def center_cuts(self) -> None:
        """Center cuts on artwork without recreating avoidable overlaps."""
        if self.mapper is None:
            self._request_image()
            return
        if self._review_centering_complete:
            self.statusBar().showMessage(
                "The drawings are already centered; preview or export",
                5000,
            )
            return
        if any(
            detection.enabled and detection.overlaps_cut
            for detection in self.detections
        ):
            self.statusBar().showMessage(
                "Fix the overlapping cut layout before centering the drawings",
                7000,
            )
            return
        if not any(detection.enabled for detection in self.detections):
            self.statusBar().showMessage("There are no enabled cuts to center", 4000)
            return

        self._push_history("Center drawings")
        self.selected_id = None
        self.selected_ids = set()
        moved_ids, problem_ids = center_cuts_on_visual_anchors(
            self.detections, self.mapper
        )
        self._review_centering_complete = True
        self._refresh()
        if problem_ids:
            clipped_count = sum(
                detection.enabled and not detection.valid_cut
                for detection in self.detections
            )
            collision_count = sum(
                detection.enabled and detection.overlaps_cut
                for detection in self.detections
            )
            self.statusBar().showMessage(
                f"Centered {len(moved_ids)} squares with layout constraints — "
                f"{collision_count} unavoidable collisions and {clipped_count} "
                "drawings need a larger cut size or detection review",
                10000,
            )
        elif moved_ids:
            self.statusBar().showMessage(
                f"Centered {len(moved_ids)} cuts on their complete drawing bounds — "
                "review complete",
                7000,
            )
        else:
            self.statusBar().showMessage(
                "All cuts are already centered on their complete drawings", 5000
            )

    def verify_export(self) -> None:
        if self.mapper is None:
            self._request_image()
            return
        result = verify_export_geometry(
            self.mapper, self.detections, self.panel.export_unit()
        )
        self.canvas.set_verification_rectangles(result.overlay_rectangles_px)
        self.panel.set_verification_result(
            result.maximum_error_x_px, result.maximum_error_y_px
        )
        self.statusBar().showMessage(
            "Verify Export: reconstructed SVG geometry shown in purple dots — "
            f"max error X {result.maximum_error_x_px:.12f} px, "
            f"Y {result.maximum_error_y_px:.12f} px",
            10000,
        )

    def export_svg(self) -> None:
        if self.mapper is None:
            self._request_image()
            return
        if not self._preflight_complete:
            self.show_preflight()
            self.statusBar().showMessage(
                "Review the preflight summary, then choose Export SVG again",
                7000,
            )
            return
        exported = sum(item.enabled for item in self.detections)
        warnings = sum(
            item.enabled and not item.exportable for item in self.detections
        )
        if exported == 0:
            QMessageBox.warning(
                self,
                "Nothing to export",
                "No cut is currently checked. Select at least one cut to export.",
            )
            return
        if warnings:
            answer = QMessageBox.warning(
                self,
                "Some cuts have warnings",
                f"All {exported} checked cuts will be exported, but {warnings} "
                "have warnings (too small, outside the bed, or overlapping). "
                "The preflight summary shows the reasons. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        export_unit = self.panel.export_unit()
        if self.panel.export_uses_override() and export_unit != self.working_unit:
            answer = QMessageBox.warning(
                self,
                "Export unit differs from working unit",
                "The SVG will be exported in "
                f"{export_unit.display_name.lower()} ({export_unit.value}), while the "
                f"application is displaying {self.working_unit.display_name.lower()} "
                f"({self.working_unit.value}).\n\n"
                "All geometry will be converted, but downstream laser software may "
                "interpret explicit units or viewBox values differently. Verify the "
                "imported bed size and position before using the file.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = Path.cwd() / f"lalikul_cut_{timestamp}.svg"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export cuts", str(suggested), "SVG files (*.svg)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".svg":
            path = path.with_suffix(".svg")
        try:
            result = self.svg_exporter.export(
                path, self.mapper, self.detections, export_unit
            )
            json_path: Path | None = None
            if self.panel.debug_json_checkbox.isChecked():
                json_path = export_debug_json(
                    path.with_suffix(".json"),
                    self.mapper,
                    self.detections,
                    self.working_unit,
                    export_unit,
                    self.current_machine.name,
                )
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        details = f"SVG saved with {result.rectangle_count} cuts:\n{result.path}"
        if json_path is not None:
            details += f"\n\nDebug JSON:\n{json_path}"
        QMessageBox.information(self, "Export complete", details)
        self._workflow_phase = "export"
        self._update_review_controls()
        self.statusBar().showMessage(
            f"Exported {result.rectangle_count} cuts in {result.unit.value} to "
            f"{result.path.name}",
            7000,
        )

    def change_machine(self, machine_id: str) -> None:
        profile = next(
            (item for item in self.machine_profiles if item.id == machine_id), None
        )
        if profile is not None:
            self._apply_machine(profile)

    def add_machine(self) -> None:
        dialog = AddMachineDialog(self)
        if dialog.exec() != AddMachineDialog.DialogCode.Accepted:
            return
        try:
            profile = self.machine_repository.add_custom_profile(*dialog.values())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not add machine", str(exc))
            return
        self.machine_profiles = self.machine_repository.all_profiles()
        self.panel.set_machine_profiles(self.machine_profiles, profile.id)
        self._apply_machine(profile, select_in_panel=True)
        self.statusBar().showMessage(f"Added machine profile: {profile.name}", 5000)

    def change_working_unit(self, unit_value: str) -> None:
        self.working_unit = LengthUnit(unit_value)
        self.canvas.set_working_unit(self.working_unit)
        self.panel.refresh_unit_display()
        self._refresh()

    def change_cut_size(self, width_inches: float, height_inches: float) -> None:
        if (
            abs(self.cut_width_inches - width_inches) <= 1e-12
            and abs(self.cut_height_inches - height_inches) <= 1e-12
        ):
            return
        self._push_history("Change cut size")
        self.cut_width_inches = width_inches
        self.cut_height_inches = height_inches
        if self.mapper is not None:
            for detection in self.detections:
                detection.set_cut_size(width_inches, height_inches, self.mapper)
        self._review_centering_complete = False
        self._refresh()

    def change_image_placement(
        self,
        x_in: float,
        y_in: float,
        width_in: float,
        height_in: float,
        record_history: bool = True,
    ) -> None:
        if self.image_bgr is None or self.mapper is None:
            return
        requested = (x_in, y_in, width_in, height_in)
        if all(
            abs(first - second) <= 1e-12
            for first, second in zip(
                requested, self.mapper.image_bed_rect_inches
            )
        ):
            return
        if record_history:
            self._push_history("Change image placement")
        self.mapper = CoordinateMapper(
            self.mapper.image_width_px,
            self.mapper.image_height_px,
            self.current_machine.bed_width_in,
            self.current_machine.bed_height_in,
            x_in,
            y_in,
            width_in,
            height_in,
        )
        for detection in self.detections:
            detection.recalculate_for_mapper(self.mapper)
        self._review_centering_complete = False
        self.canvas.set_scene(
            self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
        )
        self.panel.set_image_info(self.mapper)
        self._refresh()

    def _apply_machine(
        self, profile: MachineProfile, select_in_panel: bool = False
    ) -> None:
        self.current_machine = profile
        if select_in_panel:
            self.panel.select_machine_id(profile.id)
        self.panel.set_machine(profile)
        if self.image_bgr is not None:
            height, width = self.image_bgr.shape[:2]
            self.mapper = CoordinateMapper.contain_image(
                width,
                height,
                profile.bed_width_in,
                profile.bed_height_in,
            )
            for detection in self.detections:
                detection.recalculate_for_mapper(self.mapper)
            self._review_centering_complete = False
            self.canvas.set_scene(
                self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
            )
            self.canvas.reset_view()
        self.canvas.set_bed_configuration(
            profile.bed_width_in, profile.bed_height_in
        )
        self.panel.set_image_info(self.mapper)
        self._refresh()

    def _refresh(self) -> None:
        self._preflight_complete = False
        recalculate_cut_overlaps(self.detections)
        existing_ids = {detection.id for detection in self.detections}
        self.selected_ids.intersection_update(existing_ids)
        if self.selected_id not in self.selected_ids:
            self.selected_id = next(iter(self.selected_ids), None)
        self._update_review_controls()
        has_detections = bool(self.detections)
        self.cut_preview_toggle.setEnabled(has_detections)
        if not has_detections and self.cut_preview_toggle.isChecked():
            self.cut_preview_toggle.setChecked(False)
        self.canvas.set_detections(self.detections)
        self.canvas.set_selected_ids(self.selected_ids)
        self.canvas.set_verification_rectangles({})
        self.panel.set_detections(
            self.detections, self.selected_ids, self.selected_id
        )
        self.panel.verification_label.setText("Round-trip verification not run")

    def _update_review_controls(self) -> None:
        collision_count = sum(
            detection.enabled and detection.overlaps_cut
            for detection in self.detections
        )
        invalid_geometry_count = sum(
            detection.enabled and not detection.valid_cut
            for detection in self.detections
        )
        has_detections = bool(self.detections)
        has_enabled_detections = any(
            detection.enabled for detection in self.detections
        )
        selected_count = len(self.selected_ids)
        has_image = self.image_bgr is not None
        ready_count = sum(detection.enabled for detection in self.detections)
        self.workflow_grid_button.setEnabled(True)
        self.workflow_detect_button.setEnabled(has_image)
        self.workflow_review_button.setEnabled(
            has_detections and self._detection_review_complete
        )
        self.workflow_check_button.setEnabled(
            has_detections and self._detection_review_complete
        )
        self.workflow_export_button.setEnabled(
            self._preflight_complete and ready_count > 0
        )
        self.add_action.setEnabled(
            has_image and self._workflow_phase == "review"
        )
        self.remove_detection_button.setEnabled(selected_count > 0)
        self.remove_detection_button.setText(
            f"Delete selected ({selected_count})"
            if selected_count
            else "Select cuts to delete"
        )
        self.fix_overlaps_button.setEnabled(
            has_enabled_detections and collision_count > 0
        )
        self.fix_overlaps_button.setText(
            f"Fix overlaps ({collision_count})"
            if collision_count
            else "✓ No overlaps"
        )
        self.center_cuts_button.setEnabled(
            has_enabled_detections
            and collision_count == 0
            and not self._review_centering_complete
        )
        self.center_cuts_button.setText(
            "✓ Drawings centered"
            if self._review_centering_complete
            else "Center drawings"
        )
        self.panel.set_detection_review_state(
            has_detections, self._detection_review_complete
        )
        if not has_image:
            self.review_guidance.setText("Load or paste an image to begin.")
        elif not has_detections:
            self.review_guidance.setText(
                "Run Detect figures first. Add a grid only if the result needs it."
            )
        elif not self._detection_review_complete:
            self.review_guidance.setText(
                "Check the detection · Continue only if every figure is correct."
            )
        elif not self._review_centering_complete:
            if selected_count:
                self.review_guidance.setText(
                    f"{selected_count} selected · Shift+click adds more · "
                    "Delete mistakes, then fix overlaps"
                )
            elif collision_count:
                self.review_guidance.setText(
                    f"{collision_count} overlapping cuts · Fix layout, then center"
                )
            else:
                self.review_guidance.setText(
                    "Layout clear · Center cuts on their drawings"
                )
        elif collision_count:
            self.review_guidance.setText(
                f"Centered · {collision_count} overlapping cuts still need resolution"
            )
        elif invalid_geometry_count:
            self.review_guidance.setText(
                f"Centered · Review {invalid_geometry_count} clipped or out-of-bed cuts"
            )
        else:
            self.review_guidance.setText(
                "Review complete · Check exactly what will be exported"
            )

        self._set_workflow_state(
            self.remove_detection_button,
            "active"
            if selected_count
            else "neutral"
            if self._review_centering_complete
            else "available",
        )
        self._set_workflow_state(
            self.workflow_detect_button,
            "complete"
            if self._detection_review_complete
            else "active"
            if self._workflow_phase in {"detect", "grid"}
            else "available"
            if has_image
            else "locked",
        )
        self._set_workflow_state(
            self.workflow_grid_button,
            "active"
            if self._workflow_phase == "setup"
            else "complete"
            if has_image
            else "available",
        )
        review_complete = (
            has_detections
            and self._review_centering_complete
            and collision_count == 0
        )
        self._set_workflow_state(
            self.workflow_review_button,
            "active"
            if self._workflow_phase == "review"
            else "warning"
            if self._detection_review_complete
            and (collision_count or invalid_geometry_count)
            else "complete"
            if review_complete
            else "available"
            if self._detection_review_complete
            else "locked",
        )
        self._set_workflow_state(
            self.workflow_check_button,
            "active"
            if self._workflow_phase == "preflight"
            else "complete"
            if self._preflight_complete
            else "available"
            if has_detections and self._detection_review_complete
            else "locked",
        )
        self._set_workflow_state(
            self.workflow_export_button,
            "active" if self._preflight_complete else "locked",
        )
        self._set_workflow_state(
            self.center_cuts_button,
            "complete"
            if self._review_centering_complete
            else "active"
            if collision_count == 0
            else "locked",
        )
        self._set_workflow_state(
            self.fix_overlaps_button,
            (
                "warning"
                if self._review_centering_complete and collision_count
                else "active"
                if collision_count
                else "complete"
            ),
        )
        self.clear_detections_button.setEnabled(has_detections)

    @staticmethod
    def _set_workflow_state(button: QPushButton, state: str) -> None:
        if button.property("workflowState") == state:
            return
        button.setProperty("workflowState", state)
        button.style().unpolish(button)
        button.style().polish(button)

    def _find_detection(self, detection_id: int) -> Detection | None:
        return next((item for item in self.detections if item.id == detection_id), None)

    def _request_image(self) -> None:
        QMessageBox.information(
            self,
            "Image required",
            "Choose Demo Image, Paste Image, or Open Image first.",
        )

    @staticmethod
    def _bgr_to_qimage(image_bgr: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        return QImage(
            rgb.data,
            width,
            height,
            int(rgb.strides[0]),
            QImage.Format.Format_RGB888,
        ).copy()

    @staticmethod
    def _qimage_to_bgr(image: QImage) -> np.ndarray:
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = rgba.width(), rgba.height()
        raw = np.frombuffer(rgba.bits(), dtype=np.uint8, count=rgba.sizeInBytes())
        rows = raw.reshape(height, rgba.bytesPerLine())
        pixels = rows[:, : width * 4].reshape(height, width, 4)
        return cv2.cvtColor(pixels, cv2.COLOR_RGBA2BGR).copy()
