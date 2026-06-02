# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Dict, List, Optional

from qgis.PyQt.QtCore import QObject, QEventLoop, QSize, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QApplication,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.resources import svg_icon
from ..utils.i18n_runtime import tr_text as _rt
from .database_metadata_service import DatabaseMetadataService
from .database_models import DatabaseConnectionSnapshot, DatabaseGroup, DatabaseObject


class _MetadataLoadWorker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, connection_meta: Dict):
        super().__init__()
        self._connection_meta = dict(connection_meta or {})

    @pyqtSlot()
    def run(self):
        try:
            snapshot = DatabaseMetadataService(self._connection_meta).load_snapshot()
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            snapshot = DatabaseConnectionSnapshot(
                connection_meta=dict(self._connection_meta),
                connected=False,
                error_message=str(exc or "") or "Falha ao listar o banco.",
            )
        self.finished.emit(snapshot)


class _StatusDot(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = "#94A3B8"
        self.setFixedSize(10, 10)

    def set_color(self, color: str):
        self._color = str(color or "#94A3B8")
        self.update()

    def paintEvent(self, event):  # noqa: D401 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(1, 1, 8, 8)
        painter.end()


class _ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):  # noqa: D401 - Qt override
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):  # noqa: D401 - Qt override
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _ObjectRow(QFrame):
    activated = pyqtSignal(object)

    def __init__(self, database_object: DatabaseObject, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.database_object = database_object
        self._loading = False
        self._loading_offset = 0
        self._activation_loading = False
        self._loading_duration_ms = 0
        self.setObjectName("DatabaseObjectRow")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumWidth(190)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_rt("Clique para abrir"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(9)

        kind = self._kind_label(database_object)
        kind.setFixedSize(24, 24)
        layout.addWidget(kind, 0, Qt.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        name = QLabel(self._display_name(database_object.name), self)
        name.setObjectName("DatabaseObjectName")
        name.setWordWrap(True)
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_layout.addWidget(name)

        detail = self._detail_text(database_object)
        if detail:
            detail_label = QLabel(detail, self)
            detail_label.setObjectName("DatabaseObjectDetail")
            detail_label.setWordWrap(True)
            detail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            text_layout.addWidget(detail_label)

        layout.addLayout(text_layout, 1)

        if database_object.is_vector:
            spatial = QLabel(_rt("spatial"), self)
            spatial.setObjectName("DatabaseSpatialBadge")
            spatial.setAlignment(Qt.AlignCenter)
            layout.addWidget(spatial, 0, Qt.AlignVCenter)

        self.loading_bar = QFrame(self)
        self.loading_bar.setObjectName("DatabaseObjectLoadingBar")
        self.loading_bar.hide()

    def _display_name(self, raw_name: str) -> str:
        text = str(raw_name or "(sem nome)").strip()
        if "_" not in text or len(text) <= 18:
            return text
        return text.replace("_", "_\n")

    def mousePressEvent(self, event):  # noqa: D401 - Qt override
        if event.button() == Qt.LeftButton:
            self._activation_loading = True
            self.set_loading(True)
            self.activated.emit(self.database_object)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: D401 - Qt override
        event.accept()

    def set_loading(self, loading: bool):
        self._loading = bool(loading)
        if not self._loading:
            self._loading_offset = 0
            self._loading_duration_ms = 0
            self._activation_loading = False
            self.loading_bar.hide()
            self.update()
            return
        self._position_loading_bar()
        self.loading_bar.show()
        self.loading_bar.raise_()
        self.update()

    def advance_loading(self):
        if not self._loading:
            return
        self._loading_duration_ms += 45
        self._loading_offset = (self._loading_offset + 12) % max(1, self.width() + 90)
        self._position_loading_bar()
        self.update()

    def has_shown_loading_cycle(self, minimum_ms: int = 900) -> bool:
        return self._loading_duration_ms >= minimum_ms

    def set_loaded(self, loaded: bool):
        self.setProperty("loaded", bool(loaded))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def resizeEvent(self, event):  # noqa: D401 - Qt override
        super().resizeEvent(event)
        if self._loading:
            self._position_loading_bar()

    def _position_loading_bar(self):
        width = max(44, min(120, self.width() // 3))
        x = 8 + self._loading_offset - width
        self.loading_bar.setGeometry(max(8, x), self.height() - 3, min(width, self.width() - 16), 2)

    def _kind_label(self, database_object: DatabaseObject) -> QLabel:
        label = QLabel(self)
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("DatabaseObjectKind")
        object_type = str(database_object.object_type or "").lower()
        if database_object.is_vector or object_type == "vector":
            label.setText("S")
            label.setProperty("kind", "spatial")
            label.setToolTip(_rt("Camada espacial"))
        elif object_type in {"view", "materialized_view"}:
            label.setText("V")
            label.setProperty("kind", "view")
            label.setToolTip(_rt("View"))
        else:
            label.setText("T")
            label.setProperty("kind", "table")
            label.setToolTip(_rt("Tabela"))
        return label

    def _detail_text(self, database_object: DatabaseObject) -> str:
        parts: List[str] = []
        object_type = str(database_object.object_type or "").replace("_", " ")
        if object_type and object_type != "unknown":
            parts.append(object_type)
        if database_object.geometry_column:
            parts.append(f"geom: {database_object.geometry_column}")
        if database_object.comment:
            parts.append(database_object.comment)
        return " - ".join(parts)


class _SchemaCard(QFrame):
    objectActivated = pyqtSignal(object)
    rowsMaterialized = pyqtSignal(object)

    def __init__(
        self,
        group: DatabaseGroup,
        objects: List[DatabaseObject],
        parent: Optional[QWidget] = None,
        *,
        expanded: bool = False,
    ):
        super().__init__(parent)
        self.group = group
        self.objects = list(objects)
        self._rows: List[_ObjectRow] = []
        self._expanded = bool(expanded)
        self._object_layout: Optional[QGridLayout] = None
        self._object_host: Optional[QWidget] = None
        self.setObjectName("DatabaseSchemaCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.toggle_btn = QToolButton(self)
        self.toggle_btn.setObjectName("DatabaseSchemaToggle")
        self.toggle_btn.setAutoRaise(True)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedSize(22, 22)
        self.toggle_btn.clicked.connect(self.toggle_expanded)
        header.addWidget(self.toggle_btn, 0, Qt.AlignVCenter)

        title = QLabel(group.name or "(padrao)", self)
        title.setObjectName("DatabaseSchemaTitle")
        header.addWidget(title, 1)

        count = QLabel(self._counter_text(objects), self)
        count.setObjectName("DatabaseSchemaCount")
        count.setAlignment(Qt.AlignCenter)
        header.addWidget(count, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(header)

        self._body_layout = layout
        self._sync_expanded_state()
        if self._expanded:
            self._materialize_rows()

    def object_rows(self) -> List[_ObjectRow]:
        return list(self._rows)

    def toggle_expanded(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        next_state = bool(expanded)
        if next_state == self._expanded:
            return
        self._expanded = next_state
        self._sync_expanded_state()
        if self._expanded:
            self._materialize_rows()

    def _sync_expanded_state(self):
        self.toggle_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        self.setProperty("collapsed", not self._expanded)
        if self._object_host is not None:
            self._object_host.setVisible(self._expanded)
        self.style().unpolish(self)
        self.style().polish(self)

    def _materialize_rows(self):
        if self._object_host is not None:
            self._object_host.setVisible(True)
            return
        self._object_host = QWidget(self)
        self._object_host.setObjectName("DatabaseSchemaObjectHost")
        object_layout = QGridLayout(self._object_host)
        object_layout.setContentsMargins(0, 0, 0, 0)
        object_layout.setHorizontalSpacing(8)
        object_layout.setVerticalSpacing(8)
        self._object_layout = object_layout

        column_count = self._object_column_count(self.objects)
        for index, database_object in enumerate(self.objects):
            row = _ObjectRow(database_object, self._object_host)
            row.activated.connect(self.objectActivated)
            self._rows.append(row)
            object_layout.addWidget(row, index // column_count, index % column_count)
        self._body_layout.addWidget(self._object_host)
        self.rowsMaterialized.emit(self)

    def _object_column_count(self, objects: List[DatabaseObject]) -> int:
        longest_name = max((len(str(obj.name or "")) for obj in objects), default=0)
        if longest_name >= 28:
            return 2
        if longest_name >= 18:
            return 3
        if len(objects) >= 9:
            return 4
        if len(objects) >= 4:
            return 3
        return 2

    def _counter_text(self, objects: List[DatabaseObject]) -> str:
        table_count = 0
        view_count = 0
        spatial_count = 0
        for obj in objects:
            object_type = str(obj.object_type or "").lower()
            if obj.is_vector or object_type == "vector":
                spatial_count += 1
            elif object_type in {"view", "materialized_view"}:
                view_count += 1
            else:
                table_count += 1

        parts = []
        if table_count:
            parts.append(_rt("{count} tabela", count=table_count) if table_count == 1 else _rt("{count} tabelas", count=table_count))
        if view_count:
            parts.append(_rt("{count} view", count=view_count) if view_count == 1 else _rt("{count} views", count=view_count))
        if spatial_count:
            parts.append(_rt("{count} spatial", count=spatial_count))
        return " - ".join(parts) or _rt("0 itens")


class DatabaseExplorerPanel(QWidget):
    """Standalone panel that renders a database catalog snapshot."""

    tableActivated = pyqtSignal(object)
    connectionEditRequested = pyqtSignal(dict)
    statusChanged = pyqtSignal(str)

    def __init__(
        self,
        connection_meta: Optional[Dict] = None,
        snapshot: Optional[DatabaseConnectionSnapshot] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._connection_meta: Dict = {}
        self._snapshot: Optional[DatabaseConnectionSnapshot] = None
        self._pending_refresh = False
        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[_MetadataLoadWorker] = None
        self._cards: List[_SchemaCard] = []
        self._connection_edit_handler = None
        self._loading_rows: List[_ObjectRow] = []
        self._activating_object_keys = set()
        self._loaded_object_keys = set()
        self._row_loading_timer = QTimer(self)
        self._row_loading_timer.setInterval(45)
        self._row_loading_timer.timeout.connect(self._advance_row_loading)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._render_snapshot)
        self._build_ui()
        self._apply_styles()
        if snapshot is not None:
            self.set_snapshot(snapshot)
        elif connection_meta:
            self.set_connection(connection_meta)
        else:
            self.clear()

    def set_connection(self, connection_meta: Dict):
        next_meta = dict(connection_meta or {})
        previous_key = self._connection_key(self._connection_meta)
        next_key = self._connection_key(next_meta)
        if next_key and next_key == previous_key:
            if self._pending_refresh or self._worker_thread is not None:
                return
            if self._snapshot is not None:
                return

        self._connection_meta = next_meta
        self._snapshot = None
        self._activating_object_keys.clear()
        self._loaded_object_keys.clear()
        self._set_ready_state()
        QTimer.singleShot(120, self.refresh)

    def set_snapshot(self, snapshot: DatabaseConnectionSnapshot):
        self._connection_meta = dict(snapshot.connection_meta or {})
        self._snapshot = snapshot
        self._render_snapshot()

    def refresh(self):
        if not self._connection_meta:
            self.clear()
            return
        if self._pending_refresh:
            return
        self._pending_refresh = True
        self._set_loading_state()
        QTimer.singleShot(0, self._start_metadata_worker)

    def clear(self):
        self._pending_refresh = False
        self._connection_meta = {}
        self._snapshot = None
        self._worker_thread = None
        self._worker = None
        self._activating_object_keys.clear()
        self._loaded_object_keys.clear()
        self.search_edit.clear()
        self._set_header({}, "idle")
        self._clear_cards()
        self._stop_row_loading()
        self._set_message(_rt("Nenhum banco conectado"), _rt("Conecte um banco para visualizar schemas e tabelas"))

    def has_connection(self) -> bool:
        return bool(self._connection_meta)

    def set_connection_edit_handler(self, handler):
        self._connection_edit_handler = handler if callable(handler) else None

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        self._build_toolbar(root)
        self._build_catalog_area(root)

    def _build_toolbar(self, root: QVBoxLayout):
        self.toolbar_frame = QWidget(self)
        self.toolbar_frame.setObjectName("DatabaseExplorerToolbar")
        toolbar = QHBoxLayout(self.toolbar_frame)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)

        header = _ClickableFrame(self.toolbar_frame)
        header.setObjectName("DatabaseExplorerHeader")
        header.setCursor(Qt.PointingHandCursor)
        header.clicked.connect(self._request_connection_edit)
        header.setMinimumHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        header_layout.setSpacing(2)

        self.status_dot = _StatusDot(header)
        header_layout.addWidget(self.status_dot, 0, Qt.AlignVCenter)

        self.status_label = QLabel(_rt("Desconectado"), header)
        self.status_label.setObjectName("DatabaseExplorerStatus")
        header_layout.addWidget(self.status_label, 0, Qt.AlignVCenter)
        header_layout.addWidget(self._toolbar_separator(header), 0)

        self.database_label = QPushButton("", header)
        self.database_label.setObjectName("DatabaseExplorerDatabase")
        self.database_label.setCursor(Qt.PointingHandCursor)
        self.database_label.setFlat(True)
        self.database_label.setToolTip(_rt("Editar conexÃ£o"))
        self.database_label.clicked.connect(self._request_connection_edit)
        header_layout.addWidget(self.database_label, 0, Qt.AlignVCenter)

        self.driver_label = QPushButton("", header)
        self.driver_label.setObjectName("DatabaseExplorerDriver")
        self.driver_label.setCursor(Qt.PointingHandCursor)
        self.driver_label.setFlat(True)
        self.driver_label.setToolTip(_rt("Editar conexão"))
        self.driver_label.clicked.connect(self._request_connection_edit)
        header_layout.addWidget(self.driver_label, 0, Qt.AlignVCenter)

        self.search_edit = QLineEdit(header)
        self.search_edit.setObjectName("DatabaseExplorerSearch")
        self.search_edit.setPlaceholderText(_rt("Buscar"))
        self.search_edit.setFixedHeight(28)
        self.search_edit.setMinimumWidth(166)
        self.search_edit.setMaximumWidth(220)
        self.search_edit.addAction(svg_icon("Search.svg"), QLineEdit.LeadingPosition)
        self.search_edit.textChanged.connect(lambda *_: self._search_timer.start())
        header_layout.addStretch(1)
        header_layout.addWidget(self.search_edit, 0)

        self.refresh_btn = QPushButton("", header)
        self.refresh_btn.setObjectName("DatabaseExplorerRefresh")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setIcon(svg_icon("Refresh.svg"))
        self.refresh_btn.setIconSize(QSize(17, 17))
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip(_rt("Atualizar"))
        self.refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(self.refresh_btn, 0, Qt.AlignVCenter)

        toolbar.addWidget(header, 1)
        root.addWidget(self.toolbar_frame, 0)

    def _build_catalog_area(self, root: QVBoxLayout):
        self.message_frame = QFrame(self)
        self.message_frame.setObjectName("DatabaseExplorerMessage")
        message_layout = QVBoxLayout(self.message_frame)
        message_layout.setContentsMargins(18, 48, 18, 48)
        message_layout.setSpacing(8)
        self.message_title = QLabel("", self.message_frame)
        self.message_title.setObjectName("DatabaseExplorerMessageTitle")
        self.message_title.setAlignment(Qt.AlignCenter)
        message_layout.addWidget(self.message_title)
        self.message_body = QLabel("", self.message_frame)
        self.message_body.setObjectName("DatabaseExplorerMessageBody")
        self.message_body.setAlignment(Qt.AlignCenter)
        self.message_body.setWordWrap(True)
        message_layout.addWidget(self.message_body)
        root.addWidget(self.message_frame, 1)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("DatabaseExplorerScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.cards_host = QWidget(self.scroll_area)
        self.cards_host.setObjectName("DatabaseExplorerCardsHost")
        self.cards_layout = QGridLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(14)
        self.cards_layout.setVerticalSpacing(14)
        self.scroll_area.setWidget(self.cards_host)
        root.addWidget(self.scroll_area, 1)

    def _toolbar_separator(self, parent: QWidget) -> QFrame:
        separator = QFrame(parent)
        separator.setObjectName("DatabaseExplorerToolbarSeparator")
        separator.setFrameShape(QFrame.VLine)
        return separator

    def _apply_styles(self):
        self.setObjectName("DatabaseExplorerPanel")
        self.setStyleSheet(
            """
            QWidget#DatabaseExplorerPanel {
                background: #F8FAFC;
                color: #111827;
            }
            QFrame#DatabaseExplorerHeader {
                background: #FFFFFF;
                border: 1px solid #D6D9E0;
                border-radius: 8px;
            }
            QFrame#DatabaseExplorerToolbarSeparator {
                min-width: 1px;
                max-width: 1px;
                margin: 4px 6px;
                background: #E5E7EB;
                border: none;
            }
            QLabel#DatabaseExplorerStatus {
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                padding-left: 4px;
                padding-right: 6px;
            }
            QPushButton#DatabaseExplorerDatabase {
                color: #111827;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
                padding: 0 6px;
                text-align: left;
            }
            QPushButton#DatabaseExplorerDatabase:hover {
                color: #4F46E5;
            }
            QPushButton#DatabaseExplorerDriver {
                background: #EEF2FF;
                color: #3730A3;
                border-radius: 8px;
                padding: 4px 9px;
                font-size: 11px;
                font-weight: 700;
                border: none;
                text-align: center;
            }
            QPushButton#DatabaseExplorerDriver:hover {
                background: #E0E7FF;
            }
            QLineEdit#DatabaseExplorerSearch {
                min-height: 28px;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 0 9px;
                color: #4b5563;
                font-size: 12px;
                font-weight: 400;
            }
            QLineEdit#DatabaseExplorerSearch:hover,
            QLineEdit#DatabaseExplorerSearch:focus {
                border: 1px solid #9CA3AF;
                background: #FFFFFF;
            }
            QPushButton#DatabaseExplorerRefresh {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                background: transparent;
                color: #111827;
                border: none;
                border-radius: 6px;
                padding: 0px;
                text-align: center;
            }
            QPushButton#DatabaseExplorerRefresh:hover {
                background: #F3F4F6;
            }
            QPushButton#DatabaseExplorerRefresh:disabled {
                background: transparent;
                color: #94A3B8;
            }
            QFrame#DatabaseExplorerMessage {
                background: #FFFFFF;
                border: 1px dashed #CBD5E1;
                border-radius: 8px;
            }
            QLabel#DatabaseExplorerMessageTitle {
                color: #111827;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#DatabaseExplorerMessageBody {
                color: #64748B;
                font-size: 12px;
            }
            QWidget#DatabaseExplorerCardsHost {
                background: transparent;
            }
            QScrollArea#DatabaseExplorerScroll,
            QScrollArea#DatabaseSchemaObjectScroll {
                background: transparent;
                border: none;
            }
            QFrame#DatabaseSchemaCard {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            QFrame#DatabaseSchemaCard:hover {
                border-color: #CBD5E1;
            }
            QFrame#DatabaseSchemaCard[collapsed="true"] {
                background: #FFFFFF;
            }
            QToolButton#DatabaseSchemaToggle {
                background: transparent;
                border: none;
                color: #475569;
                padding: 0px;
            }
            QToolButton#DatabaseSchemaToggle:hover {
                background: #F3F4F6;
                border-radius: 4px;
            }
            QLabel#DatabaseSchemaTitle {
                color: #111827;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#DatabaseSchemaCount {
                background: #F1F5F9;
                color: #475569;
                border-radius: 8px;
                min-width: 0px;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#DatabaseObjectRow {
                background: #F8FAFC;
                border: 1px solid transparent;
                border-radius: 7px;
            }
            QFrame#DatabaseObjectRow:hover {
                background: #F1F5F9;
                border-color: #E2E8F0;
            }
            QFrame#DatabaseObjectRow[loaded="true"] {
                background: #ECFDF5;
                border-color: #86EFAC;
            }
            QFrame#DatabaseObjectRow[loaded="true"]:hover {
                background: #DCFCE7;
                border-color: #4ADE80;
            }
            QFrame#DatabaseObjectLoadingBar {
                background: #16A34A;
                border: none;
                border-radius: 1px;
            }
            QLabel#DatabaseObjectKind {
                border-radius: 6px;
                font-size: 10px;
                font-weight: 800;
            }
            QLabel#DatabaseObjectKind[kind="table"] {
                background: #E0F2FE;
                color: #0369A1;
            }
            QLabel#DatabaseObjectKind[kind="view"] {
                background: #FCE7F3;
                color: #BE185D;
            }
            QLabel#DatabaseObjectKind[kind="spatial"] {
                background: #DCFCE7;
                color: #15803D;
            }
            QLabel#DatabaseObjectName {
                color: #111827;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#DatabaseObjectDetail {
                color: #64748B;
                font-size: 10px;
            }
            QLabel#DatabaseSpatialBadge {
                background: #DCFCE7;
                color: #15803D;
                border-radius: 7px;
                padding: 3px 7px;
                font-size: 10px;
                font-weight: 700;
            }
            """
        )

    def _start_metadata_worker(self):
        if not self._connection_meta:
            self._pending_refresh = False
            self.clear()
            return
        if self._worker_thread is not None:
            return
        self.refresh_btn.setEnabled(False)
        thread = QThread(self)
        worker = _MetadataLoadWorker(self._connection_meta)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_snapshot_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker_refs)
        self._worker_thread = thread
        self._worker = worker
        thread.start()

    def _on_snapshot_loaded(self, snapshot: DatabaseConnectionSnapshot):
        self._pending_refresh = False
        self.refresh_btn.setEnabled(True)
        self._snapshot = snapshot
        self._render_snapshot()

    def _render_snapshot(self):
        snapshot = self._snapshot
        if snapshot is None:
            return

        self._set_header(snapshot.connection_meta, self._snapshot_status(snapshot))
        self._clear_cards()

        if not snapshot.connected:
            self._set_message(_rt("Não foi possível listar o banco"), snapshot.error_message)
            return

        filtered_groups = self._filtered_groups(snapshot.groups, self.search_edit.text())
        if not filtered_groups:
            body = "" if self.search_edit.text().strip() else _rt("Conecte um banco para visualizar schemas e tabelas")
            self._set_message(_rt("Nenhum item encontrado"), body)
            return

        self.message_frame.hide()
        self.scroll_area.show()
        column_count = self._column_count()
        search_active = bool(self.search_edit.text().strip())
        default_expanded_name = self._default_expanded_group_name(filtered_groups)
        for index, group in enumerate(filtered_groups):
            group_name = str(group.name or "").strip()
            expanded = search_active or group_name == default_expanded_name
            card = _SchemaCard(group, group.objects, self.cards_host, expanded=expanded)
            card.objectActivated.connect(self._handle_object_activated)
            card.rowsMaterialized.connect(self._sync_loaded_rows)
            self._cards.append(card)
            self._sync_loaded_rows(card)
            row = index // column_count
            column = index % column_count
            self.cards_layout.addWidget(card, row, column)
        self.cards_layout.setRowStretch((len(filtered_groups) // column_count) + 1, 1)

    def _default_expanded_group_name(self, groups: List[DatabaseGroup]) -> str:
        if not groups:
            return ""
        for group in groups:
            name = str(group.name or "").strip()
            if name.lower() == "base_cartografica":
                return name
        return str(getattr(groups[0], "name", "") or "").strip()

    def _filtered_groups(self, groups: List[DatabaseGroup], search_text: str) -> List[DatabaseGroup]:
        needle = str(search_text or "").strip().lower()
        if not needle:
            return groups

        filtered: List[DatabaseGroup] = []
        for group in groups:
            schema_matches = needle in str(group.name or "").lower()
            objects = [
                obj
                for obj in group.objects
                if schema_matches
                or needle in str(obj.name or "").lower()
                or needle in str(obj.object_type or "").lower()
                or needle in str(obj.comment or "").lower()
            ]
            if objects:
                filtered.append(DatabaseGroup(name=group.name, objects=objects))
        return filtered

    def _clear_cards(self):
        self._stop_row_loading()
        self._cards = []
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _handle_object_activated(self, database_object: DatabaseObject):
        object_key = self._object_key(database_object)
        if object_key in self._activating_object_keys or object_key in self._loaded_object_keys:
            return
        self._activating_object_keys.add(object_key)
        self._start_row_loading(database_object)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents, 50)
        QTimer.singleShot(900, lambda obj=database_object: self._emit_object_after_loading_intro(obj))

    def mark_object_loaded(self, database_object: Optional[DatabaseObject] = None, loaded: bool = False):
        object_key = self._object_key(database_object) if database_object is not None else ""
        if object_key:
            self._activating_object_keys.discard(object_key)
            if loaded:
                self._loaded_object_keys.add(object_key)
                self._set_object_loaded(database_object, True)
        QTimer.singleShot(250, self._stop_row_loading)

    def mark_object_unloaded(self, database_object: Optional[DatabaseObject] = None):
        object_key = self._object_key(database_object) if database_object is not None else ""
        if not object_key:
            return
        self._activating_object_keys.discard(object_key)
        self._loaded_object_keys.discard(object_key)
        self._set_object_loaded(database_object, False)

    def _emit_object_after_loading_intro(self, database_object: DatabaseObject):
        if self._loading_rows and not all(row.has_shown_loading_cycle() for row in self._loading_rows):
            QTimer.singleShot(180, lambda obj=database_object: self._emit_object_after_loading_intro(obj))
            return
        self.tableActivated.emit(database_object)

    def _start_row_loading(self, database_object: DatabaseObject):
        self._stop_row_loading()
        for card in self._cards:
            for row in card.object_rows():
                if (
                    row.database_object.schema == database_object.schema
                    and row.database_object.name == database_object.name
                ):
                    row.set_loading(True)
                    row.repaint()
                    self._loading_rows.append(row)
        if self._loading_rows:
            self._row_loading_timer.start()
            QTimer.singleShot(12000, self._stop_row_loading)

    def _sync_loaded_rows(self, card: _SchemaCard):
        for row in card.object_rows():
            row.set_loaded(self._object_key(row.database_object) in self._loaded_object_keys)

    def _set_object_loaded(self, database_object: DatabaseObject, loaded: bool):
        object_key = self._object_key(database_object)
        for card in self._cards:
            for row in card.object_rows():
                if self._object_key(row.database_object) == object_key:
                    row.set_loaded(loaded)

    def _object_key(self, database_object: Optional[DatabaseObject]) -> str:
        if database_object is None:
            return ""
        return "|".join(
            str(value or "")
            for value in (
                getattr(database_object, "provider_key", ""),
                getattr(database_object, "schema", ""),
                getattr(database_object, "name", ""),
                getattr(database_object, "geometry_column", ""),
            )
        )

    def _advance_row_loading(self):
        active_rows = [row for row in self._loading_rows if row is not None]
        for row in active_rows:
            row.advance_loading()
        if not active_rows:
            self._row_loading_timer.stop()

    def _stop_row_loading(self):
        if hasattr(self, "_row_loading_timer"):
            self._row_loading_timer.stop()
        for row in getattr(self, "_loading_rows", []):
            if row is not None:
                row.set_loading(False)
        self._loading_rows = []

    def _set_header(self, connection_meta: Dict, status: str):
        database = connection_meta.get("database") or connection_meta.get("name") or "Banco"
        driver = connection_meta.get("driver") or connection_meta.get("source_driver") or ""
        colors = {
            "connected": ("#22C55E", _rt("Conectado")),
            "empty": ("#F59E0B", _rt("Sem itens")),
            "error": ("#EF4444", _rt("Erro")),
            "idle": ("#94A3B8", _rt("Desconectado")),
            "loading": ("#F59E0B", _rt("Carregando")),
            "ready": ("#F59E0B", _rt("Conectado")),
        }
        color, text = colors.get(status, colors["idle"])
        self.database_label.setText(str(database))
        self.driver_label.setText(str(driver))
        self.driver_label.setVisible(bool(driver))
        self.status_dot.set_color(color)
        self.status_dot.setVisible(bool(connection_meta))
        self.status_label.setText(text)
        self.status_label.setVisible(bool(connection_meta))
        self.statusChanged.emit(status)

    def _request_connection_edit(self):
        if not self._connection_meta:
            return
        meta = dict(self._connection_meta)
        if callable(self._connection_edit_handler):
            QTimer.singleShot(0, lambda: self._connection_edit_handler(dict(meta)))
            return
        self.connectionEditRequested.emit(meta)

    def _set_loading_state(self):
        self._set_header(self._connection_meta, "loading")
        self._clear_cards()
        self.scroll_area.hide()
        self.message_frame.show()
        self.message_title.setText(_rt("Carregando banco"))
        self.message_body.setText("")

    def _set_ready_state(self):
        self._set_header(self._connection_meta, "ready")
        self._clear_cards()
        self.scroll_area.hide()
        self.message_frame.show()
        self.message_title.setText(_rt("Banco conectado"))
        self.message_body.setText(_rt("Listando schemas e tabelas..."))

    def _clear_worker_refs(self):
        self._worker_thread = None
        self._worker = None

    def _snapshot_status(self, snapshot: DatabaseConnectionSnapshot) -> str:
        if not snapshot.connected:
            return "error"
        has_objects = any(group.objects for group in snapshot.groups)
        return "connected" if has_objects else "empty"

    def _set_message(self, title: str, body: str):
        self._clear_cards()
        self.scroll_area.hide()
        self.message_frame.show()
        self.message_title.setText(title)
        self.message_body.setText(body or "")
        self.message_body.setVisible(bool(body))

    def _column_count(self) -> int:
        return 1

    def _connection_key(self, connection_meta: Dict) -> str:
        meta = connection_meta or {}
        return str(
            meta.get("fingerprint")
            or "|".join(
                str(meta.get(key) or "")
                for key in ("driver", "source_driver", "host", "service", "port", "database", "name", "username")
            )
        )
