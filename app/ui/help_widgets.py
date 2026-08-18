"""Reusable contextual-help widgets for the desktop interface."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QFont, QPainter
from PySide6.QtWidgets import QToolBar, QToolButton, QToolTip, QWidget


def _tooltip_html(text: str) -> str:
    paragraphs = "<br>".join(escape(line) for line in text.splitlines())
    return f'<div style="width: 300px; white-space: normal;">{paragraphs}</div>'


class InfoButton(QToolButton):
    """Small information icon that opens an English floating explanation."""

    def __init__(self, help_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.help_text = help_text
        self.setObjectName("infoButton")
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(16, 16)
        self.setText("")
        self.setAccessibleName("Information")
        self.setAccessibleDescription(help_text)
        self.setToolTip(help_text)
        self.clicked.connect(self.show_help)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        painter = QPainter(self)
        font = QFont("Segoe UI")
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(self.palette().buttonText().color())
        painter.drawText(
            self.rect().adjusted(0, -1, 0, 0), Qt.AlignmentFlag.AlignCenter, "i"
        )

    def show_help(self) -> None:
        position = self.mapToGlobal(QPoint(0, self.height() + 4))
        QToolTip.showText(position, _tooltip_html(self.help_text), self, msecShowTime=15000)


class DelayedHelpToolBar(QToolBar):
    """Toolbar that shows action help after a deliberate 1.3-second hover."""

    HOVER_DELAY_MS = 1300

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._help_by_widget: dict[QObject, str] = {}
        self._pending_widget: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.HOVER_DELAY_MS)
        self._timer.timeout.connect(self._show_pending_help)

    def register_action_help(self, action: QAction, help_text: str) -> None:
        action.setWhatsThis(help_text)
        action.setStatusTip(help_text)
        widget = self.widgetForAction(action)
        if widget is None:
            return
        widget.setToolTip("")
        widget.setAccessibleDescription(help_text)
        widget.installEventFilter(self)
        self._help_by_widget[widget] = help_text

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched in self._help_by_widget:
            if event.type() == QEvent.Type.Enter:
                QToolTip.hideText()
                self._pending_widget = watched if isinstance(watched, QWidget) else None
                self._timer.start()
            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Hide,
            ):
                if watched is self._pending_widget:
                    self._timer.stop()
                    self._pending_widget = None
                QToolTip.hideText()
        return super().eventFilter(watched, event)

    def _show_pending_help(self) -> None:
        widget = self._pending_widget
        if widget is None or not widget.underMouse():
            return
        help_text = self._help_by_widget.get(widget)
        if not help_text:
            return
        position = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        QToolTip.showText(position, _tooltip_html(help_text), widget, msecShowTime=12000)
