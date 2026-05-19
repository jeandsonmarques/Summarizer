# ruff: noqa: I001
from __future__ import annotations

import json
from typing import Dict, List, Optional

import pandas as pd
from qgis.PyQt.QtCore import QMimeData, QRect, QSize, QTimer, Qt
from qgis.PyQt.QtGui import (
    QCursor,
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPalette,
    QPen,
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QGraphicsDropShadowEffect,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QToolButton,
    QToolTip,
)

from ..palette import TYPOGRAPHY
from ..report_view.pivot import PivotFieldSpec
from ..utils.i18n_runtime import tr_text as _rt
from ..utils.logging_utils import log_exception

PIVOT_FIELD_MIME = "application/x-summarizer-pivot-field"
INK_COLOR = "#252B33"


def build_field_drag_payload(items) -> List[Dict[str, str]]:
    payload: List[Dict[str, str]] = []
    for item in items or []:
        spec_key = item.data(Qt.UserRole)
        if spec_key:
            payload.append({"spec_key": spec_key, "text": item.text()})
    return payload


def field_matches_filter(text: str, query: str) -> bool:
    return str(query or "").strip().lower() in str(text or "").lower()


def detect_numeric_candidates(df: pd.DataFrame, is_numeric_column) -> List[str]:
    result = []
    for column in df.columns:
        if is_numeric_column(df[column]):
            result.append(column)
    return result


def build_attribute_field_spec(widget, field_name: str, layer, df: pd.DataFrame) -> PivotFieldSpec:
    data_type = "text"
    display_name = field_name
    if layer is not None:
        field_index = layer.fields().indexFromName(field_name)
        field = layer.fields()[field_index] if field_index >= 0 else None
        if field is not None:
            data_type = widget._map_variant_to_data_type(field.type())
            display_name = field.alias() or field.name()
    elif field_name in df.columns and widget._is_numeric_column(df[field_name]):
        data_type = "numeric"
    return PivotFieldSpec(
        field_name=field_name,
        display_name=display_name,
        source_type="attribute",
        data_type=data_type,
    )


def geometry_field_specs_for_layer(layer) -> List[PivotFieldSpec]:
    specs = []
    try:
        geometry_type = layer.geometryType()
    except Exception:
        geometry_type = None
    if geometry_type in (1, 2):
        specs.append(
            PivotFieldSpec(
                field_name="__geometry_length__",
                display_name="Comprimento geometrico",
                source_type="geometry",
                geometry_op="length",
                data_type="numeric",
            )
        )
    if geometry_type == 2:
        specs.append(
            PivotFieldSpec(
                field_name="__geometry_area__",
                display_name="Area geometrica",
                source_type="geometry",
                geometry_op="area",
                data_type="numeric",
            )
        )
    return specs


class _PivotFieldSourceListWidget(QListWidget):
    def __init__(self, owner=None, parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def supportedDropActions(self):
        return Qt.CopyAction

    def mimeTypes(self):
        return [PIVOT_FIELD_MIME]

    def mimeData(self, items):
        mime = QMimeData()
        mime.setData(PIVOT_FIELD_MIME, json.dumps(build_field_drag_payload(items)).encode("utf-8"))
        return mime

    def startDrag(self, supported_actions):
        items = [item for item in self.selectedItems() if item.data(Qt.UserRole)]
        if not items:
            current = self.currentItem()
            if current is not None and current.data(Qt.UserRole):
                items = [current]
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec_(Qt.CopyAction)

    def contextMenuEvent(self, event):
        if self._owner is None:
            super().contextMenuEvent(event)
            return
        item = self.itemAt(event.pos()) or self.currentItem()
        if item is None:
            return
        spec_key = item.data(Qt.UserRole)
        if not spec_key or spec_key == "__placeholder__":
            return
        spec = self._owner._field_spec_from_key(spec_key)
        if spec is None:
            return
        menu = QMenu(self)
        add_last = menu.addAction(
            f"{_rt('Adicionar em')} {self._owner._area_label(self._owner._last_active_area)}"
        )
        add_rows = menu.addAction(_rt("Adicionar em Linhas"))
        add_columns = menu.addAction(_rt("Adicionar em Colunas"))
        add_values = menu.addAction(_rt("Adicionar em Valores"))
        action = menu.exec_(event.globalPos())
        if action is None:
            return
        if action == add_last:
            self._owner._add_field_to_area(self._owner._last_active_area, spec)
        elif action == add_rows:
            self._owner._add_field_to_area("row", spec)
        elif action == add_columns:
            self._owner._add_field_to_area("column", spec)
        elif action == add_values:
            self._owner._add_field_to_area("value", spec)


class _VerticalPanelLabel(QLabel):
    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(max(28, hint.height() + 10), max(128, hint.width() + 16))

    def minimumSizeHint(self):
        return QSize(28, 124)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        rect = QRect(
            int(-self.height() / 2),
            int(-self.width() / 2),
            int(self.height()),
            int(self.width()),
        )
        painter.setPen(self.palette().color(QPalette.WindowText))
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignCenter, self.text())


class _SummarySourceCard(QToolButton):
    def __init__(
        self,
        title: str,
        badge_text: Optional[str] = None,
        tooltip_text: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("summarySourceCard")
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(title)
        self.setFixedSize(244, 68)
        self.setAutoRaise(False)
        self.setMouseTracking(True)
        if tooltip_text:
            self.setToolTip(tooltip_text)
        self._hovered = False
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)
        self._badge = None
        self.toggled.connect(self._sync_shadow)
        if badge_text:
            self._badge = QLabel(badge_text, self)
            self._badge.setObjectName("summarySourceCardBadge")
            self._badge.adjustSize()
        self._sync_shadow()

    def _sync_shadow(self):
        active = self._hovered or self.isChecked()
        self._shadow.setBlurRadius(14 if active else 8)
        self._shadow.setOffset(0, 4 if active else 2)
        self._shadow.setColor(QColor(15, 23, 42, 10 if active else 5))

    def enterEvent(self, event):
        self._hovered = True
        self._sync_shadow()
        if self.toolTip():
            QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._sync_shadow()
        QToolTip.hideText()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._badge is not None:
            self._badge.adjustSize()
            self._badge.move(max(10, self.width() - self._badge.width() - 14), 12)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = 12

        if self.isDown():
            fill_color = QColor("#F8FAFC")
            border_color = QColor("#CBD5E1")
        elif self.isChecked():
            fill_color = QColor("#FFFFFF")
            border_color = QColor("#94A3B8")
        elif self._hovered:
            fill_color = QColor("#F8FAFC")
            border_color = QColor("#CBD5E1")
        else:
            fill_color = QColor("#FFFFFF")
            border_color = QColor("#D7DEE8")

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(rect, radius, radius)

        text_rect = rect.adjusted(18, 0, -18, 0)
        title_font = QFont(self.font())
        title_font.setPixelSize(int(TYPOGRAPHY.get("font_body_px", 13)))
        title_font.setWeight(int(TYPOGRAPHY.get("font_weight_regular", 400)))
        title_font.setBold(False)
        painter.setFont(title_font)
        painter.setPen(QColor("#0F172A"))
        metrics = QFontMetrics(title_font)
        title = metrics.elidedText(self.text(), Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignCenter, title)


class _PivotFieldListDelegate(QStyledItemDelegate):
    _TEXT_COLOR = QColor(INK_COLOR)
    _TEXT_SELECTED_COLOR = QColor(INK_COLOR)
    _TEXT_SELECTED_BG = QColor("#E5E7EB")
    _NUMERIC_COLOR = QColor(INK_COLOR)
    _NUMERIC_SELECTED_COLOR = QColor(INK_COLOR)
    _NUMERIC_SELECTED_BG = QColor("#E5E7EB")

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        is_numeric = bool(index.data(Qt.UserRole + 1))
        is_selected = bool(opt.state & QStyle.State_Selected)

        if is_selected:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._NUMERIC_SELECTED_BG if is_numeric else self._TEXT_SELECTED_BG)
            painter.drawRoundedRect(opt.rect.adjusted(1, 0, -1, 0), 4, 4)
            painter.restore()

        opt.state &= ~QStyle.State_Selected
        opt.state &= ~QStyle.State_HasFocus
        opt.palette.setColor(QPalette.Text, self._NUMERIC_COLOR if is_numeric else self._TEXT_COLOR)
        if is_selected:
            opt.palette.setColor(
                QPalette.Text,
                self._NUMERIC_SELECTED_COLOR if is_numeric else self._TEXT_SELECTED_COLOR,
            )

        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)


def populate_field_panel(
    widget,
    df: pd.DataFrame,
    *,
    icon_factory,
    toolbar_icons,
    translate,
) -> None:
    self = widget
    _rt = translate
    _svg_icon_from_template = icon_factory
    _TOOLBAR_SVG_ICONS = toolbar_icons

    self.fields_list.clear()
    self._field_specs_by_key = {}
    self.filter_fields_list.clear()
    self.row_fields_list.clear()
    self.column_fields_list.clear()
    self.value_fields_list.clear()
    self._sync_area_placeholder()

    text_icon = _svg_icon_from_template(
        _TOOLBAR_SVG_ICONS["field_text"],
        size=14,
        color_map={
            QIcon.Normal: "#60a5fa",
            QIcon.Active: "#3b82f6",
            QIcon.Selected: "#1d4ed8",
            QIcon.Disabled: "#cbd5e1",
        },
    )
    numeric_icon = _svg_icon_from_template(
        _TOOLBAR_SVG_ICONS["field_numeric"],
        size=14,
        color_map={
            QIcon.Normal: "#c084fc",
            QIcon.Active: "#a855f7",
            QIcon.Selected: "#9333ea",
            QIcon.Disabled: "#e9d5ff",
        },
    )

    combos = [
        self.filter_field_combo,
        self.column_field_combo,
        self.row_field_combo,
        self.value_field_combo,
    ]
    for combo in combos:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_rt("(Nenhum)"), None)
        combo.blockSignals(False)

    layer = self._current_layer
    for column in df.columns:
        field_spec = build_attribute_field_spec(self, column, layer, df)
        spec_key = self._register_field_spec(field_spec)
        is_numeric = bool(field_spec.data_type == "numeric")
        item = QListWidgetItem(
            f"# {field_spec.display_name}" if is_numeric else field_spec.display_name
        )
        item.setData(Qt.UserRole, spec_key)
        item.setData(Qt.UserRole + 1, is_numeric)
        item.setData(Qt.UserRole + 2, field_spec.display_name)
        item.setIcon(numeric_icon if is_numeric else text_icon)
        self.fields_list.addItem(item)
        self.filter_field_combo.addItem(field_spec.display_name, spec_key)
        self.column_field_combo.addItem(field_spec.display_name, spec_key)
        self.row_field_combo.addItem(field_spec.display_name, spec_key)
        self.value_field_combo.addItem(field_spec.display_name, spec_key)

    if layer is not None:
        geometry_specs = geometry_field_specs_for_layer(layer)
        for field_spec in geometry_specs:
            spec_key = self._register_field_spec(field_spec)
            self.value_field_combo.addItem(field_spec.display_name, spec_key)

    self.value_field_combo.blockSignals(True)
    self.value_field_combo.setCurrentIndex(0)
    self.value_field_combo.blockSignals(False)
    self._sync_value_area_from_combo()
    self._update_context_summary()
    QTimer.singleShot(0, self._sync_fields_panel_width_to_content)


def handle_field_double_click(widget, item: QListWidgetItem):
    self = widget
    spec_key = item.data(Qt.UserRole)
    field_spec = self._field_spec_from_key(spec_key)
    if field_spec is None:
        return
    is_numeric = item.data(Qt.UserRole + 1)
    target_area = getattr(self, "_last_active_area", "row")
    if target_area == "value":
        if not is_numeric and field_spec.source_type != "geometry":
            self._show_inline_message(
                f"O campo {field_spec.display_name} nao pode ser usado como valor.",
                level="warning",
            )
            return
        self._add_field_to_area("value", field_spec)
        return
    self._add_field_to_area(target_area, field_spec)


def clear_field_search(widget) -> None:
    self = widget
    if getattr(self, "field_search", None) is not None:
        try:
            self.field_search.blockSignals(True)
            self.field_search.clear()
            self.field_search.blockSignals(False)
        except Exception:
            log_exception("falha opcional ignorada")
    filter_field_list(widget, "")


def filter_field_list(widget, text: str) -> None:
    self = widget
    for index in range(self.fields_list.count()):
        item = self.fields_list.item(index)
        visible = field_matches_filter(item.text(), text)
        self.fields_list.setRowHidden(index, not visible)


def desired_fields_panel_width(
    widget,
    *,
    tools_fields_default_width: int,
    tools_fields_min_width: int,
    tools_fields_max_width: int,
) -> int:
    self = widget
    width = tools_fields_default_width
    try:
        metrics = QFontMetrics(self.fields_list.font())
        widest_text = 0
        for index in range(self.fields_list.count()):
            item = self.fields_list.item(index)
            if item is None or item.data(Qt.UserRole) == "__placeholder__":
                continue
            widest_text = max(widest_text, metrics.horizontalAdvance(str(item.text() or "")))
        icon_width = int(self.fields_list.iconSize().width() or 14)
        width = max(width, widest_text + icon_width + 54)
    except Exception:
        log_exception("falha opcional ignorada")
    for candidate in (
        getattr(self, "fields_panel_header", None),
        getattr(self, "fields_context_card", None),
    ):
        if candidate is None:
            continue
        try:
            width = max(width, int(candidate.sizeHint().width() or 0))
        except Exception:
            log_exception("falha opcional ignorada")
    return max(tools_fields_min_width, min(tools_fields_max_width, width))


def sync_fields_panel_width_to_content(
    widget,
    *,
    tools_panel_collapsed_width: int,
    tools_fields_default_width: int,
    tools_fields_min_width: int,
    tools_fields_max_width: int,
    tools_filters_min_width: int,
    tools_filters_default_width: int,
) -> None:
    self = widget
    desired_width = desired_fields_panel_width(
        widget,
        tools_fields_default_width=tools_fields_default_width,
        tools_fields_min_width=tools_fields_min_width,
        tools_fields_max_width=tools_fields_max_width,
    )
    self._tools_fields_width = desired_width
    if getattr(self, "_tools_panels_hidden", False) or getattr(
        self, "_fields_panel_collapsed", False
    ):
        return
    if not hasattr(self, "analytics_splitter"):
        return
    sizes = self.analytics_splitter.sizes()
    if len(sizes) < 3:
        return
    total_width = sum(size for size in sizes if size > 0)
    if total_width <= 0:
        total_width = max(int(self.analytics_splitter.width() or 0), 1040)
    builder_width = (
        tools_panel_collapsed_width
        if getattr(self, "_filters_panel_collapsed", False)
        else max(
            tools_filters_min_width,
            int(
                getattr(self, "_tools_builder_width", tools_filters_default_width)
                or tools_filters_default_width
            ),
        )
    )
    table_width = max(1, total_width - desired_width - builder_width)
    self.analytics_splitter.setSizes([desired_width, builder_width, table_width])
