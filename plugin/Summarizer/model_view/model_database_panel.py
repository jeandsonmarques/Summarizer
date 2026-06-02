# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Dict, Optional

try:
    from qgis.PyQt.QtCore import QObject, QRect, QSize, Qt, QThread, pyqtSignal, pyqtSlot
    from qgis.PyQt.QtGui import QColor, QIcon, QPainter
    from qgis.PyQt.QtWidgets import (
        QFrame,
        QHBoxLayout,
        QLabel,
        QSizePolicy,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except Exception:  # pragma: no cover - non-QGIS unit imports
    QObject = QThread = QFrame = QHBoxLayout = QLabel = QSizePolicy = QToolButton = QTreeWidget = QTreeWidgetItem = QVBoxLayout = QWidget = object
    QRect = QSize = Qt = QColor = QIcon = QPainter = None
    pyqtSignal = pyqtSlot = None

try:
    from ..database_explorer import DatabaseConnectionSnapshot, DatabaseMetadataService
    from ..database_explorer.database_models import DatabaseObject
except Exception:  # pragma: no cover
    DatabaseConnectionSnapshot = DatabaseMetadataService = DatabaseObject = None

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
    from ..utils.resources import svg_icon
except Exception:

    def svg_icon(_name: str):
        return QIcon() if QIcon is not None else None

try:
    from .model_theme import _model_panel_chevron_icon
except Exception:

    def _model_panel_chevron_icon(_direction: str = "right", _size: int = 20):
        return QIcon() if QIcon is not None else None


if pyqtSignal is not None:

    class _ModelDatabaseVerticalLabel(QLabel):
        def sizeHint(self):
            hint = super().sizeHint()
            return QSize(max(28, hint.height() + 10), max(96, hint.width() + 16))

        def minimumSizeHint(self):
            return QSize(28, 96)

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(-90)
            rect = QRect(
                int(-self.height() / 2),
                int(-self.width() / 2),
                self.height(),
                self.width(),
            )
            painter.drawText(rect, Qt.AlignCenter, self.text())

    class _ModelDatabaseWorker(QObject):
        finished = pyqtSignal(object)

        def __init__(self, connection_meta: Dict):
            super().__init__()
            self._connection_meta = dict(connection_meta or {})

        @pyqtSlot()
        def run(self):
            try:
                snapshot = DatabaseMetadataService(self._connection_meta).load_snapshot()
            except Exception as exc:  # pragma: no cover - worker boundary
                snapshot = DatabaseConnectionSnapshot(
                    connection_meta=dict(self._connection_meta),
                    connected=False,
                    error_message=str(exc or "") or _rt("Falha ao listar o banco."),
                )
            self.finished.emit(snapshot)


    class ModelDatabasePanel(QFrame):
        objectActivated = pyqtSignal(object)
        toggleRequested = pyqtSignal()

        def __init__(self, parent: Optional[QWidget] = None):
            super().__init__(parent)
            self._connection_meta: Dict = {}
            self._connection_key: str = ""
            self._loaded_connection_key: str = ""
            self._group_objects: Dict[str, list] = {}
            self._thread: Optional[QThread] = None
            self._worker: Optional[_ModelDatabaseWorker] = None
            self.setObjectName("ModelDatabasePanel")
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._build_ui()
            self.clear()

        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            header = QFrame(self)
            header.setObjectName("ModelDatabasePanelHeader")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(6)

            self.title_label = QLabel(_rt("Banco"), header)
            self.title_label.setObjectName("ModelDatabasePanelTitle")
            header_layout.addWidget(self.title_label, 1, Qt.AlignVCenter)

            self.status_label = QLabel("", header)
            self.status_label.setObjectName("ModelDatabasePanelStatus")
            header_layout.addWidget(self.status_label, 0, Qt.AlignVCenter)

            self.refresh_btn = QToolButton(header)
            self.refresh_btn.setObjectName("ModelDatabasePanelRefresh")
            self.refresh_btn.setAutoRaise(True)
            self.refresh_btn.setText("")
            self.refresh_btn.setIcon(svg_icon("Refresh.svg"))
            self.refresh_btn.setIconSize(QSize(14, 14))
            self.refresh_btn.setToolTip(_rt("Atualizar banco"))
            self.refresh_btn.setFixedSize(20, 20)
            self.refresh_btn.clicked.connect(self.refresh)
            header_layout.addWidget(self.refresh_btn, 0, Qt.AlignRight | Qt.AlignVCenter)

            self.toggle_btn = QToolButton(header)
            self.toggle_btn.setObjectName("ModelDatabasePanelToggle")
            self.toggle_btn.setAutoRaise(True)
            self.toggle_btn.setCursor(Qt.PointingHandCursor)
            self.toggle_btn.setArrowType(Qt.NoArrow)
            self.toggle_btn.setIcon(_model_panel_chevron_icon("right", 18))
            self.toggle_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.toggle_btn.setText("")
            self.toggle_btn.setFixedSize(22, 22)
            self.toggle_btn.clicked.connect(self.toggleRequested.emit)
            header_layout.addWidget(self.toggle_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
            self.header = header
            layout.addWidget(self.header, 0)

            self.body = QWidget(self)
            self.body.setObjectName("ModelDatabasePanelBody")
            body_layout = QVBoxLayout(self.body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(5)

            self.tree = QTreeWidget(self)
            self.tree.setObjectName("ModelDatabaseTree")
            self.tree.setHeaderHidden(True)
            self.tree.setRootIsDecorated(True)
            self.tree.setAnimated(True)
            self.tree.setExpandsOnDoubleClick(True)
            self.tree.setIndentation(14)
            self.tree.setMinimumHeight(130)
            self.tree.setMaximumHeight(16777215)
            self.tree.itemClicked.connect(self._handle_item_activated)
            self.tree.itemExpanded.connect(self._materialize_group_item)
            body_layout.addWidget(self.tree, 1)

            self.empty_label = QLabel("", self)
            self.empty_label.setObjectName("ModelDatabasePanelEmpty")
            self.empty_label.setWordWrap(True)
            body_layout.addWidget(self.empty_label, 0)
            layout.addWidget(self.body, 1)

            self.collapsed_rail = QFrame(self)
            self.collapsed_rail.setObjectName("ModelDatabasePanelCollapsedRail")
            rail_layout = QVBoxLayout(self.collapsed_rail)
            rail_layout.setContentsMargins(2, 6, 2, 6)
            rail_layout.setSpacing(8)
            self.collapsed_btn = QToolButton(self.collapsed_rail)
            self.collapsed_btn.setObjectName("ModelDatabasePanelToggle")
            self.collapsed_btn.setAutoRaise(True)
            self.collapsed_btn.setCursor(Qt.PointingHandCursor)
            self.collapsed_btn.setArrowType(Qt.NoArrow)
            self.collapsed_btn.setIcon(_model_panel_chevron_icon("left", 18))
            self.collapsed_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.collapsed_btn.setText("")
            self.collapsed_btn.setFixedSize(22, 22)
            self.collapsed_btn.clicked.connect(self.toggleRequested.emit)
            rail_layout.addWidget(self.collapsed_btn, 0, Qt.AlignHCenter | Qt.AlignTop)
            self.collapsed_title = _ModelDatabaseVerticalLabel(_rt("Banco"), self.collapsed_rail)
            self.collapsed_title.setObjectName("ModelDatabasePanelCollapsedTitle")
            rail_layout.addWidget(self.collapsed_title, 0, Qt.AlignHCenter | Qt.AlignTop)
            rail_layout.addStretch(1)
            self.collapsed_rail.hide()
            layout.addWidget(self.collapsed_rail, 1)

            self.setStyleSheet(
                """
                QFrame#ModelDatabasePanel {
                    background: #FFFFFF;
                    border: 1px solid rgba(17, 24, 39, 0.09);
                    border-radius: 2px;
                }
                QFrame#ModelDatabasePanelHeader {
                    background: #FFFFFF;
                    border: none;
                }
                QLabel#ModelDatabasePanelTitle {
                    color: #111827;
                    font-size: 12px;
                    font-weight: 600;
                }
                QLabel#ModelDatabasePanelCollapsedTitle {
                    color: #111827;
                    font-size: 8pt;
                    font-weight: 500;
                    background: transparent;
                }
                QLabel#ModelDatabasePanelStatus,
                QLabel#ModelDatabasePanelEmpty {
                    color: #64748B;
                    font-size: 10px;
                    font-weight: 400;
                }
                QToolButton#ModelDatabasePanelRefresh,
                QToolButton#ModelDatabasePanelToggle {
                    border: none;
                    color: #475569;
                    background: transparent;
                    font-size: 15px;
                }
                QToolButton#ModelDatabasePanelRefresh:hover,
                QToolButton#ModelDatabasePanelToggle:hover {
                    background: rgba(15, 23, 42, 0.06);
                    border-radius: 3px;
                }
                QTreeWidget#ModelDatabaseTree {
                    border: 1px solid rgba(17, 24, 39, 0.08);
                    border-radius: 2px;
                    background: #FFFFFF;
                    color: #111827;
                    font-size: 11px;
                    outline: 0px;
                    padding: 2px;
                    selection-background-color: rgba(17, 24, 39, 0.04);
                    selection-color: #111827;
                    show-decoration-selected: 0;
                }
                QTreeWidget#ModelDatabaseTree::item {
                    min-height: 28px;
                    padding: 4px 6px;
                    margin: 1px 0px;
                    border-radius: 5px;
                }
                QTreeWidget#ModelDatabaseTree::item:hover {
                    background: rgba(17, 24, 39, 0.035);
                }
                QTreeWidget#ModelDatabaseTree::item:selected {
                    background: rgba(17, 24, 39, 0.045);
                    color: #111827;
                    border: 1px solid transparent;
                }
                QTreeWidget#ModelDatabaseTree::item:selected:active,
                QTreeWidget#ModelDatabaseTree::item:selected:!active {
                    background: rgba(17, 24, 39, 0.045);
                    color: #111827;
                    border: 1px solid transparent;
                }
                """
            )

        def set_collapsed(self, collapsed: bool):
            collapsed = bool(collapsed)
            self.setProperty("collapsed", collapsed)
            self.header.setVisible(not collapsed)
            self.body.setVisible(not collapsed)
            self.collapsed_rail.setVisible(collapsed)
            if collapsed:
                self.release_catalog(keep_groups=True)
            try:
                self.style().unpolish(self)
                self.style().polish(self)
            except Exception:
                log_exception("falha opcional ignorada")

        def release_catalog(self, *, keep_groups: bool = True):
            if not keep_groups:
                self._group_objects = {}
                self.tree.clear()
                self.tree.setVisible(False)
                return
            for index in range(self.tree.topLevelItemCount()):
                group_item = self.tree.topLevelItem(index)
                if group_item is None:
                    continue
                group_key = str(group_item.data(0, Qt.UserRole + 1) or "")
                if not group_key or group_key not in self._group_objects:
                    continue
                while group_item.childCount():
                    group_item.takeChild(0)
                placeholder = QTreeWidgetItem([_rt("Abrir para carregar")])
                placeholder.setData(0, Qt.UserRole, "__placeholder__")
                placeholder.setForeground(0, QColor("#94A3B8"))
                group_item.addChild(placeholder)
                group_item.setExpanded(False)

        def set_connection(self, connection_meta: Dict, *, autoload: bool = True):
            new_meta = dict(connection_meta or {})
            new_key = self._meta_key(new_meta)
            if not new_meta:
                self.clear()
                return
            connection_changed = new_key != self._connection_key
            self._connection_meta = new_meta
            self._connection_key = new_key
            self._set_connection_title(new_meta)
            self.refresh_btn.setEnabled(True)
            if autoload:
                if connection_changed or self._loaded_connection_key != self._connection_key:
                    self.refresh()
                return
            if connection_changed:
                self.tree.clear()
                self.tree.setVisible(False)
                self.status_label.setText("")
                self.empty_label.setText(_rt("Abra o painel para listar o banco"))
                self.empty_label.setVisible(True)

        def clear(self):
            self._connection_meta = {}
            self._connection_key = ""
            self._loaded_connection_key = ""
            self._group_objects = {}
            self.tree.clear()
            self.tree.setVisible(False)
            self.refresh_btn.setEnabled(False)
            self.status_label.setText("")
            self.title_label.setText(_rt("Banco"))
            self.collapsed_title.setText(_rt("Banco"))
            self.empty_label.setText(_rt("Nenhum banco conectado"))
            self.empty_label.setVisible(True)

        def refresh(self):
            if not self._connection_meta:
                self.clear()
                return
            if self._thread is not None:
                return
            self.refresh_btn.setEnabled(False)
            self.status_label.setText(_rt("Carregando"))
            self.empty_label.setText(_rt("Carregando banco"))
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            self.tree.clear()
            self._group_objects = {}

            self._thread = QThread(self)
            self._worker = _ModelDatabaseWorker(self._connection_meta)
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._handle_snapshot)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._clear_worker)
            self._thread.start()

        def _clear_worker(self):
            self._thread = None
            self._worker = None
            self.refresh_btn.setEnabled(bool(self._connection_meta))

        def _handle_snapshot(self, snapshot):
            self.tree.clear()
            self._group_objects = {}
            if snapshot is None or not getattr(snapshot, "connected", False):
                self.status_label.setText(_rt("Erro"))
                self.empty_label.setText(
                    str(getattr(snapshot, "error_message", "") or _rt("Nao foi possivel listar o banco."))
                )
                self.empty_label.setVisible(True)
                self.tree.setVisible(False)
                return

            groups = list(getattr(snapshot, "groups", []) or [])
            total = 0
            default_expand_item = None
            for group in groups:
                objects = list(getattr(group, "objects", []) or [])
                if not objects:
                    continue
                group_name = str(getattr(group, "name", "") or _rt("(padrao)"))
                group_item = QTreeWidgetItem([group_name])
                group_item.setData(0, Qt.UserRole, None)
                group_key = str(len(self._group_objects))
                group_item.setData(0, Qt.UserRole + 1, group_key)
                group_item.setForeground(0, QColor("#111827"))
                group_item.setIcon(0, svg_icon("Dataset.svg"))
                group_item.setToolTip(0, _rt("{count} itens", count=len(objects)))
                self.tree.addTopLevelItem(group_item)
                self._group_objects[group_key] = objects
                placeholder = QTreeWidgetItem([_rt("Carregar itens")])
                placeholder.setData(0, Qt.UserRole, "__placeholder__")
                placeholder.setForeground(0, QColor("#94A3B8"))
                group_item.addChild(placeholder)
                if group_name.strip().lower() == "base_cartografica":
                    default_expand_item = group_item
                total += len(objects)
            self.status_label.setText(_rt("{count} itens", count=total))
            self.empty_label.setVisible(total == 0)
            self.empty_label.setText(_rt("Nenhum item encontrado") if total == 0 else "")
            self.tree.setVisible(total > 0)
            if default_expand_item is not None:
                self.tree.expandItem(default_expand_item)
            self._loaded_connection_key = self._connection_key

        def _materialize_group_item(self, group_item):
            if group_item is None:
                return
            group_key = str(group_item.data(0, Qt.UserRole + 1) or "")
            objects = list(self._group_objects.get(group_key, []) or [])
            if not objects:
                return
            if group_item.childCount() == 1:
                first_child = group_item.child(0)
                if first_child is not None and first_child.data(0, Qt.UserRole) == "__placeholder__":
                    group_item.takeChild(0)
                else:
                    return
            elif group_item.childCount() > 1:
                return
            for database_object in objects:
                label = self._object_label(database_object)
                item = QTreeWidgetItem([label])
                item.setData(0, Qt.UserRole, database_object)
                item.setForeground(0, QColor("#334155"))
                item.setIcon(0, svg_icon("Table.svg"))
                item.setToolTip(0, self._object_tooltip(database_object))
                group_item.addChild(item)

        def _handle_item_activated(self, item, _column: int):
            payload = item.data(0, Qt.UserRole) if item is not None else None
            if payload is not None:
                self.objectActivated.emit(payload)

        def _meta_key(self, connection_meta: Dict) -> str:
            parts = [
                str(connection_meta.get("driver") or ""),
                str(connection_meta.get("host") or ""),
                str(connection_meta.get("port") or ""),
                str(connection_meta.get("database") or ""),
                str(connection_meta.get("service") or ""),
                str(connection_meta.get("name") or ""),
                str(connection_meta.get("user") or ""),
            ]
            return "|".join(parts)

        def _set_connection_title(self, connection_meta: Dict):
            title = self._connection_label(connection_meta)
            self.title_label.setText(title)
            self.collapsed_title.setText(title)

        def _connection_label(self, connection_meta: Dict) -> str:
            for key in ("driver", "provider", "type", "database", "name"):
                value = str(connection_meta.get(key) or "").strip()
                if value:
                    return value
            return _rt("Banco")

        def _object_label(self, database_object) -> str:
            return str(getattr(database_object, "name", "") or "")

        def _object_tooltip(self, database_object) -> str:
            parts = [
                str(getattr(database_object, "name", "") or ""),
                str(getattr(database_object, "object_type", "") or ""),
            ]
            geom = str(getattr(database_object, "geometry_column", "") or "")
            if geom:
                parts.append(_rt("Geom: {geom}", geom=geom))
            return "\n".join(part for part in parts if part)


else:

    class ModelDatabasePanel:  # pragma: no cover - fallback for non-QGIS imports
        pass


__all__ = ["ModelDatabasePanel"]
