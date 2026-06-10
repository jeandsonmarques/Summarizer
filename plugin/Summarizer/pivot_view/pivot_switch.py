# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from qgis.PyQt.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPainter, QPen
from qgis.PyQt.QtWidgets import QWidget


def _is_dark_theme() -> bool:
    from qgis.PyQt.QtCore import QSettings

    theme_name = str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower()
    return theme_name == "dark"


class PivotSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._pressed = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(30, 16)
        self._handle_position = 0.0
        self._animation = QPropertyAnimation(self, b"handlePosition", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return self.size()

    def _get_handle_position(self) -> float:
        return float(self._handle_position)

    def _set_handle_position(self, value: float):
        self._handle_position = max(0.0, min(1.0, float(value)))
        self.update()

    handlePosition = pyqtProperty(float, fget=_get_handle_position, fset=_set_handle_position)

    def isChecked(self) -> bool:
        return bool(self._checked)

    def setChecked(self, checked: bool):
        self.set_checked_state(checked, animated=False)

    def set_checked_state(self, checked: bool, *, animated: bool = True):
        target = bool(checked)
        changed = target != self._checked
        self._checked = target
        if animated:
            self._animate_handle(target)
        else:
            self._animation.stop()
            self._set_handle_position(1.0 if target else 0.0)
        if changed and not self.signalsBlocked():
            self.toggled.emit(self._checked)

    def _toggle(self):
        self.set_checked_state(not self._checked, animated=True)

    def _animate_handle(self, checked: bool):
        target = 1.0 if checked else 0.0
        self._animation.stop()
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(target)
        self._animation.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        was_pressed = self._pressed
        self._pressed = False
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            if was_pressed:
                self._toggle()
            event.accept()
            return
        self.update()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._pressed:
            self._pressed = False
            self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception:
            pass

        inset = 2.0 if self._pressed else 1.0
        track_rect = QRectF(
            inset,
            inset,
            float(max(1, self.width() - inset * 2)),
            float(max(1, self.height() - inset * 2)),
        )
        radius = track_rect.height() / 2.0

        track_on = QColor("#1F2937")
        track_off = QColor("#D8DEE8")
        border_on = QColor("#111827")
        border_off = QColor("#C9D0DA")
        if not self.isEnabled():
            track_on = QColor("#A3AAB5")
            track_off = QColor("#E5E7EB")
            border_on = QColor("#A3AAB5")
            border_off = QColor("#D1D5DB")

        active_track = track_on if self.isChecked() else track_off
        active_border = border_on if self.isChecked() else border_off
        if self.underMouse() and self.isEnabled() and not self.isChecked():
            active_track = QColor("#C7CDD6")
        if self._pressed and self.isEnabled():
            active_track = QColor("#374151") if self.isChecked() else QColor("#BCC5D1")
            active_border = QColor("#475569")

        if self.isEnabled() and (self.underMouse() or self._pressed):
            halo = QColor("#7C6CFF" if self.isChecked() else "#64748B")
            halo.setAlpha(70 if self._pressed else 42)
            painter.setPen(QPen(halo, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                track_rect.adjusted(-1.0, -1.0, 1.0, 1.0),
                radius + 1.0,
                radius + 1.0,
            )

        painter.setPen(QPen(active_border, 1.0))
        painter.setBrush(active_track)
        painter.drawRoundedRect(track_rect, radius, radius)

        knob_size = track_rect.height() - (4.5 if self._pressed else 4.0)
        min_x = track_rect.left() + 2.0
        max_x = track_rect.left() + track_rect.width() - knob_size - 2.0
        knob_x = min_x + (max_x - min_x) * self._handle_position
        knob_y = track_rect.top() + (track_rect.height() - knob_size) / 2.0
        knob_rect = QRectF(knob_x, knob_y, knob_size, knob_size)
        if self._pressed:
            glow = QColor("#FFFFFF")
            glow.setAlpha(70)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(knob_rect.adjusted(-1.0, -1.0, 1.0, 1.0))
        painter.setPen(QPen(QColor("#475569" if _is_dark_theme() else "#D7DEE8"), 0.8))
        painter.setBrush(QColor("#F8FAFC" if _is_dark_theme() else "#FFFFFF"))
        painter.drawEllipse(knob_rect)
        painter.end()
