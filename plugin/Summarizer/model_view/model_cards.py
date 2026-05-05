from __future__ import annotations

from qgis.PyQt.QtCore import QEasingCurve, QPoint, QRectF, Qt, QVariantAnimation, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPen
from qgis.PyQt.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..utils.logging_utils import log_exception
from ..utils.resources import svg_icon
from .model_interactions import event_point


class _ModelCardAction(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, description: str, icon_name: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ModelActionCard")
        self.setCursor(Qt.PointingHandCursor)
        self._description = str(description or "")
        self._icon_name = str(icon_name or "")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(132)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self.icon_chip = QLabel("", self)
        self.icon_chip.setObjectName("ModelActionCardIcon")
        self.icon_chip.setFixedSize(34, 34)
        icon = svg_icon(self._icon_name) if self._icon_name else QIcon()
        if not icon.isNull():
            self.icon_chip.setPixmap(icon.pixmap(18, 18))
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
        self.description_label.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.description_label.setVisible(False)
        super().leaveEvent(event)


class _ModelRecentCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelRecentCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title, self)
        title_label.setObjectName("ModelRecentCardTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        text_label = QLabel(description, self)
        text_label.setObjectName("ModelRecentCardText")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

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
