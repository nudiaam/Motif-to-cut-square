"""Controls, machine setup, detection list, and physical geometry inspection."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QStyle,
    QStyleOptionSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config.machines import MachineProfile
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import (
    LengthUnit,
    area_from_square_inches,
    area_to_square_inches,
    convert_area,
    convert_length,
    from_inches,
    to_inches,
)
from app.imaging.detector import DetectorSettings
from app.models import Detection
from app.ui.help_widgets import InfoButton


class MinimalArrowDoubleSpinBox(QDoubleSpinBox):
    """Double spin box with small, reliably visible chevron arrows."""

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        color = self.palette().buttonText().color()
        if not self.isEnabled():
            color.setAlpha(110)
        pen = QPen(color, 1.15)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for control, direction in (
            (QStyle.SubControl.SC_SpinBoxUp, -1),
            (QStyle.SubControl.SC_SpinBoxDown, 1),
        ):
            rectangle = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox, option, control, self
            )
            center = rectangle.center()
            left = QPointF(center.x() - 2.5, center.y() - 1.25 * direction)
            middle = QPointF(center.x(), center.y() + 1.25 * direction)
            right = QPointF(center.x() + 2.5, center.y() - 1.25 * direction)
            painter.drawLine(left, middle)
            painter.drawLine(middle, right)


HELP = {
    "machine_section": "Select the laser model that defines the physical work area, or add a named custom machine profile.",
    "machine": "The active machine profile. Its stored bed width and height define the physical coordinate system.",
    "work_area": "The usable physical bed size of the selected machine, displayed in the current working units.",
    "working_units": "The unit used for all visible physical positions, dimensions, rulers, cut sizes, and margins.",
    "bed_image_section": "Shows the active physical bed, source image resolution, and the mapping between image pixels and real bed distance.",
    "bed": "The physical work area represented by the canvas, using the current working units.",
    "image": "The pixel resolution of the loaded or pasted image. The prototype assumes the image covers the complete selected bed.",
    "scale": "Image scale tells the app how much image data represents real bed distance. Horizontal scale is image width in pixels divided by physical bed width. Vertical scale is image height divided by physical bed height. They are calculated independently and may differ.",
    "cut_section": "Sets one global cut size for every detection. The default is a 5 by 5 inch square, but it can be changed for future workflows.",
    "cut_width": "The physical width of every exported cut rectangle, displayed in the current working units.",
    "cut_height": "The physical height of every exported cut rectangle, displayed in the current working units.",
    "keep_square": "When enabled, cut height follows cut width so every cut remains square.",
    "settings_section": "Controls the classical OpenCV detector. Change a value and press Detect again to recalculate automatic detections.",
    "sensitivity": "Higher sensitivity detects subtler differences from the estimated fabric background, but may also detect more noise. Double-click the control to reset it to 65.",
    "minimum_area": "Rejects motif groups smaller than this area. Use image pixels squared or the current physical working unit squared; physical values are converted automatically from the loaded image scale. Double-click to reset to 500 px².",
    "cleanup": "A dimensionless, freely adjustable OpenCV cleanup strength. It removes small noise and closes short gaps; it is not a physical measurement. Double-click to reset to 25 percent.",
    "merge": "The maximum physical gap used to group nearby printed fragments into one motif, such as a bird and branch or a mushroom cap and stem. Large values may merge separate motifs. Double-click to reset to 0.35 inches.",
    "detections_section": "Lists every automatically detected or manually added motif center. A row checkbox controls export inclusion.",
    "total": "The total number of detections currently present.",
    "valid": "Enabled detections whose global cut rectangle fits inside the bed and does not touch another enabled cut.",
    "invalid": "Enabled cuts that extend outside the bed or touch another cut. Outside cuts are red, collisions are orange, and neither is exported.",
    "disabled": "Detections manually excluded from export. They remain visible and can be enabled again.",
    "selected_section": "Shows pixel coordinates, physical coordinates, global cut geometry, boundary status, and export state for the selected detection.",
    "export_units": "SVG units normally follow the working units. Choosing another unit triggers a warning before export because downstream software may interpret unit conversions differently.",
}


class SidePanel(QWidget):
    detection_selected = Signal(int)
    enabled_changed = Signal(int, bool)
    machine_changed = Signal(str)
    add_machine_requested = Signal()
    working_unit_changed = Signal(str)
    cut_size_changed = Signal(float, float)
    image_lock_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._detections: list[Detection] = []
        self._selected_id: int | None = None
        self._mapper: CoordinateMapper | None = None
        self._machine: MachineProfile | None = None
        self._working_unit = LengthUnit.INCHES
        self._minimum_area_mode = "px2"
        self._syncing_cut_size = False
        self._double_click_resets: dict[QObject, object] = {}
        # Long detection states such as "COLLISION" must never resize the
        # inspector or push numerical step buttons outside the viewport.
        self.setFixedWidth(420)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("sidePanelScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(scroll)

        content = QWidget()
        content.setObjectName("sidePanelContent")
        content.setMinimumWidth(0)
        content.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("CUT PREP")
        title.setObjectName("panelTitle")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        layout.addWidget(self._build_machine_section())
        layout.addWidget(self._build_bed_image_section())
        layout.addWidget(self._build_cut_section())
        layout.addWidget(self._build_detection_settings_section())
        layout.addWidget(self._build_detections_section(), 1)
        layout.addWidget(self._build_selected_section())

        export_row = QWidget()
        export_layout = QHBoxLayout(export_row)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(5)
        export_label = QLabel("Export units")
        export_layout.addWidget(export_label)
        export_layout.addWidget(InfoButton(HELP["export_units"]), 0, Qt.AlignmentFlag.AlignTop)
        self.export_unit_combo = QComboBox()
        self.export_unit_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.export_unit_combo.setMinimumContentsLength(16)
        self.export_unit_combo.addItem("Same as working units", "same")
        for unit in LengthUnit:
            self.export_unit_combo.addItem(f"{unit.display_name} ({unit.value})", unit.value)
        export_layout.addWidget(self.export_unit_combo, 1)
        layout.addWidget(export_row)

        self.debug_json_checkbox = QCheckBox("Write debug JSON beside SVG")
        self.debug_json_checkbox.setChecked(True)
        layout.addWidget(self.debug_json_checkbox)

        self.verification_label = QLabel("Round-trip verification not run")
        self.verification_label.setObjectName("verificationLabel")
        self.verification_label.setWordWrap(True)
        layout.addWidget(self.verification_label)
        scroll.setWidget(content)

    def _build_machine_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.machine_combo = QComboBox()
        self.machine_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.machine_combo.setMinimumContentsLength(18)
        self.machine_combo.currentIndexChanged.connect(self._on_machine_changed)
        add_button = QPushButton("Add machine…")
        add_button.clicked.connect(self.add_machine_requested)
        machine_header = QHBoxLayout()
        machine_header.setContentsMargins(0, 0, 0, 0)
        machine_header.setSpacing(5)
        machine_header.addWidget(QLabel("Machine"))
        machine_header.addWidget(
            InfoButton(HELP["machine"]), 0, Qt.AlignmentFlag.AlignTop
        )
        machine_header.addStretch(1)
        layout.addLayout(machine_header)
        layout.addWidget(self.machine_combo)
        layout.addWidget(add_button, 0, Qt.AlignmentFlag.AlignRight)

        self.work_area_value_label = QLabel("36.000 × 24.000 in")
        layout.addWidget(
            self._parameter_readout(
                "WORK AREA", self.work_area_value_label, HELP["work_area"]
            )
        )

        self.working_unit_combo = QComboBox()
        for unit in LengthUnit:
            self.working_unit_combo.addItem(
                f"{unit.display_name} ({unit.value})", unit.value
            )
        self.working_unit_combo.currentIndexChanged.connect(
            self._on_working_unit_changed
        )
        layout.addLayout(
            self._labeled_control(
                "Working units", self.working_unit_combo, HELP["working_units"]
            )
        )
        return self._section("MACHINE / WORK AREA", box, HELP["machine_section"])

    def _build_bed_image_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self.bed_value_label = QLabel("36.000 × 24.000 in")
        self.image_value_label = QLabel("No image loaded")
        self.scale_value_label = QLabel("Load an image to calculate scale")
        layout.addWidget(self._parameter_readout("BED", self.bed_value_label, HELP["bed"]))
        layout.addWidget(self._parameter_readout("IMAGE", self.image_value_label, HELP["image"]))
        layout.addWidget(
            self._parameter_readout("IMAGE SCALE", self.scale_value_label, HELP["scale"])
        )
        self.lock_image_checkbox = QCheckBox("Lock image placement")
        self.lock_image_checkbox.setChecked(True)
        self.lock_image_checkbox.setEnabled(False)
        self.lock_image_checkbox.toggled.connect(self.image_lock_changed)
        layout.addWidget(self.lock_image_checkbox)
        return self._section("BED / IMAGE", box, HELP["bed_image_section"])

    def _build_cut_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.cut_width_spin = self._physical_spin(5.0)
        self.cut_height_spin = self._physical_spin(5.0)
        self.cut_width_spin.valueChanged.connect(self._on_cut_width_changed)
        self.cut_height_spin.valueChanged.connect(self._on_cut_height_changed)
        layout.addLayout(
            self._labeled_control("Width", self.cut_width_spin, None)
        )
        layout.addLayout(
            self._labeled_control("Height", self.cut_height_spin, None)
        )
        self.keep_square_checkbox = QCheckBox("Keep cut square")
        self.keep_square_checkbox.setChecked(True)
        self.keep_square_checkbox.toggled.connect(self._on_square_lock_changed)
        layout.addWidget(self.keep_square_checkbox)
        return self._section("GLOBAL CUT SIZE", box, HELP["cut_section"])

    def _build_detection_settings_section(self) -> QFrame:
        controls = QWidget()
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(0, 100)
        self.sensitivity_slider.setValue(65)
        self.sensitivity_value = QLabel("65")
        self.sensitivity_slider.valueChanged.connect(
            lambda value: self.sensitivity_value.setText(str(value))
        )
        layout.addLayout(
            self._labeled_control(
                "Sensitivity", self.sensitivity_slider, HELP["sensitivity"], self.sensitivity_value
            )
        )

        minimum_widget = QWidget()
        minimum_layout = QHBoxLayout(minimum_widget)
        minimum_layout.setContentsMargins(0, 0, 0, 0)
        minimum_layout.setSpacing(4)
        self.minimum_area_spin = MinimalArrowDoubleSpinBox()
        self.minimum_area_spin.setMinimumWidth(0)
        self.minimum_area_spin.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self.minimum_area_spin.setRange(1, 500_000)
        self.minimum_area_spin.setDecimals(0)
        self.minimum_area_spin.setValue(500)
        self.minimum_area_unit_combo = QComboBox()
        self.minimum_area_unit_combo.addItem("px²", "px2")
        self.minimum_area_unit_combo.addItem("in²", "physical")
        self.minimum_area_unit_combo.currentIndexChanged.connect(
            self._on_minimum_area_mode_changed
        )
        minimum_layout.addWidget(self.minimum_area_spin, 1)
        minimum_layout.addWidget(self.minimum_area_unit_combo)
        layout.addLayout(
            self._labeled_control("Minimum area", minimum_widget, HELP["minimum_area"])
        )

        self.cleanup_slider = QSlider(Qt.Orientation.Horizontal)
        self.cleanup_slider.setRange(0, 100)
        self.cleanup_slider.setValue(25)
        self.cleanup_value = QLabel("25%")
        self.cleanup_slider.valueChanged.connect(
            lambda value: self.cleanup_value.setText(f"{value}%")
        )
        layout.addLayout(
            self._labeled_control(
                "Cleanup", self.cleanup_slider, HELP["cleanup"], self.cleanup_value
            )
        )

        self.merge_distance_spin = self._physical_spin(0.35)
        layout.addLayout(
            self._labeled_control(
                "Merge distance", self.merge_distance_spin, HELP["merge"]
            )
        )
        self._register_detection_resets()
        return self._section("DETECTION SETTINGS", controls, HELP["settings_section"])

    def _build_detections_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        stats = QWidget()
        stats_layout = QGridLayout(stats)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setHorizontalSpacing(4)
        self.total_value_label = QLabel("0")
        self.valid_value_label = QLabel("0")
        self.invalid_value_label = QLabel("0")
        self.disabled_value_label = QLabel("0")
        for column, (label, value, help_text) in enumerate(
            (
                ("Total", self.total_value_label, HELP["total"]),
                ("Valid", self.valid_value_label, HELP["valid"]),
                ("Invalid", self.invalid_value_label, HELP["invalid"]),
                ("Disabled", self.disabled_value_label, HELP["disabled"]),
            )
        ):
            stats_layout.setColumnMinimumWidth(column, 0)
            stats_layout.setColumnStretch(column, 1)
            stats_layout.addWidget(self._stat_header(label, help_text), 0, column)
            value.setObjectName("statValue")
            value.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            stats_layout.addWidget(value, 1, column, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(stats)

        self.detection_list = QListWidget()
        self.detection_list.setMinimumHeight(170)
        self.detection_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.detection_list.setAlternatingRowColors(True)
        self.detection_list.currentItemChanged.connect(self._on_current_item_changed)
        self.detection_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.detection_list)
        return self._section("DETECTIONS", box, HELP["detections_section"])

    def _build_selected_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self.include_checkbox = QCheckBox("Include in export")
        self.include_checkbox.setEnabled(False)
        self.include_checkbox.toggled.connect(self._on_include_toggled)
        self.detail_label = QLabel("Select a detection to inspect its geometry.")
        self.detail_label.setObjectName("detailBlock")
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.include_checkbox)
        layout.addWidget(self.detail_label)
        return self._section("SELECTED", box, HELP["selected_section"])

    def set_machine_profiles(
        self, profiles: list[MachineProfile], selected_id: str
    ) -> None:
        blocker = QSignalBlocker(self.machine_combo)
        self.machine_combo.clear()
        selected_index = 0
        for index, profile in enumerate(profiles):
            self.machine_combo.addItem(profile.name, profile.id)
            if profile.id == selected_id:
                selected_index = index
        self.machine_combo.setCurrentIndex(selected_index)
        del blocker

    def select_machine_id(self, machine_id: str) -> None:
        blocker = QSignalBlocker(self.machine_combo)
        for index in range(self.machine_combo.count()):
            if self.machine_combo.itemData(index) == machine_id:
                self.machine_combo.setCurrentIndex(index)
                break
        del blocker

    def set_machine(self, profile: MachineProfile) -> None:
        self._machine = profile
        self._update_physical_readouts()

    def working_unit(self) -> LengthUnit:
        return self._working_unit

    def export_unit(self) -> LengthUnit:
        data = self.export_unit_combo.currentData()
        return self._working_unit if data == "same" else LengthUnit(data)

    def export_uses_override(self) -> bool:
        return self.export_unit_combo.currentData() != "same"

    def image_locked(self) -> bool:
        return self.lock_image_checkbox.isChecked()

    def set_image_locked(self, locked: bool) -> None:
        self.lock_image_checkbox.setChecked(locked)

    def set_cut_size_inches(self, width_in: float, height_in: float) -> None:
        width_blocker = QSignalBlocker(self.cut_width_spin)
        height_blocker = QSignalBlocker(self.cut_height_spin)
        self.cut_width_spin.setValue(from_inches(width_in, self._working_unit))
        self.cut_height_spin.setValue(from_inches(height_in, self._working_unit))
        del width_blocker, height_blocker

    def detector_settings(self, mapper: CoordinateMapper) -> DetectorSettings:
        if self._minimum_area_mode == "px2":
            minimum_area_px = max(1, int(round(self.minimum_area_spin.value())))
        else:
            area_in2 = area_to_square_inches(
                self.minimum_area_spin.value(), self._working_unit
            )
            minimum_area_px = max(
                1,
                int(round(area_in2 * mapper.px_per_inch_x * mapper.px_per_inch_y)),
            )
        merge_in = to_inches(self.merge_distance_spin.value(), self._working_unit)
        return DetectorSettings(
            sensitivity=self.sensitivity_slider.value(),
            minimum_area_px=minimum_area_px,
            morphological_cleanup=self.cleanup_slider.value() / 100.0,
            merge_distance_px_x=merge_in * mapper.px_per_inch_x,
            merge_distance_px_y=merge_in * mapper.px_per_inch_y,
        )

    def set_image_info(self, mapper: CoordinateMapper | None) -> None:
        self._mapper = mapper
        if mapper is None:
            self.image_value_label.setText("No image loaded")
            self.scale_value_label.setText("Load an image to calculate scale")
        else:
            self.image_value_label.setText(
                f"{mapper.image_width_px} × {mapper.image_height_px} px"
            )
            scale_x, scale_y = mapper.pixels_per_unit(self._working_unit)
            unit_name = self._working_unit.singular_name
            self.scale_value_label.setText(
                f"Horizontal: {scale_x:.3f} px / {unit_name}\n"
                f"Vertical:   {scale_y:.3f} px / {unit_name}"
            )
        self.lock_image_checkbox.setEnabled(mapper is not None)
        self._update_physical_readouts()

    def set_detections(
        self, detections: list[Detection], selected_id: int | None
    ) -> None:
        self._detections = detections
        self._selected_id = selected_id
        blocker = QSignalBlocker(self.detection_list)
        self.detection_list.clear()
        selected_item: QListWidgetItem | None = None
        for detection in detections:
            if not detection.enabled:
                state = "DISABLED"
            elif detection.overlaps_cut:
                state = "COLLISION"
            elif not detection.valid_cut:
                state = "OUTSIDE"
            else:
                state = "VALID"
            source = "manual" if detection.manual else f"{detection.score:.0%}"
            item = QListWidgetItem(f"#{detection.id:02d}   {state:<9}   {source}")
            item.setData(Qt.ItemDataRole.UserRole, detection.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if detection.enabled else Qt.CheckState.Unchecked
            )
            if detection.overlaps_cut and detection.enabled:
                item.setForeground(QColor("#ff8a3d"))
            elif not detection.valid_cut and detection.enabled:
                item.setForeground(Qt.GlobalColor.red)
            self.detection_list.addItem(item)
            if detection.id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.detection_list.setCurrentItem(selected_item)
        del blocker
        disabled = sum(1 for item in detections if not item.enabled)
        valid = sum(1 for item in detections if item.exportable)
        invalid = sum(
            1
            for item in detections
            if item.enabled and (not item.valid_cut or item.overlaps_cut)
        )
        self.total_value_label.setText(str(len(detections)))
        self.valid_value_label.setText(str(valid))
        self.invalid_value_label.setText(str(invalid))
        self.disabled_value_label.setText(str(disabled))
        self._update_details()

    def set_selected_id(self, detection_id: int | None) -> None:
        self._selected_id = detection_id
        blocker = QSignalBlocker(self.detection_list)
        for index in range(self.detection_list.count()):
            item = self.detection_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == detection_id:
                self.detection_list.setCurrentItem(item)
                break
        else:
            self.detection_list.setCurrentRow(-1)
        del blocker
        self._update_details()

    def set_verification_result(self, error_x_px: float, error_y_px: float) -> None:
        self.verification_label.setText(
            "Maximum round-trip error:\n"
            f"X  {error_x_px:.12f} px / Y  {error_y_px:.12f} px"
        )

    def refresh_unit_display(self) -> None:
        self._update_physical_readouts()
        self.set_image_info(self._mapper)
        self._update_details()

    def _update_physical_readouts(self) -> None:
        if self._machine is None:
            return
        width = from_inches(self._machine.bed_width_in, self._working_unit)
        height = from_inches(self._machine.bed_height_in, self._working_unit)
        text = f"{width:.3f} × {height:.3f} {self._working_unit.value}"
        self.work_area_value_label.setText(text)
        self.bed_value_label.setText(text)

    def _update_details(self) -> None:
        detection = next(
            (item for item in self._detections if item.id == self._selected_id), None
        )
        blocker = QSignalBlocker(self.include_checkbox)
        if detection is None:
            self.include_checkbox.setChecked(False)
            self.include_checkbox.setEnabled(False)
            self.detail_label.setText("Select a detection to inspect its geometry.")
            del blocker
            return
        self.include_checkbox.setEnabled(True)
        self.include_checkbox.setChecked(detection.enabled)
        square = detection.square_inches
        unit = self._working_unit
        center_x = from_inches(detection.center_inches[0], unit)
        center_y = from_inches(detection.center_inches[1], unit)
        x = from_inches(square.x, unit)
        y = from_inches(square.y, unit)
        width = from_inches(square.width, unit)
        height = from_inches(square.height, unit)
        if not detection.enabled:
            status = "Disabled - excluded from export"
        elif detection.overlaps_cut:
            status = "Collision - touches another enabled cut; not exported"
        elif not detection.valid_cut:
            status = "Outside bed - not exported"
        else:
            status = "Valid"
        self.detail_label.setText(
            f"Detection #{detection.id:02d}\n\n"
            "PIXELS\n"
            f"center X:  {detection.center_px[0]:.3f}\n"
            f"center Y:  {detection.center_px[1]:.3f}\n\n"
            f"PHYSICAL POSITION ({unit.value})\n"
            f"center X:  {center_x:.3f} {unit.value}\n"
            f"center Y:  {center_y:.3f} {unit.value}\n\n"
            f"CUT ({unit.value})\n"
            f"x:       {x:.3f}\n"
            f"y:       {y:.3f}\n"
            f"width:   {width:.3f}\n"
            f"height:  {height:.3f}\n\n"
            f"STATUS\n{status}"
        )
        del blocker

    def _on_machine_changed(self) -> None:
        machine_id = self.machine_combo.currentData()
        if machine_id:
            self.machine_changed.emit(str(machine_id))

    def _on_working_unit_changed(self) -> None:
        data = self.working_unit_combo.currentData()
        if not data:
            return
        new_unit = LengthUnit(data)
        old_unit = self._working_unit
        if new_unit == old_unit:
            return
        controls = (
            self.cut_width_spin,
            self.cut_height_spin,
            self.merge_distance_spin,
        )
        converted = [convert_length(control.value(), old_unit, new_unit) for control in controls]
        blockers = [QSignalBlocker(control) for control in controls]
        for control, value in zip(controls, converted):
            control.setValue(value)
            control.setSuffix(f" {new_unit.value}")
        if self._minimum_area_mode == "physical":
            area_blocker = QSignalBlocker(self.minimum_area_spin)
            self.minimum_area_spin.setValue(
                convert_area(self.minimum_area_spin.value(), old_unit, new_unit)
            )
            del area_blocker
        self.minimum_area_unit_combo.setItemText(1, new_unit.area_suffix)
        self._working_unit = new_unit
        del blockers
        self.refresh_unit_display()
        self.working_unit_changed.emit(new_unit.value)

    def _on_minimum_area_mode_changed(self) -> None:
        new_mode = str(self.minimum_area_unit_combo.currentData())
        if new_mode == self._minimum_area_mode:
            return
        current = self.minimum_area_spin.value()
        if self._mapper is not None:
            pixels_per_in2 = self._mapper.px_per_inch_x * self._mapper.px_per_inch_y
            if new_mode == "physical":
                current = area_from_square_inches(current / pixels_per_in2, self._working_unit)
            else:
                current = area_to_square_inches(current, self._working_unit) * pixels_per_in2
        else:
            current = 0.5 if new_mode == "physical" else 500.0
        blocker = QSignalBlocker(self.minimum_area_spin)
        if new_mode == "physical":
            self.minimum_area_spin.setDecimals(4)
            self.minimum_area_spin.setRange(0.0001, 100_000.0)
        else:
            self.minimum_area_spin.setDecimals(0)
            self.minimum_area_spin.setRange(1.0, 500_000.0)
        self.minimum_area_spin.setValue(current)
        del blocker
        self._minimum_area_mode = new_mode

    def _on_cut_width_changed(self, value: float) -> None:
        if self._syncing_cut_size:
            return
        if self.keep_square_checkbox.isChecked():
            self._syncing_cut_size = True
            blocker = QSignalBlocker(self.cut_height_spin)
            self.cut_height_spin.setValue(value)
            del blocker
            self._syncing_cut_size = False
        self._emit_cut_size()

    def _on_cut_height_changed(self, value: float) -> None:
        if self._syncing_cut_size:
            return
        if self.keep_square_checkbox.isChecked():
            self._syncing_cut_size = True
            blocker = QSignalBlocker(self.cut_width_spin)
            self.cut_width_spin.setValue(value)
            del blocker
            self._syncing_cut_size = False
        self._emit_cut_size()

    def _on_square_lock_changed(self, locked: bool) -> None:
        if locked:
            blocker = QSignalBlocker(self.cut_height_spin)
            self.cut_height_spin.setValue(self.cut_width_spin.value())
            del blocker
        self._emit_cut_size()

    def _emit_cut_size(self) -> None:
        self.cut_size_changed.emit(
            to_inches(self.cut_width_spin.value(), self._working_unit),
            to_inches(self.cut_height_spin.value(), self._working_unit),
        )

    def _register_detection_resets(self) -> None:
        self._register_double_click_reset(
            self.sensitivity_slider, lambda: self.sensitivity_slider.setValue(65)
        )
        self._register_double_click_reset(
            self.cleanup_slider, lambda: self.cleanup_slider.setValue(25)
        )
        self._register_double_click_reset(
            self.merge_distance_spin,
            lambda: self.merge_distance_spin.setValue(
                from_inches(0.35, self._working_unit)
            ),
        )
        self._register_double_click_reset(
            self.minimum_area_spin, self._reset_minimum_area
        )
        self._register_double_click_reset(
            self.minimum_area_unit_combo, self._reset_minimum_area
        )

    def _register_double_click_reset(self, widget: QWidget, callback) -> None:
        widget.installEventFilter(self)
        self._double_click_resets[widget] = callback
        if isinstance(widget, QDoubleSpinBox) and widget.lineEdit() is not None:
            widget.lineEdit().installEventFilter(self)
            self._double_click_resets[widget.lineEdit()] = callback

    def _reset_minimum_area(self) -> None:
        self.minimum_area_unit_combo.setCurrentIndex(0)
        self.minimum_area_spin.setValue(500.0)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonDblClick:
            callback = self._double_click_resets.get(watched)
            if callback is not None:
                callback()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _on_current_item_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        del previous
        if current is None:
            return
        detection_id = int(current.data(Qt.ItemDataRole.UserRole))
        self._selected_id = detection_id
        self._update_details()
        self.detection_selected.emit(detection_id)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        self.enabled_changed.emit(
            int(item.data(Qt.ItemDataRole.UserRole)),
            item.checkState() == Qt.CheckState.Checked,
        )

    def _on_include_toggled(self, enabled: bool) -> None:
        if self._selected_id is not None:
            self.enabled_changed.emit(self._selected_id, enabled)

    @staticmethod
    def _physical_spin(value: float) -> QDoubleSpinBox:
        spin = MinimalArrowDoubleSpinBox()
        spin.setMinimumWidth(0)
        spin.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        spin.setRange(0.001, 100_000.0)
        spin.setDecimals(3)
        spin.setValue(value)
        spin.setSuffix(" in")
        spin.setKeyboardTracking(False)
        return spin

    @staticmethod
    def _section(title: str, content: QWidget, help_text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panelSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(7)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        title_layout.addWidget(label)
        title_layout.addWidget(InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop)
        title_layout.addStretch(1)
        layout.addLayout(title_layout)
        layout.addWidget(content)
        return frame

    @staticmethod
    def _labeled_control(
        label_text: str,
        control: QWidget,
        help_text: str | None,
        value_label: QLabel | None = None,
    ) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label_group = QWidget()
        label_group.setFixedWidth(113)
        label_layout = QHBoxLayout(label_group)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(5)
        label_layout.addWidget(QLabel(label_text))
        if help_text:
            label_layout.addWidget(
                InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop
            )
        label_layout.addStretch(1)
        layout.addWidget(label_group)
        control.setMinimumWidth(0)
        control_policy = control.sizePolicy()
        control_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        control.setSizePolicy(control_policy)
        layout.addWidget(control, 1)
        if value_label is not None:
            value_label.setMinimumWidth(30)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(value_label)
        return layout

    @staticmethod
    def _readout_row(label_text: str, value: QLabel, help_text: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = QLabel(label_text)
        layout.addWidget(label)
        layout.addWidget(InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        value.setObjectName("infoBlock")
        layout.addWidget(value)
        return layout

    @staticmethod
    def _checkbox_help_row(checkbox: QCheckBox, help_text: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(checkbox)
        layout.addWidget(InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        return layout

    @staticmethod
    def _parameter_readout(
        label_text: str, value_label: QLabel, help_text: str
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(5)
        label = QLabel(label_text)
        label.setObjectName("parameterTitle")
        header.addWidget(label)
        header.addWidget(InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop)
        header.addStretch(1)
        value_label.setObjectName("infoBlock")
        layout.addLayout(header)
        layout.addWidget(value_label)
        return widget

    @staticmethod
    def _stat_header(label_text: str, help_text: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addStretch(1)
        label = QLabel(label_text)
        label.setObjectName("statTitle")
        layout.addWidget(label)
        layout.addWidget(InfoButton(help_text), 0, Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)
        return widget
