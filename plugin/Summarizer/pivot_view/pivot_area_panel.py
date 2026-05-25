# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import json
from functools import partial
from typing import List, Optional

from qgis.PyQt.QtCore import QEvent, QMimeData, QSize, Qt
from qgis.PyQt.QtGui import QDrag, QIcon, QMouseEvent
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..report_view.pivot import PivotFieldSpec
from ..walker_dialogs import apply_walker_menu

PIVOT_FIELD_MIME = "application/x-summarizer-pivot-field"


def _configure_area_drop_list(
    list_widget: QListWidget, *, min_height: int, max_height: int
) -> None:
    list_widget.setUniformItemSizes(False)
    list_widget.setSpacing(2)
    list_widget.setMinimumHeight(min_height)
    list_widget.setMaximumHeight(max_height)
    list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


class _PivotDropListWidget(QListWidget):
    def __init__(self, owner, area_name: str, allow_multiple: bool = True, parent=None):
        super().__init__(parent)
        self._owner = owner
        self._area_name = area_name
        self._allow_multiple = allow_multiple
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setAcceptDrops(True)

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def mimeTypes(self):
        return [PIVOT_FIELD_MIME]

    def mimeData(self, items):
        mime = QMimeData()
        payload = []
        for item in items or []:
            spec_key = item.data(Qt.UserRole)
            if not spec_key or spec_key == "__placeholder__":
                continue
            payload.append(
                {
                    "spec_key": spec_key,
                    "text": item.text(),
                    "from_area": self._area_name,
                }
            )
        mime.setData(PIVOT_FIELD_MIME, json.dumps(payload).encode("utf-8"))
        return mime

    def startDrag(self, supported_actions):
        del supported_actions
        items = [
            item
            for item in self.selectedItems()
            if item.data(Qt.UserRole) and item.data(Qt.UserRole) != "__placeholder__"
        ]
        if not items:
            current = self.currentItem()
            if current is not None and current.data(Qt.UserRole) != "__placeholder__":
                items = [current]
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec_(Qt.MoveAction)

    def _resolved_drop_action(self, event):
        source_widget = event.source()
        if isinstance(source_widget, _PivotDropListWidget) and source_widget is not self:
            return Qt.MoveAction
        if source_widget is self:
            return Qt.MoveAction
        return Qt.CopyAction

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(PIVOT_FIELD_MIME) or event.source() is self:
            event.setDropAction(self._resolved_drop_action(event))
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(PIVOT_FIELD_MIME) or event.source() is self:
            event.setDropAction(self._resolved_drop_action(event))
            event.accept()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.source() is self:
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return

        if not event.mimeData().hasFormat(PIVOT_FIELD_MIME):
            source_widget = (
                event.source() if isinstance(event.source(), _PivotDropListWidget) else None
            )
            super().dropEvent(event)
            if self._owner is not None:
                self._owner._set_last_active_area(self._area_name)
                self._owner._sync_area_placeholder(self._area_name)
                if source_widget is not None and source_widget is not self:
                    self._owner._sync_area_placeholder(source_widget._area_name)
                self._owner._maybe_refresh()
            return

        try:
            payload = json.loads(bytes(event.mimeData().data(PIVOT_FIELD_MIME)).decode("utf-8"))
        except Exception:
            payload = []

        source_widget = event.source() if isinstance(event.source(), _PivotDropListWidget) else None
        added = False
        for item in payload or []:
            spec_key = item.get("spec_key")
            spec = self._owner._field_spec_from_key(item.get("spec_key"))
            if spec is None:
                continue
            added = (
                self._owner._add_field_to_area(self._area_name, spec, auto_refresh=False)
                or added
            )
            if added and source_widget is not None and source_widget is not self and spec_key:
                self._owner._take_area_field_by_key(source_widget._area_name, spec_key)
            if not self._allow_multiple:
                break

        if added:
            event.setDropAction(
                Qt.MoveAction
                if source_widget is not None and source_widget is not self
                else Qt.CopyAction
            )
            event.acceptProposedAction()
            if self._owner is not None:
                self._owner._set_last_active_area(self._area_name)
                self._owner._sync_area_placeholder(self._area_name)
                if source_widget is not None and source_widget is not self:
                    self._owner._sync_area_placeholder(source_widget._area_name)
                self._owner._maybe_refresh()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.currentRow() >= 0 and self._owner is not None:
                self._owner._remove_selected_area_field(self._area_name)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        super().focusInEvent(event)

    def contextMenuEvent(self, event):
        if self._owner is not None:
            self._owner._set_last_active_area(self._area_name)
        menu = apply_walker_menu(QMenu(self))
        remove_action = menu.addAction("Remover")
        up_action = menu.addAction("Mover para cima")
        down_action = menu.addAction("Mover para baixo")
        menu.addSeparator()
        clear_action = menu.addAction("Limpar área")
        action = menu.exec_(event.globalPos())
        if action == remove_action and self._owner is not None:
            self._owner._remove_selected_area_field(self._area_name)
        elif action == up_action and self._owner is not None:
            self._owner._move_selected_area_field(self._area_name, -1)
        elif action == down_action and self._owner is not None:
            self._owner._move_selected_area_field(self._area_name, 1)
        elif action == clear_action and self._owner is not None:
            self._owner._clear_area(self._area_name)
            self._owner._maybe_refresh()


class _PivotAreaChipContainer(QWidget):
    def __init__(self, list_widget: QListWidget, parent=None):
        super().__init__(parent)
        self._list_widget = list_widget
        self._drag_start_pos = None

    def _find_bound_item(self):
        if self._list_widget is None:
            return None
        for index in range(self._list_widget.count()):
            item = self._list_widget.item(index)
            if self._list_widget.itemWidget(item) is self:
                return item
        return None

    def _select_bound_item(self):
        item = self._find_bound_item()
        if item is None:
            return None
        self._list_widget.setCurrentItem(item)
        self._list_widget.setFocus(Qt.MouseFocusReason)
        return item

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._select_bound_item()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (
            event.pos() - self._drag_start_pos
        ).manhattanLength() < QApplication.startDragDistance():
            event.accept()
            return
        item = self._select_bound_item()
        if item is None:
            self._drag_start_pos = None
            super().mouseMoveEvent(event)
            return
        spec_key = item.data(Qt.UserRole)
        if not spec_key or spec_key == "__placeholder__":
            self._drag_start_pos = None
            event.ignore()
            return
        drag = QDrag(self._list_widget)
        drag.setMimeData(self._list_widget.mimeData([item]))
        drag.exec_(Qt.MoveAction)
        self._drag_start_pos = None
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._select_bound_item()
            self._drag_start_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            mapped = QMouseEvent(
                event.type(),
                self.mapFromGlobal(watched.mapToGlobal(event.pos())),
                event.globalPos(),
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            if event.type() == QEvent.MouseButtonPress:
                self.mousePressEvent(mapped)
            elif event.type() == QEvent.MouseMove:
                self.mouseMoveEvent(mapped)
            else:
                self.mouseReleaseEvent(mapped)
            return True
        return super().eventFilter(watched, event)


def build_area_panels(
    widget,
    *,
    section_title_font,
    helper_text_font,
    body_text_font,
    translate,
    supported_aggregators,
) -> None:
    self = widget
    self.filter_field_combo = QComboBox()
    self.filter_field_combo.hide()
    self.row_field_combo = QComboBox()
    self.row_field_combo.hide()
    self.column_field_combo = QComboBox()
    self.column_field_combo.hide()

    self.filter_fields_list = _PivotDropListWidget(
        self,
        "filter",
        allow_multiple=False,
        parent=self.filters_panel,
    )
    self.filter_fields_list.setObjectName("summaryFilterList")
    _configure_area_drop_list(self.filter_fields_list, min_height=58, max_height=80)
    self.filter_fields_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.filter_fields_list.hide()

    self.value_fields_list = _PivotDropListWidget(self, "value", allow_multiple=False)
    self.value_fields_list.setObjectName("summaryValueList")
    _configure_area_drop_list(self.value_fields_list, min_height=58, max_height=74)

    self.row_fields_list = _PivotDropListWidget(self, "row", allow_multiple=True)
    self.row_fields_list.setObjectName("summaryRowList")
    self.row_fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
    _configure_area_drop_list(self.row_fields_list, min_height=58, max_height=80)

    self.column_fields_list = _PivotDropListWidget(self, "column", allow_multiple=True)
    self.column_fields_list.setObjectName("summaryColumnList")
    self.column_fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
    _configure_area_drop_list(self.column_fields_list, min_height=58, max_height=80)

    self.row_area_card = _create_area_card()
    row_layout = QVBoxLayout(self.row_area_card)
    row_layout.setContentsMargins(6, 6, 6, 6)
    row_layout.setSpacing(4)
    self.row_area_title = QLabel(translate("Linhas"))
    self.row_area_title.setObjectName("summaryAxisTitle")
    self.row_area_title.setFont(section_title_font)
    row_layout.addWidget(self.row_area_title)
    row_layout.addWidget(self.row_fields_list)
    self.filters_builder_layout.addWidget(self.row_area_card)

    self.column_area_card = _create_area_card()
    col_layout = QVBoxLayout(self.column_area_card)
    col_layout.setContentsMargins(6, 6, 6, 6)
    col_layout.setSpacing(4)
    self.column_area_title = QLabel(translate("Colunas"))
    self.column_area_title.setObjectName("summaryAxisTitle")
    self.column_area_title.setFont(section_title_font)
    col_layout.addWidget(self.column_area_title)
    col_layout.addWidget(self.column_fields_list)
    self.filters_builder_layout.addWidget(self.column_area_card)

    self.value_area_card = _create_area_card()
    value_layout = QVBoxLayout(self.value_area_card)
    value_layout.setContentsMargins(6, 6, 6, 6)
    value_layout.setSpacing(4)
    self.value_area_title = QLabel(translate("Valores"))
    self.value_area_title.setObjectName("summaryAxisTitle")
    self.value_area_title.setFont(section_title_font)
    value_layout.addWidget(self.value_area_title)
    operation_label = QLabel(translate("Operação"))
    operation_label.setObjectName("summaryFieldLabel")
    operation_label.setFont(helper_text_font)
    value_layout.addWidget(operation_label)

    self.agg_combo = QComboBox()
    self.agg_combo.setObjectName("summaryOperationCombo")
    self.agg_combo.setFixedHeight(32)
    self.agg_combo.setFont(body_text_font)
    for label, func in supported_aggregators:
        self.agg_combo.addItem(label, func)
    self.agg_combo.setCurrentIndex(self.agg_combo.findData("count"))
    self.agg_combo.currentIndexChanged.connect(self._on_operation_changed)
    value_layout.addWidget(self.agg_combo)
    value_layout.addWidget(self.value_fields_list)
    self.filters_builder_layout.addWidget(self.value_area_card)


def _create_area_card() -> QWidget:
    card = QWidget()
    card.setProperty("sidebarSection", True)
    card.setProperty("filterSectionCard", True)
    card.setAttribute(Qt.WA_StyledBackground, True)
    return card


def placeholder_item(translate) -> QListWidgetItem:
    item = QListWidgetItem(translate("Nenhum campo"))
    item.setData(Qt.UserRole, "__placeholder__")
    item.setFlags(Qt.NoItemFlags)
    return item


def create_area_chip_widget(
    widget,
    area: str,
    field_spec: PivotFieldSpec,
    *,
    icon_factory,
    toolbar_icons,
) -> QWidget:
    self = widget
    row_widget = _PivotAreaChipContainer(self._area_list(area))
    row_widget.setObjectName("summaryAreaChipRow")
    row_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(0)

    chip = QFrame(row_widget)
    chip.setObjectName("summaryAreaChip")
    chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    layout = QHBoxLayout(chip)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(6)

    remove_btn = QToolButton(chip)
    remove_btn.setObjectName("summaryAreaChipRemove")
    remove_btn.setCursor(Qt.PointingHandCursor)
    remove_btn.setAutoRaise(True)
    remove_btn.setFixedSize(18, 18)
    remove_btn.setIcon(
        icon_factory(
            toolbar_icons["clear"],
            size=14,
            color_map={
                QIcon.Normal: "#ef4444",
                QIcon.Active: "#dc2626",
                QIcon.Selected: "#dc2626",
                QIcon.Disabled: "#fca5a5",
            },
        )
    )
    remove_btn.setIconSize(QSize(14, 14))
    remove_btn.setToolTip(f"Remover de {self._area_label(area)}")
    remove_btn.clicked.connect(
        partial(self._remove_area_field_by_key, area, self._register_field_spec(field_spec))
    )
    layout.addWidget(remove_btn, 0, Qt.AlignTop)

    label = QLabel(field_spec.display_name)
    label.setObjectName("summaryAreaChipText")
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
    layout.addWidget(label, 0, Qt.AlignVCenter)

    chip.installEventFilter(row_widget)
    label.installEventFilter(row_widget)

    row_layout.addWidget(chip, 0, Qt.AlignLeft | Qt.AlignVCenter)
    row_widget.ensurePolished()
    chip.ensurePolished()
    label.ensurePolished()
    text_width = label.fontMetrics().horizontalAdvance(field_spec.display_name) + 10
    label.setMinimumWidth(text_width)
    label.setMaximumWidth(text_width)
    chip_width = (
        layout.contentsMargins().left()
        + remove_btn.width()
        + layout.spacing()
        + text_width
        + layout.contentsMargins().right()
        + 6
    )
    chip.setMinimumWidth(chip_width)
    row_widget.setMinimumWidth(chip_width)
    layout.activate()
    row_layout.activate()
    chip.adjustSize()
    row_widget.adjustSize()
    return row_widget


def refresh_area_item_widgets(widget, area: str) -> None:
    self = widget
    list_widget = self._area_list(area)
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        spec_key = item.data(Qt.UserRole)
        if spec_key == "__placeholder__":
            list_widget.removeItemWidget(item)
            item.setSizeHint(QSize(0, 28))
            continue
        spec = self._field_spec_from_key(spec_key)
        if spec is None:
            continue
        area_widget = self._create_area_chip_widget(area, spec)
        hint = area_widget.sizeHint()
        item.setSizeHint(QSize(hint.width() + 6, hint.height()))
        list_widget.setItemWidget(item, area_widget)
    list_widget.doItemsLayout()
    list_widget.updateGeometry()


def set_last_active_area(widget, area: str) -> None:
    if area in {"filter", "row", "column", "value"}:
        widget._last_active_area = area
        widget._refresh_active_area_styles()


def refresh_active_area_styles(widget) -> None:
    self = widget
    active = self._last_active_area
    for area_widget, title, area in (
        (getattr(self, "row_fields_list", None), getattr(self, "row_area_title", None), "row"),
        (
            getattr(self, "column_fields_list", None),
            getattr(self, "column_area_title", None),
            "column",
        ),
        (
            getattr(self, "value_fields_list", None),
            getattr(self, "value_area_title", None),
            "value",
        ),
        (
            getattr(self, "filter_fields_list", None),
            getattr(self, "filter_area_title", None),
            "filter",
        ),
    ):
        if area_widget is None or title is None:
            continue
        area_widget.setProperty("activeArea", active == area)
        title.setProperty("activeArea", active == area)
        area_widget.style().unpolish(area_widget)
        area_widget.style().polish(area_widget)
        title.style().unpolish(title)
        title.style().polish(title)


def area_combo(widget, area: str):
    if area == "row":
        return widget.row_field_combo
    if area == "column":
        return widget.column_field_combo
    if area == "value":
        return widget.value_field_combo
    return widget.filter_field_combo


def area_list(widget, area: str) -> QListWidget:
    if area == "row":
        return widget.row_fields_list
    if area == "column":
        return widget.column_fields_list
    if area == "value":
        return widget.value_fields_list
    return widget.filter_fields_list


def area_label(area: str, translate) -> str:
    if area == "row":
        return translate("Linhas")
    if area == "column":
        return translate("Colunas")
    if area == "value":
        return translate("Valores")
    return "Filtros"


def selected_area_specs(widget, area: str) -> List[PivotFieldSpec]:
    specs: List[PivotFieldSpec] = []
    list_widget = widget._area_list(area)
    for index in range(list_widget.count()):
        item = list_widget.item(index)
        if item.data(Qt.UserRole) == "__placeholder__":
            continue
        spec = widget._field_spec_from_key(item.data(Qt.UserRole))
        if spec is not None:
            specs.append(spec)
    return specs


def add_selected_field_to_area(widget, area: str, auto_refresh: bool = True):
    widget._set_last_active_area(area)
    combo = widget._area_combo(area)
    return widget._add_field_to_area(
        area,
        widget._field_spec_from_key(combo.currentData()),
        auto_refresh=auto_refresh,
    )


def add_field_to_area(
    widget,
    area: str,
    field_spec: Optional[PivotFieldSpec],
    *,
    auto_refresh: bool = True,
) -> bool:
    if field_spec is None:
        return False
    list_widget = widget._area_list(area)
    spec_key = widget._register_field_spec(field_spec)
    widget._set_last_active_area(area)
    if area in {"filter", "value"}:
        list_widget.clear()
    elif any(
        list_widget.item(index).data(Qt.UserRole) == spec_key
        for index in range(list_widget.count())
    ):
        widget._show_inline_message(
            f"O campo {field_spec.display_name} ja existe em {widget._area_label(area)}.",
            level="warning",
        )
        return False

    for index in reversed(range(list_widget.count())):
        if list_widget.item(index).data(Qt.UserRole) == "__placeholder__":
            list_widget.takeItem(index)

    item = QListWidgetItem(field_spec.display_name)
    item.setData(Qt.UserRole, spec_key)
    list_widget.addItem(item)
    list_widget.setCurrentItem(item)
    if area == "value":
        combo_index = widget.value_field_combo.findData(spec_key)
        if combo_index != -1:
            widget.value_field_combo.blockSignals(True)
            widget.value_field_combo.setCurrentIndex(combo_index)
            widget.value_field_combo.blockSignals(False)
    widget._show_inline_message("", level="info")
    widget._sync_area_placeholder(area)
    if auto_refresh:
        widget._maybe_refresh()
    return True


def remove_selected_area_field(widget, area: str) -> None:
    list_widget = widget._area_list(area)
    row = list_widget.currentRow()
    if row < 0:
        return
    if list_widget.item(row).data(Qt.UserRole) == "__placeholder__":
        return
    spec_key = list_widget.item(row).data(Qt.UserRole)
    widget._take_area_field_by_key(area, spec_key)
    widget._maybe_refresh()


def remove_area_field_by_key(widget, area: str, spec_key: str) -> None:
    if widget._take_area_field_by_key(area, spec_key) is not None:
        widget._maybe_refresh()


def take_area_field_by_key(widget, area: str, spec_key: str):
    list_widget = widget._area_list(area)
    for row in range(list_widget.count()):
        item = list_widget.item(row)
        if item.data(Qt.UserRole) != spec_key:
            continue
        taken = list_widget.takeItem(row)
        if area == "value":
            widget.value_field_combo.blockSignals(True)
            widget.value_field_combo.setCurrentIndex(0)
            widget.value_field_combo.blockSignals(False)
        widget._sync_area_placeholder(area)
        return taken
    return None


def move_selected_area_field(widget, area: str, offset: int) -> None:
    list_widget = widget._area_list(area)
    row = list_widget.currentRow()
    if row < 0:
        return
    if list_widget.item(row).data(Qt.UserRole) == "__placeholder__":
        return
    new_row = row + offset
    if new_row < 0 or new_row >= list_widget.count():
        return
    if list_widget.item(new_row).data(Qt.UserRole) == "__placeholder__":
        return
    item = list_widget.takeItem(row)
    list_widget.insertItem(new_row, item)
    list_widget.setCurrentRow(new_row)
    widget._refresh_area_item_widgets(area)
    widget._maybe_refresh()


def clear_area(widget, area: str) -> None:
    widget._area_list(area).clear()
    if area == "value":
        widget.value_field_combo.blockSignals(True)
        widget.value_field_combo.setCurrentIndex(0)
        widget.value_field_combo.blockSignals(False)
    widget._sync_area_placeholder(area)


def handle_filter_panel_drop_event(widget, event) -> bool:
    if event.type() not in {QEvent.DragEnter, QEvent.DragMove, QEvent.Drop}:
        return False
    if not event.mimeData().hasFormat(PIVOT_FIELD_MIME):
        return False
    event.setDropAction(Qt.CopyAction)
    if event.type() in {QEvent.DragEnter, QEvent.DragMove}:
        event.accept()
        return True

    try:
        payload = json.loads(bytes(event.mimeData().data(PIVOT_FIELD_MIME)).decode("utf-8"))
    except Exception:
        payload = []
    added = False
    for item in payload or []:
        spec = widget._field_spec_from_key(item.get("spec_key"))
        if spec is None:
            continue
        added = widget._add_field_to_area("filter", spec, auto_refresh=False) or added
        break
    if added:
        widget._set_last_active_area("filter")
        widget._sync_area_placeholder("filter")
        widget._maybe_refresh()
        event.accept()
        return True
    event.ignore()
    return True

