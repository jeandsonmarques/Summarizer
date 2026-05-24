# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from qgis.PyQt.QtCore import QEasingCurve, QPoint, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..utils.logging_utils import log_exception
from ..utils.resources import svg_icon
from .model_interactions import event_point


class _ModelClockIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelRecentsClockIcon")
        self.setFixedSize(18, 18)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#6B7280"), 1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        rect = QRectF(2.0, 2.0, 14.0, 14.0)
        painter.drawEllipse(rect)
        center = QPointF(9.0, 9.0)
        painter.drawLine(center, QPointF(9.0, 5.2))
        painter.drawLine(center, QPointF(12.0, 10.5))


class _ModelElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__("", parent)
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self.setText(self._full_text)

    def setText(self, text: str):  # noqa: N802 - Qt override
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        metrics = self.fontMetrics()
        width = max(24, self.width() or self.sizeHint().width() or 120)
        super().setText(metrics.elidedText(self._full_text, Qt.ElideRight, width))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self._full_text)


class _ModelCardAction(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, description: str, icon_name: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ModelActionCard")
        self.setCursor(Qt.PointingHandCursor)
        self._description = str(description or "")
        self._icon_name = str(icon_name or "")
        self._connected = False
        if self._description:
            self.setToolTip(self._description)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.icon_chip = QLabel("", self)
        self.icon_chip.setObjectName("ModelActionCardIcon")
        self.icon_chip.setFixedSize(22, 22)
        icon = svg_icon(self._icon_name) if self._icon_name else QIcon()
        if not icon.isNull():
            self.icon_chip.setPixmap(icon.pixmap(20, 20))
            self.icon_chip.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.icon_chip, 0)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("ModelActionCardTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("ModelActionCardText")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(False)
        layout.addWidget(self.description_label)
        layout.addStretch(1)
        self._apply_card_style()

    def set_connected(self, connected: bool):
        self._connected = bool(connected)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._connected:
            return
        rect = self.icon_chip.geometry()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
        painter.setBrush(QColor("#22C55E"))
        painter.drawEllipse(QRectF(rect.right() - 4.0, rect.bottom() - 4.0, 8.0, 8.0))

    def _apply_card_style(self):
        self.setStyleSheet(
            """
            QFrame#ModelActionCard {
                background: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 10px;
            }
            QFrame#ModelActionCard:hover {
                background: #F7F7F7;
                border-color: #D5DAE1;
            }
            QLabel#ModelActionCardIcon {
                background: transparent;
                border: none;
            }
            QLabel#ModelActionCardTitle {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 16px;
                font-weight: 400;
            }
            QLabel#ModelActionCardText {
                background: transparent;
                border: none;
                color: #6B7280;
                font-size: 13px;
                font-weight: 400;
            }
            """
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)


class _ModelRecentFolderIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelRecentCardIcon")
        self.setFixedSize(48, 48)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#4B5563"), 2.0)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._folder_path())

    def _folder_path(self):
        path = QPainterPath()
        path.moveTo(8, 18)
        path.lineTo(18, 18)
        path.lineTo(22, 22)
        path.lineTo(40, 22)
        path.lineTo(40, 36)
        path.lineTo(8, 36)
        path.closeSubpath()
        return path


class _ModelRecentCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelRecentCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(212, 238)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(15, 23, 42, 28))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        preview = QFrame(self)
        preview.setObjectName("ModelRecentCardPreview")
        preview.setFixedHeight(126)
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        icon_widget = _ModelRecentFolderIcon(preview)
        preview_layout.addWidget(icon_widget, 1, Qt.AlignCenter)
        layout.addWidget(preview)

        content = QWidget(self)
        content.setObjectName("ModelRecentCardContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 12)
        content_layout.setSpacing(6)

        title_label = _ModelElidedLabel(title, content)
        title_label.setObjectName("ModelRecentCardTitle")
        content_layout.addWidget(title_label)

        text_label = _ModelElidedLabel(description, content)
        text_label.setObjectName("ModelRecentCardText")
        content_layout.addWidget(text_label)
        content_layout.addStretch(1)
        layout.addWidget(content)
        self._apply_card_style()

    def _apply_card_style(self):
        self.setStyleSheet(
            """
            QFrame#ModelRecentCard {
                background: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 10px;
            }
            QFrame#ModelRecentCard:hover {
                background: #F7F7F7;
                border-color: #D5DAE1;
            }
            QFrame#ModelRecentCardPreview {
                background: #F5F5F5;
                border: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QWidget#ModelRecentCardContent {
                background: #FFFFFF;
                border: none;
            }
            QLabel#ModelRecentCardIcon {
                background: transparent;
                border: none;
            }
            QLabel#ModelRecentCardTitle {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#ModelRecentCardText {
                background: transparent;
                border: none;
                color: #6B7280;
                font-size: 12px;
                font-weight: 400;
            }
            """
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mouseReleaseEvent(event)


class _DialogDragHandle(QFrame):
    def __init__(self, target: QDialog, parent=None):
        super().__init__(parent)
        self._target = target
        self._drag_active = False
        self._drag_offset = QPoint()
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_offset = (
                event_point(event, prefer_global=True) - self._target.frameGeometry().topLeft()
            )
            self.setCursor(Qt.ClosedHandCursor)
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active:
            self._target.move(event_point(event, prefer_global=True) - self._drag_offset)
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = False
            self.setCursor(Qt.OpenHandCursor)
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mouseReleaseEvent(event)


class _ModelModeToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = True
        self._thumb_pos = 1.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(34, 18)

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(170)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._handle_animation_step)

    def _handle_animation_step(self, value):
        try:
            self._thumb_pos = float(value)
        except Exception:
            self._thumb_pos = 1.0 if self._checked else 0.0
        self.update()

    def isChecked(self) -> bool:
        return bool(self._checked)

    def setChecked(self, checked: bool, animated: bool = True):
        checked = bool(checked)
        changed = checked != self._checked
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animated and self.isVisible():
            self._animation.stop()
            self._animation.setStartValue(float(self._thumb_pos))
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._thumb_pos = target
            self.update()
        if changed and not self.signalsBlocked():
            self.toggled.emit(self._checked)

    def _toggle(self):
        self.setChecked(not self._checked, animated=True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event_point(event)):
            self._toggle()
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self._toggle()
            try:
                event.accept()
            except Exception:
                log_exception("falha opcional ignorada")
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        try:
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except Exception:
            log_exception("falha opcional ignorada")
        painter.setPen(Qt.NoPen)
        track_rect = QRectF(
            0.5,
            0.5,
            float(max(1, self.width() - 1)),
            float(max(1, self.height() - 1)),
        )
        radius = track_rect.height() / 2.0

        track_on = QColor("#111827")
        track_off = QColor("#D1D5DB")
        border_on = QColor("#111827")
        border_off = QColor("#C7CDD6")
        if not self.isEnabled():
            track_on = QColor("#A3AAB5")
            track_off = QColor("#E5E7EB")
            border_on = QColor("#A3AAB5")
            border_off = QColor("#D1D5DB")

        active_track = track_on if self._checked else track_off
        active_border = border_on if self._checked else border_off
        if self.underMouse() and self.isEnabled() and not self._checked:
            active_track = QColor("#C7CDD6")

        painter.setPen(QPen(active_border, 1.0))
        painter.setBrush(active_track)
        painter.drawRoundedRect(track_rect, radius, radius)

        thumb_margin = 2.0
        thumb_diameter = track_rect.height() - (thumb_margin * 2.0)
        thumb_travel = max(0.0, track_rect.width() - thumb_diameter - (thumb_margin * 2.0))
        thumb_x = track_rect.left() + thumb_margin + (thumb_travel * float(self._thumb_pos))
        thumb_y = track_rect.top() + thumb_margin

        painter.setPen(QPen(QColor("#E5E7EB"), 0.8))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diameter, thumb_diameter))
