"""Interactive, aspect-correct visualization of the Epilog bed."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.geometry.coordinate_mapper import (
    BED_HEIGHT_IN,
    BED_WIDTH_IN,
    CoordinateMapper,
)
from app.models import Detection
from app.geometry.units import LengthUnit, from_inches
from app.imaging.panel_grid import PanelGrid


class BedCanvas(QWidget):
    detection_selected = Signal(int, bool)
    empty_selected = Signal()
    edit_started = Signal(str)
    center_moved = Signal(int, float, float)
    add_center_requested = Signal(float, float)
    image_placement_changed = Signal(float, float, float, float)
    grid_line_moved = Signal(str, int, float)
    grid_edit_started = Signal()
    grid_edit_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = QImage()
        self._mapper: CoordinateMapper | None = None
        self._detections: list[Detection] = []
        self._selected_ids: set[int] = set()
        self._add_mode = False
        self._dragging_id: int | None = None
        self._drag_edit_announced = False
        self._verification_rectangles: dict[int, tuple[float, float, float, float]] = {}
        self._cut_preview_active = False
        self._panel_grid: PanelGrid | None = None
        self._grid_visible = True
        self._grid_edit_active = False
        self._dragging_grid_line: tuple[str, int] | None = None
        self._grid_edit_announced = False
        self._bed_width_in = BED_WIDTH_IN
        self._bed_height_in = BED_HEIGHT_IN
        self._working_unit = LengthUnit.INCHES
        self._image_locked = True
        self._image_selected = False
        self._image_drag_mode: str | None = None
        self._image_drag_start_point_in: tuple[float, float] | None = None
        self._image_drag_start_rect_in: tuple[float, float, float, float] | None = None
        self._image_scale_handle: str | None = None
        self._view_scale = 1.0
        self._view_offset = QPointF()
        self._space_pan_active = False
        self._hand_tool_active = False
        self._zoom_tool_active = False
        self._temporary_zoom_direction = 0
        self._panning = False
        self._pan_last_point: QPointF | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(560, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Laser bed workspace")
        self.setAccessibleDescription(
            "Image and cut-area workspace. Use Tab to reach the review list for a textual view."
        )

    def set_scene(
        self,
        image: QImage,
        mapper: CoordinateMapper,
        detections: list[Detection],
    ) -> None:
        self._image = image
        self._mapper = mapper
        self._bed_width_in = mapper.bed_width_in
        self._bed_height_in = mapper.bed_height_in
        self._detections = detections
        self._verification_rectangles = {}
        self.update()

    def set_bed_configuration(self, width_in: float, height_in: float) -> None:
        self._bed_width_in = width_in
        self._bed_height_in = height_in
        self.update()

    def set_working_unit(self, unit: LengthUnit) -> None:
        self._working_unit = unit
        self.update()

    @property
    def view_scale(self) -> float:
        return self._view_scale

    def reset_view(self) -> None:
        """Fit the complete bed in the canvas, like Illustrator's Ctrl+0."""
        self._view_scale = 1.0
        self._view_offset = QPointF()
        self.update()

    def zoom_in(self, anchor: QPointF | None = None) -> None:
        self._zoom_at(anchor or self.rect().center(), self._view_scale * 1.25)

    def zoom_out(self, anchor: QPointF | None = None) -> None:
        self._zoom_at(anchor or self.rect().center(), self._view_scale / 1.25)

    def set_image_locked(self, locked: bool) -> None:
        self._image_locked = locked
        self._image_selected = not locked and not self._image.isNull()
        self._image_drag_mode = None
        self._image_scale_handle = None
        self._update_interaction_cursor()
        self.update()

    def set_detections(self, detections: list[Detection]) -> None:
        self._detections = detections
        self.update()

    def set_selected_id(self, detection_id: int | None) -> None:
        self.set_selected_ids({detection_id} if detection_id is not None else set())

    def set_selected_ids(self, detection_ids: set[int]) -> None:
        self._selected_ids = set(detection_ids)
        self.update()

    def set_add_mode(self, active: bool) -> None:
        self._add_mode = active
        self._update_interaction_cursor()

    def set_verification_rectangles(
        self, rectangles: dict[int, tuple[float, float, float, float]]
    ) -> None:
        self._verification_rectangles = rectangles
        self.update()

    def set_panel_grid(self, panel_grid: PanelGrid | None) -> None:
        self._panel_grid = panel_grid
        if panel_grid is None:
            self._dragging_grid_line = None
            self._grid_edit_active = False
        self.update()

    def set_grid_edit_active(self, active: bool) -> None:
        self._grid_edit_active = bool(
            active and self._grid_visible and self._panel_grid is not None
        )
        self._dragging_grid_line = None
        self._update_interaction_cursor()
        self.update()

    def set_grid_visible(self, visible: bool) -> None:
        self._grid_visible = bool(visible)
        if not self._grid_visible:
            self._grid_edit_active = False
            self._dragging_grid_line = None
        self._update_interaction_cursor()
        self.update()

    @property
    def cut_preview_active(self) -> bool:
        return self._cut_preview_active

    def set_cut_preview(self, active: bool) -> None:
        self._cut_preview_active = active
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#15191f"))
        bed = self._bed_rect()

        painter.setPen(QPen(QColor("#080a0d"), 10))
        painter.setBrush(QColor("#d9d7ce"))
        painter.drawRect(bed)

        if not self._image.isNull() and self._mapper is not None:
            painter.drawImage(self._image_rect_widget(), self._image)
        else:
            painter.setPen(QColor("#68717d"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(
                bed,
                Qt.AlignmentFlag.AlignCenter,
                "Load an image, paste from Epilog Dashboard,\nor choose Demo Image",
            )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#77818d"), 1))
        painter.drawRect(bed)

        self._paint_cut_preview(painter, bed)
        self._paint_rulers(painter, bed)
        self._paint_panel_grid(painter)

        if self._mapper is not None and self._image_selected and not self._image_locked:
            self._paint_image_selection(painter)

        if self._mapper is None:
            self._paint_view_indicator(painter)
            return
        self._paint_detections(painter)
        self._paint_verification(painter)
        self._paint_view_indicator(painter)

    def _paint_cut_preview(self, painter: QPainter, bed: QRectF) -> None:
        if not self._cut_preview_active or self._mapper is None:
            return
        shaded_area = QPainterPath()
        shaded_area.setFillRule(Qt.FillRule.OddEvenFill)
        shaded_area.addRect(bed)
        for detection in self._detections:
            if not detection.enabled:
                continue
            square_px = self._mapper.inches_rect_to_pixel(
                detection.square_inches.as_tuple()
            )
            square = self._pixel_rect_to_widget(square_px).intersected(bed)
            if not square.isEmpty():
                shaded_area.addRect(square)
        painter.fillPath(shaded_area, QColor(7, 10, 14, 178))

    def _paint_view_indicator(self, painter: QPainter) -> None:
        if abs(self._view_scale - 1.0) < 1e-9 and self._view_offset.isNull():
            return
        text = f"View {self._view_scale * 100:.0f}%  ·  Ctrl+0: Fit"
        rectangle = QRectF(12, self.height() - 38, 150, 25)
        painter.setPen(QPen(QColor("#53606c"), 1))
        painter.setBrush(QColor(16, 20, 25, 220))
        painter.drawRoundedRect(rectangle, 4, 4)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#c8d1d9"))
        painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_panel_grid(self, painter: QPainter) -> None:
        if not self._grid_visible or self._panel_grid is None or self._mapper is None:
            return
        color = QColor("#55e6ff")
        color.setAlpha(225 if self._grid_edit_active else 105)
        pen = QPen(color, 2 if self._grid_edit_active else 1)
        pen.setCosmetic(True)
        pen.setStyle(
            Qt.PenStyle.SolidLine
            if self._grid_edit_active
            else Qt.PenStyle.DashLine
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        top = self._pixel_to_widget(0.0, self._panel_grid.y_lines_px[0]).y()
        bottom = self._pixel_to_widget(0.0, self._panel_grid.y_lines_px[-1]).y()
        left = self._pixel_to_widget(self._panel_grid.x_lines_px[0], 0.0).x()
        right = self._pixel_to_widget(self._panel_grid.x_lines_px[-1], 0.0).x()
        for index, x_px in enumerate(self._panel_grid.x_lines_px):
            x = self._pixel_to_widget(x_px, 0.0).x()
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            if self._grid_edit_active:
                painter.setBrush(QColor("#142b31"))
                painter.drawEllipse(QPointF(x, top), 4.0, 4.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, y_px in enumerate(self._panel_grid.y_lines_px):
            y = self._pixel_to_widget(0.0, y_px).y()
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            if self._grid_edit_active:
                painter.setBrush(QColor("#142b31"))
                painter.drawEllipse(QPointF(left, y), 4.0, 4.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_detections(self, painter: QPainter) -> None:
        assert self._mapper is not None
        label_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        for detection in self._detections:
            selected = detection.id in self._selected_ids
            if not detection.enabled:
                color = QColor(145, 153, 163, 135)
            elif detection.overlaps_cut:
                color = QColor("#ff8a3d")
            elif not detection.valid_cut:
                color = QColor("#ff5364")
            else:
                color = QColor("#39d6a4")

            if detection.bounding_box_px is not None:
                bbox = self._pixel_rect_to_widget(detection.bounding_box_px)
                bbox_pen = QPen(QColor(color.red(), color.green(), color.blue(), 125), 1)
                bbox_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(bbox_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bbox)

            square_px = self._mapper.inches_rect_to_pixel(
                detection.square_inches.as_tuple()
            )
            square = self._pixel_rect_to_widget(square_px)
            # Selection owns the cut square itself: a bright cyan edge, center,
            # label, and translucent interior.  It does not add an outer halo,
            # so the highlighted geometry is exactly the geometry being edited.
            square_color = QColor("#55e6ff") if selected else color
            square_pen = QPen(square_color, 4 if selected else 2)
            square_pen.setCosmetic(True)
            painter.setPen(square_pen)
            painter.setBrush(
                QColor(85, 230, 255, 68)
                if selected
                else QColor(color.red(), color.green(), color.blue(), 18)
            )
            painter.drawRect(square)

            center = self._pixel_to_widget(*detection.center_px)
            painter.setPen(QPen(QColor("#11151a"), 6 if selected else 4))
            painter.drawPoint(center)
            selection_color = QColor("#55e6ff") if selected else color
            painter.setPen(QPen(QColor("#ffffff") if selected else color, 2))
            painter.setBrush(selection_color)
            painter.drawEllipse(center, 6.0 if selected else 3.5, 6.0 if selected else 3.5)

            painter.setFont(label_font)
            label_rect = QRectF(center.x() + 7, center.y() - 19, 42, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(selection_color if selected else QColor(15, 18, 23, 190))
            painter.drawRoundedRect(label_rect, 3, 3)
            painter.setPen(QColor("#071419") if selected else color)
            painter.drawText(
                label_rect, Qt.AlignmentFlag.AlignCenter, f"#{detection.id:02d}"
            )

    def _paint_verification(self, painter: QPainter) -> None:
        if not self._verification_rectangles:
            return
        verify_pen = QPen(QColor("#d989ff"), 3)
        verify_pen.setStyle(Qt.PenStyle.DotLine)
        verify_pen.setCosmetic(True)
        painter.setPen(verify_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for rectangle_px in self._verification_rectangles.values():
            painter.drawRect(self._pixel_rect_to_widget(rectangle_px))

    def _paint_image_selection(self, painter: QPainter) -> None:
        rectangle = self._image_rect_widget()
        pen = QPen(QColor("#78aee8"), 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rectangle)
        painter.setPen(QPen(QColor("#d9e8f7"), 1))
        painter.setBrush(QColor("#3e78ad"))
        for point in (
            rectangle.topLeft(),
            rectangle.topRight(),
            rectangle.bottomRight(),
            rectangle.bottomLeft(),
        ):
            painter.drawRect(QRectF(point.x() - 4, point.y() - 4, 8, 8))

    def _paint_rulers(self, painter: QPainter, bed: QRectF) -> None:
        ruler_color = QColor("#9ca8b4")
        secondary = QColor("#626e79")
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        width_value = from_inches(self._bed_width_in, self._working_unit)
        height_value = from_inches(self._bed_height_in, self._working_unit)
        x_step = _nice_tick_step(width_value, bed.width())
        y_step = _nice_tick_step(height_value, bed.height())

        painter.setPen(QPen(secondary, 1))
        painter.drawLine(QPointF(bed.left(), bed.top() - 5), QPointF(bed.right(), bed.top() - 5))
        painter.drawLine(QPointF(bed.left() - 5, bed.top()), QPointF(bed.left() - 5, bed.bottom()))

        value = 0.0
        while value <= width_value + x_step * 0.01:
            x = bed.left() + value / width_value * bed.width()
            painter.setPen(QPen(ruler_color, 1))
            painter.drawLine(QPointF(x, bed.top() - 5), QPointF(x, bed.top() - 13))
            label = _format_ruler_value(value)
            painter.drawText(QRectF(x - 25, bed.top() - 35, 50, 18), Qt.AlignmentFlag.AlignCenter, label)
            minor = value + x_step / 2.0
            if minor < width_value:
                minor_x = bed.left() + minor / width_value * bed.width()
                painter.setPen(QPen(secondary, 1))
                painter.drawLine(QPointF(minor_x, bed.top() - 5), QPointF(minor_x, bed.top() - 9))
            value += x_step

        value = 0.0
        while value <= height_value + y_step * 0.01:
            y = bed.top() + value / height_value * bed.height()
            painter.setPen(QPen(ruler_color, 1))
            painter.drawLine(QPointF(bed.left() - 5, y), QPointF(bed.left() - 13, y))
            painter.drawText(
                QRectF(bed.left() - 58, y - 9, 40, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _format_ruler_value(value),
            )
            minor = value + y_step / 2.0
            if minor < height_value:
                minor_y = bed.top() + minor / height_value * bed.height()
                painter.setPen(QPen(secondary, 1))
                painter.drawLine(QPointF(bed.left() - 5, minor_y), QPointF(bed.left() - 9, minor_y))
            value += y_step

        painter.setPen(QPen(QColor("#39d6a4"), 1.5))
        painter.setBrush(QColor("#39d6a4"))
        painter.drawEllipse(QPointF(bed.left(), bed.top()), 3.5, 3.5)
        painter.drawText(
            QRectF(bed.left() + 7, bed.top() + 5, 110, 18),
            Qt.AlignmentFlag.AlignLeft,
            "Origin (0, 0)",
        )

        painter.setPen(ruler_color)
        painter.drawText(
            QRectF(bed.left(), bed.bottom() + 8, bed.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{width_value:.3f} {self._working_unit.value}",
        )
        painter.save()
        painter.translate(bed.right() + 18, bed.center().y())
        painter.rotate(90)
        painter.drawText(
            QRectF(-bed.height() / 2.0, -10, bed.height(), 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{height_value:.3f} {self._working_unit.value}",
        )
        painter.restore()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        point = event.position()
        pan_requested = event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and (self._space_pan_active or self._hand_tool_active)
        )
        if pan_requested:
            self._panning = True
            self._pan_last_point = point
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return

        zoom_direction = self._temporary_zoom_direction
        if self._zoom_tool_active:
            zoom_direction = -1 if event.modifiers() & Qt.KeyboardModifier.AltModifier else 1
        if event.button() == Qt.MouseButton.LeftButton and zoom_direction:
            if zoom_direction > 0:
                self.zoom_in(point)
            else:
                self.zoom_out(point)
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton or self._mapper is None:
            return
        if not self._bed_rect().contains(point):
            # Empty-space clicks are easy to make while reviewing a group.
            # Preserve the current selection until another detection or an
            # explicit command changes it.
            event.accept()
            return

        if self._grid_visible and self._grid_edit_active and self._panel_grid is not None:
            grid_line = self._grid_line_at(point)
            if grid_line is not None:
                self._dragging_grid_line = grid_line
                self._grid_edit_announced = False
                axis, _index = grid_line
                self.setCursor(
                    QCursor(
                        Qt.CursorShape.SplitHCursor
                        if axis == "x"
                        else Qt.CursorShape.SplitVCursor
                    )
                )
                event.accept()
                return

        if not self._image_locked:
            handle = self._image_handle_at(point)
            image_rect = self._image_rect_widget()
            if handle is not None:
                self._image_selected = True
                self._image_drag_mode = "scale"
                self._image_scale_handle = handle
                self._drag_edit_announced = False
            elif image_rect.contains(point):
                self._image_selected = True
                self._image_drag_mode = "move"
                self._image_scale_handle = None
                self._drag_edit_announced = False
            else:
                self._image_selected = False
                self._image_drag_mode = None
                self._image_scale_handle = None
                self.update()
                return
            self._image_drag_start_point_in = self._widget_to_bed_inches(point)
            self._image_drag_start_rect_in = self._mapper.image_bed_rect_inches
            self.update()
            return

        image_point = self._widget_to_pixel(point)
        if self._add_mode:
            self.add_center_requested.emit(image_point.x(), image_point.y())
            return

        detection_id = self._hit_test(point)
        if detection_id is not None:
            additive = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.detection_selected.emit(detection_id, additive)
            # The selection signal is delivered synchronously. Only start a
            # drag if this click left the detection selected; clicking an
            # already-selected square toggles it off instead.
            if not additive and detection_id in self._selected_ids:
                self._dragging_id = detection_id
                self._drag_edit_announced = False
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and self._pan_last_point is not None:
            delta = event.position() - self._pan_last_point
            self._view_offset += delta
            self._pan_last_point = event.position()
            self._constrain_view_offset()
            self.update()
            event.accept()
            return
        if (
            self._space_pan_active
            or self._hand_tool_active
            or self._temporary_zoom_direction
            or self._zoom_tool_active
        ):
            self._update_interaction_cursor()
            return
        if self._grid_visible and self._grid_edit_active and self._panel_grid is not None:
            if self._dragging_grid_line is not None:
                if not self._grid_edit_announced:
                    self.grid_edit_started.emit()
                    self._grid_edit_announced = True
                axis, index = self._dragging_grid_line
                image_point = self._widget_to_pixel(event.position(), clamp=True)
                value = image_point.x() if axis == "x" else image_point.y()
                self.grid_line_moved.emit(axis, index, value)
                event.accept()
                return
            # A visible/editable guide must not disable moving cuts. Only a
            # guide drag owns the pointer; an active cut drag continues below.
            if self._dragging_id is None:
                grid_line = self._grid_line_at(event.position())
                if grid_line is not None:
                    axis, _index = grid_line
                    self.setCursor(
                        QCursor(
                            Qt.CursorShape.SplitHCursor
                            if axis == "x"
                            else Qt.CursorShape.SplitVCursor
                        )
                    )
                    return
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        if not self._image_locked and self._mapper is not None:
            if self._image_drag_mode is not None:
                if not self._drag_edit_announced:
                    self.edit_started.emit(
                        "Resize image"
                        if self._image_drag_mode == "scale"
                        else "Move image"
                    )
                    self._drag_edit_announced = True
                self._update_image_drag(event.position())
                return
            handle = self._image_handle_at(event.position())
            if handle in ("top_left", "bottom_right"):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            elif handle in ("top_right", "bottom_left"):
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
            elif self._image_rect_widget().contains(event.position()):
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return
        if self._dragging_id is None or self._mapper is None:
            return
        if not self._drag_edit_announced:
            self.edit_started.emit("Move cut")
            self._drag_edit_announced = True
        image_point = self._widget_to_pixel(event.position(), clamp=True)
        self.center_moved.emit(self._dragging_id, image_point.x(), image_point.y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and event.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
        ):
            self._panning = False
            self._pan_last_point = None
            self._update_interaction_cursor()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            grid_was_edited = (
                self._dragging_grid_line is not None and self._grid_edit_announced
            )
            self._dragging_id = None
            self._drag_edit_announced = False
            self._image_drag_mode = None
            self._image_scale_handle = None
            self._image_drag_start_point_in = None
            self._image_drag_start_rect_in = None
            self._dragging_grid_line = None
            self._grid_edit_announced = False
            if grid_was_edited:
                self.grid_edit_finished.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        delta = event.angleDelta()
        if delta.isNull():
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = delta.y() / 120.0
            if steps:
                self._zoom_at(event.position(), self._view_scale * (1.18**steps))
        else:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                movement = QPointF(delta.y() * 0.5, 0.0)
            else:
                movement = QPointF(delta.x() * 0.5, delta.y() * 0.5)
            self._view_offset += movement
            self._constrain_view_offset()
            self.update()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        key = event.key()
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier and key in (
            Qt.Key.Key_Equal,
            Qt.Key.Key_Plus,
        ):
            self.zoom_in()
            event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Minus:
            self.zoom_out()
            event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_0:
            self.reset_view()
            event.accept()
            return
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._temporary_zoom_direction = (
                    -1 if modifiers & Qt.KeyboardModifier.AltModifier else 1
                )
            else:
                self._space_pan_active = True
            self._update_interaction_cursor()
            event.accept()
            return
        if key == Qt.Key.Key_H:
            self._hand_tool_active = True
            self._zoom_tool_active = False
            self._update_interaction_cursor()
            event.accept()
            return
        if key == Qt.Key.Key_Z:
            self._zoom_tool_active = True
            self._hand_tool_active = False
            self._update_interaction_cursor()
            event.accept()
            return
        if key in (Qt.Key.Key_V, Qt.Key.Key_Escape):
            self._zoom_tool_active = False
            self._hand_tool_active = False
            self._temporary_zoom_direction = 0
            self._space_pan_active = False
            self._update_interaction_cursor()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = False
            self._temporary_zoom_direction = 0
            if not self._panning:
                self._update_interaction_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _update_image_drag(self, widget_point: QPointF) -> None:
        if (
            self._mapper is None
            or self._image_drag_start_point_in is None
            or self._image_drag_start_rect_in is None
        ):
            return
        point_x, point_y = self._widget_to_bed_inches(widget_point)
        start_x, start_y = self._image_drag_start_point_in
        x, y, width, height = self._image_drag_start_rect_in
        if self._image_drag_mode == "move":
            new_x = min(max(x + point_x - start_x, 0.0), self._bed_width_in - width)
            new_y = min(max(y + point_y - start_y, 0.0), self._bed_height_in - height)
            new_rect = (new_x, new_y, width, height)
        else:
            new_rect = self._scaled_image_rect(
                point_x, point_y, self._image_scale_handle, (x, y, width, height)
            )
        self.image_placement_changed.emit(*new_rect)

    def _scaled_image_rect(
        self,
        point_x: float,
        point_y: float,
        handle: str | None,
        rectangle: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        x, y, width, height = rectangle
        aspect = width / height
        minimum_width = min(width, max(0.25, self._bed_width_in * 0.02))
        if handle == "bottom_right":
            anchor_x, anchor_y = x, y
            desired = max(point_x - anchor_x, (point_y - anchor_y) * aspect)
            maximum = min(self._bed_width_in - anchor_x, (self._bed_height_in - anchor_y) * aspect)
            new_width = min(max(desired, minimum_width), maximum)
            return anchor_x, anchor_y, new_width, new_width / aspect
        if handle == "top_left":
            anchor_x, anchor_y = x + width, y + height
            desired = max(anchor_x - point_x, (anchor_y - point_y) * aspect)
            maximum = min(anchor_x, anchor_y * aspect)
            new_width = min(max(desired, minimum_width), maximum)
            new_height = new_width / aspect
            return anchor_x - new_width, anchor_y - new_height, new_width, new_height
        if handle == "top_right":
            anchor_x, anchor_y = x, y + height
            desired = max(point_x - anchor_x, (anchor_y - point_y) * aspect)
            maximum = min(self._bed_width_in - anchor_x, anchor_y * aspect)
            new_width = min(max(desired, minimum_width), maximum)
            new_height = new_width / aspect
            return anchor_x, anchor_y - new_height, new_width, new_height
        anchor_x, anchor_y = x + width, y
        desired = max(anchor_x - point_x, (point_y - anchor_y) * aspect)
        maximum = min(anchor_x, (self._bed_height_in - anchor_y) * aspect)
        new_width = min(max(desired, minimum_width), maximum)
        new_height = new_width / aspect
        return anchor_x - new_width, anchor_y, new_width, new_height

    def _hit_test(self, point: QPointF) -> int | None:
        assert self._mapper is not None
        for detection in reversed(self._detections):
            center = self._pixel_to_widget(*detection.center_px)
            delta = center - point
            if delta.x() * delta.x() + delta.y() * delta.y() <= 15.0 * 15.0:
                return detection.id
        for detection in reversed(self._detections):
            square_px = self._mapper.inches_rect_to_pixel(
                detection.square_inches.as_tuple()
            )
            if self._pixel_rect_to_widget(square_px).contains(point):
                return detection.id
        return None

    def _grid_line_at(self, point: QPointF) -> tuple[str, int] | None:
        if self._panel_grid is None or self._mapper is None:
            return None
        tolerance = 7.0
        candidates: list[tuple[float, str, int]] = []
        top = self._pixel_to_widget(0.0, self._panel_grid.y_lines_px[0]).y()
        bottom = self._pixel_to_widget(0.0, self._panel_grid.y_lines_px[-1]).y()
        left = self._pixel_to_widget(self._panel_grid.x_lines_px[0], 0.0).x()
        right = self._pixel_to_widget(self._panel_grid.x_lines_px[-1], 0.0).x()
        if top - tolerance <= point.y() <= bottom + tolerance:
            for index, x_px in enumerate(self._panel_grid.x_lines_px):
                x = self._pixel_to_widget(x_px, 0.0).x()
                distance = abs(point.x() - x)
                if distance <= tolerance:
                    candidates.append((distance, "x", index))
        if left - tolerance <= point.x() <= right + tolerance:
            for index, y_px in enumerate(self._panel_grid.y_lines_px):
                y = self._pixel_to_widget(0.0, y_px).y()
                distance = abs(point.y() - y)
                if distance <= tolerance:
                    candidates.append((distance, "y", index))
        if not candidates:
            return None
        _distance, axis, index = min(candidates, key=lambda item: item[0])
        return axis, index

    def _fit_bed_rect(self) -> QRectF:
        left_margin, top_margin, right_margin, bottom_margin = 68.0, 48.0, 36.0, 42.0
        available_width = max(1.0, self.width() - left_margin - right_margin)
        available_height = max(1.0, self.height() - top_margin - bottom_margin)
        bed_width = self._mapper.bed_width_in if self._mapper else self._bed_width_in
        bed_height = self._mapper.bed_height_in if self._mapper else self._bed_height_in
        target_ratio = bed_width / bed_height
        if available_width / available_height > target_ratio:
            height = available_height
            width = height * target_ratio
        else:
            width = available_width
            height = width / target_ratio
        area_left = left_margin
        area_top = top_margin
        return QRectF(
            area_left + (available_width - width) / 2.0,
            area_top + (available_height - height) / 2.0,
            width,
            height,
        )

    def _bed_rect(self) -> QRectF:
        fitted = self._fit_bed_rect()
        center = fitted.center() + self._view_offset
        width = fitted.width() * self._view_scale
        height = fitted.height() * self._view_scale
        return QRectF(
            center.x() - width / 2.0,
            center.y() - height / 2.0,
            width,
            height,
        )

    def _zoom_at(self, anchor, requested_scale: float) -> None:
        anchor_point = QPointF(anchor)
        old_rect = self._bed_rect()
        if old_rect.width() <= 0 or old_rect.height() <= 0:
            return
        relative_x = (anchor_point.x() - old_rect.left()) / old_rect.width()
        relative_y = (anchor_point.y() - old_rect.top()) / old_rect.height()
        new_scale = min(max(float(requested_scale), 0.25), 12.0)
        if abs(new_scale - self._view_scale) < 1e-12:
            return
        fitted = self._fit_bed_rect()
        new_width = fitted.width() * new_scale
        new_height = fitted.height() * new_scale
        new_left = anchor_point.x() - relative_x * new_width
        new_top = anchor_point.y() - relative_y * new_height
        new_center = QPointF(new_left + new_width / 2.0, new_top + new_height / 2.0)
        self._view_scale = new_scale
        self._view_offset = new_center - fitted.center()
        self._constrain_view_offset()
        self.update()

    def _constrain_view_offset(self) -> None:
        rectangle = self._bed_rect()
        minimum_visible = 64.0
        correction = QPointF()
        if rectangle.right() < minimum_visible:
            correction.setX(minimum_visible - rectangle.right())
        elif rectangle.left() > self.width() - minimum_visible:
            correction.setX(self.width() - minimum_visible - rectangle.left())
        if rectangle.bottom() < minimum_visible:
            correction.setY(minimum_visible - rectangle.bottom())
        elif rectangle.top() > self.height() - minimum_visible:
            correction.setY(self.height() - minimum_visible - rectangle.top())
        self._view_offset += correction

    def _update_interaction_cursor(self) -> None:
        if self._panning:
            cursor = Qt.CursorShape.ClosedHandCursor
        elif self._space_pan_active or self._hand_tool_active:
            cursor = Qt.CursorShape.OpenHandCursor
        elif self._temporary_zoom_direction or self._zoom_tool_active:
            cursor = Qt.CursorShape.CrossCursor
        elif self._add_mode:
            cursor = Qt.CursorShape.CrossCursor
        elif not self._image_locked:
            cursor = Qt.CursorShape.SizeAllCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor
        self.setCursor(QCursor(cursor))

    def _image_rect_widget(self) -> QRectF:
        if self._mapper is None:
            return QRectF()
        return self._inches_rect_to_widget(self._mapper.image_bed_rect_inches)

    def _image_handle_at(self, point: QPointF) -> str | None:
        if not self._image_selected or self._mapper is None:
            return None
        rectangle = self._image_rect_widget()
        for name, corner in (
            ("top_left", rectangle.topLeft()),
            ("top_right", rectangle.topRight()),
            ("bottom_right", rectangle.bottomRight()),
            ("bottom_left", rectangle.bottomLeft()),
        ):
            delta = corner - point
            if delta.x() * delta.x() + delta.y() * delta.y() <= 10.0 * 10.0:
                return name
        return None

    def _widget_to_bed_inches(self, point: QPointF) -> tuple[float, float]:
        bed = self._bed_rect()
        return (
            min(max((point.x() - bed.left()) / bed.width() * self._bed_width_in, 0.0), self._bed_width_in),
            min(max((point.y() - bed.top()) / bed.height() * self._bed_height_in, 0.0), self._bed_height_in),
        )

    def _inches_rect_to_widget(
        self, rectangle_in: tuple[float, float, float, float]
    ) -> QRectF:
        bed = self._bed_rect()
        x, y, width, height = rectangle_in
        return QRectF(
            bed.left() + x / self._bed_width_in * bed.width(),
            bed.top() + y / self._bed_height_in * bed.height(),
            width / self._bed_width_in * bed.width(),
            height / self._bed_height_in * bed.height(),
        )

    def _pixel_to_widget(self, x_px: float, y_px: float) -> QPointF:
        assert self._mapper is not None
        x_in, y_in = self._mapper.pixel_to_inches(x_px, y_px)
        rectangle = self._inches_rect_to_widget((x_in, y_in, 0.0, 0.0))
        return rectangle.topLeft()

    def _widget_to_pixel(self, point: QPointF, clamp: bool = False) -> QPointF:
        assert self._mapper is not None
        x_in, y_in = self._widget_to_bed_inches(point)
        x, y = self._mapper.inches_to_pixel(x_in, y_in)
        if clamp:
            x = min(max(x, 0.0), float(self._mapper.image_width_px))
            y = min(max(y, 0.0), float(self._mapper.image_height_px))
        return QPointF(x, y)

    def _pixel_rect_to_widget(
        self, rectangle_px: tuple[float, float, float, float]
    ) -> QRectF:
        x, y, width, height = rectangle_px
        top_left = self._pixel_to_widget(x, y)
        bottom_right = self._pixel_to_widget(x + width, y + height)
        return QRectF(top_left, bottom_right).normalized()


def _nice_tick_step(physical_span: float, pixel_span: float) -> float:
    import math

    target_ticks = max(2.0, pixel_span / 90.0)
    rough = physical_span / target_ticks
    exponent = 10.0 ** math.floor(math.log10(max(rough, 1e-12)))
    normalized = rough / exponent
    if normalized <= 1.0:
        nice = 1.0
    elif normalized <= 2.0:
        nice = 2.0
    elif normalized <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * exponent


def _format_ruler_value(value: float) -> str:
    if abs(value - round(value)) < 1e-8:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")
