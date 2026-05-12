from __future__ import annotations

import copy
import json
import os
from typing import Optional

from qgis.PyQt.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QBrush, QIcon, QPainter, QPainterPath, QPen
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .dashboard_models import (
    DashboardChartBinding,
    DashboardChartItem,
    ROLE_X_AXIS,
    binding_slot_definitions,
    empty_binding_message,
    suggest_binding_slot,
    deserialize_chart_visual_state,
    serialize_chart_visual_state,
)
from .report_view.charts import ChartVisualState
from .report_view.chart_factory import ReportChartWidget
from .slim_dialogs import slim_get_text
from .utils.fonts import ui_font
from .utils.i18n_runtime import tr_text as _rt


from .utils.logging_utils import log_exception

_MODEL_FIELD_MIME = "application/x-summarizer-model-field"
def _icon_from_resource(name: str) -> QIcon:
    base_dir = os.path.dirname(__file__)
    candidate_name = str(name or "").strip()
    for parts in (("resources", "icons", candidate_name), ("resources", "SVG", candidate_name)):
        path = os.path.abspath(os.path.join(base_dir, *parts))
        if os.path.exists(path):
            return QIcon(path)
    return QIcon()


class _DashboardConnectorOverlay(QWidget):
    def __init__(self, host: "DashboardItemWidget", parent=None):
        super().__init__(parent)
        self._host = host
        self.setObjectName("ModelDashboardOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not bool(getattr(self._host, "_edit_mode", False)):
            return
        highlight_mode = str(getattr(self._host, "_highlight_mode", "idle") or "idle").strip().lower()
        if highlight_mode not in {"selected", "drag", "resize"}:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        frame_rect = self.rect().adjusted(1, 1, -2, -2)
        if frame_rect.width() <= 0 or frame_rect.height() <= 0:
            return

        border_color = QColor("#A3A3A3")
        handle_color = QColor("#8A8A8A")
        if highlight_mode == "drag":
            border_color = QColor("#737373")
            handle_color = QColor("#6B7280")
        elif highlight_mode == "resize":
            border_color = QColor("#525252")
            handle_color = QColor("#4B5563")

        selection_pen = QPen(border_color, 1)
        selection_pen.setCosmetic(True)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(frame_rect)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(handle_color))
        zoom = max(0.8, min(1.4, float(getattr(self._host, "_zoom_scale", 1.0) or 1.0)))
        handle_size = max(5, min(8, int(round(6 * zoom))))
        half = handle_size // 2
        points = [
            QPoint(frame_rect.left(), frame_rect.top()),
            QPoint(frame_rect.center().x(), frame_rect.top()),
            QPoint(frame_rect.right(), frame_rect.top()),
            QPoint(frame_rect.left(), frame_rect.center().y()),
            QPoint(frame_rect.right(), frame_rect.center().y()),
            QPoint(frame_rect.left(), frame_rect.bottom()),
            QPoint(frame_rect.center().x(), frame_rect.bottom()),
            QPoint(frame_rect.right(), frame_rect.bottom()),
        ]
        for point in points:
            painter.drawRect(QRect(point.x() - half, point.y() - half, handle_size, handle_size))


def _read_model_field_payload(mime_data) -> Optional[dict]:
    try:
        if mime_data is None or not mime_data.hasFormat(_MODEL_FIELD_MIME):
            return None
        raw = bytes(mime_data.data(_MODEL_FIELD_MIME)).decode("utf-8")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        log_exception("falha opcional ignorada")
        return None


class _VisualDropSlot(QFrame):
    fieldDropped = pyqtSignal(str, object)

    def __init__(self, slot_name: str, label: str, parent=None):
        super().__init__(parent)
        self.slot_name = str(slot_name or "").strip()
        self.setObjectName("ModelVisualDropSlot")
        self.setAcceptDrops(True)
        self._active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        self.title_label = QLabel(label, self)
        self.title_label.setObjectName("ModelVisualDropSlotLabel")
        layout.addWidget(self.title_label, 1)

    def set_active(self, active: bool):
        self._active = bool(active)
        self.setProperty("dropActive", self._active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def dragEnterEvent(self, event):
        if _read_model_field_payload(event.mimeData()) is None:
            event.ignore()
            return
        self.set_active(True)
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if _read_model_field_payload(event.mimeData()) is None:
            event.ignore()
            return
        self.set_active(True)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.set_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        payload = _read_model_field_payload(event.mimeData())
        self.set_active(False)
        if payload is None:
            event.ignore()
            return
        self.fieldDropped.emit(self.slot_name, payload)
        event.acceptProposedAction()


class _EmptyVisualPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart_type = "bar"
        self.setObjectName("ModelDashboardEmptyPreview")
        self.setMinimumSize(190, 150)

    def set_chart_type(self, chart_type: str):
        normalized = str(chart_type or "bar").strip().lower() or "bar"
        if normalized == self._chart_type:
            return
        self._chart_type = normalized
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        bounds = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.fillRect(bounds, QColor("#F3F4F6"))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        for step in range(1, 4):
            y = bounds.top() + bounds.height() * step / 4.0
            painter.drawLine(QPoint(int(bounds.left()), int(y)), QPoint(int(bounds.right()), int(y)))

        chart_type = str(self._chart_type or "bar").lower()
        bar_color = QColor("#C9CDD2")
        darker = QColor("#B8BDC3")
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bar_color))

        if chart_type in {"barh", "funnel"}:
            widths = [0.58, 0.78, 0.46, 0.70, 0.52]
            top = bounds.top() + bounds.height() * 0.22
            row_h = bounds.height() * 0.10
            for index, factor in enumerate(widths):
                y = top + index * row_h * 1.55
                painter.drawRect(QRectF(bounds.left() + 16, y, bounds.width() * factor, row_h))
        elif chart_type in {"line", "area"}:
            points = [
                QPointF(bounds.left() + bounds.width() * 0.12, bounds.bottom() - bounds.height() * 0.25),
                QPointF(bounds.left() + bounds.width() * 0.30, bounds.bottom() - bounds.height() * 0.44),
                QPointF(bounds.left() + bounds.width() * 0.48, bounds.bottom() - bounds.height() * 0.36),
                QPointF(bounds.left() + bounds.width() * 0.66, bounds.bottom() - bounds.height() * 0.62),
                QPointF(bounds.left() + bounds.width() * 0.84, bounds.bottom() - bounds.height() * 0.52),
            ]
            if chart_type == "area":
                path = QPainterPath(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                path.lineTo(QPointF(points[-1].x(), bounds.bottom() - 12))
                path.lineTo(QPointF(points[0].x(), bounds.bottom() - 12))
                path.closeSubpath()
                painter.setBrush(QBrush(QColor(201, 205, 210, 105)))
                painter.drawPath(path)
            painter.setPen(QPen(darker, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for index in range(len(points) - 1):
                painter.drawLine(points[index], points[index + 1])
        elif chart_type in {"pie", "donut"}:
            rect = QRectF(
                bounds.center().x() - bounds.height() * 0.30,
                bounds.center().y() - bounds.height() * 0.30,
                bounds.height() * 0.60,
                bounds.height() * 0.60,
            )
            painter.setBrush(QBrush(bar_color))
            painter.drawPie(rect, 30 * 16, 130 * 16)
            painter.setBrush(QBrush(darker))
            painter.drawPie(rect, 160 * 16, 90 * 16)
            painter.setBrush(QBrush(QColor("#D9DDE2")))
            painter.drawPie(rect, 250 * 16, 140 * 16)
            if chart_type == "donut":
                painter.setBrush(QBrush(QColor("#F3F4F6")))
                painter.drawEllipse(rect.adjusted(rect.width() * 0.28, rect.height() * 0.28, -rect.width() * 0.28, -rect.height() * 0.28))
        elif chart_type in {"matrix", "table", "slicer"}:
            left = bounds.left() + 16
            top = bounds.top() + 22
            col_w = (bounds.width() - 32) / 3.0
            row_h = (bounds.height() - 44) / 5.0
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            for row in range(5):
                for col in range(3):
                    shade = QColor("#C9CDD2") if row == 0 else QColor("#D9DDE2")
                    painter.fillRect(QRectF(left + col * col_w, top + row * row_h, col_w - 2, row_h - 2), shade)
        else:
            values = [0.36, 0.44, 0.38, 0.72, 0.88, 0.60]
            gap = bounds.width() * 0.045
            bar_w = (bounds.width() - gap * 7) / 6.0
            baseline = bounds.bottom() - 12
            for index, factor in enumerate(values):
                h = (bounds.height() - 34) * factor
                x = bounds.left() + gap + index * (bar_w + gap)
                painter.drawRect(QRectF(x, baseline - h, bar_w, h))


class _DashboardVisualDropOverlay(QFrame):
    fieldDropped = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelDashboardDropOverlay")
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.message_label = QLabel(_rt("Arraste campos para configurar este visual"), self)
        self.message_label.setObjectName("ModelDashboardEmptyVisualText")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.message_label, 0)

        self.preview_widget = _EmptyVisualPreview(self)
        layout.addWidget(self.preview_widget, 1)

        self.slots_row = QWidget(self)
        slots_layout = QGridLayout(self.slots_row)
        slots_layout.setContentsMargins(0, 0, 0, 0)
        slots_layout.setHorizontalSpacing(0)
        slots_layout.setVerticalSpacing(0)
        self._slots = {}
        self._slot_layout = slots_layout
        self._chart_type = "bar"
        for index, slot_def in enumerate(binding_slot_definitions("bar")):
            slot_name = str(slot_def.get("name") or "")
            label = str(slot_def.get("label") or slot_name)
            slot = _VisualDropSlot(slot_name, _rt(label), self.slots_row)
            slot.fieldDropped.connect(self.fieldDropped.emit)
            if index < 2:
                slots_layout.addWidget(slot, 0, index, 1, 1)
            else:
                slots_layout.addWidget(slot, 1, index - 2, 1, 1)
            self._slots[slot_name] = slot
        self.slots_row.hide()

    def set_chart_context(self, chart_type: str, binding: Optional[DashboardChartBinding] = None):
        self._chart_type = str(chart_type or "bar").strip().lower() or "bar"
        self.preview_widget.set_chart_type(self._chart_type)
        self.message_label.setText(_rt("Selecione ou arraste campos para preencher este visual"))
        wanted = binding_slot_definitions(chart_type)
        wanted_names = [str(slot.get("name") or "") for slot in wanted]
        for slot_name, slot in self._slots.items():
            slot.setVisible(slot_name in wanted_names)
        for index, slot_def in enumerate(wanted):
            slot_name = str(slot_def.get("name") or "")
            slot = self._slots.get(slot_name)
            if slot is None:
                label = str(slot_def.get("label") or slot_name)
                slot = _VisualDropSlot(slot_name, _rt(label), self.slots_row)
                slot.fieldDropped.connect(self.fieldDropped.emit)
                self._slots[slot_name] = slot
            self._slot_layout.removeWidget(slot)
            row = 0 if index < 3 else 1
            column = index if index < 3 else index - 3
            self._slot_layout.addWidget(slot, row, column, 1, 1)

    def dragEnterEvent(self, event):
        if _read_model_field_payload(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if _read_model_field_payload(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()

    def dropEvent(self, event):
        payload = _read_model_field_payload(event.mimeData())
        if payload is None:
            event.ignore()
            return
        suggested = suggest_binding_slot(self._chart_type, str(payload.get("field_group") or "other"))
        target_slot = suggested if suggested in self._slots else ROLE_X_AXIS
        self.fieldDropped.emit(target_slot, payload)
        event.acceptProposedAction()


_VISUAL_STYLE_CLIPBOARD = {}


class _ColorButton(QPushButton):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = "#FFFFFF"
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(92)
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
            f"QPushButton {{ background: {self._color}; color: {text_color}; border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px 8px; }}"
        )

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, _rt("Escolher cor"))
        if color.isValid():
            self.set_color(color.name())


class VisualPropertiesDialog(QDialog):
    STYLE_PRESETS = {
        "clean": {
            "label": "Limpo",
            "show_background": True,
            "background_color": "#FFFFFF",
            "show_border": True,
            "border_color": "#E2E8F0",
            "border_width": 1,
            "border_radius": 8,
            "padding": 8,
            "title_color": "#0F172A",
            "label_color": "#475569",
            "primary_color": "#2563EB",
            "category_palette": ["#2563EB", "#14B8A6", "#F59E0B", "#64748B"],
        },
        "executive": {
            "label": "Executivo",
            "show_background": True,
            "background_color": "#F8FAFC",
            "show_border": True,
            "border_color": "#CBD5E1",
            "border_width": 1,
            "border_radius": 10,
            "padding": 12,
            "title_color": "#111827",
            "label_color": "#4B5563",
            "primary_color": "#1D4ED8",
            "category_palette": ["#1D4ED8", "#0F766E", "#B45309", "#7C3AED"],
        },
        "focus": {
            "label": "Destaque",
            "show_background": True,
            "background_color": "#FEFCE8",
            "show_border": True,
            "border_color": "#FACC15",
            "border_width": 2,
            "border_radius": 12,
            "padding": 12,
            "title_color": "#713F12",
            "label_color": "#854D0E",
            "primary_color": "#CA8A04",
            "category_palette": ["#CA8A04", "#0284C7", "#16A34A", "#DC2626"],
        },
        "graphite": {
            "label": "Grafite",
            "show_background": True,
            "background_color": "#F3F4F6",
            "show_border": True,
            "border_color": "#9CA3AF",
            "border_width": 1,
            "border_radius": 6,
            "padding": 10,
            "title_color": "#111827",
            "label_color": "#374151",
            "primary_color": "#374151",
            "category_palette": ["#111827", "#4B5563", "#6B7280", "#9CA3AF"],
        },
    }

    def __init__(self, state: ChartVisualState, default_state: ChartVisualState, apply_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_rt("Propriedades visuais"))
        self._state = copy.deepcopy(state)
        self._default_state = copy.deepcopy(default_state)
        self._apply_callback = apply_callback
        self._loading = True
        self._controls = {}
        self._palette_buttons = []
        self._build_ui()
        self._load_state(self._state)
        self._loading = False

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(_rt("Preset"), self), 0)
        self.preset_combo = QComboBox(self)
        for preset_key, preset in self.STYLE_PRESETS.items():
            self.preset_combo.addItem(_rt(str(preset.get("label") or preset_key)), preset_key)
        self.apply_preset_btn = QPushButton(_rt("Aplicar preset"), self)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.apply_preset_btn, 0)
        root.addLayout(preset_row)

        general = QGroupBox(_rt("Geral"), self)
        general_form = QFormLayout(general)
        general_form.setContentsMargins(10, 12, 10, 10)
        self._controls["show_background"] = QCheckBox(_rt("Mostrar fundo"), general)
        self._controls["background_color"] = _ColorButton("#FFFFFF", general)
        self._controls["show_border"] = QCheckBox(_rt("Mostrar borda"), general)
        self._controls["border_color"] = _ColorButton("#CBD5E1", general)
        self._controls["border_width"] = self._spin(1, 6, general)
        self._controls["border_radius"] = self._spin(0, 32, general)
        self._controls["padding"] = self._spin(0, 40, general)
        general_form.addRow("", self._controls["show_background"])
        general_form.addRow(_rt("Cor de fundo"), self._controls["background_color"])
        general_form.addRow("", self._controls["show_border"])
        general_form.addRow(_rt("Cor da borda"), self._controls["border_color"])
        general_form.addRow(_rt("Espessura da borda"), self._controls["border_width"])
        general_form.addRow(_rt("Raio da borda"), self._controls["border_radius"])
        general_form.addRow(_rt("Padding"), self._controls["padding"])
        root.addWidget(general)

        text_group = QGroupBox(_rt("Texto"), self)
        text_form = QFormLayout(text_group)
        text_form.setContentsMargins(10, 12, 10, 10)
        self._controls["title_color"] = _ColorButton("#1F2937", text_group)
        self._controls["title_size"] = self._spin(0, 48, text_group)
        self._controls["label_color"] = _ColorButton("#4B5563", text_group)
        self._controls["label_size"] = self._spin(0, 36, text_group)
        align_combo = QComboBox(text_group)
        align_combo.addItem(_rt("Esquerda"), "left")
        align_combo.addItem(_rt("Centro"), "center")
        align_combo.addItem(_rt("Direita"), "right")
        self._controls["text_align"] = align_combo
        text_form.addRow(_rt("Cor do titulo"), self._controls["title_color"])
        text_form.addRow(_rt("Tamanho do titulo"), self._controls["title_size"])
        text_form.addRow(_rt("Cor dos rotulos"), self._controls["label_color"])
        text_form.addRow(_rt("Tamanho dos rotulos"), self._controls["label_size"])
        text_form.addRow(_rt("Alinhamento"), align_combo)
        root.addWidget(text_group)

        number_group = QGroupBox(_rt("Numero"), self)
        number_form = QFormLayout(number_group)
        number_form.setContentsMargins(10, 12, 10, 10)
        self._controls["number_prefix"] = QLineEdit(number_group)
        self._controls["number_suffix"] = QLineEdit(number_group)
        self._controls["decimal_places"] = self._spin(0, 8, number_group)
        self._controls["null_value"] = QLineEdit(number_group)
        number_form.addRow(_rt("Prefixo"), self._controls["number_prefix"])
        number_form.addRow(_rt("Sufixo"), self._controls["number_suffix"])
        number_form.addRow(_rt("Casas decimais"), self._controls["decimal_places"])
        number_form.addRow(_rt("Valor nulo"), self._controls["null_value"])
        root.addWidget(number_group)

        colors_group = QGroupBox(_rt("Cores"), self)
        colors_layout = QGridLayout(colors_group)
        colors_layout.setContentsMargins(10, 12, 10, 10)
        self._controls["primary_color"] = _ColorButton("#5A3FE6", colors_group)
        colors_layout.addWidget(QLabel(_rt("Cor principal"), colors_group), 0, 0)
        colors_layout.addWidget(self._controls["primary_color"], 0, 1)
        palette_defaults = ["#2B7DE9", "#F2C811", "#2FB26A", "#F2994A"]
        for index, color in enumerate(palette_defaults):
            button = _ColorButton(color, colors_group)
            self._palette_buttons.append(button)
            colors_layout.addWidget(QLabel(f"{_rt('Paleta')} {index + 1}", colors_group), index + 1, 0)
            colors_layout.addWidget(button, index + 1, 1)
        root.addWidget(colors_group)

        action_row = QHBoxLayout()
        self.copy_btn = QPushButton(_rt("Copiar estilo"), self)
        self.paste_btn = QPushButton(_rt("Colar estilo"), self)
        self.reset_btn = QPushButton(_rt("Restaurar padrao"), self)
        action_row.addWidget(self.copy_btn)
        action_row.addWidget(self.paste_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.reset_btn)
        root.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Apply).setText(_rt("Aplicar"))
        buttons.button(QDialogButtonBox.Cancel).setText(_rt("Cancelar"))
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.reset_btn.clicked.connect(self._restore_defaults)
        self.copy_btn.clicked.connect(self._copy_style)
        self.paste_btn.clicked.connect(self._paste_style)
        self.apply_preset_btn.clicked.connect(self._apply_selected_preset)
        self._connect_live_updates()

    def _spin(self, minimum: int, maximum: int, parent) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(1)
        return spin

    def _connect_live_updates(self):
        for key, control in self._controls.items():
            if isinstance(control, _ColorButton):
                control.clicked.connect(self._preview)
            elif isinstance(control, QCheckBox):
                control.toggled.connect(self._preview)
            elif isinstance(control, QSpinBox):
                control.valueChanged.connect(self._preview)
            elif isinstance(control, QLineEdit):
                control.textChanged.connect(self._preview)
            elif isinstance(control, QComboBox):
                control.currentIndexChanged.connect(self._preview)
        for button in self._palette_buttons:
            button.clicked.connect(self._preview)

    def _load_state(self, state: ChartVisualState):
        self._controls["show_background"].setChecked(bool(getattr(state, "show_background", True)))
        self._controls["background_color"].set_color(getattr(state, "background_color", "#FFFFFF"))
        self._controls["show_border"].setChecked(bool(getattr(state, "show_border", False)))
        self._controls["border_color"].set_color(getattr(state, "border_color", "#CBD5E1"))
        self._controls["border_width"].setValue(int(getattr(state, "border_width", 1) or 1))
        self._controls["border_radius"].setValue(int(getattr(state, "border_radius", 8) or 8))
        self._controls["padding"].setValue(int(getattr(state, "padding", 8) or 8))
        self._controls["title_color"].set_color(getattr(state, "title_color", "#1F2937"))
        self._controls["title_size"].setValue(int(getattr(state, "title_size", 0) or 0))
        self._controls["label_color"].set_color(getattr(state, "label_color", "#4B5563"))
        self._controls["label_size"].setValue(int(getattr(state, "label_size", 0) or 0))
        align = str(getattr(state, "text_align", "left") or "left")
        index = self._controls["text_align"].findData(align)
        self._controls["text_align"].setCurrentIndex(index if index >= 0 else 0)
        self._controls["number_prefix"].setText(str(getattr(state, "number_prefix", "") or ""))
        self._controls["number_suffix"].setText(str(getattr(state, "number_suffix", "") or ""))
        self._controls["decimal_places"].setValue(int(getattr(state, "decimal_places", 2)))
        self._controls["null_value"].setText(str(getattr(state, "null_value", "-") or "-"))
        self._controls["primary_color"].set_color(getattr(state, "primary_color", "#5A3FE6"))
        palette = list(getattr(state, "category_palette", []) or [])
        fallback = ["#2B7DE9", "#F2C811", "#2FB26A", "#F2994A"]
        for index, button in enumerate(self._palette_buttons):
            button.set_color(palette[index] if index < len(palette) else fallback[index])

    def _current_state(self) -> ChartVisualState:
        state = copy.deepcopy(self._state)
        state.show_background = bool(self._controls["show_background"].isChecked())
        state.background_color = self._controls["background_color"].color()
        state.show_border = bool(self._controls["show_border"].isChecked())
        state.border_color = self._controls["border_color"].color()
        state.border_width = int(self._controls["border_width"].value())
        state.border_radius = int(self._controls["border_radius"].value())
        state.padding = int(self._controls["padding"].value())
        state.title_color = self._controls["title_color"].color()
        state.title_size = int(self._controls["title_size"].value())
        state.label_color = self._controls["label_color"].color()
        state.label_size = int(self._controls["label_size"].value())
        state.text_align = str(self._controls["text_align"].currentData() or "left")
        state.number_prefix = self._controls["number_prefix"].text()
        state.number_suffix = self._controls["number_suffix"].text()
        state.decimal_places = int(self._controls["decimal_places"].value())
        state.null_value = self._controls["null_value"].text() or "-"
        state.primary_color = self._controls["primary_color"].color()
        state.category_palette = [button.color() for button in self._palette_buttons]
        return state

    def _preview(self, *args):
        if self._loading:
            return
        self._apply_callback(self._current_state())

    def _restore_defaults(self):
        self._loading = True
        self._load_state(self._default_state)
        self._loading = False
        self._preview()

    def _apply_selected_preset(self):
        preset_key = str(self.preset_combo.currentData() or "clean")
        preset = dict(self.STYLE_PRESETS.get(preset_key) or {})
        state = self._current_state()
        for attr, value in preset.items():
            if attr == "label":
                continue
            setattr(state, attr, copy.deepcopy(value))
        self._loading = True
        self._load_state(state)
        self._loading = False
        self._preview()

    def _copy_style(self):
        global _VISUAL_STYLE_CLIPBOARD
        _VISUAL_STYLE_CLIPBOARD = serialize_chart_visual_state(self._current_state())

    def _paste_style(self):
        if not _VISUAL_STYLE_CLIPBOARD:
            return
        pasted = deserialize_chart_visual_state(_VISUAL_STYLE_CLIPBOARD)
        pasted.chart_type = self._state.chart_type
        self._loading = True
        self._load_state(pasted)
        self._loading = False
        self._preview()

    def visual_state(self) -> ChartVisualState:
        return self._current_state()


class DashboardItemWidget(QFrame):
    removeRequested = pyqtSignal(str)
    itemChanged = pyqtSignal()
    itemSelected = pyqtSignal(str)
    visualPanelRequested = pyqtSignal(str)
    selectionChanged = pyqtSignal(object)
    fieldBindingDropRequested = pyqtSignal(str, str, object)
    dragStarted = pyqtSignal(str, object)
    dragMoved = pyqtSignal(str, object)
    dragFinished = pyqtSignal(str, object)
    resizeStarted = pyqtSignal(str, object)
    resizeMoved = pyqtSignal(str, object)
    resizeFinished = pyqtSignal(str, object)
    linkStarted = pyqtSignal(str, object)
    linkMoved = pyqtSignal(str, object)
    linkFinished = pyqtSignal(str, object)
    linkCommandRequested = pyqtSignal(str)

    def __init__(self, item: DashboardChartItem, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelDashboardItem")
        self._item = item
        self._edit_mode = True
        self._highlight_mode = "idle"
        self._active_resize_mode = ""
        self._resize_margin = 10
        self._connector_radius = 6
        self._drag_candidate = False
        self._drag_active = False
        self._resize_active = False
        self._link_active = False
        self._active_link_side = ""
        self._press_pos = QPoint()
        self._header_pressed = False
        self._binding = item.binding.normalized()
        self._external_filters = {}
        self._zoom_scale = 1.0
        self._logical_chart_size = QSize()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("ModelDashboardCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(3)
        root.addWidget(self.card, 1)

        self.header = QFrame(self.card)
        self.header.setObjectName("ModelDashboardHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.drag_label = QLabel(_rt("Mover"), self.header)
        self.drag_label.setObjectName("ModelDashboardDragHandle")
        header_layout.addWidget(self.drag_label, 0)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(1)
        self.title_label = QLabel("", self.header)
        self.title_label.setObjectName("ModelDashboardItemTitle")
        self.title_label.setCursor(Qt.PointingHandCursor)
        self.title_label.setToolTip(_rt("Duplo clique para renomear"))
        self.title_label.setFont(ui_font())
        title_column.addWidget(self.title_label)
        self.subtitle_label = QLabel("", self.header)
        self.subtitle_label.setObjectName("ModelDashboardItemSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setFont(ui_font())
        title_column.addWidget(self.subtitle_label)
        header_layout.addLayout(title_column, 1)

        self.model_edit_btn = QToolButton(self.header)
        self.model_edit_btn.setObjectName("ModelDashboardHeaderIconButton")
        self.model_edit_btn.setCursor(Qt.PointingHandCursor)
        self.model_edit_btn.setToolTip(_rt("Alterar tipo de grafico"))
        model_icon = _icon_from_resource("ModelVisual-Donut.svg")
        self.model_edit_btn.setIcon(model_icon)
        self.model_edit_btn.setIconSize(QSize(16, 16))
        if model_icon.isNull():
            self.model_edit_btn.setText("T")
        self.model_edit_btn.clicked.connect(self._open_chart_model_menu)
        header_layout.addWidget(self.model_edit_btn, 0)

        self.personalize_btn = QToolButton(self.header)
        self.personalize_btn.setObjectName("ModelDashboardHeaderIconButton")
        self.personalize_btn.setCursor(Qt.PointingHandCursor)
        self.personalize_btn.setToolTip(_rt("Personalizar visual do grafico"))
        personalize_icon = _icon_from_resource("walker_chart_brush.svg")
        self.personalize_btn.setIcon(personalize_icon)
        self.personalize_btn.setIconSize(QSize(16, 16))
        if personalize_icon.isNull():
            self.personalize_btn.setText("P")
        self.personalize_btn.clicked.connect(self._request_visual_panel)
        header_layout.addWidget(self.personalize_btn, 0)

        self.link_command_btn = QPushButton("+", self.header)
        self.link_command_btn.setObjectName("ModelDashboardLinkCommandButton")
        self.link_command_btn.setCursor(Qt.PointingHandCursor)
        self.link_command_btn.setToolTip(_rt("Criar relacao com outro grafico"))
        self.link_command_btn.setFont(ui_font())
        self.link_command_btn.clicked.connect(lambda checked=False: self.linkCommandRequested.emit(self.item_id))
        header_layout.addWidget(self.link_command_btn, 0)
        self.link_command_btn.hide()

        self.remove_btn = QToolButton(self.header)
        self.remove_btn.setObjectName("ModelDashboardRemoveButton")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setToolTip(_rt("Fechar grafico"))
        close_icon = _icon_from_resource("model_close.svg")
        self.remove_btn.setIcon(close_icon)
        self.remove_btn.setIconSize(QSize(14, 14))
        if close_icon.isNull():
            self.remove_btn.setText("X")
        self.remove_btn.clicked.connect(lambda checked=False: self.removeRequested.emit(self.item_id))
        header_layout.addWidget(self.remove_btn, 0)

        card_layout.addWidget(self.header, 0)

        self.chart_widget = ReportChartWidget(self.card)
        self.chart_widget.setMinimumSize(220, 160)
        self.chart_widget.set_embedded_mode(True)
        self.chart_widget.selectionChanged.connect(self._handle_chart_selection)
        card_layout.addWidget(self.chart_widget, 1)

        self.drop_overlay = _DashboardVisualDropOverlay(self.card)
        self.drop_overlay.fieldDropped.connect(self._handle_field_drop)
        self.drop_overlay.hide()

        self.footer_label = QLabel("", self.card)
        self.footer_label.setObjectName("ModelDashboardItemFooter")
        self.footer_label.setFont(ui_font())
        card_layout.addWidget(self.footer_label, 0)

        self._overlay = _DashboardConnectorOverlay(self, self)
        self._overlay.raise_()

        self._event_widgets = (
            self,
            self.card,
            self.header,
            self.drag_label,
            self.title_label,
            self.subtitle_label,
            self.chart_widget,
            self.drop_overlay,
            self.drop_overlay.message_label,
            self.drop_overlay.preview_widget,
            self.footer_label,
        )
        for widget in self._event_widgets:
            widget.installEventFilter(self)
            try:
                widget.setMouseTracking(True)
            except Exception:
                log_exception("falha opcional ignorada")

        self._apply_styles()
        self.refresh(item)

    @property
    def item_id(self) -> str:
        return self._item.item_id

    @property
    def item(self) -> DashboardChartItem:
        return self._item

    @property
    def binding(self) -> DashboardChartBinding:
        return self._binding

    def set_binding(self, binding: Optional[DashboardChartBinding]):
        self._binding = (binding or DashboardChartBinding()).normalized()
        self._sync_chart_identity()

    def _has_minimum_binding(self) -> bool:
        return bool(self._binding.has_minimum_fields())

    def _drop_overlay_visible(self) -> bool:
        return bool(self._edit_mode and not self._has_minimum_binding())

    def _sync_drop_overlay(self):
        try:
            chart_rect = self.chart_widget.geometry()
            self.drop_overlay.setGeometry(chart_rect)
            self.drop_overlay.raise_()
            self.drop_overlay.setVisible(self._drop_overlay_visible())
            self.drop_overlay.set_chart_context(str(getattr(self._item.visual_state, "chart_type", "") or ""), self._binding)
        except Exception:
            log_exception("falha opcional ignorada")

    def _handle_field_drop(self, slot_name: str, payload):
        self.fieldBindingDropRequested.emit(self.item_id, str(slot_name or "").strip(), dict(payload or {}))

    def set_external_filters(self, filters):
        self._external_filters = dict(filters or {})
        self.chart_widget.set_external_filters(self._external_filters)

    def clear_local_selection(self):
        try:
            self.chart_widget.clear_selection(emit_signal=False)
        except Exception:
            log_exception("falha opcional ignorada")

    def visual_state(self) -> ChartVisualState:
        return copy.deepcopy(getattr(self._item, "visual_state", ChartVisualState()) or ChartVisualState())

    def apply_visual_state(self, state: ChartVisualState, *, emit_changed: bool = True):
        self._apply_visual_state_preview(state)
        if emit_changed:
            self.itemChanged.emit()

    def _sync_chart_identity(self):
        try:
            self.chart_widget.set_chart_identity(self._binding.to_dict())
        except Exception:
            log_exception("falha opcional ignorada")

    def _handle_chart_selection(self, payload):
        normalized = self._normalize_selection_payload(payload)
        self.selectionChanged.emit(normalized)

    def _normalize_selection_payload(self, payload):
        if not payload:
            semantic_key = self._binding.semantic_field_key or (
                self._binding.dimension_field.lower().strip() if self._binding.dimension_field else ""
            )
            return {
                "chart_id": self._binding.chart_id or self.item_id,
                "source_id": self._binding.source_id,
                "field": self._binding.dimension_field,
                "field_key": semantic_key,
                "semantic_field_key": semantic_key,
                "semantic_field_aliases": list(self._binding.semantic_field_aliases or []),
                "values": [],
                "feature_ids": [],
                "cleared": True,
            }
        data = dict(payload or {})
        data.setdefault("chart_id", self._binding.chart_id or self.item_id)
        data.setdefault("source_id", self._binding.source_id)
        semantic_key = self._binding.semantic_field_key or (
            self._binding.dimension_field.lower().strip() if self._binding.dimension_field else ""
        )
        data.setdefault("field", self._binding.semantic_field_key or self._binding.dimension_field)
        data.setdefault("field_key", semantic_key)
        data.setdefault("semantic_field_key", semantic_key)
        data.setdefault("semantic_field_aliases", list(self._binding.semantic_field_aliases or []))
        data.setdefault("measure_field", self._binding.measure_field)
        data.setdefault("aggregation", self._binding.aggregation)
        data.setdefault("source_name", self._binding.source_name)
        values = self._flatten_values(data.get("values"))
        if not values:
            raw_value = data.get("raw_category") or data.get("display_label") or data.get("category")
            values = self._flatten_values(raw_value)
        data["values"] = values
        data["feature_ids"] = [int(value) for value in list(data.get("feature_ids") or []) if value is not None]
        return data

    def _flatten_values(self, value):
        flattened = []

        def _walk(item):
            if item is None:
                return
            if isinstance(item, (list, tuple, set)):
                for sub_item in item:
                    _walk(sub_item)
                return
            text = str(item).strip()
            if text:
                flattened.append(text)

        _walk(value)
        return flattened

    def refresh(self, item: Optional[DashboardChartItem] = None):
        if item is not None:
            self._item = item
        layout = self._item.layout.normalized()
        self._item.layout = layout
        self._binding = self._item.binding.normalized()
        self.title_label.setText(self._item.display_title())
        self.subtitle_label.setText(self._item.subtitle or "")
        self._sync_chart_identity()
        self.chart_widget.set_payload(self._item.payload, empty_text="")
        self.chart_widget.chart_state = self._item.visual_state
        try:
            self.chart_widget.refresh_visual_state()
        except Exception:
            log_exception("falha opcional ignorada")
        self._sync_accessibility_tooltip()
        self.chart_widget.set_external_filters(self._external_filters)
        self.chart_widget.set_embedded_mode(True)
        self.chart_widget.clear_selection(emit_signal=False)
        self.chart_widget.update()
        self.footer_label.setText(f"{self._item.origin} | {layout.width}x{layout.height}")
        self.set_zoom_scale(self._zoom_scale, force=True)
        self.set_edit_mode(self._edit_mode)
        self._sync_drop_overlay()

    def set_zoom_scale(self, scale: float, force: bool = False):
        try:
            normalized = float(scale)
        except Exception:
            normalized = 1.0
        normalized = max(0.35, min(3.0, normalized))
        if not force and abs(normalized - self._zoom_scale) < 1e-3:
            return
        self._zoom_scale = normalized

        card_margin = max(0, int(round(4 * normalized)))
        card_spacing = max(0, int(round(3 * normalized)))
        header_margin = max(0, int(round(4 * normalized)))
        header_spacing = max(1, int(round(10 * normalized)))
        button_side = max(8, int(round(28 * normalized)))
        icon_side = max(5, int(round(16 * normalized)))
        remove_icon_side = max(5, int(round(14 * normalized)))

        try:
            self.card.layout().setContentsMargins(card_margin, card_margin, card_margin, card_margin)
            self.card.layout().setSpacing(card_spacing)
            self.header.layout().setContentsMargins(header_margin, header_margin, header_margin, header_margin)
            self.header.layout().setSpacing(header_spacing)
        except Exception:
            log_exception("falha opcional ignorada")

        self.model_edit_btn.setFixedSize(button_side, button_side)
        self.personalize_btn.setFixedSize(button_side, button_side)
        self.remove_btn.setFixedSize(max(8, button_side - 2), max(8, button_side - 2))
        self.model_edit_btn.setIconSize(QSize(icon_side, icon_side))
        self.personalize_btn.setIconSize(QSize(icon_side, icon_side))
        self.remove_btn.setIconSize(QSize(remove_icon_side, remove_icon_side))
        self.link_command_btn.setMinimumHeight(button_side)
        self.link_command_btn.setMaximumHeight(button_side)
        self.link_command_btn.setMinimumWidth(button_side)
        self.link_command_btn.setMaximumWidth(button_side)
        if hasattr(self.chart_widget, "set_display_scale"):
            try:
                self.chart_widget.set_display_scale(1.0)
            except Exception:
                log_exception("falha opcional ignorada")
        self.setMinimumSize(1, 1)
        self.chart_widget.setMinimumSize(1, 1)
        self._sync_logical_chart_render_size()

        title_font = ui_font()
        title_font.setPixelSize(max(5, min(36, int(round(13 * normalized)))))
        title_font.setWeight(600)
        self.title_label.setFont(title_font)
        supporting_font = ui_font()
        supporting_font.setPixelSize(max(4, min(30, int(round(11 * normalized)))))
        supporting_font.setWeight(400)
        self.subtitle_label.setFont(supporting_font)
        self.footer_label.setFont(supporting_font)
        self.drag_label.setFont(supporting_font)
        button_font = ui_font()
        button_font.setPixelSize(max(4, min(28, int(round(11 * normalized)))))
        button_font.setWeight(600)
        self.link_command_btn.setFont(button_font)

        self._apply_styles()

    def _fallback_logical_chart_size(self) -> QSize:
        layout = self._item.layout.normalized()
        return QSize(
            max(80, int(round(layout.width)) - 8),
            max(60, int(round(layout.height)) - 44),
        )

    def _sync_logical_chart_render_size(self, allow_capture: bool = False):
        zoom = max(0.0001, float(self._zoom_scale or 1.0))
        widget_size = self.chart_widget.size()
        if widget_size.width() >= 20 and widget_size.height() >= 20:
            self._logical_chart_size = QSize(
                max(20, int(round(float(widget_size.width()) / zoom))),
                max(20, int(round(float(widget_size.height()) / zoom))),
            )
        else:
            self._logical_chart_size = self._fallback_logical_chart_size()
        if hasattr(self.chart_widget, "set_fixed_render_size"):
            try:
                self.chart_widget.set_fixed_render_size(self._logical_chart_size)
            except Exception:
                log_exception("falha opcional ignorada")

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = bool(enabled)
        if not self._edit_mode:
            self._link_active = False
            self._active_link_side = ""
        self.drag_label.setVisible(self._edit_mode)
        self.remove_btn.setVisible(self._edit_mode)
        self.model_edit_btn.setVisible(self._edit_mode)
        self.personalize_btn.setVisible(self._edit_mode)
        self.link_command_btn.setVisible(self._edit_mode)
        self.subtitle_label.setVisible(False)
        self.footer_label.setVisible(False)
        self._sync_title_visibility()
        self.title_label.setToolTip(_rt("Duplo clique para renomear") if self._edit_mode else "")
        if self._edit_mode:
            try:
                margin = max(0, int(round(4 * self._zoom_scale)))
                spacing = max(0, int(round(3 * self._zoom_scale)))
                self.card.layout().setContentsMargins(margin, margin, margin, margin)
                self.card.layout().setSpacing(spacing)
            except Exception:
                log_exception("falha opcional ignorada")
        else:
            try:
                self.card.layout().setContentsMargins(0, 0, 0, 0)
                self.card.layout().setSpacing(0)
            except Exception:
                log_exception("falha opcional ignorada")
        if not self._edit_mode:
            self.unsetCursor()
        self._apply_styles()
        self._sync_drop_overlay()
        try:
            self._overlay.setVisible(self._edit_mode)
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
        except Exception:
            log_exception("falha opcional ignorada")
        self.update()

    def _sync_title_visibility(self):
        visual_state = getattr(self._item, "visual_state", None)
        show_title = bool(getattr(visual_state, "show_title", True))
        try:
            self.title_label.setVisible(show_title)
        except Exception:
            log_exception("falha opcional ignorada")

    def _sync_accessibility_tooltip(self):
        visual_state = getattr(self._item, "visual_state", None)
        alt_text = str(getattr(visual_state, "alt_text", "") or "").strip()
        try:
            self.chart_widget.setToolTip(alt_text)
            self.card.setToolTip(alt_text)
        except Exception:
            log_exception("falha opcional ignorada")

    def set_highlight_mode(self, mode: str):
        normalized = str(mode or "idle").strip().lower() or "idle"
        if normalized == self._highlight_mode:
            return
        self._highlight_mode = normalized
        self._apply_styles()
        self.update()
        try:
            self._overlay.update()
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_styles(self):
        zoom = max(0.35, min(3.0, float(self._zoom_scale or 1.0)))
        visual_state = getattr(self._item, "visual_state", None)
        border = "#D1D5DB"
        header_bg = "#FFFFFF"
        header_border = "#ECEFF3"
        card_bg = str(getattr(visual_state, "background_color", "#FFFFFF") or "#FFFFFF")
        if not bool(getattr(visual_state, "show_background", True)):
            card_bg = "transparent"
        title_color = str(getattr(visual_state, "title_color", "#1F2937") or "#1F2937")
        label_color = str(getattr(visual_state, "label_color", "#64748B") or "#64748B")
        try:
            border_radius = int(getattr(visual_state, "border_radius", 2) or 2)
        except Exception:
            border_radius = 2
        if border_radius == 8:
            border_radius = 2
        try:
            configured_title_size = int(getattr(visual_state, "title_size", 0) or 0)
        except Exception:
            configured_title_size = 0
        try:
            configured_label_size = int(getattr(visual_state, "label_size", 0) or 0)
        except Exception:
            configured_label_size = 0
        border_radius = max(0, min(8, border_radius))
        title_size = configured_title_size if configured_title_size > 0 else max(5, min(36, int(round(13 * zoom))))
        label_size = configured_label_size if configured_label_size > 0 else max(4, min(30, int(round(11 * zoom))))
        if bool(getattr(visual_state, "show_border", False)):
            border = str(getattr(visual_state, "border_color", border) or border)
        try:
            border_width = int(getattr(visual_state, "border_width", 1) or 1)
        except Exception:
            border_width = 1
        border_width = max(1, min(6, border_width))
        card_border = f"{border_width}px solid {border}"
        header_border_rule = f"1px solid {header_border}"
        if not self._edit_mode:
            card_bg = "transparent"
            card_border = "none"
            header_bg = "transparent"
            header_border_rule = "none"
        elif self._highlight_mode == "drag":
            border = "#9CA3AF"
            card_border = f"1px solid {border}"
        elif self._highlight_mode == "resize":
            border = "#6B7280"
            card_border = f"1px solid {border}"
        elif self._highlight_mode == "selected":
            border = "#A3A3A3"
            card_border = f"1px solid {border}"

        self.setStyleSheet(
            f"""
            QFrame#ModelDashboardItem {{
                background: transparent;
                border: none;
            }}
            QFrame#ModelDashboardCard {{
                background: {card_bg};
                border: {card_border};
                border-radius: {border_radius}px;
            }}
            QFrame#ModelDashboardHeader {{
                background: {header_bg};
                border: {header_border_rule};
                border-radius: 0px;
            }}
            QLabel#ModelDashboardItemTitle {{
                color: {title_color};
                font-size: {title_size}px;
                font-weight: 600;
            }}
            QLabel#ModelDashboardItemSubtitle,
            QLabel#ModelDashboardItemFooter,
            QLabel#ModelDashboardDragHandle {{
                color: {label_color};
                font-size: {label_size}px;
                font-weight: 400;
            }}
            QToolButton#ModelDashboardRemoveButton,
            QToolButton#ModelDashboardHeaderIconButton {{
                min-height: {max(8, int(round(24 * zoom)))}px;
                max-height: {max(8, int(round(24 * zoom)))}px;
                min-width: {max(8, int(round(24 * zoom)))}px;
                max-width: {max(8, int(round(24 * zoom)))}px;
                padding: 0;
                color: #374151;
                background: transparent;
                border: none;
                border-radius: {max(4, int(round(6 * zoom)))}px;
                font-weight: 400;
            }}
            QToolButton#ModelDashboardRemoveButton:hover,
            QToolButton#ModelDashboardHeaderIconButton:hover {{
                background: #F3F4F6;
            }}
            QPushButton#ModelDashboardLinkCommandButton {{
                min-height: {max(8, int(round(24 * zoom)))}px;
                max-height: {max(8, int(round(24 * zoom)))}px;
                min-width: {max(8, int(round(24 * zoom)))}px;
                max-width: {max(8, int(round(24 * zoom)))}px;
                padding: 0;
                color: #4B5563;
                background: transparent;
                border: none;
                border-radius: {max(6, int(round(8 * zoom)))}px;
                font-size: {max(4, min(28, int(round(11 * zoom))))}px;
                font-weight: 600;
            }}
            QPushButton#ModelDashboardLinkCommandButton:hover {{
                background: #F3F4F6;
            }}
            QFrame#ModelDashboardDropOverlay {{
                background: #FFFFFF;
                border: none;
                border-radius: 0px;
            }}
            QLabel#ModelDashboardEmptyVisualText {{
                color: #374151;
                font-size: {max(4, min(30, int(round(11 * zoom))))}px;
                font-weight: 400;
            }}
            QWidget#ModelDashboardEmptyPreview {{
                background: #F3F4F6;
                border: none;
            }}
            QFrame#ModelVisualDropSlot {{
                background: rgba(255, 255, 255, 235);
                border: 1px dashed #D6DEE8;
                border-radius: {max(6, int(round(8 * zoom)))}px;
            }}
            QFrame#ModelVisualDropSlot[dropActive="true"] {{
                background: #F8FBFF;
                border: 1px solid #93C5FD;
            }}
            QLabel#ModelVisualDropSlotLabel {{
                color: #334155;
                font-size: {max(4, min(28, int(round(10 * zoom))))}px;
                font-weight: 500;
            }}
            """
        )
        self._sync_drop_overlay()

    def _header_button_anchor(self, button: QWidget) -> QPoint:
        try:
            local = QPoint(max(8, int(button.width() / 2)), max(8, int(button.height()) + 2))
            return button.mapToGlobal(local)
        except Exception:
            try:
                return self.mapToGlobal(self.rect().center())
            except Exception:
                return QPoint()

    def _open_chart_model_menu(self):
        if not self._edit_mode:
            return
        menu = QMenu(self)
        type_group = QActionGroup(menu)
        type_group.setExclusive(True)

        priority_menu = menu.addMenu(_rt("Prioridade"))
        for chart_type in list(self.chart_widget.TYPE_PRIORITY or []):
            label = self.chart_widget._type_label(chart_type)
            action = QAction(label, menu, checkable=True)
            action.setChecked(str(self.chart_widget.chart_state.chart_type or "bar") == chart_type)
            action.triggered.connect(lambda checked=False, value=chart_type: self.chart_widget._set_chart_type(value))
            type_group.addAction(action)
            priority_menu.addAction(action)

        if priority_menu.actions():
            menu.addSeparator()

        for group_label, chart_types in list(self.chart_widget.TYPE_GROUPS or []):
            group_menu = menu.addMenu(_rt(str(group_label or "Tipos")))
            for chart_type in list(chart_types or []):
                label = self.chart_widget._type_label(chart_type)
                action = QAction(label, menu, checkable=True)
                action.setChecked(str(self.chart_widget.chart_state.chart_type or "bar") == chart_type)
                action.triggered.connect(lambda checked=False, value=chart_type: self.chart_widget._set_chart_type(value))
                type_group.addAction(action)
                group_menu.addAction(action)

        before = copy.deepcopy(self.chart_widget.chart_state)
        menu.exec_(self._header_button_anchor(self.model_edit_btn))
        if before != self.chart_widget.chart_state:
            self._item.visual_state = copy.deepcopy(self.chart_widget.chart_state)
            self.itemChanged.emit()

    def _open_chart_personalize_menu(self):
        if not self._edit_mode:
            return
        menu = QMenu(self)
        font_menu = menu.addMenu(_rt("Tamanho da fonte"))
        palette_menu = menu.addMenu(_rt("Paleta"))
        sort_menu = menu.addMenu(_rt("Ordenacao"))
        corners_menu = menu.addMenu(_rt("Cantos"))

        self.chart_widget._ensure_visual_state_compatibility()

        font_group = QActionGroup(menu)
        font_group.setExclusive(True)
        for scale, label in list(self.chart_widget.FONT_SCALE_PRESETS or []):
            action = QAction(_rt(label), menu, checkable=True)
            action.setChecked(abs(float(getattr(self.chart_widget.chart_state, "font_scale", 1.0) or 1.0) - float(scale)) < 0.01)
            action.triggered.connect(lambda checked=False, value=scale: self.chart_widget.set_font_scale(value))
            font_group.addAction(action)
            font_menu.addAction(action)

        palette_group = QActionGroup(menu)
        palette_group.setExclusive(True)
        for palette_name in dict(self.chart_widget.PALETTE_LABELS):
            action = QAction(self.chart_widget._palette_label(palette_name), menu, checkable=True)
            action.setChecked(str(self.chart_widget.chart_state.palette or "") == palette_name)
            action.triggered.connect(lambda checked=False, value=palette_name: self.chart_widget._set_chart_palette(value))
            palette_group.addAction(action)
            palette_menu.addAction(action)

        legend_action = QAction(_rt("Mostrar legenda"), menu, checkable=True)
        legend_action.setChecked(bool(self.chart_widget.chart_state.show_legend))
        legend_action.triggered.connect(self.chart_widget._toggle_show_legend)
        menu.addAction(legend_action)

        values_action = QAction(_rt("Mostrar valores"), menu, checkable=True)
        values_action.setChecked(bool(self.chart_widget.chart_state.show_values))
        values_action.triggered.connect(self.chart_widget._toggle_show_values)
        menu.addAction(values_action)

        percent_action = QAction(_rt("Mostrar percentual"), menu, checkable=True)
        percent_action.setChecked(bool(self.chart_widget.chart_state.show_percent))
        percent_action.setEnabled(bool(self.chart_widget._supports_percentage()))
        percent_action.triggered.connect(self.chart_widget._toggle_show_percent)
        menu.addAction(percent_action)

        grid_action = QAction(_rt("Mostrar grade"), menu, checkable=True)
        grid_action.setChecked(bool(self.chart_widget.chart_state.show_grid))
        grid_action.setEnabled(str(self.chart_widget.chart_state.chart_type or "") in {"bar", "barh", "line", "area"})
        grid_action.triggered.connect(self.chart_widget._toggle_show_grid)
        menu.addAction(grid_action)

        border_action = QAction(_rt("Mostrar borda"), menu, checkable=True)
        border_action.setChecked(bool(getattr(self.chart_widget.chart_state, "show_border", False)))
        border_action.triggered.connect(self.chart_widget._toggle_show_border)
        menu.addAction(border_action)

        background_action = QAction(_rt("Cor de fundo..."), menu)
        background_action.triggered.connect(lambda checked=False: self.chart_widget._pick_visual_color("background_color", "#FFFFFF"))
        menu.addAction(background_action)

        primary_action = QAction(_rt("Cor principal..."), menu)
        primary_action.triggered.connect(lambda checked=False: self.chart_widget._pick_visual_color("primary_color", "#5A3FE6"))
        menu.addAction(primary_action)

        border_color_action = QAction(_rt("Cor da borda..."), menu)
        border_color_action.setEnabled(bool(getattr(self.chart_widget.chart_state, "show_border", False)))
        border_color_action.triggered.connect(lambda checked=False: self.chart_widget._pick_visual_color("border_color", "#CBD5E1"))
        menu.addAction(border_color_action)

        properties_action = QAction(_rt("Propriedades visuais..."), menu)
        properties_action.triggered.connect(self._open_visual_properties_dialog)
        menu.addAction(properties_action)

        sort_group = QActionGroup(menu)
        sort_group.setExclusive(True)
        for sort_mode in dict(self.chart_widget.SORT_LABELS):
            action = QAction(self.chart_widget._sort_label(sort_mode), menu, checkable=True)
            action.setChecked(str(self.chart_widget.chart_state.sort_mode or "default") == sort_mode)
            action.triggered.connect(lambda checked=False, value=sort_mode: self.chart_widget._set_sort_mode(value))
            sort_group.addAction(action)
            sort_menu.addAction(action)

        corners_group = QActionGroup(menu)
        corners_group.setExclusive(True)
        straight_action = QAction(_rt("Retos"), menu, checkable=True)
        straight_action.setChecked(self.chart_widget._normalized_corner_style() == "square")
        straight_action.triggered.connect(lambda checked=False: self.chart_widget._set_bar_corner_style("square"))
        corners_group.addAction(straight_action)
        corners_menu.addAction(straight_action)

        rounded_action = QAction(_rt("Arredondados"), menu, checkable=True)
        rounded_action.setChecked(self.chart_widget._normalized_corner_style() == "rounded")
        rounded_action.triggered.connect(lambda checked=False: self.chart_widget._set_bar_corner_style("rounded"))
        corners_group.addAction(rounded_action)
        corners_menu.addAction(rounded_action)

        menu.addSeparator()
        reset_action = QAction(_rt("Restaurar visual padrao"), menu)
        reset_action.triggered.connect(self.chart_widget._reset_chart_style)
        menu.addAction(reset_action)

        before = copy.deepcopy(self.chart_widget.chart_state)
        menu.exec_(self._header_button_anchor(self.personalize_btn))
        if before != self.chart_widget.chart_state:
            self._item.visual_state = copy.deepcopy(self.chart_widget.chart_state)
            self._sync_title_visibility()
            self._apply_styles()
            self.itemChanged.emit()

    def _request_visual_panel(self):
        if not self._edit_mode:
            return
        self.itemSelected.emit(self.item_id)
        self.visualPanelRequested.emit(self.item_id)

    def _apply_visual_state_preview(self, state: ChartVisualState):
        self._item.visual_state = copy.deepcopy(state)
        self.chart_widget.chart_state = self._item.visual_state
        self.chart_widget._ensure_visual_state_compatibility()
        self.chart_widget.refresh_visual_state()
        self.chart_widget._rerender_chart(transition="data")
        self._sync_accessibility_tooltip()
        self._sync_title_visibility()
        self._apply_styles()

    def _open_visual_properties_dialog(self):
        if not self._edit_mode:
            return
        self.chart_widget._ensure_visual_state_compatibility()
        original = copy.deepcopy(self.chart_widget.chart_state)
        default_state = self.chart_widget._default_visual_state(self.chart_widget._payload)
        default_state.chart_type = original.chart_type
        dialog = VisualPropertiesDialog(
            original,
            default_state,
            self._apply_visual_state_preview,
            self,
        )
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self._apply_visual_state_preview(dialog.visual_state())
            self.itemChanged.emit()
            return
        self._apply_visual_state_preview(original)

    def _event_global_pos(self, event) -> QPoint:
        try:
            return event.globalPos()
        except Exception:
            try:
                return self.mapToGlobal(event.pos())
            except Exception:
                return QPoint()

    def _map_event_pos(self, watched: QWidget, event) -> QPoint:
        try:
            local_pos = event.pos()
        except Exception:
            return QPoint()
        if watched is self:
            return local_pos
        try:
            return watched.mapTo(self, local_pos)
        except Exception:
            return local_pos

    def _header_drag_rect(self) -> QRect:
        return self.header.geometry()

    def _resize_mode_for_pos(self, pos: QPoint) -> str:
        rect = self.rect()
        margin = self._resize_margin
        if rect.width() <= 0 or rect.height() <= 0:
            return ""
        near_left = pos.x() <= rect.left() + margin
        near_right = pos.x() >= rect.right() - margin
        near_top = pos.y() <= rect.top() + margin
        near_bottom = pos.y() >= rect.bottom() - margin
        if near_left and near_top:
            return "top_left"
        if near_right and near_top:
            return "top_right"
        if near_left and near_bottom:
            return "bottom_left"
        if near_right and near_bottom:
            return "bottom_right"
        if near_left:
            return "left"
        if near_right:
            return "right"
        if near_top:
            return "top"
        if near_bottom:
            return "bottom"
        return ""

    def _cursor_for_resize_mode(self, mode: str):
        return {
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "top_left": Qt.SizeFDiagCursor,
            "bottom_right": Qt.SizeFDiagCursor,
            "top_right": Qt.SizeBDiagCursor,
            "bottom_left": Qt.SizeBDiagCursor,
        }.get(mode, Qt.ArrowCursor)

    def _set_hover_cursor(self, pos: QPoint):
        if not self._edit_mode:
            self.unsetCursor()
            return
        connector_side = self.connector_hit_side(pos)
        if connector_side:
            self.setCursor(Qt.CrossCursor)
            return
        resize_mode = self._resize_mode_for_pos(pos)
        if resize_mode:
            self.setCursor(self._cursor_for_resize_mode(resize_mode))
            return
        if self._header_drag_rect().contains(pos):
            self.setCursor(Qt.OpenHandCursor if not self._drag_active else Qt.ClosedHandCursor)
            return
        self.unsetCursor()

    def _start_drag(self, global_pos: QPoint):
        self._drag_candidate = True
        self._drag_active = False
        self._header_pressed = True
        self._press_pos = global_pos
        self.setCursor(Qt.ClosedHandCursor)

    def _start_resize(self, resize_mode: str, global_pos: QPoint):
        self._resize_active = True
        self._active_resize_mode = resize_mode
        self._press_pos = global_pos
        self.set_highlight_mode("resize")
        self.resizeStarted.emit(
            self.item_id,
            {
                "mode": resize_mode,
                "global_pos": global_pos,
            },
        )

    def _start_link(self, side: str, global_pos: QPoint):
        self._link_active = True
        self._active_link_side = str(side or "").strip().lower()
        self._press_pos = global_pos
        self.set_highlight_mode("drag")
        self.linkStarted.emit(
            self.item_id,
            {
                "side": self._active_link_side,
                "global_pos": global_pos,
            },
        )

    def _emit_drag_move(self, global_pos: QPoint):
        if not self._drag_active:
            return
        self.dragMoved.emit(self.item_id, {"global_pos": global_pos})

    def _emit_resize_move(self, global_pos: QPoint):
        if not self._resize_active:
            return
        self.resizeMoved.emit(
            self.item_id,
            {
                "mode": self._active_resize_mode,
                "global_pos": global_pos,
            },
        )

    def _emit_link_move(self, global_pos: QPoint):
        if not self._link_active:
            return
        self.linkMoved.emit(
            self.item_id,
            {
                "side": self._active_link_side,
                "global_pos": global_pos,
            },
        )

    def _finish_drag(self, global_pos: QPoint):
        self.dragFinished.emit(self.item_id, {"global_pos": global_pos})
        self._drag_candidate = False
        self._drag_active = False
        self._header_pressed = False
        self.set_highlight_mode("idle")
        self.setCursor(Qt.OpenHandCursor if self._edit_mode else Qt.ArrowCursor)

    def _finish_resize(self, global_pos: QPoint):
        self.resizeFinished.emit(
            self.item_id,
            {
                "mode": self._active_resize_mode,
                "global_pos": global_pos,
            },
        )
        self._resize_active = False
        self._active_resize_mode = ""
        self.set_highlight_mode("idle")
        self.unsetCursor()

    def _finish_link(self, global_pos: QPoint):
        self.linkFinished.emit(
            self.item_id,
            {
                "side": self._active_link_side,
                "global_pos": global_pos,
            },
        )
        self._link_active = False
        self._active_link_side = ""
        self.set_highlight_mode("idle")
        self.unsetCursor()

    def connector_points(self):
        rect = self.rect().adjusted(1, 1, -1, -1)
        return {
            "left": QPoint(rect.left(), rect.center().y()),
            "right": QPoint(rect.right(), rect.center().y()),
            "top": QPoint(rect.center().x(), rect.top()),
            "bottom": QPoint(rect.center().x(), rect.bottom()),
        }

    def display_handle_points(self):
        rect = self.rect().adjusted(1, 1, -1, -1)
        return [
            QPoint(rect.left(), rect.top()),
            QPoint(rect.center().x(), rect.top()),
            QPoint(rect.right(), rect.top()),
            QPoint(rect.right(), rect.center().y()),
            QPoint(rect.right(), rect.bottom()),
            QPoint(rect.center().x(), rect.bottom()),
            QPoint(rect.left(), rect.bottom()),
            QPoint(rect.left(), rect.center().y()),
        ]

    def connector_point(self, side: str) -> QPoint:
        points = self.connector_points()
        return QPoint(points.get(str(side or "").strip().lower(), points["right"]))

    def connector_radius(self) -> int:
        return int(self._connector_radius)

    def connector_hit_side(self, pos: QPoint) -> str:
        radius = max(6, int(self._connector_radius) + 3)
        for side, point in self.connector_points().items():
            dx = int(pos.x()) - int(point.x())
            dy = int(pos.y()) - int(point.y())
            if (dx * dx + dy * dy) <= int(radius * radius):
                return side
        return ""

    def eventFilter(self, watched, event):
        if watched not in self._event_widgets:
            return super().eventFilter(watched, event)

        event_type = event.type()
        local_pos = self._map_event_pos(watched, event)
        global_pos = self._event_global_pos(event)

        if watched is self.chart_widget and event_type == QEvent.Resize:
            self._sync_logical_chart_render_size()
            return super().eventFilter(watched, event)

        if event_type == QEvent.Wheel:
            canvas = self._find_canvas_host()
            if canvas is not None and hasattr(canvas, "is_edit_mode"):
                try:
                    if not canvas.is_edit_mode():
                        try:
                            event.accept()
                        except Exception:
                            log_exception("falha opcional ignorada")
                        return True
                except Exception:
                    log_exception("falha opcional ignorada")
            if canvas is not None and hasattr(canvas, "_handle_wheel_zoom"):
                try:
                    if canvas._handle_wheel_zoom(event):
                        return True
                except Exception:
                    return False
            return False

        if not self._edit_mode:
            return super().eventFilter(watched, event)

        if event_type == QEvent.MouseMove:
            if self._link_active:
                self._emit_link_move(global_pos)
                return True
            if self._resize_active:
                self._emit_resize_move(global_pos)
                return True
            if self._drag_candidate and self._header_pressed:
                distance = (global_pos - self._press_pos).manhattanLength()
                if not self._drag_active and distance >= 5:
                    self._drag_active = True
                    self.set_highlight_mode("drag")
                    self.dragStarted.emit(self.item_id, {"global_pos": self._press_pos})
                if self._drag_active:
                    self._emit_drag_move(global_pos)
                    return True
            self._set_hover_cursor(local_pos)
            return False

        if event_type == QEvent.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.LeftButton:
            self.itemSelected.emit(self.item_id)
            link_side = self.connector_hit_side(local_pos)
            if link_side:
                self._start_link(link_side, global_pos)
                return True
            resize_mode = self._resize_mode_for_pos(local_pos)
            if resize_mode:
                self._start_resize(resize_mode, global_pos)
                return True
            if watched is self.title_label:
                return False
            if watched not in {self.chart_widget, self.title_label} and self._header_drag_rect().contains(local_pos):
                self._start_drag(global_pos)
                return True
            return False

        if event_type == QEvent.MouseButtonDblClick and watched is self.title_label and self._edit_mode:
            self._edit_title()
            return True

        if event_type == QEvent.MouseButtonRelease and getattr(event, "button", lambda: None)() == Qt.LeftButton:
            if self._link_active:
                self._finish_link(global_pos)
                return True
            if self._resize_active:
                self._finish_resize(global_pos)
                return True
            if self._drag_active:
                self._finish_drag(global_pos)
                return True
            if self._drag_candidate:
                self._drag_candidate = False
                self._header_pressed = False
                self._set_hover_cursor(local_pos)
                return True
            return False

        return super().eventFilter(watched, event)

    def _find_canvas_host(self):
        widget = self.parentWidget()
        while widget is not None:
            if hasattr(widget, "_handle_wheel_zoom"):
                return widget
            widget = widget.parentWidget()
        return None

    def _edit_title(self):
        current = self._item.display_title()
        try:
            new_text, accepted = slim_get_text(
                parent=self,
                title=_rt("Editar titulo"),
                label_text=_rt("Titulo do grafico"),
                text=current,
                placeholder=_rt("Digite o novo titulo"),
                helper_text=_rt("Altere apenas o nome exibido no card."),
                accept_label=_rt("Salvar"),
            )
        except Exception:
            return
        if not accepted:
            return
        self._item.title = str(new_text or "").strip()
        self.title_label.setText(self._item.display_title())
        self.itemChanged.emit()

    def leaveEvent(self, event):
        if not self._drag_active and not self._resize_active and not self._link_active:
            self.unsetCursor()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_logical_chart_render_size(allow_capture=True)
        try:
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
        except Exception:
            log_exception("falha opcional ignorada")
        self._sync_drop_overlay()
