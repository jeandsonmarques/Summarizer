# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Optional

from qgis.PyQt.QtCore import QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRectF, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPainter, QPainterPath, QPolygonF
from qgis.PyQt.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QHBoxLayout, QWidget

from .utils.fonts import ui_font
from .utils.logging_utils import log_exception


WALKER_TOOLTIP_STYLE = """
QLabel#WalkerTooltipLabel {
    background: transparent;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 500;
}
"""


class _WalkerTooltipPopup(QWidget):
    _ARROW_HEIGHT = 6

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setObjectName("WalkerTooltip")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet(WALKER_TOOLTIP_STYLE)
        self._arrow_on_top = False

        self._label = QLabel(self)
        self._label.setObjectName("WalkerTooltipLabel")
        self._label.setFont(ui_font(8))
        self._label.setAlignment(Qt.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7 + self._ARROW_HEIGHT)
        layout.setSpacing(0)
        layout.addWidget(self._label)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._move_animation: Optional[QPropertyAnimation] = None
        self._fade_animation: Optional[QPropertyAnimation] = None

    def show_for(self, anchor: QWidget, text: str) -> None:
        clean_text = str(text or "").strip()
        if not clean_text:
            self.hide()
            return

        self._label.setText(clean_text)
        self.adjustSize()

        target = self._target_position(anchor)
        start = QPoint(target.x(), target.y() + 8)
        self.move(start)
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()

        self._move_animation = QPropertyAnimation(self, b"pos", self)
        self._move_animation.setDuration(120)
        self._move_animation.setStartValue(start)
        self._move_animation.setEndValue(target)
        self._move_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._fade_animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_animation.setDuration(90)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)

        self._move_animation.start()
        self._fade_animation.start()

    def _target_position(self, anchor: QWidget) -> QPoint:
        center = anchor.mapToGlobal(anchor.rect().center())
        top = anchor.mapToGlobal(anchor.rect().topLeft()).y()
        x = center.x() - self.width() // 2
        y = top - self.height() - 6

        screen = QApplication.screenAt(center)
        rect = screen.availableGeometry() if screen is not None else QApplication.primaryScreen().availableGeometry()
        x = max(rect.left() + 4, min(x, rect.right() - self.width() - 4))
        if y < rect.top() + 4:
            bottom = anchor.mapToGlobal(anchor.rect().bottomLeft()).y()
            y = bottom + 6
            self._arrow_on_top = True
            self.layout().setContentsMargins(12, 7 + self._ARROW_HEIGHT, 12, 7)
        else:
            self._arrow_on_top = False
            self.layout().setContentsMargins(12, 7, 12, 7 + self._ARROW_HEIGHT)
        return QPoint(x, y)

    def paintEvent(self, event):  # noqa: N802 - Qt naming style
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#111111"))

        arrow = float(self._ARROW_HEIGHT)
        if self._arrow_on_top:
            body = QRectF(0, arrow, self.width(), self.height() - arrow)
            triangle = QPolygonF(
                [
                    QPoint(self.width() // 2 - 5, int(arrow)),
                    QPoint(self.width() // 2 + 5, int(arrow)),
                    QPoint(self.width() // 2, 0),
                ]
            )
        else:
            body = QRectF(0, 0, self.width(), self.height() - arrow)
            triangle = QPolygonF(
                [
                    QPoint(self.width() // 2 - 5, int(body.bottom())),
                    QPoint(self.width() // 2 + 5, int(body.bottom())),
                    QPoint(self.width() // 2, self.height()),
                ]
            )

        path = QPainterPath()
        path.addRoundedRect(body, 6, 6)
        path.addPolygon(triangle)
        painter.drawPath(path)


class _WalkerTooltipFilter(QObject):
    def __init__(self, widget: QWidget):
        super().__init__(widget)
        self.widget = widget
        self.popup: Optional[_WalkerTooltipPopup] = None
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_tooltip)

    def eventFilter(self, watched, event):  # noqa: N802 - Qt naming style
        if watched is not self.widget:
            return False
        event_type = event.type()
        if event_type == QEvent.Enter:
            self._show_timer.start(260)
            return False
        if event_type == QEvent.ToolTip:
            self._show_timer.start(0)
            return True
        if event_type in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.Hide, QEvent.Close, QEvent.FocusOut):
            self.hide()
        return False

    def _show_tooltip(self) -> None:
        if not self.widget.isVisible() or not self.widget.isEnabled():
            return
        text = str(self.widget.property("walkerTooltipText") or self.widget.toolTip() or "").strip()
        if not text:
            return
        if self.popup is None:
            self.popup = _WalkerTooltipPopup()
        self.popup.show_for(self.widget, text)

    def hide(self) -> None:
        self._show_timer.stop()
        if self.popup is not None:
            self.popup.hide()


def set_walker_tooltip(widget: Optional[QWidget], text: str) -> None:
    if widget is None:
        return
    try:
        widget.setProperty("walkerTooltipText", str(text or ""))
        widget.setToolTip("")
        if getattr(widget, "_walker_tooltip_filter", None) is None:
            event_filter = _WalkerTooltipFilter(widget)
            widget._walker_tooltip_filter = event_filter
            widget.installEventFilter(event_filter)
    except Exception:
        log_exception("falha opcional ignorada")


def install_walker_tooltip(widget: Optional[QWidget]) -> None:
    if widget is None:
        return
    try:
        text = str(widget.property("walkerTooltipText") or widget.toolTip() or "")
        set_walker_tooltip(widget, text)
    except Exception:
        log_exception("falha opcional ignorada")
