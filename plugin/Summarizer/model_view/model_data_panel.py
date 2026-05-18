from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

try:
    from qgis.PyQt.QtCore import QPoint, QSize, Qt, QMimeData, pyqtSignal
    from qgis.PyQt.QtGui import QColor, QDrag, QFontMetrics, QIcon
    from qgis.PyQt.QtWidgets import (
        QAbstractItemView,
        QFrame,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
    from qgis.core import QgsMapLayerProxyModel
    from qgis.gui import QgsMapLayerComboBox
except Exception:
    QPoint = QSize = Qt = QMimeData = QFontMetrics = QIcon = QColor = QDrag = None
    pyqtSignal = None
    QAbstractItemView = QFrame = QHBoxLayout = QLabel = QListWidget = QListWidgetItem = QToolButton = QVBoxLayout = QWidget = object
    QgsMapLayerProxyModel = QgsMapLayerComboBox = None

from ..dashboard_models import ROLE_TOOLTIP, ROLE_VALUES, ROLE_X_AXIS
try:
    from ..field_list_helpers import configure_field_item, field_kind_from_field_def, normalize_field_kind
except Exception:
    configure_field_item = None

    def normalize_field_kind(kind: Optional[str]) -> str:
        normalized = str(kind or "").strip().lower()
        if normalized in {"numeric", "number", "integer", "float", "double", "decimal", "real"}:
            return "numeric"
        if normalized in {"date", "datetime", "time"}:
            return "date"
        if normalized == "other":
            return "other"
        return "text"

    def field_kind_from_field_def(field_def) -> str:
        if field_def is None:
            return "other"
        try:
            if bool(field_def.isNumeric()):
                return "numeric"
        except Exception:
            pass
        type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
        if any(token in type_name for token in ("date", "time")):
            return "date"
        if any(token in type_name for token in ("int", "double", "float", "real", "numeric", "decimal")):
            return "numeric"
        if any(token in type_name for token in ("string", "text", "char")):
            return "text"
        return "other"
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
    from .model_theme import _force_model_white_background, _model_panel_fields_icon, _model_theme_color
except Exception:

    def _force_model_white_background(widget):
        return None

    def _model_panel_fields_icon(size: int = 14):
        return QIcon() if QIcon is not None else None

    def _model_theme_color(name: str) -> str:
        return "#0F172A" if name == "text" else "#FFFFFF"

MODEL_FIELD_MIME = "application/x-summarizer-model-field"
MODEL_FIELD_ROLE_OFFSET = 41


def model_fields_panel_font():
    font = ui_font()
    font.setPixelSize(12)
    return font


def _field_role():
    return Qt.UserRole + MODEL_FIELD_ROLE_OFFSET


if pyqtSignal is not None:

    class ModelFieldList(QListWidget):
        fieldActivated = pyqtSignal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._drag_start_pos = QPoint()
            self.setDragEnabled(True)
            self.setSelectionMode(QAbstractItemView.SingleSelection)
            self.setDragDropMode(QAbstractItemView.DragOnly)
            self.setDefaultDropAction(Qt.CopyAction)
            self.itemDoubleClicked.connect(self._emit_activated)

        def supportedDropActions(self):
            return Qt.CopyAction

        def mousePressEvent(self, event):
            item = self.itemAt(event.pos())
            if item is not None:
                self.setCurrentItem(item)
                if event.button() == Qt.LeftButton:
                    self._drag_start_pos = event.pos()
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if event.buttons() & Qt.LeftButton:
                if (event.pos() - self._drag_start_pos).manhattanLength() >= 6:
                    self.startDrag(Qt.CopyAction)
                    return
            super().mouseMoveEvent(event)

        def _emit_activated(self, item):
            payload = item.data(_field_role()) if item is not None else None
            if isinstance(payload, dict):
                self.fieldActivated.emit(dict(payload))

        def startDrag(self, supportedActions):
            item = self.currentItem()
            selected = self.selectedItems()
            if selected:
                item = selected[0]
            if item is None:
                return
            payload = item.data(_field_role())
            if not isinstance(payload, dict):
                return
            mime = QMimeData()
            mime.setData(MODEL_FIELD_MIME, json.dumps(payload).encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)

else:

    class ModelFieldList:
        pass


@dataclass
class ModelDataPanelParts:
    panel: QFrame
    data_panel_header: QWidget
    data_panel_icon: QLabel
    data_panel_title: QLabel
    data_panel_toggle_btn: QToolButton
    data_panel_body: QWidget
    builder_layer_combo: QgsMapLayerComboBox
    builder_fields_list: ModelFieldList
    data_panel_collapsed_rail: QFrame
    data_panel_collapsed_btn: QToolButton
    data_panel_collapsed_title: QLabel


def field_is_numeric(field_def) -> bool:
    if field_def is None:
        return False
    try:
        return bool(field_def.isNumeric())
    except Exception:
        log_exception("falha opcional ignorada")
    type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
    return any(token in type_name for token in ("int", "double", "float", "real", "numeric", "decimal"))


def field_is_date_like(field_def) -> bool:
    if field_def is None:
        return False
    type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
    return any(token in type_name for token in ("date", "time"))


def field_group_for_def(field_def) -> str:
    if field_is_numeric(field_def):
        return "measure"
    if field_is_date_like(field_def):
        return "date"
    type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip().lower()
    if any(token in type_name for token in ("string", "text", "char")):
        return "dimension"
    return "other"


def suggested_role_for_group(group: str) -> str:
    mapping = {
        "dimension": ROLE_X_AXIS,
        "measure": ROLE_VALUES,
        "date": ROLE_X_AXIS,
        "other": ROLE_TOOLTIP,
    }
    return mapping.get(str(group or "").strip().lower(), ROLE_X_AXIS)


def field_catalog_for_layer(layer) -> Dict[str, List[Dict[str, str]]]:
    catalog = {"all": []}
    if layer is None:
        return catalog
    try:
        field_defs = list(layer.fields())
    except Exception:
        field_defs = []
    for field_def in field_defs:
        field_name = str(field_def.name() or "").strip()
        if not field_name:
            continue
        group = field_group_for_def(field_def)
        type_name = str(getattr(field_def, "typeName", lambda: "")() or "").strip()
        field_kind = field_kind_from_field_def(field_def)
        catalog["all"].append(
            {
                "layer_name": layer.name(),
                "layer_id": layer.id(),
                "field_name": field_name,
                "field_type": type_name,
                "field_kind": field_kind,
                "field_group": group,
                "suggested_role": suggested_role_for_group(group),
            }
        )
    return catalog


def resolve_layer_field_name(layer, field_name: str) -> str:
    candidate = str(field_name or "").strip()
    if layer is None or not candidate:
        return ""
    try:
        fields = layer.fields()
    except Exception:
        return candidate
    try:
        index = fields.lookupField(candidate)
    except Exception:
        index = -1
    if index is not None and index >= 0:
        try:
            return str(fields.field(index).name() or candidate).strip()
        except Exception:
            return candidate
    lowered = candidate.lower()
    try:
        for field in fields:
            name = str(field.name() or "").strip()
            if name and (name == candidate or name.lower() == lowered):
                return name
    except Exception:
        log_exception("falha opcional ignorada")
    return ""


def field_kind_for_layer_field(layer, field_name: str) -> str:
    try:
        fields = layer.fields()
        index = fields.lookupField(str(field_name or ""))
        if index is not None and index >= 0:
            return normalize_field_kind(field_kind_from_field_def(fields.field(index)))
    except Exception:
        log_exception("falha opcional ignorada")
    return "unknown"


def text_width(metrics: QFontMetrics, text: str) -> int:
    if hasattr(metrics, "horizontalAdvance"):
        return int(metrics.horizontalAdvance(text))
    return int(metrics.width(text))


def desired_data_panel_width(
    fields_list,
    layer_combo,
    *,
    minimum_width: int,
    maximum_width: int,
    default_width: int,
) -> int:
    try:
        metrics = QFontMetrics(fields_list.font())
        max_text = 0
        for index in range(fields_list.count()):
            item = fields_list.item(index)
            if item is None:
                continue
            text = str(item.text() or item.data(Qt.UserRole + 2) or "")
            max_text = max(max_text, text_width(metrics, text))
        layer_text = ""
        try:
            layer_text = layer_combo.currentText()
        except Exception:
            layer_text = ""
        max_text = max(max_text, text_width(metrics, layer_text))
        icon_width = int(fields_list.iconSize().width() or 14)
        chrome = icon_width + 54
        desired = max(minimum_width, max_text + chrome)
        return min(maximum_width, desired)
    except Exception:
        log_exception("falha opcional ignorada")
        return default_width


def build_model_data_panel(
    parent: QWidget,
    *,
    toggle_data_panel: Callable[[], None],
    on_builder_layer_changed: Callable[..., None],
    handle_field_list_activation: Callable[[object], None],
    vertical_label_cls,
) -> ModelDataPanelParts:
    if QgsMapLayerComboBox is None:
        raise RuntimeError("QGIS runtime not available")
    panel = QFrame(parent)
    panel.setObjectName("ModelBuilderDataPanel")
    _force_model_white_background(panel)
    panel.setStyleSheet(
        """
        QFrame#ModelBuilderDataPanel {
            background: #FFFFFF;
            border: 1px solid rgba(17, 24, 39, 0.09);
            border-radius: 2px;
        }
        QFrame#ModelBuilderDataPanel QWidget,
        QFrame#ModelBuilderDataPanel QFrame,
        QFrame#ModelBuilderDataPanel QListWidget,
        QFrame#ModelBuilderDataPanel QAbstractScrollArea,
        QFrame#ModelBuilderDataPanel QAbstractScrollArea::viewport {
            background-color: #FFFFFF;
        }
        QFrame#ModelBuilderDataPanel[collapsed="true"] {
            border-color: #E2E8F0;
        }
        QWidget#ModelDataPanelHeader {
            background: #FFFFFF;
            border: none;
        }
        QLabel#ModelDataPanelIcon {
            min-width: 14px;
            max-width: 14px;
            min-height: 14px;
            max-height: 14px;
        }
        QFrame#ModelDataPanelCollapsedRail {
            background: transparent;
            border: none;
        }
        QLabel#ModelDataPanelCollapsedTitle {
            color: #111827;
            font-size: 8pt;
            font-weight: 500;
            background: transparent;
        }
        QFrame#ModelBuilderDataSection {
            background: #FFFFFF;
            border: none;
        }
        QComboBox#ModelBuilderCombo {
            min-height: 28px;
            border: 1px solid rgba(17, 24, 39, 0.09);
            border-radius: 6px;
            background: #FFFFFF;
            padding: 3px 8px;
            color: #111827;
            font-size: 12px;
        }
        QListWidget#ModelBuilderFieldList {
            border: 1px solid rgba(17, 24, 39, 0.09);
            border-radius: 2px;
            background: #FFFFFF;
            padding: 2px;
            color: #111827;
            font-size: 12px;
            outline: 0px;
        }
        QWidget#ModelBuilderFieldListViewport {
            background: #FFFFFF;
        }
        QListWidget#ModelBuilderFieldList::item {
            padding: 4px 6px;
            margin: 0px;
            border-radius: 2px;
        }
        QListWidget#ModelBuilderFieldList::item:hover {
            background: rgba(17, 24, 39, 0.035);
        }
        QListWidget#ModelBuilderFieldList::item:selected {
            background: rgba(81, 96, 116, 0.12);
            color: #111827;
        }
        QListWidget#ModelBuilderFieldList QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 0px;
        }
        QListWidget#ModelBuilderFieldList QScrollBar::handle:vertical {
            background: rgba(107, 114, 128, 0.28);
            border-radius: 5px;
            min-height: 24px;
        }
        QListWidget#ModelBuilderFieldList QScrollBar::handle:vertical:hover {
            background: rgba(107, 114, 128, 0.40);
        }
        QListWidget#ModelBuilderFieldList QScrollBar::add-line:vertical,
        QListWidget#ModelBuilderFieldList QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QListWidget#ModelBuilderFieldList QScrollBar::add-page:vertical,
        QListWidget#ModelBuilderFieldList QScrollBar::sub-page:vertical {
            background: transparent;
        }
        QLabel#ModelBuilderTitle {
            color: #4B5563;
            font-size: 12px;
            font-weight: 500;
        }
        QLabel#ModelBuilderFieldLabel {
            color: #6B7280;
            font-size: 10px;
            font-weight: 500;
        }
        """
    )

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    data_panel_header = QWidget(panel)
    data_panel_header.setObjectName("ModelDataPanelHeader")
    _force_model_white_background(data_panel_header)
    header = QHBoxLayout(data_panel_header)
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)
    data_panel_icon = QLabel(data_panel_header)
    data_panel_icon.setObjectName("ModelDataPanelIcon")
    data_panel_icon.setPixmap(_model_panel_fields_icon(14).pixmap(14, 14))
    header.addWidget(data_panel_icon, 0, Qt.AlignVCenter)
    data_panel_title = QLabel(_rt("Campos"), data_panel_header)
    data_panel_title.setObjectName("ModelBuilderTitle")
    data_panel_title.setFont(model_fields_panel_font())
    header.addWidget(data_panel_title, 1, Qt.AlignVCenter)
    data_panel_toggle_btn = QToolButton(data_panel_header)
    data_panel_toggle_btn.setObjectName("ModelDataPanelToggle")
    data_panel_toggle_btn.setAutoRaise(True)
    data_panel_toggle_btn.setCursor(Qt.PointingHandCursor)
    data_panel_toggle_btn.setFixedSize(22, 22)
    data_panel_toggle_btn.clicked.connect(toggle_data_panel)
    header.addWidget(data_panel_toggle_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
    layout.addWidget(data_panel_header, 0)

    data_panel_body = QWidget(panel)
    data_panel_body.setObjectName("ModelDataPanelBody")
    _force_model_white_background(data_panel_body)
    body_layout = QVBoxLayout(data_panel_body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(6)

    layer_card = QFrame(panel)
    layer_card.setObjectName("ModelBuilderDataSection")
    _force_model_white_background(layer_card)
    layer_layout = QHBoxLayout(layer_card)
    layer_layout.setContentsMargins(0, 0, 0, 0)
    layer_layout.setSpacing(8)
    layer_title = QLabel(_rt("Camada"), layer_card)
    layer_title.setObjectName("ModelBuilderFieldLabel")
    layer_layout.addWidget(layer_title, 0, Qt.AlignVCenter)
    builder_layer_combo = QgsMapLayerComboBox(panel)
    builder_layer_combo.setObjectName("ModelBuilderCombo")
    builder_layer_combo.setFont(model_fields_panel_font())
    try:
        builder_layer_combo.view().setFont(model_fields_panel_font())
    except Exception:
        log_exception("falha opcional ignorada")
    builder_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    builder_layer_combo.layerChanged.connect(on_builder_layer_changed)
    layer_layout.addWidget(builder_layer_combo, 1)
    body_layout.addWidget(layer_card, 0)

    fields_card = QFrame(panel)
    fields_card.setObjectName("ModelBuilderDataSection")
    _force_model_white_background(fields_card)
    fields_layout = QVBoxLayout(fields_card)
    fields_layout.setContentsMargins(0, 0, 0, 0)
    fields_layout.setSpacing(0)
    fields_body = QWidget(fields_card)
    fields_body.setObjectName("ModelDataFieldsBody")
    _force_model_white_background(fields_body)
    fields_body_layout = QVBoxLayout(fields_body)
    fields_body_layout.setContentsMargins(0, 4, 0, 0)
    fields_body_layout.setSpacing(0)
    builder_fields_list = ModelFieldList(fields_body)
    builder_fields_list.setObjectName("ModelBuilderFieldList")
    builder_fields_list.setFont(model_fields_panel_font())
    builder_fields_list.viewport().setObjectName("ModelBuilderFieldListViewport")
    _force_model_white_background(builder_fields_list)
    _force_model_white_background(builder_fields_list.viewport())
    builder_fields_list.setMinimumHeight(220)
    builder_fields_list.setUniformItemSizes(True)
    builder_fields_list.setSpacing(1)
    builder_fields_list.setIconSize(QSize(14, 14))
    builder_fields_list.fieldActivated.connect(handle_field_list_activation)
    fields_body_layout.addWidget(builder_fields_list, 1)
    fields_layout.addWidget(fields_body, 1)
    body_layout.addWidget(fields_card, 1)
    layout.addWidget(data_panel_body, 1)

    data_panel_collapsed_rail = QFrame(panel)
    data_panel_collapsed_rail.setObjectName("ModelDataPanelCollapsedRail")
    data_panel_collapsed_rail.hide()
    rail_layout = QVBoxLayout(data_panel_collapsed_rail)
    rail_layout.setContentsMargins(2, 6, 2, 6)
    rail_layout.setSpacing(8)
    data_panel_collapsed_btn = QToolButton(data_panel_collapsed_rail)
    data_panel_collapsed_btn.setObjectName("ModelDataPanelToggle")
    data_panel_collapsed_btn.setAutoRaise(True)
    data_panel_collapsed_btn.setCursor(Qt.PointingHandCursor)
    data_panel_collapsed_btn.setFixedSize(22, 22)
    data_panel_collapsed_btn.clicked.connect(toggle_data_panel)
    rail_layout.addWidget(data_panel_collapsed_btn, 0, Qt.AlignHCenter | Qt.AlignTop)
    data_panel_collapsed_title = vertical_label_cls(_rt("Campos"), data_panel_collapsed_rail)
    data_panel_collapsed_title.setObjectName("ModelDataPanelCollapsedTitle")
    rail_layout.addWidget(data_panel_collapsed_title, 0, Qt.AlignHCenter | Qt.AlignTop)
    rail_layout.addStretch(1)
    layout.addWidget(data_panel_collapsed_rail, 1)

    return ModelDataPanelParts(
        panel=panel,
        data_panel_header=data_panel_header,
        data_panel_icon=data_panel_icon,
        data_panel_title=data_panel_title,
        data_panel_toggle_btn=data_panel_toggle_btn,
        data_panel_body=data_panel_body,
        builder_layer_combo=builder_layer_combo,
        builder_fields_list=builder_fields_list,
        data_panel_collapsed_rail=data_panel_collapsed_rail,
        data_panel_collapsed_btn=data_panel_collapsed_btn,
        data_panel_collapsed_title=data_panel_collapsed_title,
    )


def refresh_builder_data_fonts(data_panel_owner):
    for widget in (
        getattr(data_panel_owner, "data_panel_title", None),
        getattr(data_panel_owner, "builder_layer_combo", None),
        getattr(data_panel_owner, "builder_fields_list", None),
    ):
        if widget is None:
            continue
        try:
            widget.setFont(model_fields_panel_font())
        except Exception:
            log_exception("falha opcional ignorada")
    try:
        data_panel_owner.data_panel_title.setText(_rt("Campos"))
        data_panel_owner.data_panel_title.setFont(model_fields_panel_font())
    except Exception:
        log_exception("falha opcional ignorada")
    try:
        data_panel_owner.builder_layer_combo.view().setFont(model_fields_panel_font())
    except Exception:
        log_exception("falha opcional ignorada")
    try:
        for index in range(data_panel_owner.builder_fields_list.count()):
            item = data_panel_owner.builder_fields_list.item(index)
            if item is not None:
                item.setFont(model_fields_panel_font())
                item.setFlags(item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
    except Exception:
        log_exception("falha opcional ignorada")


def populate_builder_field_list(data_panel_owner, layer) -> Dict[str, List[Dict[str, str]]]:
    catalog = field_catalog_for_layer(layer)
    data_panel_owner.builder_fields_list.clear()
    for payload in list(catalog.get("all") or []):
        label = str(payload.get("field_name") or "")
        field_kind = str(payload.get("field_kind") or "other")
        is_numeric = normalize_field_kind(field_kind) == "numeric"
        display_label = f"# {label}" if is_numeric else label
        tooltip = _rt(
            "{name}\nTipo: {kind}",
            name=label,
            kind=str(payload.get("field_type") or field_kind).strip() or field_kind,
        )
        item = QListWidgetItem()
        configure_field_item(
            item,
            display_name=label,
            kind=field_kind,
            tooltip=tooltip,
            payload=dict(payload),
            role=_field_role(),
            include_badge=False,
        )
        item.setText(display_label)
        item.setFont(model_fields_panel_font())
        item.setForeground(QColor(_model_theme_color("text")))
        data_panel_owner.builder_fields_list.addItem(item)
    return catalog


def sync_data_panel_chrome(data_panel_owner, *, collapsed_width: int, min_width: int, max_width: int):
    if not hasattr(data_panel_owner, "data_panel"):
        return
    collapsed = bool(getattr(data_panel_owner, "_data_panel_collapsed", False))
    data_panel_owner.data_panel.setMinimumWidth(collapsed_width if collapsed else min_width)
    data_panel_owner.data_panel.setMaximumWidth(collapsed_width if collapsed else max_width)
    data_panel_owner.data_panel.setProperty("collapsed", collapsed)
    if hasattr(data_panel_owner, "data_panel_header"):
        data_panel_owner.data_panel_header.setVisible(not collapsed)
    if hasattr(data_panel_owner, "data_panel_body"):
        data_panel_owner.data_panel_body.setVisible(not collapsed)
    if hasattr(data_panel_owner, "data_panel_collapsed_rail"):
        data_panel_owner.data_panel_collapsed_rail.setVisible(collapsed)
    if hasattr(data_panel_owner, "data_panel_toggle_btn"):
        data_panel_owner.data_panel_toggle_btn.setArrowType(Qt.NoArrow)
        data_panel_owner.data_panel_toggle_btn.setIcon(QIcon())
        data_panel_owner.data_panel_toggle_btn.setText("‹")
        data_panel_owner.data_panel_toggle_btn.setFixedSize(22, 22)
        data_panel_owner.data_panel_toggle_btn.setToolTip(_rt("Recolher campos"))
    if hasattr(data_panel_owner, "data_panel_collapsed_btn"):
        data_panel_owner.data_panel_collapsed_btn.setArrowType(Qt.NoArrow)
        data_panel_owner.data_panel_collapsed_btn.setIcon(QIcon())
        data_panel_owner.data_panel_collapsed_btn.setText("›")
        data_panel_owner.data_panel_collapsed_btn.setFixedSize(22, 22)
        data_panel_owner.data_panel_collapsed_btn.setToolTip(_rt("Expandir campos"))
    try:
        data_panel_owner.data_panel.style().unpolish(data_panel_owner.data_panel)
        data_panel_owner.data_panel.style().polish(data_panel_owner.data_panel)
    except Exception:
        log_exception("falha opcional ignorada")


def toggle_data_panel_state(
    data_panel_owner,
    *,
    collapsed_width: int,
    min_width: int,
    max_width: int,
    default_width: int,
):
    if not getattr(data_panel_owner, "_data_panel_collapsed", False):
        sizes = data_panel_owner.canvas_splitter.sizes() if hasattr(data_panel_owner, "canvas_splitter") else []
        if len(sizes) >= 3 and sizes[2] > collapsed_width:
            data_panel_owner._data_panel_width = min(max_width, max(min_width, int(sizes[2])))
    elif not getattr(data_panel_owner, "_data_panel_width", 0):
        data_panel_owner._data_panel_width = default_width
    data_panel_owner._data_panel_collapsed = not bool(getattr(data_panel_owner, "_data_panel_collapsed", False))


__all__ = [
    "MODEL_FIELD_MIME",
    "MODEL_FIELD_ROLE_OFFSET",
    "ModelDataPanelParts",
    "ModelFieldList",
    "build_model_data_panel",
    "desired_data_panel_width",
    "field_catalog_for_layer",
    "field_group_for_def",
    "field_is_date_like",
    "field_is_numeric",
    "field_kind_for_layer_field",
    "model_fields_panel_font",
    "populate_builder_field_list",
    "refresh_builder_data_fonts",
    "resolve_layer_field_name",
    "suggested_role_for_group",
    "sync_data_panel_chrome",
    "text_width",
    "toggle_data_panel_state",
]
