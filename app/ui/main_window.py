"""Main window coordinating the image, domain logic, and exporters."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
from app.imaging.detector import MotifDetector
from app.models import Detection, recalculate_cut_overlaps
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
        "Run the classical OpenCV detector using the current sensitivity, minimum "
        "area, and morphological cleanup settings."
    ),
    "add": (
        "Toggle manual center placement. While active, click anywhere on the bed "
        "to create a new cut using the current global width and height."
    ),
    "delete": "Delete the currently selected detection. Shortcut: Delete.",
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lalikul Cut Prep — Laser Bed Prototype")
        self.resize(1420, 880)
        self.setMinimumSize(1080, 700)

        self.image_bgr: np.ndarray | None = None
        self.mapper: CoordinateMapper | None = None
        self.detections: list[Detection] = []
        self.selected_id: int | None = None
        self.detector = MotifDetector()
        self.svg_exporter = SVGExporter()
        self.machine_repository = MachineRepository()
        self.machine_profiles = self.machine_repository.all_profiles()
        self.current_machine = EPILOG_FUSION_MAKER_36
        self.working_unit = LengthUnit.INCHES
        self.cut_width_inches = 5.0
        self.cut_height_inches = 5.0

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
        self._connect_signals()
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
        self.add_action = self._action("Add Center", self._toggle_add_mode)
        self.add_action.setCheckable(True)
        self.delete_action = self._action(
            "Delete", self.delete_selected, QKeySequence(Qt.Key.Key_Delete)
        )
        self.clear_action = self._action("Clear Detections", self.clear_detections)
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
        toolbar.addSeparator()
        toolbar.addAction(self.detect_action)
        toolbar.addAction(self.add_action)
        toolbar.addAction(self.delete_action)
        toolbar.addAction(self.clear_action)
        toolbar.addSeparator()
        toolbar.addAction(self.verify_action)
        toolbar.addAction(self.export_action)

        for action, help_text in (
            (self.demo_action, TOOLBAR_HELP["demo"]),
            (self.paste_action, TOOLBAR_HELP["paste"]),
            (self.open_action, TOOLBAR_HELP["open"]),
            (self.detect_action, TOOLBAR_HELP["detect"]),
            (self.add_action, TOOLBAR_HELP["add"]),
            (self.delete_action, TOOLBAR_HELP["delete"]),
            (self.clear_action, TOOLBAR_HELP["clear"]),
            (self.verify_action, TOOLBAR_HELP["verify"]),
            (self.export_action, TOOLBAR_HELP["export"]),
        ):
            toolbar.register_action_help(action, help_text)

    def _build_central_widget(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.canvas, 1)
        content_layout.addWidget(self.panel)
        outer.addWidget(content, 1)

        self.assumption_label = QLabel()
        self.assumption_label.setObjectName("assumptionBanner")
        self.assumption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.assumption_label.setWordWrap(True)
        outer.addWidget(self.assumption_label)
        self._update_assumption_text()
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.canvas.detection_selected.connect(self.select_detection)
        self.canvas.empty_selected.connect(lambda: self.select_detection(None))
        self.canvas.center_moved.connect(self.move_detection)
        self.canvas.add_center_requested.connect(self.add_center)
        self.panel.detection_selected.connect(self.select_detection)
        self.panel.enabled_changed.connect(self.set_detection_enabled)
        self.panel.machine_changed.connect(self.change_machine)
        self.panel.add_machine_requested.connect(self.add_machine)
        self.panel.working_unit_changed.connect(self.change_working_unit)
        self.panel.cut_size_changed.connect(self.change_cut_size)
        self.panel.image_lock_changed.connect(self.canvas.set_image_locked)
        self.canvas.image_placement_changed.connect(self.change_image_placement)

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

    def load_demo_image(self) -> None:
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
        self._load_image(image, f"Loaded {Path(filename).name}")

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
        self.selected_id = None
        self.canvas.set_scene(
            self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
        )
        self.canvas.reset_view()
        self.canvas.set_image_locked(self.panel.image_locked())
        self.panel.set_image_info(self.mapper)
        self.panel.set_detections(self.detections, self.selected_id)
        self.panel.verification_label.setText("Round-trip verification not run")
        self.statusBar().showMessage(f"{message} — {width} × {height} px", 6000)

    def detect_motifs(self) -> None:
        if self.image_bgr is None or self.mapper is None:
            self._request_image()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            candidates = self.detector.detect(
                self.image_bgr, self.panel.detector_settings(self.mapper)
            )
        except Exception as exc:  # present processing failures as UI errors
            QMessageBox.critical(self, "Detection failed", str(exc))
            return
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
        self.selected_id = self.detections[0].id if self.detections else None
        self._refresh()
        valid = sum(item.exportable for item in self.detections)
        self.statusBar().showMessage(
            f"Detected {len(self.detections)} motifs — {valid} valid cuts", 7000
        )

    def _toggle_add_mode(self, active: bool) -> None:
        if active:
            self.panel.set_image_locked(True)
        self.canvas.set_add_mode(active)
        if active:
            self.statusBar().showMessage("Add Center active — click anywhere on the bed")
        else:
            self.statusBar().showMessage("Add Center off", 3000)

    def add_center(self, x_px: float, y_px: float) -> None:
        if self.mapper is None:
            return
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
        self.selected_id = detection.id
        self._refresh()
        self.statusBar().showMessage(f"Added manual center #{next_id:02d}", 4000)

    def move_detection(self, detection_id: int, x_px: float, y_px: float) -> None:
        if self.mapper is None:
            return
        detection = self._find_detection(detection_id)
        if detection is None:
            return
        detection.move_to_pixel((x_px, y_px), self.mapper)
        self.selected_id = detection_id
        self.canvas.set_verification_rectangles({})
        self.panel.verification_label.setText("Round-trip verification not run")
        self._refresh()

    def select_detection(self, detection_id: int | None) -> None:
        self.selected_id = detection_id
        self.canvas.set_selected_id(detection_id)
        self.panel.set_selected_id(detection_id)

    def set_detection_enabled(self, detection_id: int, enabled: bool) -> None:
        detection = self._find_detection(detection_id)
        if detection is None or detection.enabled == enabled:
            return
        detection.enabled = enabled
        self._refresh()

    def delete_selected(self) -> None:
        if self.selected_id is None:
            self.statusBar().showMessage("Select a detection before deleting", 3000)
            return
        deleted_id = self.selected_id
        self.detections = [item for item in self.detections if item.id != deleted_id]
        self.selected_id = None
        self._refresh()
        self.statusBar().showMessage(f"Deleted detection #{deleted_id:02d}", 4000)

    def clear_detections(self) -> None:
        self.detections = []
        self.selected_id = None
        self._refresh()
        self.statusBar().showMessage("Detections cleared", 4000)

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
        self.cut_width_inches = width_inches
        self.cut_height_inches = height_inches
        if self.mapper is not None:
            for detection in self.detections:
                detection.set_cut_size(width_inches, height_inches, self.mapper)
        self._refresh()

    def change_image_placement(
        self, x_in: float, y_in: float, width_in: float, height_in: float
    ) -> None:
        if self.image_bgr is None or self.mapper is None:
            return
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
        self.canvas.set_scene(
            self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
        )
        self.panel.set_image_info(self.mapper)
        self._refresh()

    def _apply_machine(
        self, profile: MachineProfile, select_in_panel: bool = False
    ) -> None:
        self.current_machine = profile
        self._update_assumption_text()
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
            self.canvas.set_scene(
                self._bgr_to_qimage(self.image_bgr), self.mapper, self.detections
            )
            self.canvas.reset_view()
        self.canvas.set_bed_configuration(
            profile.bed_width_in, profile.bed_height_in
        )
        self.panel.set_image_info(self.mapper)
        self._refresh()

    def _update_assumption_text(self) -> None:
        if not hasattr(self, "assumption_label"):
            return
        self.assumption_label.setText(
            "Prototype — camera-to-bed mapping must be validated on the physical "
            f"{self.current_machine.name}. No machine control or laser parameters "
            "are included."
        )

    def _refresh(self) -> None:
        recalculate_cut_overlaps(self.detections)
        self.canvas.set_detections(self.detections)
        self.canvas.set_selected_id(self.selected_id)
        self.canvas.set_verification_rectangles({})
        self.panel.set_detections(self.detections, self.selected_id)
        self.panel.verification_label.setText("Round-trip verification not run")

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
