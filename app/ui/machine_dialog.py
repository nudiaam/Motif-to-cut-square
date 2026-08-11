"""Dialog for creating a named custom machine bed profile."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.geometry.units import LengthUnit, convert_length


class AddMachineDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add custom machine")
        self.setModal(True)
        self.setMinimumWidth(390)
        self._unit = LengthUnit.INCHES

        layout = QVBoxLayout(self)
        introduction = QLabel(
            "Create a named machine profile with its physical bed dimensions."
        )
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Example: Workshop laser 900 × 600")
        form.addRow("Machine name", self.name_edit)

        self.width_spin = self._dimension_spin(36.0)
        self.height_spin = self._dimension_spin(24.0)
        form.addRow("Bed width", self.width_spin)
        form.addRow("Bed height", self.height_spin)

        self.unit_combo = QComboBox()
        for unit in LengthUnit:
            self.unit_combo.addItem(f"{unit.display_name} ({unit.value})", unit.value)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        form.addRow("Dimension units", self.unit_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _dimension_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.001, 100_000.0)
        spin.setDecimals(3)
        spin.setValue(value)
        spin.setSuffix(" in")
        return spin

    def values(self) -> tuple[str, float, float, LengthUnit]:
        return (
            self.name_edit.text().strip(),
            self.width_spin.value(),
            self.height_spin.value(),
            LengthUnit(self.unit_combo.currentData()),
        )

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Machine name required", "Enter a machine name.")
            self.name_edit.setFocus()
            return
        self.accept()

    def _on_unit_changed(self) -> None:
        new_unit = LengthUnit(self.unit_combo.currentData())
        if new_unit == self._unit:
            return
        for spin in (self.width_spin, self.height_spin):
            blocker = QSignalBlocker(spin)
            spin.setValue(convert_length(spin.value(), self._unit, new_unit))
            spin.setSuffix(f" {new_unit.value}")
            del blocker
        self._unit = new_unit
