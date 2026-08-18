"""Controls, machine setup, detection list, and physical geometry inspection."""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QObject,
    QPointF,
    QSignalBlocker,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
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
    QAbstractItemView,
    QSlider,
    QSpinBox,
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
    "settings_section": "Technical detection overrides. Normal grid correction and cut review do not require changing these values.",
    "layout": "This choice applies only when improving an existing free detection. Automatic estimates repeated panels, Use a panel grid lets you enter boundaries, and No grid keeps a free composition.",
    "result_style": "Clean result favours fewer false detections on busy fabric. Balanced works for most images. Find faint figures accepts subtler differences and may need more review.",
    "join_parts": "Keeps nearby detached pieces of the same figure together, such as an antenna, branch, or separate appliqué detail.",
    "grid": "Panel guides are independent from detector settings. Show or hide them, unlock them for dragging, or enter rows and columns. Changes preserve the current result until you explicitly detect again.",
    "sensitivity": "Controls how different a region must be from the estimated local fabric background. Low values keep only strong visual differences, reducing noise but possibly missing faint motifs. High values include subtler differences, detecting pale motifs but also more fabric texture, shadows, and noise.",
    "minimum_area": "Rejects detected groups smaller than this area. Low values retain small motifs and fragments, but may also keep specks and texture. High values suppress more noise, but may discard small or faint motifs. Use image pixels squared or the current physical working unit squared; physical values are converted automatically from the loaded image scale.",
    "cleanup": "Controls the strength of OpenCV noise removal and gap closing; it is dimensionless, not a physical measurement. Low values preserve fine details and separate fragments, but leave more specks and gaps. High values remove noise and close gaps more aggressively, but may erase thin details or join nearby shapes.",
    "merge": "Sets the maximum physical gap for grouping nearby printed fragments into one motif, such as a bird and branch or a mushroom cap and stem. Low values keep groups separate and may split one motif into several detections. High values join fragments farther apart, but may combine neighboring motifs.",
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
    detection_selection_changed = Signal(object)
    enabled_changed = Signal(int, bool)
    machine_changed = Signal(str)
    add_machine_requested = Signal()
    working_unit_changed = Signal(str)
    cut_size_changed = Signal(float, float)
    image_lock_changed = Signal(bool)
    grid_dimensions_changed = Signal(int, int)
    grid_action_requested = Signal(str)
    grid_edit_toggled = Signal(bool)
    grid_visibility_changed = Signal(bool)
    layout_mode_changed = Signal(str)
    grid_confirmation_requested = Signal()
    advanced_visibility_changed = Signal(bool)
    detection_settings_changed = Signal()
    detection_confirmation_requested = Signal()
    grid_review_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._detections: list[Detection] = []
        self._selected_id: int | None = None
        self._selected_ids: set[int] = set()
        self._mapper: CoordinateMapper | None = None
        self._machine: MachineProfile | None = None
        self._working_unit = LengthUnit.INCHES
        self._minimum_area_mode = "px2"
        self._syncing_cut_size = False
        self._grid_available = False
        self._double_click_resets: dict[QObject, object] = {}
        # Long cut states such as "TOO SMALL" must never resize the
        # inspector or push numerical step buttons outside the viewport.
        self.setFixedWidth(360)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("sidePanelScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root_layout.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("sidePanelContent")
        content.setMinimumWidth(0)
        content.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.context_title = QLabel("1  PREPARE THE JOB")
        self.context_title.setObjectName("contextTitle")
        self.context_hint = QLabel(
            "Choose the machine, load the bed image, and confirm its divisions."
        )
        self.context_hint.setObjectName("contextHint")
        self.context_hint.setWordWrap(True)
        layout.addWidget(self.context_title)
        layout.addWidget(self.context_hint)

        self.machine_section = self._build_machine_section()
        self.bed_image_section = self._build_bed_image_section()
        self.cut_section = self._build_cut_section()
        self.grid_section = self._build_grid_section()
        self.advanced_toggle = QPushButton("Show advanced detection settings")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setObjectName("advancedToggle")
        self.advanced_toggle.toggled.connect(self._toggle_advanced_settings)
        self.advanced_section = self._build_advanced_detection_settings_section()
        self.detections_section = self._build_detections_section()
        self.selected_section = self._build_selected_section()
        self.detection_review = self._build_detection_review()
        self.review_actions = QWidget()
        self.review_actions.setObjectName("reviewActions")
        self.review_actions_layout = QVBoxLayout(self.review_actions)
        self.review_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.review_actions_layout.setSpacing(6)

        for widget in (
            self.machine_section,
            self.bed_image_section,
            self.cut_section,
            self.grid_section,
            self.advanced_toggle,
            self.advanced_section,
            self.detection_review,
            self.review_actions,
            self.detections_section,
            self.selected_section,
        ):
            layout.addWidget(widget)

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
        self.export_options = QWidget()
        export_options_layout = QVBoxLayout(self.export_options)
        export_options_layout.setContentsMargins(0, 0, 0, 0)
        export_options_layout.setSpacing(8)
        export_options_layout.addWidget(export_row)

        self.debug_json_checkbox = QCheckBox("Write debug JSON beside SVG")
        self.debug_json_checkbox.setChecked(False)
        self.debug_json_checkbox.setVisible(False)
        export_options_layout.addWidget(self.debug_json_checkbox)

        self.verification_label = QLabel("Round-trip verification not run")
        self.verification_label.setObjectName("verificationLabel")
        self.verification_label.setWordWrap(True)
        export_options_layout.addWidget(self.verification_label)
        layout.addWidget(self.export_options)
        # Keep contextual controls packed at the top. Without this terminal
        # stretch, Qt distributes spare viewport height between labels and
        # creates large, misleading gaps when most phase sections are hidden.
        layout.addStretch(1)
        self.scroll.setWidget(content)
        self.set_phase("setup")

    def _build_detection_review(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self.detection_review_hint = QLabel(
            "Run detection, then compare every result with the image."
        )
        self.detection_review_hint.setWordWrap(True)
        layout.addWidget(self.detection_review_hint)
        self.confirm_detection_button = QPushButton(
            "Detection is correct — continue"
        )
        self.confirm_detection_button.setObjectName("primaryPanelAction")
        self.confirm_detection_button.setEnabled(False)
        self.confirm_detection_button.clicked.connect(
            self.detection_confirmation_requested
        )
        layout.addWidget(self.confirm_detection_button)
        self.review_grid_button = QPushButton("Improve with panel grid")
        self.review_grid_button.setEnabled(False)
        self.review_grid_button.clicked.connect(self.grid_review_requested)
        layout.addWidget(self.review_grid_button)
        return self._section(
            "CHECK THE DETECTION",
            box,
            "Confirm only after every intended figure has one cut area. Use a panel grid when the free detection misses or merges figures.",
        )

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

    def _build_grid_section(self) -> QFrame:
        controls = QWidget()
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem("Automatic", "auto")
        self.layout_mode_combo.addItem("Use a panel grid", "panels")
        self.layout_mode_combo.addItem("No grid", "free")
        self.layout_mode_combo.currentIndexChanged.connect(
            self._on_layout_mode_changed
        )
        layout.addLayout(
            self._labeled_control(
                "Grid source", self.layout_mode_combo, HELP["layout"]
            )
        )

        self.grid_controls = QWidget()
        grid_layout = QVBoxLayout(self.grid_controls)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)
        self.grid_status_label = QLabel("No panel grid detected")
        self.grid_status_label.setWordWrap(True)
        self.grid_status_label.setObjectName("infoBlock")
        grid_layout.addWidget(self.grid_status_label)

        visibility_row = QWidget()
        visibility_layout = QHBoxLayout(visibility_row)
        visibility_layout.setContentsMargins(0, 0, 0, 0)
        self.show_grid_checkbox = QCheckBox("Show grid")
        self.show_grid_checkbox.setChecked(True)
        self.show_grid_checkbox.setEnabled(False)
        self.show_grid_checkbox.toggled.connect(self._on_grid_visibility_toggled)
        self.edit_grid_checkbox = QCheckBox("Edit grid lines")
        self.edit_grid_checkbox.setEnabled(False)
        self.edit_grid_checkbox.toggled.connect(self._on_grid_edit_toggled)
        visibility_layout.addWidget(self.show_grid_checkbox)
        visibility_layout.addWidget(self.edit_grid_checkbox)
        visibility_layout.addStretch(1)
        grid_layout.addWidget(visibility_row)

        dimensions = QWidget()
        dimensions_layout = QGridLayout(dimensions)
        dimensions_layout.setContentsMargins(0, 0, 0, 0)
        dimensions_layout.setHorizontalSpacing(6)
        self.grid_columns_spin = QSpinBox()
        self.grid_columns_spin.setRange(2, 24)
        self.grid_columns_spin.setValue(2)
        self.grid_rows_spin = QSpinBox()
        self.grid_rows_spin.setRange(2, 24)
        self.grid_rows_spin.setValue(2)
        dimensions_layout.addWidget(QLabel("Columns"), 0, 0)
        dimensions_layout.addWidget(self.grid_columns_spin, 0, 1)
        dimensions_layout.addWidget(QLabel("Rows"), 0, 2)
        dimensions_layout.addWidget(self.grid_rows_spin, 0, 3)
        grid_layout.addWidget(dimensions)

        self.grid_columns_spin.valueChanged.connect(self._emit_grid_dimensions)
        self.grid_rows_spin.valueChanged.connect(self._emit_grid_dimensions)
        immediate_hint = QLabel("Rows and columns update immediately")
        immediate_hint.setObjectName("mutedHint")
        grid_layout.addWidget(immediate_hint)

        self.grid_spacing_controls = QWidget()
        distribute_layout = QHBoxLayout(self.grid_spacing_controls)
        distribute_layout.setContentsMargins(0, 0, 0, 0)
        distribute_layout.setSpacing(5)
        self.distribute_columns_button = QPushButton("Space columns evenly")
        self.distribute_rows_button = QPushButton("Space rows evenly")
        self.distribute_columns_button.setEnabled(False)
        self.distribute_rows_button.setEnabled(False)
        self.distribute_columns_button.setToolTip(
            "Space all vertical lines evenly between the left and right boundaries."
        )
        self.distribute_rows_button.setToolTip(
            "Space all horizontal lines evenly between the top and bottom boundaries."
        )
        self.distribute_columns_button.clicked.connect(
            lambda: self.grid_action_requested.emit("distribute_columns")
        )
        self.distribute_rows_button.clicked.connect(
            lambda: self.grid_action_requested.emit("distribute_rows")
        )
        distribute_layout.addWidget(self.distribute_columns_button)
        distribute_layout.addWidget(self.distribute_rows_button)
        self.grid_spacing_controls.setVisible(False)
        grid_layout.addWidget(self.grid_spacing_controls)

        self.redetect_grid_button = QPushButton("Restore automatic grid")
        self.redetect_grid_button.clicked.connect(
            lambda: self.grid_action_requested.emit("redetect")
        )
        grid_layout.addWidget(self.redetect_grid_button)
        self.confirm_grid_button = QPushButton("Confirm: divisions are correct")
        self.confirm_grid_button.setObjectName("primaryPanelAction")
        self.confirm_grid_button.setEnabled(False)
        self.confirm_grid_button.clicked.connect(self.grid_confirmation_requested)
        grid_layout.addWidget(self.confirm_grid_button)
        layout.addWidget(self.grid_controls)
        self.grid_section = self._section("PANEL GRID", controls, HELP["grid"])
        self.grid_section.setObjectName("panelGridSection")
        self.grid_section.setProperty("workflowActive", False)
        return self.grid_section

    def add_review_action(self, widget: QWidget) -> None:
        """Place a review command in the contextual review phase."""
        self.review_actions_layout.addWidget(widget)

    def set_phase(self, phase: str) -> None:
        """Expose only controls that belong to the current user goal."""
        phase = phase if phase in {"setup", "grid", "detect", "review", "export"} else "setup"
        titles = {
            "setup": (
                "1  PREPARE THE IMAGE",
                "Choose the machine, units, image placement, and cut size.",
            ),
            "grid": (
                "2  IMPROVE WITH A GRID",
                "Adjust panel boundaries, then detect again and check the new result.",
            ),
            "detect": (
                "2  DETECT AND CHECK",
                "Run detection, inspect every result, and continue only when it is correct.",
            ),
            "review": (
                "3  REVIEW CUTS",
                "Correct missing, false, clipped, or overlapping cut areas.",
            ),
            "export": (
                "4–5  CHECK AND EXPORT",
                "Confirm exactly what will be saved before creating the SVG.",
            ),
        }
        title, hint = titles[phase]
        self.context_title.setText(title)
        self.context_hint.setText(hint)
        visibility = {
            "setup": {"machine", "bed", "cut"},
            "grid": {"bed", "grid"},
            "detect": {"cut", "advanced", "detection_review", "detections"},
            "review": {"cut", "detections", "selected", "actions"},
            "export": {"detections", "export"},
        }[phase]
        self.machine_section.setVisible("machine" in visibility)
        self.bed_image_section.setVisible("bed" in visibility)
        self.cut_section.setVisible("cut" in visibility)
        self.grid_section.setVisible("grid" in visibility)
        self.advanced_toggle.setVisible("advanced" in visibility)
        self.advanced_section.setVisible(
            "advanced" in visibility and self.advanced_toggle.isChecked()
        )
        self.detection_review.setVisible("detection_review" in visibility)
        self.detections_section.setVisible("detections" in visibility)
        self.selected_section.setVisible("selected" in visibility)
        self.review_actions.setVisible("actions" in visibility)
        self.export_options.setVisible("export" in visibility)
        self.scroll.verticalScrollBar().setValue(0)

    def set_detection_review_state(
        self, has_detections: bool, confirmed: bool
    ) -> None:
        self.confirm_detection_button.setEnabled(has_detections and not confirmed)
        self.review_grid_button.setEnabled(has_detections and not confirmed)
        if confirmed:
            self.detection_review_hint.setText(
                "✓ Detection confirmed. Review the cut areas next."
            )
            self.confirm_detection_button.setText("✓ Detection confirmed")
        elif has_detections:
            self.detection_review_hint.setText(
                "Compare every cut area with the image. Are all intended figures detected exactly once?"
            )
            self.confirm_detection_button.setText(
                "Detection is correct — continue"
            )
        else:
            self.detection_review_hint.setText(
                "Run detection, then compare every result with the image."
            )
            self.confirm_detection_button.setText(
                "Detection is correct — continue"
            )

    def set_grid_confirmation_state(
        self, enabled: bool, confirmed: bool, has_grid: bool
    ) -> None:
        self.confirm_grid_button.setEnabled(enabled)
        if confirmed:
            self.confirm_grid_button.setText(
                "✓ Divisions confirmed" if has_grid else "✓ No grid confirmed"
            )
        else:
            self.confirm_grid_button.setText(
                "Use this grid and detect again"
                if has_grid
                else "Detect again without a grid"
            )

    def _toggle_advanced_settings(self, visible: bool) -> None:
        self.advanced_toggle.setText(
            "Hide advanced detection settings"
            if visible
            else "Show advanced detection settings"
        )
        self.advanced_section.setVisible(visible and self.advanced_toggle.isVisible())
        self.advanced_visibility_changed.emit(visible)

    def _build_advanced_detection_settings_section(self) -> QFrame:
        self.advanced_detection_controls = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_detection_controls)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(6)

        self.join_parts_checkbox = QCheckBox("Join separated parts of one figure")
        self.join_parts_checkbox.setChecked(True)
        self.join_parts_checkbox.setToolTip(HELP["join_parts"])
        self.join_parts_checkbox.toggled.connect(self.detection_settings_changed)
        advanced_layout.addWidget(self.join_parts_checkbox)

        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(0, 100)
        self.sensitivity_slider.setValue(65)
        self.sensitivity_value = QLabel("65")
        self.sensitivity_slider.valueChanged.connect(
            lambda value: self.sensitivity_value.setText(str(value))
        )
        self.sensitivity_slider.valueChanged.connect(
            lambda _value: self.detection_settings_changed.emit()
        )
        advanced_layout.addLayout(
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
        self.minimum_area_spin.valueChanged.connect(
            lambda _value: self.detection_settings_changed.emit()
        )
        self.minimum_area_unit_combo.currentIndexChanged.connect(
            lambda _index: self.detection_settings_changed.emit()
        )
        minimum_layout.addWidget(self.minimum_area_spin, 1)
        minimum_layout.addWidget(self.minimum_area_unit_combo)
        advanced_layout.addLayout(
            self._labeled_control("Minimum area", minimum_widget, HELP["minimum_area"])
        )

        self.cleanup_slider = QSlider(Qt.Orientation.Horizontal)
        self.cleanup_slider.setRange(0, 100)
        self.cleanup_slider.setValue(25)
        self.cleanup_value = QLabel("25%")
        self.cleanup_slider.valueChanged.connect(
            lambda value: self.cleanup_value.setText(f"{value}%")
        )
        self.cleanup_slider.valueChanged.connect(
            lambda _value: self.detection_settings_changed.emit()
        )
        advanced_layout.addLayout(
            self._labeled_control(
                "Cleanup", self.cleanup_slider, HELP["cleanup"], self.cleanup_value
            )
        )

        self.merge_distance_spin = self._physical_spin(0.35)
        self.merge_distance_spin.valueChanged.connect(
            lambda _value: self.detection_settings_changed.emit()
        )
        advanced_layout.addLayout(
            self._labeled_control(
                "Merge distance", self.merge_distance_spin, HELP["merge"]
            )
        )
        self._register_detection_resets()
        return self._section(
            "ADVANCED DETECTION SETTINGS",
            self.advanced_detection_controls,
            HELP["settings_section"],
        )

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
                ("Ready", self.valid_value_label, HELP["valid"]),
                ("Problems", self.invalid_value_label, HELP["invalid"]),
                ("Excluded", self.disabled_value_label, HELP["disabled"]),
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
        self.detection_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.detection_list.setMinimumHeight(170)
        self.detection_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.detection_list.setAlternatingRowColors(True)
        self.detection_list.itemSelectionChanged.connect(
            self._on_detection_selection_changed
        )
        self.detection_list.itemChanged.connect(self._on_item_changed)
        self.detection_list.viewport().installEventFilter(self)
        layout.addWidget(self.detection_list)
        return self._section("CUT AREAS", box, HELP["detections_section"])

    def _build_selected_section(self) -> QFrame:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self.include_checkbox = QCheckBox("Include in SVG")
        self.include_checkbox.setEnabled(False)
        self.include_checkbox.toggled.connect(self._on_include_toggled)
        self.detail_label = QLabel("Select a cut area to inspect it.")
        self.detail_label.setObjectName("detailBlock")
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.include_checkbox)
        layout.addWidget(self.detail_label)
        return self._section("SELECTED CUT", box, HELP["selected_section"])

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
        if not self.join_parts_checkbox.isChecked():
            merge_in = 0.0
        return DetectorSettings(
            sensitivity=self.sensitivity_slider.value(),
            minimum_area_px=minimum_area_px,
            morphological_cleanup=self.cleanup_slider.value() / 100.0,
            merge_distance_px_x=merge_in * mapper.px_per_inch_x,
            merge_distance_px_y=merge_in * mapper.px_per_inch_y,
            layout_mode=str(self.layout_mode_combo.currentData() or "auto"),
        )

    def set_grid_info(
        self,
        columns: int | None,
        rows: int | None,
        confidence: float = 0.0,
        source: str = "automatic",
        figure_count: int | None = None,
    ) -> None:
        available = columns is not None and rows is not None
        forced_panels = self.layout_mode_combo.currentData() == "panels"
        self.show_grid_checkbox.setEnabled(available)
        self.edit_grid_checkbox.setEnabled(available)
        edit_enabled = available and self.edit_grid_checkbox.isChecked()
        self.distribute_columns_button.setEnabled(edit_enabled)
        self.distribute_rows_button.setEnabled(edit_enabled)
        self.grid_spacing_controls.setVisible(edit_enabled)
        self.redetect_grid_button.setEnabled(available)
        if not available:
            self.grid_status_label.setText(
                "Enter rows and columns to create the panel grid"
                if forced_panels
                else "No panel grid detected"
            )
            blocker = QSignalBlocker(self.edit_grid_checkbox)
            self.edit_grid_checkbox.setChecked(False)
            del blocker
            show_blocker = QSignalBlocker(self.show_grid_checkbox)
            self.show_grid_checkbox.setChecked(False)
            del show_blocker
            self._grid_available = False
            return
        if not self._grid_available:
            show_blocker = QSignalBlocker(self.show_grid_checkbox)
            self.show_grid_checkbox.setChecked(True)
            del show_blocker
            self.grid_visibility_changed.emit(True)
        self._grid_available = True
        column_blocker = QSignalBlocker(self.grid_columns_spin)
        row_blocker = QSignalBlocker(self.grid_rows_spin)
        self.grid_columns_spin.setValue(int(columns))
        self.grid_rows_spin.setValue(int(rows))
        del column_blocker, row_blocker
        if source == "automatic":
            status = (
                f"Detected {columns} columns × {rows} rows · "
                f"{confidence:.0%} confidence"
            )
        else:
            status = f"Manual grid · {columns} columns × {rows} rows"
        if figure_count is not None:
            total = int(columns) * int(rows)
            review = max(0, total - figure_count)
            status += f"\n{figure_count} figures · {review} cells need review"
        self.grid_status_label.setText(status)

    def _on_layout_mode_changed(self) -> None:
        mode = str(self.layout_mode_combo.currentData() or "auto")
        if mode == "panels":
            if self.grid_status_label.text() == "No panel grid detected":
                self.grid_status_label.setText(
                    "Enter rows and columns to create the panel grid"
                )
        elif mode == "free":
            self.show_grid_checkbox.setChecked(False)
            self.edit_grid_checkbox.setChecked(False)
        self.layout_mode_changed.emit(mode)

    def _emit_grid_dimensions(self) -> None:
        self.grid_dimensions_changed.emit(
            self.grid_columns_spin.value(), self.grid_rows_spin.value()
        )

    def _on_grid_edit_toggled(self, active: bool) -> None:
        if active and not self.show_grid_checkbox.isChecked():
            self.show_grid_checkbox.setChecked(True)
        self.distribute_columns_button.setEnabled(active)
        self.distribute_rows_button.setEnabled(active)
        self.grid_spacing_controls.setVisible(active)
        self.grid_edit_toggled.emit(active)

    def _on_grid_visibility_toggled(self, visible: bool) -> None:
        if not visible and self.edit_grid_checkbox.isChecked():
            self.edit_grid_checkbox.setChecked(False)
        self.grid_visibility_changed.emit(visible)

    def set_grid_workflow_active(self, active: bool) -> None:
        """Highlight and reveal the controls belonging to the grid step."""
        active = bool(active)
        if self.grid_section.property("workflowActive") != active:
            self.grid_section.setProperty("workflowActive", active)
            self.grid_section.style().unpolish(self.grid_section)
            self.grid_section.style().polish(self.grid_section)
            self.grid_section.update()
        if active:
            self.scroll.ensureWidgetVisible(self.grid_section, 12, 24)

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
        self,
        detections: list[Detection],
        selected_ids: set[int] | int | None,
        primary_id: int | None = None,
    ) -> None:
        self._detections = detections
        if isinstance(selected_ids, int):
            selected_ids = {selected_ids}
        self._selected_ids = set(selected_ids or set())
        self._selected_id = (
            primary_id
            if primary_id in self._selected_ids
            else next(iter(self._selected_ids), None)
        )
        blocker = QSignalBlocker(self.detection_list)
        self.detection_list.clear()
        primary_item: QListWidgetItem | None = None
        for detection in detections:
            if not detection.enabled:
                state = "EXCLUDED"
            elif detection.overlaps_cut:
                state = "OVERLAP"
            elif not detection.valid_cut:
                state = (
                    "TOO SMALL"
                    if self._mapper is not None
                    and not detection.contains_artwork(self._mapper)
                    else "OUTSIDE"
                )
            else:
                state = "READY"
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
            if detection.id in self._selected_ids:
                item.setSelected(True)
            if detection.id == self._selected_id:
                primary_item = item
        if primary_item is not None:
            self.detection_list.setCurrentItem(
                primary_item, QItemSelectionModel.SelectionFlag.NoUpdate
            )
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
        self.set_selected_ids(
            {detection_id} if detection_id is not None else set(), detection_id
        )

    def set_selected_ids(
        self, detection_ids: set[int], primary_id: int | None = None
    ) -> None:
        self._selected_ids = set(detection_ids)
        self._selected_id = (
            primary_id
            if primary_id in self._selected_ids
            else next(iter(self._selected_ids), None)
        )
        blocker = QSignalBlocker(self.detection_list)
        for index in range(self.detection_list.count()):
            item = self.detection_list.item(index)
            item.setSelected(
                int(item.data(Qt.ItemDataRole.UserRole)) in self._selected_ids
            )
            if item.data(Qt.ItemDataRole.UserRole) == self._selected_id:
                self.detection_list.setCurrentItem(
                    item, QItemSelectionModel.SelectionFlag.NoUpdate
                )
        if not self._selected_ids:
            # Clearing only the current row can leave its selection bit set in
            # ExtendedSelection mode. Clear both states so canvas and list
            # cannot disagree after a toggle-off or a fresh detection pass.
            self.detection_list.clearSelection()
            self.detection_list.setCurrentItem(None)
        del blocker
        self._update_details()
        if self._selected_ids and not self.selected_section.isHidden():
            self.scroll.ensureWidgetVisible(self.selected_section, 12, 24)

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
        if len(self._selected_ids) > 1:
            blocker = QSignalBlocker(self.include_checkbox)
            self.include_checkbox.setChecked(False)
            self.include_checkbox.setEnabled(False)
            self.detail_label.setText(
                f"{len(self._selected_ids)} cut areas selected\n\n"
                "Shift+click to add or remove items from the selection.\n"
                "Use Delete to remove them together."
            )
            del blocker
            return
        detection = next(
            (item for item in self._detections if item.id == self._selected_id), None
        )
        blocker = QSignalBlocker(self.include_checkbox)
        if detection is None:
            self.include_checkbox.setChecked(False)
            self.include_checkbox.setEnabled(False)
            self.detail_label.setText("Select a cut area to inspect it.")
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
            status = "Excluded from the SVG"
        elif detection.overlaps_cut:
            status = "Overlap - touches another cut; not exported"
        elif not detection.valid_cut:
            status = (
                "Cut is too small for the drawing - not exported"
                if self._mapper is not None
                and not detection.contains_artwork(self._mapper)
                else "Outside bed - not exported"
            )
        else:
            status = "Ready for export"
        self.detail_label.setText(
            f"CUT #{detection.id:02d}\n"
            f"STATUS\n{status}\n\n"
            f"CENTER ({unit.value})\n"
            f"center X:  {center_x:.3f} {unit.value}\n"
            f"center Y:  {center_y:.3f} {unit.value}\n\n"
            f"SIZE ({unit.value})\n"
            f"width:   {width:.3f}\n"
            f"height:  {height:.3f}\n\n"
            f"Top-left: {x:.3f}, {y:.3f} {unit.value}"
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
        detection_list = getattr(self, "detection_list", None)
        if (
            detection_list is not None
            and watched is detection_list.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and detection_list.itemAt(event.position().toPoint()) is None  # type: ignore[attr-defined]
        ):
            # Empty list space is not a selection command. This mirrors the
            # canvas and protects a prepared multi-selection from stray clicks.
            event.accept()
            return True
        if event.type() == QEvent.Type.MouseButtonDblClick:
            callback = self._double_click_resets.get(watched)
            if callback is not None:
                callback()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _on_detection_selection_changed(self) -> None:
        selected_items = self.detection_list.selectedItems()
        selected_ids = {
            int(item.data(Qt.ItemDataRole.UserRole)) for item in selected_items
        }
        current = self.detection_list.currentItem()
        current_id = (
            int(current.data(Qt.ItemDataRole.UserRole))
            if current is not None
            and int(current.data(Qt.ItemDataRole.UserRole)) in selected_ids
            else next(iter(selected_ids), None)
        )
        self._selected_ids = selected_ids
        self._selected_id = current_id
        self._update_details()
        self.detection_selection_changed.emit((selected_ids, current_id))
        if current_id is not None:
            self.detection_selected.emit(current_id)

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
        label = QLabel(label_text)
        label.setBuddy(control)
        label_layout.addWidget(label)
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
