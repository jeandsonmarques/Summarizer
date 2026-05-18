from __future__ import annotations

import copy
from typing import Optional

from qgis.PyQt.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSettings, Qt, pyqtProperty, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPainter, QPalette, QPen
from qgis.PyQt.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QAbstractSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .dashboard_item_widget import VisualPropertiesDialog
from .report_view.charts import ChartVisualState
from .utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font


def _rt(text: str) -> str:
    return str(text or "")


def _is_dark_theme() -> bool:
    try:
        return str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower() == "dark"
    except Exception:
        return False


def _panel_color(name: str) -> str:
    dark = {
        "app": "#0B1020",
        "surface": "#111827",
        "surface_2": "#172033",
        "surface_hover": "#1F2A3D",
        "border": "#334155",
        "border_hover": "#475569",
        "text": "#F8FAFC",
        "muted": "#CBD5E1",
        "disabled": "#64748B",
        "checked": "#312E81",
        "checked_border": "#7C6CFF",
    }
    light = {
        "app": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_2": "#F8FAFC",
        "surface_hover": "#F8FAFC",
        "border": "#CBD5E1",
        "border_hover": "#94A3B8",
        "text": "#334155",
        "muted": "#667085",
        "disabled": "#94A3B8",
        "checked": "#E0F2FE",
        "checked_border": "#38BDF8",
    }
    return (dark if _is_dark_theme() else light).get(name, light["surface"])


def _force_panel_white_background(widget: QWidget):
    widget.setAttribute(Qt.WA_StyledBackground, True)
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    color = QColor(_panel_color("surface"))
    alternate = QColor(_panel_color("surface_2"))
    palette.setColor(widget.backgroundRole(), color)
    palette.setColor(QPalette.Window, color)
    palette.setColor(QPalette.Base, color)
    palette.setColor(QPalette.AlternateBase, alternate)
    widget.setPalette(palette)


def _force_transparent_background(widget: QWidget):
    widget.setAttribute(Qt.WA_StyledBackground, False)
    widget.setAutoFillBackground(False)
    palette = widget.palette()
    transparent = QColor(0, 0, 0, 0)
    palette.setColor(widget.backgroundRole(), transparent)
    palette.setColor(QPalette.Window, transparent)
    palette.setColor(QPalette.Base, transparent)
    widget.setPalette(palette)


class _ColorButton(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = "#FFFFFF"
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(86)
        self.set_color(color)
        self.clicked.connect(self._pick_color)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str):
        candidate = QColor(str(color or ""))
        if not candidate.isValid():
            candidate = QColor("#FFFFFF")
        self._color = candidate.name().upper()
        self.setText(self._color)
        text_color = "#FFFFFF" if candidate.lightness() < 120 else "#111827"
        self.setStyleSheet(
            "QPushButton {"
            f"background: {self._color}; color: {text_color};"
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px 8px;"
            "}"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, _rt("Escolher cor"))
        if color.isValid():
            self.set_color(color.name())


class _Switch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._pressed = False
        _force_transparent_background(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(30, 16)
        self._handle_position = 0.0
        self._animation = QPropertyAnimation(self, b"handlePosition", self)
        self._animation.setDuration(160)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

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
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        was_pressed = self._pressed
        self._pressed = False
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
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
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self._toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except Exception:
            pass
        inset = 2.0 if self._pressed else 1.0
        track_rect = QRectF(inset, inset, float(max(1, self.width() - inset * 2)), float(max(1, self.height() - inset * 2)))
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
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track_rect.adjusted(-1.0, -1.0, 1.0, 1.0), radius + 1.0, radius + 1.0)

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
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(knob_rect.adjusted(-1.0, -1.0, 1.0, 1.0))
        painter.setPen(QPen(QColor("#475569" if _is_dark_theme() else "#D7DEE8"), 0.8))
        painter.setBrush(QColor("#F8FAFC" if _is_dark_theme() else "#FFFFFF"))
        painter.drawEllipse(knob_rect)
        painter.end()


class _SectionHeader(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisualPanelSectionHeader")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setFrameShadow(QFrame.Plain)
        self.setLineWidth(0)
        self.setMinimumHeight(29)
        self.setMaximumHeight(29)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            child = self.childAt(event.pos())
            while child is not None and child is not self:
                if isinstance(child, _Switch):
                    return super().mouseReleaseEvent(event)
                child = child.parent()
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0.5, 0.5, float(max(1, self.width() - 1)), float(max(1, self.height() - 1)))
        border = QColor(_panel_color("border"))
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 5.0, 5.0)
        painter.end()


class _SectionArrowLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisualPanelSectionArrow")
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(14, 16)
        self.setProperty("expanded", False)

    def set_expanded(self, expanded: bool):
        self.setProperty("expanded", bool(expanded))
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(_panel_color("muted"))
        pen = QPen(color, 1.05)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        if bool(self.property("expanded")):
            painter.drawLine(5, 6, 7, 9)
            painter.drawLine(7, 9, 9, 6)
        else:
            painter.drawLine(5, 5, 8, 8)
            painter.drawLine(8, 8, 5, 11)
        painter.end()


class _PanelSection(QFrame):
    def __init__(self, title: str, parent=None, *, expanded: bool = False):
        super().__init__(parent)
        self.setObjectName("VisualPanelSection")
        _force_panel_white_background(self)
        self._title = str(title or "")
        self._expanded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = _SectionHeader(self)
        self.header.clicked.connect(lambda: self.set_expanded(not self._expanded))
        header = self.header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 1, 5, 1)
        header_layout.setSpacing(4)

        self.arrow_label = _SectionArrowLabel(header)
        header_layout.addWidget(self.arrow_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel(str(title or ""), header)
        self.title_label.setObjectName("VisualPanelSectionTitle")
        self.title_label.setAttribute(Qt.WA_StyledBackground, False)
        self.title_label.setAutoFillBackground(False)
        self.title_label.setFocusPolicy(Qt.NoFocus)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(self.title_label, 1, Qt.AlignVCenter)

        self.header_switch = _Switch(header)
        self.header_switch.setVisible(False)
        header_layout.addWidget(self.header_switch, 0, Qt.AlignVCenter)
        layout.addWidget(header)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("VisualPanelSectionContent")
        _force_panel_white_background(self.content_frame)
        self.content_frame.setFrameShape(QFrame.NoFrame)
        self.content_frame.setFrameShadow(QFrame.Plain)
        self.content_frame.setLineWidth(0)
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(1, 0, 1, 1)
        content_layout.setSpacing(0)

        self.body = QWidget(self.content_frame)
        self.body.setObjectName("VisualPanelSectionBody")
        _force_panel_white_background(self.body)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(6, 4, 6, 6)
        self.body_layout.setSpacing(4)
        content_layout.addWidget(self.body)
        layout.addWidget(self.content_frame)
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool):
        self._expanded = bool(expanded)
        self.arrow_label.set_expanded(self._expanded)
        self.content_frame.setVisible(self._expanded)
        for widget in (self.header, self.content_frame):
            widget.setProperty("expanded", self._expanded)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def configure_switch(self, *, visible: bool, checked: bool = False, callback=None):
        self.header_switch.setVisible(bool(visible))
        self.header_switch.set_checked_state(bool(checked), animated=False)
        try:
            self.header_switch.toggled.disconnect()
        except Exception:
            pass
        if callback is not None:
            self.header_switch.toggled.connect(callback)


class VisualFormatPanel(QFrame):
    closeRequested = pyqtSignal()
    visualStateChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VisualFormatPanel")
        self.setFont(ui_font())
        self._font_enforcer = attach_ui_font_enforcer(self)
        _force_panel_white_background(self)
        self.setMinimumWidth(240)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._current_item_widget = None
        self._loading = False
        self._controls = {}
        self._palette_buttons = []
        self._custom_presets = {}
        self._sections = {}
        self._section_groups = {}
        self._section_toggles = {}
        self._active_view = "visual"
        self._build_ui()
        harmonize_widget_fonts(self)
        self.clear_selection()

    def _refresh_widget_palette(self):
        widgets = [self]
        try:
            widgets.extend(self.findChildren(QWidget))
        except Exception:
            widgets = [self]
        for widget in widgets:
            try:
                object_name = str(widget.objectName() or "")
                if object_name in {"VisualPanelSectionHeader", "VisualPanelSectionArrow", "VisualPanelSectionTitle"} or isinstance(widget, _Switch):
                    _force_transparent_background(widget)
                else:
                    _force_panel_white_background(widget)
                widget.setProperty("themeMode", "dark" if _is_dark_theme() else "light")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            except Exception:
                continue

    def _apply_panel_styles(self):
        self._refresh_widget_palette()
        scroll_style = """
            QScrollArea#VisualPanelScroll {
                background: __SURFACE__;
                background-color: __SURFACE__;
                border: none;
            }
            QScrollArea#VisualPanelScroll QWidget,
            QScrollArea#VisualPanelScroll QFrame,
            QScrollArea#VisualPanelScroll QAbstractScrollArea,
            QScrollArea#VisualPanelScroll QAbstractScrollArea::viewport {
                background: __SURFACE__;
                background-color: __SURFACE__;
            }
            """
        if hasattr(self, "scroll"):
            self.scroll.setStyleSheet(scroll_style.replace("__SURFACE__", _panel_color("surface")))
            try:
                self.scroll.viewport().setStyleSheet(
                    f"background: {_panel_color('surface')}; background-color: {_panel_color('surface')};"
                )
            except Exception:
                pass
        if hasattr(self, "form_host"):
            self.form_host.setStyleSheet(
                f"QWidget#VisualPanelFormHost {{ background: {_panel_color('surface')}; background-color: {_panel_color('surface')}; }}"
            )
        panel_style = """
            QFrame#VisualFormatPanel,
            QFrame#VisualFormatPanel QWidget,
            QFrame#VisualFormatPanel QFrame,
            QFrame#VisualFormatPanel QScrollArea,
            QFrame#VisualFormatPanel QAbstractScrollArea,
            QFrame#VisualFormatPanel QAbstractScrollArea::viewport {
                background: __SURFACE__;
                background-color: __SURFACE__;
                color: __TEXT__;
            }
            QFrame#VisualFormatPanel {
                border: 1px solid __BORDER__;
                border-radius: 6px;
            }
            QLabel#VisualPanelTitle,
            QLabel#VisualPanelSectionTitle {
                color: __TEXT__;
                background: transparent;
                background-color: transparent;
                border: none;
                font-weight: 400;
            }
            QLabel,
            QLabel#VisualPanelSubtitle,
            QLabel#VisualPanelEmpty,
            QLabel#VisualPanelSectionArrow {
                color: __MUTED__;
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QFrame#VisualPanelSectionHeader QLabel,
            QFrame#VisualPanelSectionHeader QWidget {
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QLineEdit,
            QComboBox,
            QSpinBox#VisualPanelSpin {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE_2__;
                color: __TEXT__;
                padding: 2px 6px;
                min-height: 18px;
                font-size: 8px;
                selection-background-color: __CHECKED__;
                selection-color: __TEXT__;
            }
            QComboBox QAbstractItemView {
                background: __SURFACE_2__;
                color: __TEXT__;
                border: 1px solid __BORDER__;
                selection-background-color: __CHECKED__;
                selection-color: __TEXT__;
            }
            QPushButton,
            QPushButton#VisualPanelTabButton,
            QPushButton#VisualPanelPresetButton {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE__;
                color: __TEXT__;
                padding: 2px 6px;
                min-height: 18px;
                font-weight: 400;
            }
            QPushButton:hover,
            QPushButton#VisualPanelPresetButton:hover {
                background: __SURFACE_HOVER__;
                border-color: __BORDER_HOVER__;
            }
            QPushButton:checked,
            QPushButton#VisualPanelTabButton:checked {
                background: __CHECKED__;
                border-color: __CHECKED_BORDER__;
                color: __TEXT__;
            }
            QPushButton:disabled,
            QPushButton#VisualPanelPresetButton:disabled {
                background: __SURFACE_2__;
                border-color: __BORDER__;
                color: __DISABLED__;
            }
            QFrame#VisualPanelSectionHeader {
                border: none;
                border-radius: 5px;
                min-height: 29px;
                max-height: 29px;
            }
            QFrame#VisualPanelSectionContent {
                border: none;
                border-radius: 0px;
                background: __SURFACE__;
            }
        """
        panel_style = (
            panel_style.replace("__SURFACE_HOVER__", _panel_color("surface_hover"))
            .replace("__BORDER_HOVER__", _panel_color("border_hover"))
            .replace("__CHECKED_BORDER__", _panel_color("checked_border"))
            .replace("__CHECKED__", _panel_color("checked"))
            .replace("__SURFACE_2__", _panel_color("surface_2"))
            .replace("__DISABLED__", _panel_color("disabled"))
            .replace("__SURFACE__", _panel_color("surface"))
            .replace("__BORDER__", _panel_color("border"))
            .replace("__MUTED__", _panel_color("muted"))
            .replace("__TEXT__", _panel_color("text"))
        )
        self.setStyleSheet(panel_style)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(1)
        self.title_label = QLabel("", self)
        self.title_label.setObjectName("VisualPanelTitle")
        self.title_label.setFont(ui_font())
        self.title_label.hide()
        self.item_label = QLabel("", self)
        self.item_label.setObjectName("VisualPanelSubtitle")
        self.item_label.setFont(ui_font())
        self.item_label.setWordWrap(True)
        title_column.addWidget(self.item_label)
        header.addLayout(title_column, 1)

        root.addLayout(header)

        self.empty_label = QLabel(
            _rt("Selecione um visual para editar suas propriedades."),
            self,
        )
        self.empty_label.setObjectName("VisualPanelEmpty")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("VisualPanelScroll")
        _force_panel_white_background(self.scroll)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.viewport().setObjectName("VisualPanelScrollViewport")
        _force_panel_white_background(self.scroll.viewport())
        self.form_host = QWidget(self.scroll)
        self.form_host.setObjectName("VisualPanelFormHost")
        _force_panel_white_background(self.form_host)
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(6)
        self._build_sections()
        bottom_spacer = QWidget(self.form_host)
        bottom_spacer.setObjectName("VisualPanelBottomSpacer")
        _force_panel_white_background(bottom_spacer)
        self.form_layout.addWidget(bottom_spacer, 1)
        self.scroll.setWidget(self.form_host)
        root.addWidget(self.scroll, 1)
        self._apply_panel_styles()

        panel_style = """
            QFrame#VisualFormatPanel {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 6px;
            }
            QFrame#VisualFormatPanel QWidget,
            QFrame#VisualFormatPanel QFrame,
            QFrame#VisualFormatPanel QScrollArea,
            QFrame#VisualFormatPanel QAbstractScrollArea,
            QFrame#VisualFormatPanel QAbstractScrollArea::viewport {
                background-color: __SURFACE__;
            }
            QScrollArea#VisualPanelScroll,
            QWidget#VisualPanelScrollViewport,
            QWidget#VisualPanelFormHost {
                background: __SURFACE__;
                border: none;
            }
            QLabel#VisualPanelEmpty {
                background: transparent;
            }
            QLabel#VisualPanelTitle {
                color: __TEXT__;
                font-size: 9px;
                font-weight: 400;
            }
            QLabel#VisualPanelSubtitle,
            QLabel#VisualPanelEmpty {
                color: __MUTED__;
                font-size: 8px;
            }
            QPushButton#VisualPanelTabButton {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE__;
                color: __TEXT__;
                padding: 3px 8px;
                font-weight: 400;
                min-height: 22px;
            }
            QPushButton#VisualPanelTabButton:checked {
                background: __CHECKED__;
                border-color: __CHECKED_BORDER__;
                color: __TEXT__;
            }
            QLabel {
                color: __MUTED__;
                font-size: 8px;
                font-weight: 400;
            }
            QFrame#VisualPanelSectionHeader QLabel,
            QFrame#VisualPanelSectionHeader QLabel:hover,
            QFrame#VisualPanelSectionHeader QWidget,
            QFrame#VisualPanelSectionHeader QWidget:hover {
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QFrame#VisualPanelSection {
                border: none;
                background: __SURFACE__;
            }
            QFrame#VisualPanelSectionHeader {
                border: none;
                border-radius: 5px;
                background: transparent;
                background-color: transparent;
                min-height: 29px;
                max-height: 29px;
            }
            QFrame#VisualPanelSectionHeader[expanded="true"] {
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border: none;
            }
            QLabel#VisualPanelSectionArrow {
                color: __MUTED__;
                background: transparent;
                background-color: transparent;
                border: none;
                font-size: 9px;
                font-weight: 400;
                min-width: 14px;
                max-width: 14px;
                min-height: 16px;
                max-height: 16px;
            }
            QLabel#VisualPanelSectionTitle {
                color: __MUTED__;
                background: transparent;
                background-color: transparent;
                border: none;
                font-size: 8px;
                font-weight: 400;
            }
            QFrame#VisualPanelSectionContent {
                border: none;
                border-radius: 0px;
                background: __SURFACE__;
            }
            QWidget#VisualPanelSectionBody {
                background: __SURFACE__;
            }
            QLineEdit,
            QComboBox,
            QSpinBox#VisualPanelSpin {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE_2__;
                color: __TEXT__;
                padding: 2px 6px;
                min-height: 18px;
                font-size: 8px;
                selection-background-color: __CHECKED__;
                selection-color: __TEXT__;
            }
            QComboBox QAbstractItemView {
                background: __SURFACE_2__;
                color: __TEXT__;
                border: 1px solid __BORDER__;
                selection-background-color: __CHECKED__;
                selection-color: __TEXT__;
            }
            QSpinBox#VisualPanelSpin::up-button,
            QSpinBox#VisualPanelSpin::down-button,
            QSpinBox#VisualPanelSpin::up-arrow,
            QSpinBox#VisualPanelSpin::down-arrow {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }
            QPushButton {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE__;
                color: __TEXT__;
                padding: 2px 6px;
                min-height: 18px;
                font-weight: 400;
            }
            QPushButton:hover {
                background: __SURFACE_HOVER__;
                border-color: __BORDER_HOVER__;
            }
            QPushButton:pressed {
                background: __SURFACE_2__;
            }
            QPushButton#VisualPanelPresetButton {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE__;
                color: __TEXT__;
                padding: 3px 8px;
                min-height: 18px;
                max-height: 20px;
                font-size: 8px;
                font-weight: 400;
            }
            QPushButton#VisualPanelPresetButton:hover {
                background: __SURFACE_HOVER__;
                border-color: __BORDER_HOVER__;
            }
            QPushButton#VisualPanelPresetButton:pressed {
                background: __SURFACE_2__;
            }
            QPushButton#VisualPanelPresetButton:disabled {
                background: __SURFACE_2__;
                border-color: __BORDER__;
                color: __DISABLED__;
            }
            """
        panel_style = (
            panel_style.replace("__SURFACE_HOVER__", _panel_color("surface_hover"))
            .replace("__BORDER_HOVER__", _panel_color("border_hover"))
            .replace("__CHECKED_BORDER__", _panel_color("checked_border"))
            .replace("__CHECKED__", _panel_color("checked"))
            .replace("__SURFACE_2__", _panel_color("surface_2"))
            .replace("__DISABLED__", _panel_color("disabled"))
            .replace("__SURFACE__", _panel_color("surface"))
            .replace("__BORDER__", _panel_color("border"))
            .replace("__MUTED__", _panel_color("muted"))
            .replace("__TEXT__", _panel_color("text"))
        )
        self.setStyleSheet(panel_style)
        preset_button_style = """
            QPushButton#VisualPanelPresetButton {
                border: 1px solid __BORDER__;
                border-radius: 4px;
                background: __SURFACE__;
                color: __TEXT__;
                padding: 2px 6px;
                min-height: 18px;
                max-height: 20px;
                font-size: 8px;
                font-weight: 400;
            }
            QPushButton#VisualPanelPresetButton:hover {
                background: __SURFACE_HOVER__;
                border-color: __BORDER_HOVER__;
            }
            QPushButton#VisualPanelPresetButton:disabled {
                background: __SURFACE_2__;
                border-color: __BORDER__;
                color: __DISABLED__;
            }
        """
        preset_button_style = (
            preset_button_style.replace("__SURFACE_HOVER__", _panel_color("surface_hover"))
            .replace("__BORDER_HOVER__", _panel_color("border_hover"))
            .replace("__SURFACE_2__", _panel_color("surface_2"))
            .replace("__DISABLED__", _panel_color("disabled"))
            .replace("__SURFACE__", _panel_color("surface"))
            .replace("__BORDER__", _panel_color("border"))
            .replace("__TEXT__", _panel_color("text"))
        )
        for button in (
            getattr(self, "apply_preset_btn", None),
            getattr(self, "save_preset_btn", None),
            getattr(self, "delete_preset_btn", None),
        ):
            if button is not None:
                button.setStyleSheet(preset_button_style)
        self._apply_panel_styles()
        self._set_active_view("visual")

    def _finish_build_styles(self):
        self._apply_panel_styles()
        self._set_active_view("visual")

    def _build_sections(self):
        self._build_properties_section()
        self._build_general_section()
        self._build_grid_section()
        self._build_axis_section()
        self._build_title_section()
        self._build_effects_section()
        self._build_shadow_section()
        self._build_text_section()
        self._build_number_section()
        self._build_colors_section()
        self._build_legend_section()
        self._build_shape_section()
        self._build_visual_options_section()
        self._build_presets_section()
        self._build_card_section()
        self._build_accessibility_section()
        self._connect_live_updates()

    def _create_section(self, key: str, title: str, *, view: str, expanded: bool, toggle_key: Optional[str] = None):
        section = _PanelSection(_rt(title), self.form_host, expanded=expanded)
        if toggle_key:
            self._controls[toggle_key] = section.header_switch
            self._section_toggles[key] = toggle_key
            section.configure_switch(visible=True, checked=False)
        self._sections[key] = section
        self._section_groups[key] = view
        self.form_layout.addWidget(section)
        return section

    def _set_active_view(self, view: str):
        current = str(view or "visual").strip().lower()
        if current not in {"visual", "general"}:
            current = "visual"
        self._active_view = current
        self._apply_section_filter("")

    def _current_chart_type(self) -> str:
        item_widget = self._current_item_widget
        if item_widget is None:
            return ""
        state = self._item_visual_state(item_widget)
        return str(getattr(state, "chart_type", "") or getattr(item_widget.item.payload, "chart_type", "") or "").strip().lower()

    def _visible_sections_for_current_view(self) -> set:
        return {
            "properties",
            "general",
            "title",
            "effects",
            "shadow",
            "grid",
            "axis",
            "text",
            "number",
            "colors",
            "legend",
            "shape",
            "options",
            "presets",
            "card",
            "accessibility",
        }

    def _apply_section_filter(self, text: str = ""):
        visible_keys = self._visible_sections_for_current_view()
        for key, section in self._sections.items():
            section.setVisible(key in visible_keys)

    def _form_layout(self) -> QFormLayout:
        form = QFormLayout()
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(4)
        form.setHorizontalSpacing(6)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return form

    def _switch_row(self, label: str, key: str, parent) -> QWidget:
        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        text = QLabel(_rt(label), row)
        layout.addWidget(text, 1)
        switch = _Switch(row)
        self._controls[key] = switch
        layout.addWidget(switch, 0, Qt.AlignVCenter)
        return row

    def _combo(self, parent, items):
        combo = QComboBox(parent)
        for label, value in list(items or []):
            combo.addItem(_rt(label), value)
        return combo

    def _build_properties_section(self):
        group = self._create_section("properties", "Propriedades", view="general", expanded=True)
        form = self._form_layout()
        self._controls["layout_width"] = self._spin(120, 4000, group)
        self._controls["layout_height"] = self._spin(120, 4000, group)
        self._controls["layout_x"] = self._spin(0, 4000, group)
        self._controls["layout_y"] = self._spin(0, 4000, group)
        form.addRow(_rt("Largura"), self._controls["layout_width"])
        form.addRow(_rt("Altura"), self._controls["layout_height"])
        form.addRow(_rt("Posicao X"), self._controls["layout_x"])
        form.addRow(_rt("Posicao Y"), self._controls["layout_y"])
        group.body_layout.addLayout(form)

    def _build_general_section(self):
        group = self._create_section("general", "Preenchimento", view="general", expanded=False, toggle_key="show_background")
        form = self._form_layout()
        self._controls["background_color"] = _ColorButton("#FFFFFF", group)
        self._controls["background_opacity"] = self._spin(0, 100, group)
        form.addRow(_rt("Cor de fundo"), self._controls["background_color"])
        form.addRow(_rt("Opacidade"), self._controls["background_opacity"])
        group.body_layout.addLayout(form)

    def _build_grid_section(self):
        group = self._create_section("grid", "Grade", view="visual", expanded=False, toggle_key="show_grid")
        form = self._form_layout()
        self._controls["grid_color"] = _ColorButton("#E5E7EB", group)
        self._controls["grid_width"] = self._spin(1, 4, group)
        self._controls["grid_opacity"] = self._spin(0, 100, group)
        form.addRow(_rt("Cor"), self._controls["grid_color"])
        form.addRow(_rt("Espessura"), self._controls["grid_width"])
        form.addRow(_rt("Opacidade"), self._controls["grid_opacity"])
        group.body_layout.addLayout(form)

    def _build_axis_section(self):
        group = self._create_section("axis", "Eixo", view="visual", expanded=False, toggle_key="show_axis_labels")
        form = self._form_layout()
        self._controls["axis_label_color"] = _ColorButton("#4B5563", group)
        self._controls["axis_label_size"] = self._spin(0, 36, group)
        self._controls["zero_line_color"] = _ColorButton("#CBD5E1", group)
        form.addRow(_rt("Cor dos nomes"), self._controls["axis_label_color"])
        form.addRow(_rt("Tam. nomes"), self._controls["axis_label_size"])
        form.addRow("", self._switch_row("Linha zero", "show_zero_line", group))
        form.addRow(_rt("Cor linha zero"), self._controls["zero_line_color"])
        group.body_layout.addLayout(form)

    def _build_title_section(self):
        group = self._create_section("title", "Titulo", view="general", expanded=False, toggle_key="show_title")
        form = self._form_layout()
        self._controls["title_override"] = QLineEdit(group)
        self._controls["title_color"] = _ColorButton("#1F2937", group)
        self._controls["title_size"] = self._spin(0, 48, group)
        align_combo = self._combo(
            group,
            [
                ("Esquerda", "left"),
                ("Centro", "center"),
                ("Direita", "right"),
            ],
        )
        self._controls["text_align"] = align_combo
        form.addRow(_rt("Titulo"), self._controls["title_override"])
        form.addRow(_rt("Cor"), self._controls["title_color"])
        form.addRow(_rt("Tamanho"), self._controls["title_size"])
        form.addRow(_rt("Alinhamento"), align_combo)
        group.body_layout.addLayout(form)

    def _build_effects_section(self):
        group = self._create_section("effects", "Borda", view="general", expanded=False, toggle_key="show_border")
        form = self._form_layout()
        self._controls["border_color"] = _ColorButton("#CBD5E1", group)
        self._controls["border_width"] = self._spin(1, 6, group)
        self._controls["border_radius"] = self._spin(0, 32, group)
        self._controls["padding"] = self._spin(0, 40, group)
        form.addRow(_rt("Cor da borda"), self._controls["border_color"])
        form.addRow(_rt("Espessura"), self._controls["border_width"])
        form.addRow(_rt("Raio"), self._controls["border_radius"])
        form.addRow(_rt("Padding"), self._controls["padding"])
        group.body_layout.addLayout(form)

    def _build_shadow_section(self):
        group = self._create_section("shadow", "Efeitos", view="general", expanded=False, toggle_key="shadow_enabled")
        form = self._form_layout()
        self._controls["shadow_opacity"] = self._spin(0, 60, group)
        form.addRow(_rt("Sombra"), self._controls["shadow_opacity"])
        group.body_layout.addLayout(form)

    def _build_text_section(self):
        group = self._create_section("text", "Rotulos de dados", view="visual", expanded=False, toggle_key="show_values")
        form = self._form_layout()
        self._controls["label_color"] = _ColorButton("#4B5563", group)
        self._controls["label_size"] = self._spin(0, 36, group)
        position_combo = self._combo(
            group,
            [
                ("Fora", "outside"),
                ("Dentro", "inside"),
                ("Auto", "auto"),
            ],
        )
        self._controls["data_label_position"] = position_combo
        form.addRow("", self._switch_row("Percentual", "show_percent", group))
        form.addRow(_rt("Cor dos rotulos"), self._controls["label_color"])
        form.addRow(_rt("Tam. rotulos"), self._controls["label_size"])
        form.addRow(_rt("Posicao"), position_combo)
        group.body_layout.addLayout(form)

    def _build_number_section(self):
        group = self._create_section("number", "Formato de dados", view="visual", expanded=False)
        form = self._form_layout()
        self._controls["number_prefix"] = QLineEdit(group)
        self._controls["number_suffix"] = QLineEdit(group)
        self._controls["decimal_places"] = self._spin(0, 8, group)
        unit_combo = self._combo(
            group,
            [
                ("Nenhuma", "none"),
                ("Auto", "auto"),
                ("Milhar", "thousand"),
                ("Milhao", "million"),
            ],
        )
        self._controls["display_units"] = unit_combo
        self._controls["null_value"] = QLineEdit(group)
        form.addRow(_rt("Prefixo"), self._controls["number_prefix"])
        form.addRow(_rt("Sufixo"), self._controls["number_suffix"])
        form.addRow(_rt("Casas decimais"), self._controls["decimal_places"])
        form.addRow(_rt("Unidades"), unit_combo)
        form.addRow(_rt("Valor nulo"), self._controls["null_value"])
        group.body_layout.addLayout(form)

    def _build_colors_section(self):
        group = self._create_section("colors", "Cores", view="visual", expanded=False)
        grid = QGridLayout()
        grid.setContentsMargins(10, 12, 10, 10)
        grid.setSpacing(7)
        palette_combo = self._combo(
            group,
            [
                ("Padrao", "default"),
                ("Cor unica", "single"),
                ("Por categoria", "category"),
                ("Personalizada", "custom"),
                ("Roxa", "purple"),
                ("Azul", "blue"),
                ("Teal", "teal"),
                ("Sunset", "sunset"),
                ("Cinza", "grayscale"),
            ],
        )
        self._controls["palette"] = palette_combo
        self._controls["primary_color"] = _ColorButton("#5A3FE6", group)
        grid.addWidget(QLabel(_rt("Paleta"), group), 0, 0)
        grid.addWidget(palette_combo, 0, 1)
        grid.addWidget(QLabel(_rt("Cor principal"), group), 1, 0)
        grid.addWidget(self._controls["primary_color"], 1, 1)
        palette_defaults = ["#2B7DE9", "#F2C811", "#2FB26A", "#F2994A"]
        for index, color in enumerate(palette_defaults):
            button = _ColorButton(color, group)
            self._palette_buttons.append(button)
            grid.addWidget(QLabel(f"{_rt('Cor')} {index + 1}", group), index + 2, 0)
            grid.addWidget(button, index + 2, 1)
        group.body_layout.addLayout(grid)

    def _build_legend_section(self):
        group = self._create_section("legend", "Legenda", view="visual", expanded=False, toggle_key="show_legend")
        form = self._form_layout()
        self._controls["legend_label_override"] = QLineEdit(group)
        form.addRow(_rt("Titulo"), self._controls["legend_label_override"])
        group.body_layout.addLayout(form)

    def _build_visual_options_section(self):
        group = self._create_section("options", "Opcoes", view="visual", expanded=False)
        form = self._form_layout()
        sort_combo = self._combo(
            group,
            [
                ("Padrao", "default"),
                ("Crescente", "asc"),
                ("Decrescente", "desc"),
            ],
        )
        corners_combo = self._combo(
            group,
            [
                ("Retos", "square"),
                ("Arredondados", "rounded"),
            ],
        )
        font_combo = self._combo(
            group,
            [
                ("Pequena", "0.82"),
                ("Normal", "1.0"),
                ("Grande", "1.18"),
                ("Ampliada", "1.38"),
            ],
        )
        self._controls["sort_mode"] = sort_combo
        self._controls["bar_corner_style"] = corners_combo
        self._controls["font_scale"] = font_combo
        form.addRow(_rt("Ordenacao"), sort_combo)
        form.addRow(_rt("Cantos"), corners_combo)
        form.addRow(_rt("Fonte"), font_combo)
        group.body_layout.addLayout(form)

    def _build_presets_section(self):
        group = self._create_section("presets", "Predefinicoes de estilo", view="visual", expanded=False)
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(5)
        self.preset_combo = QComboBox(group)
        self._refresh_preset_combo()
        self.apply_preset_btn = QPushButton(_rt("Aplicar preset"), group)
        self.save_preset_btn = QPushButton(_rt("Salvar estilo como preset"), group)
        self.delete_preset_btn = QPushButton(_rt("Excluir preset"), group)
        neutral_button_style = """
            QPushButton#VisualPanelPresetButton {
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                background: #FFFFFF;
                color: #0F172A;
                padding: 3px 8px;
                min-height: 22px;
                max-height: 24px;
                font-size: 9px;
                font-weight: 400;
            }
            QPushButton#VisualPanelPresetButton:hover {
                background: #F8FAFC;
                border-color: #94A3B8;
            }
            QPushButton#VisualPanelPresetButton:disabled {
                background: #F8FAFC;
                border-color: #E2E8F0;
                color: #94A3B8;
            }
        """
        for button in (self.apply_preset_btn, self.save_preset_btn, self.delete_preset_btn):
            button.setObjectName("VisualPanelPresetButton")
            button.setStyleSheet(neutral_button_style)
        self.delete_preset_btn.setEnabled(False)
        layout.addWidget(self.preset_combo)
        layout.addWidget(self.apply_preset_btn)
        layout.addWidget(self.save_preset_btn)
        layout.addWidget(self.delete_preset_btn)
        self.apply_preset_btn.clicked.connect(self._apply_selected_preset)
        self.save_preset_btn.clicked.connect(self._save_current_as_preset)
        self.delete_preset_btn.clicked.connect(self._delete_selected_preset)
        self.preset_combo.currentIndexChanged.connect(self._sync_preset_actions)
        group.body_layout.addLayout(layout)

    def _build_card_section(self):
        self.card_group = self._create_section("card", "Card/KPI", view="visual", expanded=False)
        form = self._form_layout()
        self._controls["value_color"] = _ColorButton("#111827", self.card_group)
        self._controls["value_size"] = self._spin(0, 72, self.card_group)
        value_align_combo = QComboBox(self.card_group)
        value_align_combo.addItem(_rt("Esquerda"), "left")
        value_align_combo.addItem(_rt("Centro"), "center")
        value_align_combo.addItem(_rt("Direita"), "right")
        self._controls["value_align"] = value_align_combo
        self._controls["card_density"] = QComboBox(self.card_group)
        self._controls["card_density"].addItem(_rt("Normal"), "normal")
        self._controls["card_density"].addItem(_rt("Compacto"), "compact")
        self._controls["card_density"].addItem(_rt("Expandido"), "expanded")
        form.addRow(_rt("Cor do valor"), self._controls["value_color"])
        form.addRow(_rt("Tam. valor"), self._controls["value_size"])
        form.addRow(_rt("Alinhamento"), value_align_combo)
        form.addRow(_rt("Modo"), self._controls["card_density"])
        form.addRow("", self._switch_row("Barra de destaque", "show_card_accent", self.card_group))
        form.addRow("", self._switch_row("Mini linha", "show_card_sparkline", self.card_group))
        self.card_group.body_layout.addLayout(form)

    def _build_accessibility_section(self):
        group = self._create_section("accessibility", "Texto alternativo", view="general", expanded=False)
        form = self._form_layout()
        self._controls["alt_text"] = QLineEdit(group)
        form.addRow(_rt("Descricao"), self._controls["alt_text"])
        group.body_layout.addLayout(form)

    def _spin(self, minimum: int, maximum: int, parent) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setObjectName("VisualPanelSpin")
        spin.setRange(minimum, maximum)
        spin.setSingleStep(1)
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return spin

    def _connect_live_updates(self):
        for control in self._controls.values():
            if isinstance(control, _ColorButton):
                control.clicked.connect(self.apply_changes)
            elif isinstance(control, _Switch):
                control.toggled.connect(self.apply_changes)
            elif isinstance(control, QSpinBox):
                control.valueChanged.connect(self.apply_changes)
            elif isinstance(control, QLineEdit):
                control.textChanged.connect(self.apply_changes)
            elif isinstance(control, QComboBox):
                control.currentIndexChanged.connect(self.apply_changes)
        for button in self._palette_buttons:
            button.clicked.connect(self.apply_changes)
        self._controls["show_background"].toggled.connect(self._sync_background_controls)
        self._controls["show_grid"].toggled.connect(self._sync_grid_controls)
        self._controls["show_axis_labels"].toggled.connect(self._sync_axis_controls)
        self._controls["show_zero_line"].toggled.connect(self._sync_axis_controls)
        self._controls["show_title"].toggled.connect(self._sync_title_controls)
        self._controls["show_border"].toggled.connect(self._sync_border_controls)
        self._controls["shadow_enabled"].toggled.connect(self._sync_shadow_controls)
        self._controls["show_values"].toggled.connect(self._sync_value_controls)
        self._controls["show_legend"].toggled.connect(self._sync_legend_controls)
        self._controls["show_markers"].toggled.connect(self._sync_marker_controls)

    def _build_shape_section(self):
        group = self._create_section("shape", "Barras e linhas", view="visual", expanded=False)
        form = self._form_layout()
        self._controls["bar_width_percent"] = self._spin(20, 100, group)
        self._controls["line_width"] = self._spin(1, 8, group)
        self._controls["marker_size"] = self._spin(2, 12, group)
        form.addRow(_rt("Largura barras"), self._controls["bar_width_percent"])
        form.addRow(_rt("Esp. linha"), self._controls["line_width"])
        form.addRow("", self._switch_row("Marcadores", "show_markers", group))
        form.addRow(_rt("Tam. marcador"), self._controls["marker_size"])
        group.body_layout.addLayout(form)

    def set_current_item(self, item):
        self._current_item_widget = item
        self.refresh_from_item()

    def set_visual_state(self, visual_state: ChartVisualState):
        self._load_state(visual_state or ChartVisualState())

    def clear_selection(self):
        self._current_item_widget = None
        self.item_label.setText("")
        self.empty_label.show()
        self.scroll.hide()

    def refresh_from_item(self):
        item_widget = self._current_item_widget
        if item_widget is None:
            self.clear_selection()
            return
        state = self._item_visual_state(item_widget)
        chart_type = str(getattr(state, "chart_type", "") or getattr(item_widget.item.payload, "chart_type", "bar"))
        title = ""
        try:
            title = item_widget.item.display_title()
        except Exception:
            title = str(getattr(getattr(item_widget, "item", None), "title", "") or "")
        self.item_label.setText(f"{title or _rt('Visual')} - {chart_type}")
        self.empty_label.hide()
        self.scroll.show()
        self._load_state(state)
        self._apply_section_filter("")

    def apply_changes(self, *args):
        if self._loading or self._current_item_widget is None:
            return
        state = self._current_state()
        item_widget = self._current_item_widget
        if hasattr(item_widget, "apply_visual_state"):
            item_widget.apply_visual_state(state, emit_changed=True)
        else:
            item_widget.item.visual_state = copy.deepcopy(state)
        self._apply_layout_changes(item_widget)
        self.visualStateChanged.emit(state)

    def _item_visual_state(self, item_widget) -> ChartVisualState:
        if hasattr(item_widget, "visual_state"):
            return copy.deepcopy(item_widget.visual_state())
        item = getattr(item_widget, "item", None)
        return copy.deepcopy(getattr(item, "visual_state", ChartVisualState()) or ChartVisualState())

    def _load_state(self, state: ChartVisualState):
        self._loading = True
        try:
            self._load_layout_controls()
            self._controls["show_background"].set_checked_state(bool(getattr(state, "show_background", True)), animated=False)
            self._controls["background_color"].set_color(getattr(state, "background_color", "#FFFFFF"))
            self._controls["background_opacity"].setValue(int(getattr(state, "background_opacity", 100) if getattr(state, "background_opacity", 100) != "" else 100))
            self._controls["show_grid"].set_checked_state(bool(getattr(state, "show_grid", False)), animated=False)
            self._controls["grid_color"].set_color(getattr(state, "grid_color", "#E5E7EB"))
            self._controls["grid_width"].setValue(int(getattr(state, "grid_width", 1) or 1))
            self._controls["grid_opacity"].setValue(int(getattr(state, "grid_opacity", 100) if getattr(state, "grid_opacity", 100) != "" else 100))
            self._controls["show_axis_labels"].set_checked_state(bool(getattr(state, "show_axis_labels", True)), animated=False)
            self._controls["axis_label_color"].set_color(getattr(state, "axis_label_color", "#4B5563"))
            self._controls["axis_label_size"].setValue(int(getattr(state, "axis_label_size", 0) or 0))
            self._controls["show_zero_line"].set_checked_state(bool(getattr(state, "show_zero_line", True)), animated=False)
            self._controls["zero_line_color"].set_color(getattr(state, "zero_line_color", "#CBD5E1"))
            self._controls["show_title"].set_checked_state(bool(getattr(state, "show_title", True)), animated=False)
            self._controls["show_border"].set_checked_state(bool(getattr(state, "show_border", False)), animated=False)
            self._controls["border_color"].set_color(getattr(state, "border_color", "#CBD5E1"))
            self._controls["border_width"].setValue(int(getattr(state, "border_width", 1) or 1))
            self._controls["border_radius"].setValue(int(getattr(state, "border_radius", 8) or 8))
            self._controls["padding"].setValue(int(getattr(state, "padding", 8) or 8))
            self._controls["shadow_enabled"].set_checked_state(bool(getattr(state, "shadow_enabled", False)), animated=False)
            self._controls["shadow_opacity"].setValue(int(getattr(state, "shadow_opacity", 18) if getattr(state, "shadow_opacity", 18) != "" else 18))
            self._controls["title_override"].setText(str(getattr(state, "title_override", "") or ""))
            self._controls["title_color"].set_color(getattr(state, "title_color", "#1F2937"))
            self._controls["title_size"].setValue(int(getattr(state, "title_size", 0) or 0))
            self._controls["label_color"].set_color(getattr(state, "label_color", "#4B5563"))
            self._controls["label_size"].setValue(int(getattr(state, "label_size", 0) or 0))
            self._set_combo_value(self._controls["text_align"], getattr(state, "text_align", "left") or "left")
            self._controls["show_values"].set_checked_state(bool(getattr(state, "show_values", True)), animated=False)
            self._controls["show_percent"].set_checked_state(bool(getattr(state, "show_percent", False)), animated=False)
            self._set_combo_value(self._controls["data_label_position"], getattr(state, "data_label_position", "outside") or "outside")
            self._controls["number_prefix"].setText(str(getattr(state, "number_prefix", "") or ""))
            self._controls["number_suffix"].setText(str(getattr(state, "number_suffix", "") or ""))
            self._controls["decimal_places"].setValue(int(getattr(state, "decimal_places", 2)))
            self._set_combo_value(self._controls["display_units"], getattr(state, "display_units", "none") or "none")
            self._controls["null_value"].setText(str(getattr(state, "null_value", "-") or "-"))
            self._set_combo_value(self._controls["palette"], getattr(state, "palette", "purple") or "purple")
            self._controls["primary_color"].set_color(getattr(state, "primary_color", "#5A3FE6"))
            palette = list(getattr(state, "category_palette", []) or [])
            fallback = ["#2B7DE9", "#F2C811", "#2FB26A", "#F2994A"]
            for index, button in enumerate(self._palette_buttons):
                button.set_color(palette[index] if index < len(palette) else fallback[index])
            self._controls["show_legend"].set_checked_state(bool(getattr(state, "show_legend", False)), animated=False)
            self._controls["legend_label_override"].setText(str(getattr(state, "legend_label_override", "") or ""))
            self._set_combo_value(self._controls["sort_mode"], getattr(state, "sort_mode", "default") or "default")
            self._set_combo_value(self._controls["bar_corner_style"], getattr(state, "bar_corner_style", "square") or "square")
            self._set_combo_value(self._controls["font_scale"], str(getattr(state, "font_scale", 0.82) or 0.82))
            self._controls["bar_width_percent"].setValue(int(getattr(state, "bar_width_percent", 62) or 62))
            self._controls["line_width"].setValue(int(getattr(state, "line_width", 2) or 2))
            self._controls["show_markers"].set_checked_state(bool(getattr(state, "show_markers", True)), animated=False)
            self._controls["marker_size"].setValue(int(getattr(state, "marker_size", 4) or 4))
            self._controls["value_color"].set_color(getattr(state, "value_color", "#111827"))
            self._controls["value_size"].setValue(int(getattr(state, "value_size", 0) or 0))
            self._set_combo_value(self._controls["value_align"], getattr(state, "value_align", "left") or "left")
            self._set_combo_value(self._controls["card_density"], getattr(state, "card_density", "normal") or "normal")
            self._controls["show_card_accent"].set_checked_state(bool(getattr(state, "show_card_accent", True)), animated=False)
            self._controls["show_card_sparkline"].set_checked_state(bool(getattr(state, "show_card_sparkline", True)), animated=False)
            self._controls["alt_text"].setText(str(getattr(state, "alt_text", "") or ""))
            self._sync_background_controls()
            self._sync_grid_controls()
            self._sync_axis_controls()
            self._sync_title_controls()
            self._sync_border_controls()
            self._sync_shadow_controls()
            self._sync_value_controls()
            self._sync_legend_controls()
            self._sync_marker_controls()
        finally:
            self._loading = False

    def _current_state(self) -> ChartVisualState:
        base = self._item_visual_state(self._current_item_widget) if self._current_item_widget is not None else ChartVisualState()
        state = copy.deepcopy(base)
        state.show_background = bool(self._controls["show_background"].isChecked())
        state.background_color = self._controls["background_color"].color()
        state.background_opacity = int(self._controls["background_opacity"].value())
        state.show_grid = bool(self._controls["show_grid"].isChecked())
        state.grid_color = self._controls["grid_color"].color()
        state.grid_width = int(self._controls["grid_width"].value())
        state.grid_opacity = int(self._controls["grid_opacity"].value())
        state.show_axis_labels = bool(self._controls["show_axis_labels"].isChecked())
        state.axis_label_color = self._controls["axis_label_color"].color()
        state.axis_label_size = int(self._controls["axis_label_size"].value())
        state.show_zero_line = bool(self._controls["show_zero_line"].isChecked())
        state.zero_line_color = self._controls["zero_line_color"].color()
        state.show_title = bool(self._controls["show_title"].isChecked())
        state.show_border = bool(self._controls["show_border"].isChecked())
        state.border_color = self._controls["border_color"].color()
        state.border_width = int(self._controls["border_width"].value())
        state.border_radius = int(self._controls["border_radius"].value())
        state.padding = int(self._controls["padding"].value())
        state.shadow_enabled = bool(self._controls["shadow_enabled"].isChecked())
        state.shadow_opacity = int(self._controls["shadow_opacity"].value())
        state.title_override = self._controls["title_override"].text().strip()
        state.title_color = self._controls["title_color"].color()
        state.title_size = int(self._controls["title_size"].value())
        state.label_color = self._controls["label_color"].color()
        state.label_size = int(self._controls["label_size"].value())
        state.text_align = str(self._controls["text_align"].currentData() or "left")
        state.show_values = bool(self._controls["show_values"].isChecked())
        state.show_percent = bool(state.show_values and self._controls["show_percent"].isChecked())
        state.data_label_position = str(self._controls["data_label_position"].currentData() or "outside")
        state.number_prefix = self._controls["number_prefix"].text()
        state.number_suffix = self._controls["number_suffix"].text()
        state.decimal_places = int(self._controls["decimal_places"].value())
        state.display_units = str(self._controls["display_units"].currentData() or "none")
        state.null_value = self._controls["null_value"].text() or "-"
        state.palette = str(self._controls["palette"].currentData() or "purple")
        state.primary_color = self._controls["primary_color"].color()
        state.category_palette = [button.color() for button in self._palette_buttons]
        state.show_legend = bool(self._controls["show_legend"].isChecked())
        state.legend_label_override = self._controls["legend_label_override"].text().strip()
        state.sort_mode = str(self._controls["sort_mode"].currentData() or "default")
        state.bar_corner_style = str(self._controls["bar_corner_style"].currentData() or "square")
        try:
            state.font_scale = float(self._controls["font_scale"].currentData() or 0.82)
        except Exception:
            state.font_scale = 0.82
        state.bar_width_percent = int(self._controls["bar_width_percent"].value())
        state.line_width = int(self._controls["line_width"].value())
        state.show_markers = bool(self._controls["show_markers"].isChecked())
        state.marker_size = int(self._controls["marker_size"].value())
        state.value_color = self._controls["value_color"].color()
        state.value_size = int(self._controls["value_size"].value())
        state.value_align = str(self._controls["value_align"].currentData() or "left")
        state.card_density = str(self._controls["card_density"].currentData() or "normal")
        state.show_card_accent = bool(self._controls["show_card_accent"].isChecked())
        state.show_card_sparkline = bool(self._controls["show_card_sparkline"].isChecked())
        state.alt_text = self._controls["alt_text"].text().strip()
        return state

    def _sync_background_controls(self, *args):
        enabled = bool(self._controls["show_background"].isChecked())
        for key in ("background_color", "background_opacity"):
            self._controls[key].setEnabled(enabled)

    def _sync_grid_controls(self, *args):
        enabled = bool(self._controls["show_grid"].isChecked())
        for key in ("grid_color", "grid_width", "grid_opacity"):
            self._controls[key].setEnabled(enabled)

    def _sync_axis_controls(self, *args):
        enabled = bool(self._controls["show_axis_labels"].isChecked())
        for key in ("axis_label_color", "axis_label_size", "show_zero_line"):
            self._controls[key].setEnabled(enabled)
        self._controls["zero_line_color"].setEnabled(enabled and bool(self._controls["show_zero_line"].isChecked()))

    def _sync_title_controls(self, *args):
        enabled = bool(self._controls["show_title"].isChecked())
        for key in ("title_override", "title_color", "title_size", "text_align"):
            self._controls[key].setEnabled(enabled)

    def _sync_border_controls(self, *args):
        enabled = bool(self._controls["show_border"].isChecked())
        for key in ("border_color", "border_width", "border_radius", "padding"):
            self._controls[key].setEnabled(enabled)

    def _sync_shadow_controls(self, *args):
        enabled = bool(self._controls["shadow_enabled"].isChecked())
        self._controls["shadow_opacity"].setEnabled(enabled)

    def _sync_value_controls(self, *args):
        enabled = bool(self._controls["show_values"].isChecked())
        for key in ("show_percent", "label_color", "label_size", "data_label_position"):
            self._controls[key].setEnabled(enabled)

    def _sync_legend_controls(self, *args):
        enabled = bool(self._controls["show_legend"].isChecked())
        self._controls["legend_label_override"].setEnabled(enabled)

    def _sync_marker_controls(self, *args):
        self._controls["marker_size"].setEnabled(bool(self._controls["show_markers"].isChecked()))

    def _load_layout_controls(self):
        item_widget = self._current_item_widget
        if item_widget is None:
            return
        layout = getattr(getattr(item_widget, "item", None), "layout", None)
        if layout is None:
            return
        self._controls["layout_width"].setValue(int(getattr(layout, "width", 120) or 120))
        self._controls["layout_height"].setValue(int(getattr(layout, "height", 120) or 120))
        self._controls["layout_x"].setValue(int(getattr(layout, "x", 0) or 0))
        self._controls["layout_y"].setValue(int(getattr(layout, "y", 0) or 0))

    def _apply_layout_changes(self, item_widget):
        layout = getattr(getattr(item_widget, "item", None), "layout", None)
        if layout is None:
            return
        try:
            layout.width = int(self._controls["layout_width"].value())
            layout.height = int(self._controls["layout_height"].value())
            layout.x = int(self._controls["layout_x"].value())
            layout.y = int(self._controls["layout_y"].value())
        except Exception:
            return
        canvas = self._find_canvas_host(item_widget)
        if canvas is None:
            return
        try:
            canvas._apply_geometries()
        except Exception:
            pass

    def _find_canvas_host(self, item_widget):
        widget = item_widget.parentWidget() if item_widget is not None else None
        while widget is not None:
            if hasattr(widget, "_apply_geometries") and hasattr(widget, "selected_item_widget"):
                return widget
            widget = widget.parentWidget()
        return None

    def _refresh_preset_combo(self):
        if not hasattr(self, "preset_combo"):
            return
        current = self.preset_combo.currentData()
        self.preset_combo.clear()
        for preset_key, preset in VisualPropertiesDialog.STYLE_PRESETS.items():
            self.preset_combo.addItem(_rt(str(preset.get("label") or preset_key)), preset_key)
        for preset_key in sorted(self._custom_presets):
            self.preset_combo.addItem(_rt(preset_key), f"custom:{preset_key}")
        index = self.preset_combo.findData(current)
        self.preset_combo.setCurrentIndex(index if index >= 0 else 0)
        if hasattr(self, "delete_preset_btn"):
            self._sync_preset_actions()

    def _sync_preset_actions(self, *args):
        is_custom = str(self.preset_combo.currentData() or "").startswith("custom:")
        self.delete_preset_btn.setEnabled(is_custom)

    def _apply_selected_preset(self):
        preset_key = str(self.preset_combo.currentData() or "clean")
        preset = {}
        if preset_key.startswith("custom:"):
            preset = copy.deepcopy(self._custom_presets.get(preset_key.split(":", 1)[1]) or {})
        else:
            preset = copy.deepcopy(VisualPropertiesDialog.STYLE_PRESETS.get(preset_key) or {})
        if not preset:
            return
        state = self._current_state()
        for attr, value in preset.items():
            if attr == "label":
                continue
            setattr(state, attr, copy.deepcopy(value))
        self._load_state(state)
        self.apply_changes()

    def _save_current_as_preset(self):
        label = _rt("Personalizado")
        suffix = 1
        while label in self._custom_presets:
            suffix += 1
            label = f"{_rt('Personalizado')} {suffix}"
        self._custom_presets[label] = self._state_to_preset(self._current_state())
        self._refresh_preset_combo()
        index = self.preset_combo.findData(f"custom:{label}")
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

    def _delete_selected_preset(self):
        preset_key = str(self.preset_combo.currentData() or "")
        if not preset_key.startswith("custom:"):
            return
        self._custom_presets.pop(preset_key.split(":", 1)[1], None)
        self._refresh_preset_combo()

    def _state_to_preset(self, state: ChartVisualState):
        keys = [
            "show_background",
            "background_opacity",
            "show_grid",
            "grid_color",
            "grid_width",
            "grid_opacity",
            "show_axis_labels",
            "axis_label_color",
            "axis_label_size",
            "show_zero_line",
            "zero_line_color",
            "show_title",
            "background_color",
            "show_border",
            "border_color",
            "border_width",
            "border_radius",
            "padding",
            "shadow_enabled",
            "shadow_opacity",
            "title_color",
            "title_size",
            "label_color",
            "label_size",
            "data_label_position",
            "text_align",
            "show_values",
            "show_percent",
            "number_prefix",
            "number_suffix",
            "decimal_places",
            "display_units",
            "null_value",
            "palette",
            "primary_color",
            "category_palette",
            "show_legend",
            "legend_label_override",
            "sort_mode",
            "bar_corner_style",
            "font_scale",
            "bar_width_percent",
            "line_width",
            "show_markers",
            "marker_size",
            "value_color",
            "value_size",
            "value_align",
            "card_density",
            "show_card_accent",
            "show_card_sparkline",
            "alt_text",
        ]
        return {key: copy.deepcopy(getattr(state, key)) for key in keys if hasattr(state, key)}

    def _set_combo_value(self, combo: QComboBox, value: str):
        index = combo.findData(str(value or ""))
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _is_card_visual(self, chart_type: str) -> bool:
        return str(chart_type or "").strip().lower() in {"card", "kpi"}
