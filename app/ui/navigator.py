"""Illustrator-style Navigator: bed overview, view rectangle and zoom slider."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.canvas import BedCanvas

SLIDER_STEPS = 1000
VIEW_RECT_COLOR = "#ff3b4f"


def scale_to_slider(scale: float) -> int:
    low, high = BedCanvas.MIN_VIEW_SCALE, BedCanvas.MAX_VIEW_SCALE
    scale = min(max(scale, low), high)
    return round(math.log(scale / low) / math.log(high / low) * SLIDER_STEPS)


def slider_to_scale(value: int) -> float:
    low, high = BedCanvas.MIN_VIEW_SCALE, BedCanvas.MAX_VIEW_SCALE
    return low * (high / low) ** (value / SLIDER_STEPS)


class NavigatorView(QWidget):
    """Thumbnail of the whole bed; click or drag to move the visible area."""

    def __init__(self, canvas: BedCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._dragging = False
        self.setFixedSize(240, 162)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Click or drag to move the view. Double-click to zoom in there.")
        self.setAccessibleName("Navigator overview")

    def bed_target(self) -> QRectF:
        width_in, height_in = self._canvas.bed_size_inches()
        area = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if width_in <= 0 or height_in <= 0:
            return area
        ratio = width_in / height_in
        if area.width() / area.height() > ratio:
            width, height = area.height() * ratio, area.height()
        else:
            width, height = area.width(), area.width() / ratio
        return QRectF(area.center().x() - width / 2, area.center().y() - height / 2, width, height)

    def view_rect(self) -> QRectF:
        target = self.bed_target()
        width_in, height_in = self._canvas.bed_size_inches()
        x, y, w, h = self._canvas.visible_bed_rect_inches()
        sx, sy = target.width() / width_in, target.height() / height_in
        return QRectF(target.left() + x * sx, target.top() + y * sy, w * sx, h * sy)

    def _point_to_inches(self, point: QPointF) -> tuple[float, float]:
        target = self.bed_target()
        width_in, height_in = self._canvas.bed_size_inches()
        x = min(max(point.x() - target.left(), 0.0), target.width())
        y = min(max(point.y() - target.top(), 0.0), target.height())
        return x / target.width() * width_in, y / target.height() * height_in

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#15191f"))
        target = self.bed_target()
        painter.save()
        painter.setClipRect(target)
        self._canvas.paint_overview(painter, target)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#77818d"), 1))
        painter.drawRect(target)
        view = self.view_rect().intersected(target)
        if not view.isEmpty():
            pen = QPen(QColor(VIEW_RECT_COLOR), 2)
            painter.setPen(pen)
            painter.drawRect(view)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._canvas.center_view_on_bed_inches(*self._point_to_inches(event.position()))
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._dragging:
            self._canvas.center_view_on_bed_inches(*self._point_to_inches(event.position()))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            point = self._point_to_inches(event.position())
            self._canvas.set_view_scale(self._canvas.view_scale * 2.0)
            self._canvas.center_view_on_bed_inches(*point)
            event.accept()


class NavigatorPanel(QFrame):
    """Collapsible floating panel shown over the bottom-right of the canvas.

    It opens by itself the first time the view is zoomed in, unless the
    operator has already collapsed it, and can be opened at any time.
    """

    def __init__(self, canvas: BedCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._user_collapsed = False
        self.setObjectName("navigatorPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(5)

        self.toggle = QToolButton()
        self.toggle.setObjectName("navigationToggle")
        self.toggle.setText("Navigator")
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setToolTip("Overview of the bed with the visible area in red, and zoom controls.")
        self.toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)

        self.body = QWidget()
        self.body.setObjectName("navigationDetails")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        self.view = NavigatorView(canvas)
        body_layout.addWidget(self.view)

        controls = QHBoxLayout()
        controls.setSpacing(4)
        self.zoom_out_button = self._small_button("−", "Zoom out", canvas.zoom_out)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setToolTip("Zoom")
        self.slider.setAccessibleName("Zoom")
        self.slider.valueChanged.connect(lambda v: canvas.set_view_scale(slider_to_scale(v)))
        self.zoom_in_button = self._small_button("+", "Zoom in", canvas.zoom_in)
        self.percent_label = QLabel("100%")
        self.percent_label.setObjectName("navigationText")
        self.percent_label.setMinimumWidth(42)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.fit_button = self._small_button("Fit", "Show the whole bed (Ctrl+0)", canvas.reset_view)
        for widget in (self.zoom_out_button, self.slider, self.zoom_in_button,
                       self.percent_label, self.fit_button):
            controls.addWidget(widget)
        controls.setStretchFactor(self.slider, 1)
        body_layout.addLayout(controls)
        layout.addWidget(self.body)
        self.body.setVisible(False)
        self.body.setFixedWidth(self.view.width())

        canvas.view_changed.connect(self.refresh)
        self.refresh()

    def _small_button(self, text: str, tip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setObjectName("navigatorButton")
        button.setText(text)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: slot())
        button.setFixedWidth(34 if len(text) > 1 else 24)
        return button

    @property
    def expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)

    def _on_toggled(self, expanded: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.body.setVisible(expanded)
        if not expanded and self._canvas.view_scale > 1.0 + 1e-6:
            self._user_collapsed = True
        self.refresh()

    def refresh(self) -> None:
        scale = self._canvas.view_scale
        if scale > 1.0 + 1e-6 and not self._user_collapsed and not self.expanded:
            blocker = QSignalBlocker(self.toggle)
            self.toggle.setChecked(True)
            del blocker
            self.toggle.setArrowType(Qt.ArrowType.DownArrow)
            self.body.setVisible(True)
        if not self.expanded:
            return
        blocker = QSignalBlocker(self.slider)
        self.slider.setValue(scale_to_slider(scale))
        del blocker
        self.percent_label.setText(f"{scale * 100:.0f}%")
        self.view.update()
