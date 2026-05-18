from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

try:
    from qgis.PyQt.QtCore import QPoint, QSize, Qt, QMimeData, pyqtSignal
    from qgis.PyQt.QtGui import QDrag
    from qgis.PyQt.QtWidgets import (
        QComboBox,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except Exception:
    QPoint = QSize = Qt = QMimeData = QDrag = None
    pyqtSignal = None
    QComboBox = QFormLayout = QFrame = QHBoxLayout = QLabel = QLineEdit = QScrollArea = QSizePolicy = QSpinBox = QToolButton = QVBoxLayout = QWidget = object

from ..dashboard_models import (
    FieldBindingItem,
    ROLE_FILTERS,
    ROLE_LEGEND,
    ROLE_SIZE,
    ROLE_TOOLTIP,
    ROLE_VALUES,
    ROLE_X_AXIS,
    ROLE_Y_AXIS,
    binding_slot_definitions,
    is_binding_slot_compatible,
    normalize_chart_type,
)
try:
    from ..field_list_helpers import field_kind_badge
except Exception:

    def field_kind_badge(kind: str) -> str:
        normalized = str(kind or "").strip().lower()
        return {"numeric": "#", "date": "D", "text": "T"}.get(normalized, "?")

try:
    from ..utils.fonts import ui_font
except Exception:

    def ui_font(*_args, **_kwargs):
        class _FallbackFont:
            def setPixelSize(self, _size):
                return None

        return _FallbackFont()

try:
    from ..utils.i18n_runtime import tr_text as _rt
except Exception:

    def _rt(text: str, **kwargs) -> str:
        return str(text).format(**kwargs) if kwargs else str(text)

try:
    from ..utils.logging_utils import log_exception
except Exception:

    def log_exception(_message: str):
        return None

try:
    from .model_data_panel import MODEL_FIELD_MIME
except Exception:
    MODEL_FIELD_MIME = "application/x-summarizer-model-field"

try:
    from .model_theme import _force_model_white_background, _model_builder_trash_icon, _model_tinted_svg_icon
except Exception:

    def _force_model_white_background(_widget):
        return None

    def _model_builder_trash_icon():
        return None

    def _model_tinted_svg_icon(_name: str, _size: int = 18, _color: str = ""):
        return None


@dataclass
class ModelBuilderPanelParts:
    panel: object
    builder_empty_label: object
    builder_construct_card: object
    builder_selected_visual_label: object
    builder_binding_slots: Dict[str, object]
    builder_format_card: object
    builder_option_labels: Dict[str, object]
    builder_agg_combo: object
    builder_topn_spin: object
    builder_title_edit: object
    builder_dimension_combo: object
    builder_value_combo: object
    builder_visual_buttons: Dict[str, object]
    builder_selection_widgets: list


def visual_type_specs():
    return [
        (_rt("Colunas"), "bar", "ModelVisual-Column.svg", _rt("Colunas - compara valores por categoria.")),
        (_rt("Barras"), "barh", "ModelVisual-Bar.svg", _rt("Barras - compara categorias em eixo horizontal.")),
        (_rt("Linha"), "line", "ModelVisual-Line.svg", _rt("Linha - mostra tendência ao longo do tempo.")),
        (_rt("Area"), "area", "ModelVisual-Area.svg", _rt("Area - destaca a evolução acumulada dos valores.")),
        (_rt("Pizza"), "pie", "ModelVisual-Pie.svg", _rt("Pizza - mostra composição entre partes.")),
        (_rt("Rosca"), "donut", "ModelVisual-Donut.svg", _rt("Rosca - composição com foco no total.")),
        (_rt("Card"), "card", "ModelVisual-Card.svg", _rt("Card - destaca um único indicador.")),
        (_rt("KPI"), "kpi", "ModelVisual-KPI.svg", _rt("KPI - acompanha um indicador principal.")),
        (_rt("Medidor"), "gauge", "ModelVisual-Gauge.svg", _rt("Medidor - mostra progresso em relação a uma meta.")),
        (_rt("Matriz"), "matrix", "ModelVisual-Matrix.svg", _rt("Matriz - cruza linhas, colunas e valores.")),
        (_rt("Segmentador"), "slicer", "ModelVisual-Slicer.svg", _rt("Segmentador - lista categorias para filtragem visual.")),
        (_rt("Coluna agrupada"), "column_clustered", "ModelVisual-ColumnClustered.svg", _rt("Coluna agrupada - compara séries lado a lado.")),
        (_rt("Coluna empilhada"), "column_stacked", "ModelVisual-ColumnStacked.svg", _rt("Coluna empilhada - mostra partes dentro de cada coluna.")),
        (_rt("Barra 100%"), "bar100_stacked", "ModelVisual-Bar100Stacked.svg", _rt("Barra 100% - compara proporções entre categorias.")),
        (_rt("Combo"), "combo", "ModelVisual-Combo.svg", _rt("Combo - combina barras e linha no mesmo visual.")),
        (_rt("Dispersao"), "scatter", "ModelVisual-Scatter.svg", _rt("Dispersão - compara X, Y e tamanho.")),
        (_rt("Treemap"), "treemap", "ModelVisual-Treemap.svg", _rt("Treemap - mostra participação por áreas.")),
        (_rt("Cascata"), "waterfall", "ModelVisual-Waterfall.svg", _rt("Cascata - destaca variações positivas e negativas.")),
        (_rt("Funil"), "funnel", "ModelVisual-Funnel.svg", _rt("Funil - mostra etapas em sequência.")),
    ]


def visual_type_labels() -> Dict[str, str]:
    return {str(chart_type): str(label) for label, chart_type, _icon, _tooltip in visual_type_specs()}


def chart_type_label(chart_type: str) -> str:
    return visual_type_labels().get(str(chart_type or "").strip().lower(), _rt("Grafico"))


def selected_builder_chart_type_from_buttons(buttons: Optional[Dict[str, object]]) -> str:
    for chart_type, button in dict(buttons or {}).items():
        try:
            if button.isChecked():
                return normalize_chart_type(chart_type)
        except Exception:
            log_exception("falha opcional ignorada")
    return "bar"


def builder_has_selection(item: object, binding: object) -> bool:
    return item is not None and binding is not None


def is_valid_binding_slot(chart_type: str, slot_name: str, field_group: str) -> bool:
    normalized_slot = str(slot_name or "").strip()
    if not normalized_slot or normalized_slot == "auto":
        return False
    return is_binding_slot_compatible(normalize_chart_type(chart_type or "bar"), normalized_slot, str(field_group or "other").strip().lower() or "other")


def binding_slot_label(chart_type: str, slot_name: str) -> str:
    normalized_slot = str(slot_name or "").strip()
    for slot in binding_slot_definitions(normalize_chart_type(chart_type or "bar")):
        if str(slot.get("name") or "") == normalized_slot:
            return str(slot.get("label") or normalized_slot)
    return normalized_slot


if pyqtSignal is not None:

    class _ModelFieldBindingChip(QFrame):
        removeRequested = pyqtSignal(str)
        aggregationChanged = pyqtSignal(str, str)
        moveRequested = pyqtSignal(str, int)

        def __init__(self, binding_item: FieldBindingItem, parent=None, *, source_item_id: str = ""):
            super().__init__(parent)
            self.binding_item = binding_item.normalized()
            self.source_item_id = str(source_item_id or "").strip()
            self._drag_start_pos = QPoint()
            self.setObjectName("ModelBindingFieldChip")
            self.setCursor(Qt.OpenHandCursor)
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(4, 2, 3, 2)
            layout.setSpacing(3)

            badge = QLabel(field_kind_badge(self.binding_item.type), self)
            badge.setObjectName("ModelBindingFieldBadge")
            badge.setAlignment(Qt.AlignCenter)
            layout.addWidget(badge, 0)

            name = QLabel(self.binding_item.display_name or self.binding_item.field, self)
            name.setObjectName("ModelBindingFieldName")
            name.setToolTip(self.binding_item.field)
            name.setMinimumWidth(0)
            name.setMaximumWidth(16777215)
            name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            layout.addWidget(name, 1)

            self.aggregation_combo = QComboBox(self)
            self.aggregation_combo.setObjectName("ModelBindingAggregationCombo")
            self.aggregation_combo.setFixedWidth(58)
            for label, value in (
                (_rt("Sem agreg."), "none"),
                (_rt("Soma"), "sum"),
                (_rt("Contagem"), "count"),
                (_rt("Media"), "avg"),
                (_rt("Min"), "min"),
                (_rt("Max"), "max"),
                (_rt("Unicos"), "unique_count"),
            ):
                self.aggregation_combo.addItem(label, value)
            index = self.aggregation_combo.findData(self.binding_item.aggregation)
            self.aggregation_combo.setCurrentIndex(index if index >= 0 else 0)
            self.aggregation_combo.currentIndexChanged.connect(self._emit_aggregation_changed)
            self.aggregation_combo.setVisible(self.binding_item.aggregation != "none" or self.binding_item.role in {ROLE_VALUES, ROLE_Y_AXIS, ROLE_SIZE})
            layout.addWidget(self.aggregation_combo, 0)

            for text, delta, tooltip in (("↑", -1, _rt("Mover para cima")), ("↓", 1, _rt("Mover para baixo"))):
                button = QToolButton(self)
                button.setObjectName("ModelBindingSlotMove")
                button.setText(text)
                button.setCursor(Qt.PointingHandCursor)
                button.setAutoRaise(True)
                button.setFixedSize(14, 16)
                button.setToolTip(tooltip)
                button.clicked.connect(lambda checked=False, value=delta: self.moveRequested.emit(self.binding_item.field, value))
                layout.addWidget(button, 0)

            remove = QToolButton(self)
            remove.setObjectName("ModelBindingSlotRemove")
            remove.setCursor(Qt.PointingHandCursor)
            remove.setAutoRaise(True)
            remove.setFixedSize(18, 18)
            icon = _model_builder_trash_icon()
            if icon is not None:
                remove.setIcon(icon)
            remove.setIconSize(QSize(14, 14))
            remove.setToolTip(_rt("Remover campo"))
            remove.clicked.connect(lambda checked=False: self.removeRequested.emit(self.binding_item.field))
            layout.addWidget(remove, 0)

        def _emit_aggregation_changed(self):
            aggregation = str(self.aggregation_combo.currentData() or "none")
            self.aggregationChanged.emit(self.binding_item.field, aggregation)

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                self._drag_start_pos = event.pos()
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if not (event.buttons() & Qt.LeftButton):
                super().mouseMoveEvent(event)
                return
            if (event.pos() - self._drag_start_pos).manhattanLength() < 6:
                super().mouseMoveEvent(event)
                return
            payload = {
                "field_name": self.binding_item.field,
                "display_name": self.binding_item.display_name or self.binding_item.field,
                "field_group": self.binding_item.type,
                "field_kind": self.binding_item.type,
                "aggregation": self.binding_item.aggregation,
                "source_slot": self.binding_item.role,
                "source_item_id": self.source_item_id,
            }
            mime = QMimeData()
            mime.setData(MODEL_FIELD_MIME, json.dumps(payload).encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            self.setCursor(Qt.ClosedHandCursor)
            try:
                drag.exec_(Qt.MoveAction)
            finally:
                self.setCursor(Qt.OpenHandCursor)
            super().mouseMoveEvent(event)


    class _ModelBindingSlot(QFrame):
        fieldDropped = pyqtSignal(str, object)
        removeRequested = pyqtSignal(str, str)
        aggregationChanged = pyqtSignal(str, str, str)
        moveRequested = pyqtSignal(str, str, int)

        def __init__(self, slot_name: str, label: str, parent=None):
            super().__init__(parent)
            self.slot_name = str(slot_name or "").strip()
            self._source_item_id = ""
            self.setObjectName("ModelBindingSlot")
            self.setAcceptDrops(True)
            self._active = False

            self._layout = QVBoxLayout(self)
            self._layout.setContentsMargins(6, 5, 6, 6)
            self._layout.setSpacing(4)

            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(4)

            self.label_widget = QLabel(label, self)
            self.label_widget.setObjectName("ModelBindingSlotLabel")
            self.label_widget.setFont(ui_font(8, weight=500))
            header.addWidget(self.label_widget, 1)
            self._layout.addLayout(header, 0)

            self.value_widget = QLabel(_rt("Arraste campos aqui"), self)
            self.value_widget.setObjectName("ModelBindingSlotValue")
            self.value_widget.setFont(ui_font(8))
            self.value_widget.setStyleSheet("QLabel#ModelBindingSlotValue { color: #64748B; font-size: 8pt; font-weight: 400; background: #FFFFFF; }")
            self.value_widget.setWordWrap(True)
            self._layout.addWidget(self.value_widget, 0)

            self.chips_host = QWidget(self)
            self.chips_host.setObjectName("ModelBindingSlotChips")
            self.chips_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.chips_layout = QVBoxLayout(self.chips_host)
            self.chips_layout.setContentsMargins(0, 0, 0, 0)
            self.chips_layout.setSpacing(3)
            self._layout.addWidget(self.chips_host, 0)
            self._chip_widgets = []

        def set_value(self, text: str, *, placeholder: str = ""):
            self.set_values([text] if str(text or "").strip() else [], placeholder=placeholder)

        def set_label(self, text: str):
            self.label_widget.setText(str(text or ""))

        def set_values(self, values, *, placeholder: str = "", source_item_id: str = ""):
            self._source_item_id = str(source_item_id or "").strip()
            clean_values = []
            for index, value in enumerate(list(values or [])):
                if isinstance(value, FieldBindingItem):
                    item = value.normalized(self.slot_name, index)
                elif isinstance(value, dict):
                    item = FieldBindingItem.from_payload(value, self.slot_name, index)
                else:
                    item = FieldBindingItem.from_payload(str(value or "").strip(), self.slot_name, index)
                if item is not None and item.field:
                    clean_values.append(item)
            for widget in list(getattr(self, "_chip_widgets", []) or []):
                self.chips_layout.removeWidget(widget)
                widget.deleteLater()
            self._chip_widgets = []
            if clean_values:
                self.value_widget.hide()
                self.chips_host.show()
                for item in clean_values:
                    chip = _ModelFieldBindingChip(item, self.chips_host, source_item_id=self._source_item_id)
                    chip.removeRequested.connect(lambda field_name, slot=self.slot_name: self.removeRequested.emit(slot, field_name))
                    chip.aggregationChanged.connect(lambda field_name, aggregation, slot=self.slot_name: self.aggregationChanged.emit(slot, field_name, aggregation))
                    chip.moveRequested.connect(lambda field_name, delta, slot=self.slot_name: self.moveRequested.emit(slot, field_name, delta))
                    self.chips_layout.addWidget(chip, 0)
                    self._chip_widgets.append(chip)
                self.setProperty("filled", True)
            else:
                self.chips_host.hide()
                self.value_widget.show()
                self.value_widget.setText(str(placeholder or _rt("Adicionar campo\nArraste campos aqui")))
                self.setProperty("filled", False)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

        def set_active(self, active: bool):
            self._active = bool(active)
            self.setProperty("dropActive", self._active)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

        def dragEnterEvent(self, event):
            try:
                if event.mimeData().hasFormat(MODEL_FIELD_MIME):
                    self.set_active(True)
                    event.acceptProposedAction()
                    return
            except Exception:
                log_exception("falha opcional ignorada")
            event.ignore()

        def dragMoveEvent(self, event):
            try:
                if event.mimeData().hasFormat(MODEL_FIELD_MIME):
                    self.set_active(True)
                    event.acceptProposedAction()
                    return
            except Exception:
                log_exception("falha opcional ignorada")
            event.ignore()

        def dragLeaveEvent(self, event):
            self.set_active(False)
            super().dragLeaveEvent(event)

        def dropEvent(self, event):
            self.set_active(False)
            try:
                if not event.mimeData().hasFormat(MODEL_FIELD_MIME):
                    event.ignore()
                    return
                payload = json.loads(bytes(event.mimeData().data(MODEL_FIELD_MIME)).decode("utf-8"))
            except Exception:
                payload = None
            if not isinstance(payload, dict):
                event.ignore()
                return
            self.fieldDropped.emit(self.slot_name, payload)
            event.acceptProposedAction()

else:

    class _ModelFieldBindingChip:  # pragma: no cover - fallback for non-QGIS unit imports
        pass


    class _ModelBindingSlot:  # pragma: no cover - fallback for non-QGIS unit imports
        pass


def build_visual_type_buttons(
    parent: QWidget,
    layout,
    visual_specs: Iterable[tuple],
    on_visual_selected: Callable[[str], None],
    *,
    button_size: int = 24,
    icon_size: int = 15,
) -> Dict[str, object]:
    buttons = {}
    for label_text, chart_type, icon_name, tooltip_text in visual_specs:
        button = QToolButton(parent)
        button.setObjectName("ModelVisualTypeButton")
        button.setProperty("modelIconName", icon_name)
        button.setProperty("modelIconSize", icon_size)
        button.setProperty("visualType", chart_type)
        button.setCheckable(True)
        button.setText("")
        icon = _model_tinted_svg_icon(icon_name, icon_size)
        if icon is not None:
            button.setIcon(icon)
        button.setToolTip(label_text)
        button.setStatusTip("")
        button.setWhatsThis("")
        button.setAccessibleName(label_text)
        button.setAccessibleDescription(tooltip_text)
        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        button.setAutoRaise(True)
        button.setFixedSize(button_size, button_size)
        button.setIconSize(QSize(icon_size, icon_size))
        button.clicked.connect(lambda checked=False, value=chart_type: on_visual_selected(value))
        buttons[chart_type] = button
        layout.addWidget(button, 0)
    return buttons


def build_model_builder_panel(
    parent: QWidget,
    *,
    visual_specs: Iterable[tuple],
    on_value_changed: Callable,
    on_binding_controls_changed: Callable,
    on_field_dropped: Callable,
    on_remove_requested: Callable,
    on_aggregation_changed: Callable,
    on_move_requested: Callable,
) -> ModelBuilderPanelParts:
    panel = QFrame(parent)
    panel.setObjectName("ModelBuilderPanel")
    _force_model_white_background(panel)

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 6, 8, 8)
    layout.setSpacing(4)

    scroll = QScrollArea(panel)
    scroll.setObjectName("ModelBuilderScroll")
    _force_model_white_background(scroll)
    scroll.setStyleSheet(
        """
        QScrollArea#ModelBuilderScroll {
            background: #FFFFFF;
            background-color: #FFFFFF;
            border: none;
        }
        QScrollArea#ModelBuilderScroll QWidget,
        QScrollArea#ModelBuilderScroll QFrame,
        QScrollArea#ModelBuilderScroll QAbstractScrollArea,
        QScrollArea#ModelBuilderScroll QAbstractScrollArea::viewport {
            background: #FFFFFF;
            background-color: #FFFFFF;
        }
        """
    )
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.viewport().setObjectName("ModelBuilderScrollViewport")
    _force_model_white_background(scroll.viewport())
    scroll.viewport().setStyleSheet("background: #FFFFFF; background-color: #FFFFFF;")
    layout.addWidget(scroll, 1)

    host = QWidget(scroll)
    host.setObjectName("ModelBuilderHost")
    _force_model_white_background(host)
    host.setStyleSheet("QWidget#ModelBuilderHost { background: #FFFFFF; background-color: #FFFFFF; }")
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(6)
    scroll.setWidget(host)

    builder_empty_label = QFrame(panel)
    builder_empty_label.setObjectName("ModelBuilderEmptyState")
    _force_model_white_background(builder_empty_label)
    builder_empty_label.setFrameShape(QFrame.NoFrame)
    builder_empty_label.setStyleSheet(
        """
        QFrame#ModelBuilderEmptyState,
        QFrame#ModelBuilderEmptyState QWidget,
        QFrame#ModelBuilderEmptyState QLabel {
            background: #FFFFFF;
            background-color: #FFFFFF;
            border: none;
        }
        """
    )
    empty_layout = QVBoxLayout(builder_empty_label)
    empty_layout.setContentsMargins(8, 6, 8, 6)
    empty_layout.setSpacing(0)
    empty_text = QLabel(_rt("Selecione um visual para configurar os campos e as opções."), builder_empty_label)
    empty_text.setObjectName("ModelBuilderEmptyStateLabel")
    empty_text.setFont(ui_font(8))
    empty_text.setStyleSheet("QLabel#ModelBuilderEmptyStateLabel { color: #64748B; font-size: 8pt; font-weight: 400; background: #FFFFFF; }")
    empty_text.setWordWrap(True)
    empty_layout.addWidget(empty_text)
    host_layout.addWidget(builder_empty_label, 0)

    builder_construct_card = QFrame(panel)
    builder_construct_card.setObjectName("ModelBuilderSoftDividerSection")
    _force_model_white_background(builder_construct_card)
    construct_layout = QVBoxLayout(builder_construct_card)
    construct_layout.setContentsMargins(8, 8, 8, 8)
    construct_layout.setSpacing(6)
    construct_title = QLabel(_rt("Construir visual"), builder_construct_card)
    construct_title.setObjectName("ModelBuilderSectionTitle")
    construct_title.setFont(ui_font(9, weight=500))
    construct_layout.addWidget(construct_title, 0)
    builder_selected_visual_label = QLabel(_rt("Nenhum visual selecionado"), builder_construct_card)
    builder_selected_visual_label.setObjectName("ModelBuilderHint")
    builder_selected_visual_label.setWordWrap(True)
    construct_layout.addWidget(builder_selected_visual_label, 0)
    builder_selection_widgets = []

    builder_binding_slots = {}
    for slot_name, slot_label in (
        (ROLE_X_AXIS, _rt("Eixo X")),
        (ROLE_Y_AXIS, _rt("Eixo Y")),
        (ROLE_VALUES, _rt("Valores")),
        (ROLE_LEGEND, _rt("Legenda")),
        (ROLE_TOOLTIP, _rt("Tooltip")),
        (ROLE_FILTERS, _rt("Filtros")),
        (ROLE_SIZE, _rt("Tamanho")),
    ):
        slot = _ModelBindingSlot(slot_name, slot_label, builder_construct_card)
        slot.fieldDropped.connect(on_field_dropped)
        slot.removeRequested.connect(on_remove_requested)
        slot.aggregationChanged.connect(on_aggregation_changed)
        slot.moveRequested.connect(on_move_requested)
        builder_binding_slots[slot_name] = slot
        construct_layout.addWidget(slot, 0)
        builder_selection_widgets.append(slot)

    host_layout.addWidget(builder_construct_card, 0)

    builder_format_card = QFrame(panel)
    builder_format_card.setObjectName("ModelBuilderSoftDividerSection")
    _force_model_white_background(builder_format_card)
    format_layout = QVBoxLayout(builder_format_card)
    format_layout.setContentsMargins(8, 8, 8, 8)
    format_layout.setSpacing(6)
    format_title = QLabel(_rt("Opções de dados"), builder_format_card)
    format_title.setObjectName("ModelBuilderSectionTitle")
    format_title.setFont(ui_font(9, weight=500))
    format_layout.addWidget(format_title, 0)

    options_form = QFormLayout()
    options_form.setContentsMargins(0, 2, 0, 0)
    options_form.setSpacing(5)
    options_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    options_form.setFormAlignment(Qt.AlignTop)
    options_form.setHorizontalSpacing(6)

    builder_option_labels = {}

    def add_selected_row(text: str, widget: QWidget, key: str = ""):
        label = QLabel(text, builder_format_card)
        label.setObjectName("ModelBuilderFieldLabel")
        options_form.addRow(label, widget)
        if key:
            builder_option_labels[key] = label
        builder_selection_widgets.extend([label, widget])

    builder_agg_combo = QComboBox(panel)
    builder_agg_combo.setObjectName("ModelBuilderCombo")
    builder_agg_combo.addItem(_rt("Contagem"), "count")
    builder_agg_combo.addItem(_rt("Soma"), "sum")
    builder_agg_combo.addItem(_rt("Media"), "avg")
    builder_agg_combo.addItem(_rt("Minimo"), "min")
    builder_agg_combo.addItem(_rt("Maximo"), "max")
    builder_agg_combo.addItem(_rt("Contagem distinta"), "count_distinct")
    add_selected_row(_rt("Agregacao"), builder_agg_combo, "aggregation")

    builder_topn_spin = QSpinBox(panel)
    builder_topn_spin.setObjectName("ModelBuilderSpin")
    builder_topn_spin.setRange(1, 50)
    builder_topn_spin.setValue(12)
    add_selected_row(_rt("Top N"), builder_topn_spin, "top_n")

    builder_title_edit = QLineEdit(panel)
    builder_title_edit.setObjectName("ModelBuilderLineEdit")
    builder_title_edit.setPlaceholderText(_rt("Titulo do grafico (opcional)"))
    add_selected_row(_rt("Titulo"), builder_title_edit, "title")
    format_layout.addLayout(options_form)
    builder_selection_widgets.extend([builder_agg_combo, builder_topn_spin, builder_title_edit])

    host_layout.addWidget(builder_format_card, 0)

    builder_dimension_combo = QComboBox(panel)
    builder_dimension_combo.setObjectName("ModelBuilderCombo")
    builder_value_combo = QComboBox(panel)
    builder_value_combo.setObjectName("ModelBuilderCombo")
    builder_dimension_combo.hide()
    builder_value_combo.hide()
    builder_empty_label.setVisible(True)
    builder_construct_card.setVisible(False)
    builder_format_card.setVisible(False)
    bottom_spacer = QWidget(host)
    bottom_spacer.setObjectName("ModelBuilderBottomSpacer")
    _force_model_white_background(bottom_spacer)
    bottom_spacer.setStyleSheet("QWidget#ModelBuilderBottomSpacer { background: #FFFFFF; background-color: #FFFFFF; }")
    host_layout.addWidget(bottom_spacer, 1)

    builder_value_combo.currentIndexChanged.connect(on_value_changed)
    builder_agg_combo.currentIndexChanged.connect(on_binding_controls_changed)
    builder_topn_spin.valueChanged.connect(on_binding_controls_changed)
    builder_title_edit.editingFinished.connect(on_binding_controls_changed)
    for slot in builder_binding_slots.values():
        slot.set_value("")

    return ModelBuilderPanelParts(
        panel=panel,
        builder_empty_label=builder_empty_label,
        builder_construct_card=builder_construct_card,
        builder_selected_visual_label=builder_selected_visual_label,
        builder_binding_slots=builder_binding_slots,
        builder_format_card=builder_format_card,
        builder_option_labels=builder_option_labels,
        builder_agg_combo=builder_agg_combo,
        builder_topn_spin=builder_topn_spin,
        builder_title_edit=builder_title_edit,
        builder_dimension_combo=builder_dimension_combo,
        builder_value_combo=builder_value_combo,
        builder_visual_buttons={},
        builder_selection_widgets=builder_selection_widgets,
    )


__all__ = [
    "ModelBuilderPanelParts",
    "_ModelBindingSlot",
    "_ModelFieldBindingChip",
    "binding_slot_label",
    "build_model_builder_panel",
    "build_visual_type_buttons",
    "builder_has_selection",
    "chart_type_label",
    "is_valid_binding_slot",
    "selected_builder_chart_type_from_buttons",
    "visual_type_labels",
    "visual_type_specs",
]
