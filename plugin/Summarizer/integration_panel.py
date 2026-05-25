# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from qgis.PyQt.QtCore import (
    QDateTime,
    QEvent,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QCursor, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsVectorLayer

from .slim_dialogs import SlimDialogBase, SlimMessageDialog
from .browser_integration import connection_registry
from .palette import COLORS, DARK_COLORS
from .utils.fonts import harmonize_widget_fonts, ui_font, ui_font_stack
from .utils.i18n_runtime import apply_widget_translations as _apply_i18n_widgets, tr_text as _rt
from .utils.resources import svg_icon
from .utils.security_utils import reveal_connection_payload, secure_connection_payload
from .utils.window_theme import apply_windows_rounded_corners
from .walker_dialogs import WalkerMessageBox as QMessageBox

from .utils.logging_utils import log_exception
_ICON_DIR = os.path.join(os.path.dirname(__file__), "resources", "icons")


def _is_dark_theme() -> bool:
    try:
        return str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower() == "dark"
    except Exception:
        return False

try:  # pragma: no cover - handles platforms without QtSql
    from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery
except ImportError:  # pragma: no cover
    QSqlDatabase = None
    QSqlQuery = None


PREVIEW_ROW_LIMIT = 120
RECENTS_SETTINGS_KEY = "Summarizer/integration/recent_sources"
SAVED_CONNECTIONS_KEY = "Summarizer/integration/saved_connections"
LAST_DB_PARAMS_KEY = "Summarizer/integration/last_db_params"
_CONNECTED_DATABASE_KEYS: set[str] = set()
_CONNECTED_DATABASE_TABLES: Dict[str, List[str]] = {}
_CONNECTED_DATABASE_PARAMS: Dict[str, Dict] = {}


def connected_database_drivers() -> set[str]:
    return {
        key.split("|", 1)[0]
        for key in _CONNECTED_DATABASE_KEYS
        if key
    }


def _connection_status_key_from_params(values: Dict) -> str:
    driver = str(values.get("source_driver") or values.get("driver") or "").strip()
    host = str(values.get("host") or "").strip().lower()
    port = str(values.get("port") or "").strip()
    database = str(values.get("database") or "").strip().lower()
    user = str(values.get("user") or "").strip().lower()
    ssl_mode = str(values.get("ssl_mode") or "").strip().lower()
    use_ssl = "1" if values.get("use_ssl") else "0"
    if not driver or not host or not database or not user:
        return ""
    return "|".join((driver, host, port, database, user, ssl_mode, use_ssl))


def _normalize_ssl_mode(value: object) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "ssldisable": "disable",
        "sslprefer": "prefer",
        "sslrequire": "require",
        "disable": "disable",
        "prefer": "prefer",
        "require": "require",
    }
    return mapping.get(text, text.replace("ssl", "", 1) if text.startswith("ssl") else text)


def _database_params_from_connection(connection: Dict) -> Dict:
    data = reveal_connection_payload(connection)
    source_driver = str(data.get("source_driver") or data.get("driver") or "PostgreSQL")
    normalized_driver = "PostgreSQL" if source_driver == "PostGIS" else source_driver
    try:
        port = int(data.get("port") or 5432)
    except (TypeError, ValueError):
        port = 5432
    return {
        "driver": normalized_driver,
        "source_driver": source_driver,
        "host": str(data.get("host") or "").strip(),
        "port": port,
        "database": str(data.get("database") or "").strip(),
        "user": str(data.get("user") or "").strip(),
        "password": str(data.get("password") or ""),
        "ssl_mode": _normalize_ssl_mode(data.get("ssl_mode") or data.get("sslmode") or "disable"),
        "use_ssl": bool(data.get("use_ssl")),
    }


def _mark_connected_database_params(params: Dict, tables: Optional[List[str]] = None):
    key = _connection_status_key_from_params(params)
    if not key:
        return
    _CONNECTED_DATABASE_KEYS.add(key)
    _CONNECTED_DATABASE_PARAMS[key] = dict(params)
    if tables is not None:
        _CONNECTED_DATABASE_TABLES[key] = list(tables)


def _forget_connected_database_params(params: Dict):
    key = _connection_status_key_from_params(params)
    if not key:
        return
    _CONNECTED_DATABASE_KEYS.discard(key)
    _CONNECTED_DATABASE_PARAMS.pop(key, None)
    _CONNECTED_DATABASE_TABLES.pop(key, None)


def _open_database_connection(params: Dict, owner_token: object = "auto") -> Tuple[bool, object]:
    if QSqlDatabase is None:
        return False, _rt("QtSql nÃ£o estÃ¡ disponÃ­vel nesta instalaÃ§Ã£o.")

    conn_name = f"integ_{owner_token}_{QDateTime.currentMSecsSinceEpoch()}"
    driver = params.get("driver")
    available_drivers = set(QSqlDatabase.drivers())

    if driver == "PostgreSQL":
        if "QPSQL" not in available_drivers:
            return False, _rt("Driver PostgreSQL (QPSQL) nÃ£o estÃ¡ disponÃ­vel nesta instalaÃ§Ã£o.")
        db = QSqlDatabase.addDatabase("QPSQL", conn_name)
        db.setHostName(params.get("host"))
        db.setPort(params.get("port") or 5432)
        db.setDatabaseName(params.get("database"))
        db.setUserName(params.get("user"))
        db.setPassword(params.get("password"))
        ssl_mode = str(params.get("ssl_mode") or "").strip()
        if ssl_mode:
            db.setConnectOptions(f"sslmode={ssl_mode}")
    elif driver == "SQL Server":
        if "QODBC" not in available_drivers:
            return False, _rt("Driver SQL Server (QODBC) nÃ£o estÃ¡ disponÃ­vel nesta instalaÃ§Ã£o.")
        db = QSqlDatabase.addDatabase("QODBC", conn_name)
        connection_string = (
            "Driver={ODBC Driver 17 for SQL Server};"
            f"Server={params.get('host')},{params.get('port') or 1433};"
            f"Database={params.get('database')};"
            f"Uid={params.get('user')};"
            f"Pwd={params.get('password')};"
        )
        db.setDatabaseName(connection_string)
    elif driver == "Oracle":
        if "QOCI" not in available_drivers:
            return False, _rt("Driver Oracle (QOCI) nÃ£o estÃ¡ disponÃ­vel nesta instalaÃ§Ã£o.")
        db = QSqlDatabase.addDatabase("QOCI", conn_name)
        db.setHostName(params.get("host"))
        db.setPort(params.get("port") or 1521)
        db.setDatabaseName(params.get("database"))
        db.setUserName(params.get("user"))
        db.setPassword(params.get("password"))
    elif driver == "MySQL":
        if "QMYSQL" not in available_drivers:
            return False, _rt("Driver MySQL (QMYSQL) nÃ£o estÃ¡ disponÃ­vel nesta instalaÃ§Ã£o.")
        db = QSqlDatabase.addDatabase("QMYSQL", conn_name)
        db.setHostName(params.get("host"))
        db.setPort(params.get("port") or 3306)
        db.setDatabaseName(params.get("database"))
        db.setUserName(params.get("user"))
        db.setPassword(params.get("password"))
        if params.get("use_ssl"):
            db.setConnectOptions("CLIENT_SSL=1")
    else:
        return False, _rt("Conector de banco de dados nÃ£o suportado nesta instalaÃ§Ã£o.")

    if not db.open():
        error = db.lastError().text()
        db = None
        return False, error or _rt("Falha ao abrir a conexÃ£o.")
    return True, db


def _database_table_names(db, driver: str) -> List[str]:
    tables: List[str] = []
    if QSqlQuery is None:
        return tables
    query = QSqlQuery(db)
    if driver == "PostgreSQL":
        query.exec_(
            "SELECT table_schema || '.' || table_name "
            "FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' "
            "ORDER BY 1"
        )
    elif driver == "SQL Server":
        query.exec_(
            "SELECT TABLE_SCHEMA + '.' + TABLE_NAME "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY 1"
        )
    elif driver == "Oracle":
        query.exec_(
            "SELECT OWNER || '.' || TABLE_NAME "
            "FROM ALL_TABLES "
            "ORDER BY 1"
        )
    else:
        query.exec_(
            "SELECT CONCAT(TABLE_SCHEMA, '.', TABLE_NAME) "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY 1"
        )
    while query.next():
        tables.append(str(query.value(0) or ""))
    return tables


def auto_connect_saved_databases(saved_connections: Optional[Sequence[Dict]] = None) -> set[str]:
    connections = list(saved_connections if saved_connections is not None else connection_registry.saved_connections())
    for connection in connections:
        params = _database_params_from_connection(connection)
        if not params.get("host") or not params.get("database") or not params.get("user"):
            continue
        if not params.get("password") and not connection.get("authcfg"):
            continue
        ok, db_or_error = _open_database_connection(params, owner_token="auto")
        if not ok:
            continue
        db = db_or_error
        try:
            tables = _database_table_names(db, params["driver"])
            _mark_connected_database_params(params, tables)
        finally:
            db.close()
    return connected_database_drivers()


def _apply_walker_dialog_buttons(*, primary=None, secondary=None):
    for button in list(primary or []):
        if button is None:
            continue
        button.setObjectName("SlimPrimaryButton")
        button.style().unpolish(button)
        button.style().polish(button)
    for button in list(secondary or []):
        if button is None:
            continue
        button.setObjectName("SlimSecondaryButton")
        button.style().unpolish(button)
        button.style().polish(button)


@dataclass
class ConnectorConfig:
    key: str
    title: str
    caption: str
    microcopy: str
    accent: str
    icon_text: str
    handler: Callable[[], None]
    category: str = "primary"
    description: str = ""
    icon_name: str = ""
    icon_path: str = ""
    keywords: str = ""


class ConnectorCard(QFrame):
    """Clickable tile that mimics BI get data cards."""

    triggered = pyqtSignal(str)

    def __init__(self, config: ConnectorConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.setObjectName(f"integrationCard_{config.key}")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(148, 102)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(40, 40)
        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)

        self.title_label = QLabel(self.config.title, self)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.title_label)

        self.caption_label = QLabel(self.config.caption, self)
        self.caption_label.setWordWrap(True)
        self.caption_label.setProperty("class", "cardCaption")
        self.caption_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.caption_label)

    def _apply_styles(self):
        colors = DARK_COLORS if _is_dark_theme() else COLORS
        self.setStyleSheet(
            f"""
            ConnectorCard {{
                background-color: transparent;
                border: none;
            }}
            QLabel {{
                font-family: %s;
                color: {colors["color_text_primary"]};
            }}
            QLabel[class="cardCaption"] {{
                font-size: 8.6pt;
                font-weight: 400;
                color: {colors["color_text_secondary"]};
            }}
            """
            % ui_font_stack()
        )

        self._apply_icon()
        self.title_label.setFont(ui_font(10, QFont.DemiBold))

    def _apply_icon(self):
        if self.config.icon_path and os.path.exists(self.config.icon_path):
            icon = QIcon(self.config.icon_path)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(40, 40))
                return
        if self.config.icon_name:
            icon = svg_icon(self.config.icon_name)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(QSize(40, 40)))
                return
        self.icon_label.setText(self.config.icon_text.upper()[:3])
        self.icon_label.setFont(ui_font(12, QFont.Bold))

    def enterEvent(self, event: QEvent):
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.triggered.emit(self.config.key)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.triggered.emit(self.config.key)
            event.accept()
            return
        super().keyPressEvent(event)


class ResponsiveGrid(QWidget):
    """Responsive grid that ensures target number of columns according to width."""

    BREAKPOINTS: Sequence[Tuple[int, int]] = (
        (1160, 4),
        (860, 3),
        (640, 2),
        (0, 1),
    )

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(18)
        self._items: List[ConnectorCard] = []

    def add_item(self, card: ConnectorCard):
        self._items.append(card)
        self._layout.addWidget(card, len(self._items) - 1, 0)
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        width = max(self.width(), self.parentWidget().width() if self.parentWidget() else 0, 1)
        columns = 1
        for breakpoint, cols in self.BREAKPOINTS:
            if width >= breakpoint:
                columns = cols
                break

        visible_cards = [card for card in self._items if card.isVisible()]
        for idx, card in enumerate(visible_cards):
            row = idx // columns
            col = idx % columns
            self._layout.addWidget(card, row, col, Qt.AlignHCenter | Qt.AlignTop)

        for col in range(columns):
            self._layout.setColumnStretch(col, 0)


def _show_walker_modal_overlay(dialog: QDialog) -> Optional[QFrame]:
    parent = dialog.parentWidget()
    if parent is None:
        return None
    host = parent.window() or parent
    overlay = QFrame(host)
    overlay.setObjectName("WalkerModalOverlay")
    overlay.setAttribute(Qt.WA_StyledBackground, True)
    overlay.setStyleSheet("QFrame#WalkerModalOverlay { background-color: rgba(0, 0, 0, 128); }")
    overlay.setGeometry(host.rect())
    overlay.show()
    overlay.raise_()
    return overlay


def _center_dialog_on_parent(dialog: QDialog):
    parent = dialog.parentWidget()
    if parent is None:
        return
    host = parent.window() or parent
    try:
        center = host.mapToGlobal(host.rect().center())
        dialog.move(
            int(center.x() - (dialog.width() / 2)),
            int(center.y() - (dialog.height() / 2)),
        )
    except Exception:
        log_exception("falha opcional ignorada")


def _walker_database_dialog_flags():
    flags = Qt.Dialog
    if sys.platform.startswith("win"):
        flags |= Qt.FramelessWindowHint
    else:
        flags |= Qt.WindowCloseButtonHint
    return flags


class IntegrationPanel(QWidget):
    """Integration hub for loading external datasets."""

    def __init__(self, host, iface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.host = host
        self.iface = iface
        self.settings = QSettings()
        self._recents: List[Dict] = self._load_recents()

        stored_connections = connection_registry.saved_connections()
        if stored_connections:
            self._saved_connections = stored_connections
        else:
            self._saved_connections = self._load_saved_connections()
            if self._saved_connections:
                connection_registry.replace_saved_connections(self._saved_connections, persist=False)
        connection_registry.connectionsChanged.connect(self._on_registry_connections_changed)
        self._mirror_all_connections_to_browser()

        self._build_ui()
        self._register_shortcuts()
        self._populate_recents()
        self._apply_runtime_i18n()

    def _apply_runtime_i18n(self):
        try:
            _apply_i18n_widgets(self)
        except Exception:
            log_exception("falha opcional ignorada")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_runtime_i18n()
        QTimer.singleShot(0, self._refresh_connector_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._refresh_connector_layout)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 24, 0, 24)
        root.setSpacing(24)

        wrapper = QFrame(self)
        wrapper.setObjectName("integrationWrapper")
        wrapper.setProperty("card", True)
        wrapper.setMaximumWidth(16777215)
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(28, 28, 28, 28)
        wrapper_layout.setSpacing(20)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)

        self.title_label = QLabel("Adicionar dados ao seu relatório", wrapper)
        self.title_label.setProperty("cardTitle", True)
        self.title_label.setFont(ui_font(18, QFont.DemiBold))
        header_layout.addWidget(self.title_label)

        wrapper_layout.addLayout(header_layout)

        self.grid_widget = ResponsiveGrid(wrapper)
        wrapper_layout.addWidget(self.grid_widget)

        self._build_connectors()
        recents_frame = QFrame(wrapper)
        recents_frame.setObjectName("recentsFrame")
        recents_frame.setProperty("card", True)
        recents_layout = QVBoxLayout(recents_frame)
        recents_layout.setContentsMargins(18, 18, 18, 18)
        recents_layout.setSpacing(12)

        recents_header = QHBoxLayout()
        recents_header.setSpacing(6)
        recents_title = QLabel("Recentes", recents_frame)
        recents_title.setProperty("cardTitle", True)
        recents_title.setFont(ui_font(12, QFont.DemiBold))
        recents_header.addWidget(recents_title)
        recents_header.addStretch(1)

        self.clear_recent_btn = QPushButton("Limpar", recents_frame)
        self.clear_recent_btn.setProperty("role", "recentClear")
        self.clear_recent_btn.clicked.connect(self._clear_recents)
        recents_header.addWidget(self.clear_recent_btn)

        recents_layout.addLayout(recents_header)

        self.recents_list = QListWidget(recents_frame)
        self.recents_list.setAlternatingRowColors(False)
        self.recents_list.setSpacing(6)
        self.recents_list.itemActivated.connect(self._open_recent)
        recents_layout.addWidget(self.recents_list)

        self.recents_placeholder = QLabel("Nenhuma conexão recente…", recents_frame)
        self.recents_placeholder.setAlignment(Qt.AlignCenter)
        self.recents_placeholder.setProperty("role", "helper")
        recents_layout.addWidget(self.recents_placeholder)

        wrapper_layout.addWidget(recents_frame)

        root.addWidget(wrapper, 1)

        colors = DARK_COLORS if _is_dark_theme() else COLORS
        item_bg = "#172033" if _is_dark_theme() else "#F5F7FA"
        item_hover = "#1F2A3D" if _is_dark_theme() else "#EEF2F6"
        item_selected = "#24324A" if _is_dark_theme() else "#ECEFF3"
        clear_bg = "#F8FAFC" if _is_dark_theme() else "#111827"
        clear_hover = "#E2E8F0" if _is_dark_theme() else "#1F2937"
        clear_pressed = "#CBD5E1" if _is_dark_theme() else "#0B1220"
        clear_fg = "#0B1020" if _is_dark_theme() else "#FFFFFF"
        style = (
            """
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
                padding: 0px;
                font-family: %s;
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 8px 10px;
                margin: 0px;
                border: none;
                border-radius: 10px;
                background: __ITEM_BG__;
                color: __ITEM_FG__;
            }
            QListWidget::item:selected {
                background: __ITEM_SELECTED__;
                border: none;
                color: __ITEM_FG__;
            }
            QListWidget::item:hover {
                background: __ITEM_HOVER__;
            }
            QPushButton[role="recentClear"] {
                background: __CLEAR_BG__;
                color: __CLEAR_FG__;
                border: none;
                border-radius: 8px;
                min-width: 0px;
                padding: 4px 10px;
                font-family: %s;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton[role="recentClear"]:hover {
                background: __CLEAR_HOVER__;
            }
            QPushButton[role="recentClear"]:pressed {
                background: __CLEAR_PRESSED__;
            }
            QPushButton[role="recentClear"]:disabled {
                background: #D1D5DB;
                color: #FFFFFF;
            }
            """
            % (ui_font_stack(), ui_font_stack())
        )
        style = (
            style.replace("__ITEM_BG__", item_bg)
            .replace("__ITEM_FG__", colors["color_text_primary"])
            .replace("__ITEM_SELECTED__", item_selected)
            .replace("__ITEM_HOVER__", item_hover)
            .replace("__CLEAR_BG__", clear_bg)
            .replace("__CLEAR_FG__", clear_fg)
            .replace("__CLEAR_HOVER__", clear_hover)
            .replace("__CLEAR_PRESSED__", clear_pressed)
        )
        self.setStyleSheet(style)
        self._apply_panel_styles()
        self._apply_runtime_i18n()

    def _apply_panel_styles(self):
        colors = DARK_COLORS if _is_dark_theme() else COLORS
        item_bg = "#172033" if _is_dark_theme() else "#F5F7FA"
        item_hover = "#1F2A3D" if _is_dark_theme() else "#EEF2F6"
        item_selected = "#24324A" if _is_dark_theme() else "#ECEFF3"
        clear_bg = "#F8FAFC" if _is_dark_theme() else "#111827"
        clear_hover = "#E2E8F0" if _is_dark_theme() else "#1F2937"
        clear_pressed = "#CBD5E1" if _is_dark_theme() else "#0B1220"
        clear_fg = "#0B1020" if _is_dark_theme() else "#FFFFFF"
        style = (
            """
            QFrame#integrationWrapper {
                background: __PANEL_BG__;
                border: 1px solid __PANEL_BORDER__;
                border-radius: 12px;
            }
            QFrame#recentsFrame {
                background: __PANEL_BG__;
                border: 1px solid __PANEL_BORDER__;
                border-radius: 10px;
            }
            QLabel[cardTitle="true"] {
                background: transparent;
                border: none;
                color: __ITEM_FG__;
            }
            QLabel[role="helper"] {
                background: transparent;
                border: none;
                color: __HELPER_FG__;
            }
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
                padding: 0px;
                font-family: %s;
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 8px 10px;
                margin: 0px;
                border: none;
                border-radius: 10px;
                background: __ITEM_BG__;
                color: __ITEM_FG__;
            }
            QListWidget::item:selected {
                background: __ITEM_SELECTED__;
                border: none;
                color: __ITEM_FG__;
            }
            QListWidget::item:hover {
                background: __ITEM_HOVER__;
            }
            QPushButton[role="recentClear"] {
                background: __CLEAR_BG__;
                color: __CLEAR_FG__;
                border: none;
                border-radius: 8px;
                min-width: 0px;
                padding: 4px 10px;
                font-family: %s;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton[role="recentClear"]:hover {
                background: __CLEAR_HOVER__;
            }
            QPushButton[role="recentClear"]:pressed {
                background: __CLEAR_PRESSED__;
            }
            QPushButton[role="recentClear"]:disabled {
                background: __CLEAR_DISABLED_BG__;
                color: __CLEAR_DISABLED_FG__;
            }
            """
            % (ui_font_stack(), ui_font_stack())
        )
        panel_bg = "#1F2937" if _is_dark_theme() else colors["color_surface"]
        panel_border = "rgba(148, 163, 184, 0.22)" if _is_dark_theme() else colors["color_border"]
        clear_disabled_bg = "#334155" if _is_dark_theme() else "#D1D5DB"
        clear_disabled_fg = "#94A3B8" if _is_dark_theme() else "#FFFFFF"
        style = (
            style.replace("__ITEM_BG__", item_bg)
            .replace("__ITEM_FG__", colors["color_text_primary"])
            .replace("__HELPER_FG__", colors["color_text_secondary"])
            .replace("__ITEM_SELECTED__", item_selected)
            .replace("__ITEM_HOVER__", item_hover)
            .replace("__CLEAR_BG__", clear_bg)
            .replace("__CLEAR_FG__", clear_fg)
            .replace("__CLEAR_HOVER__", clear_hover)
            .replace("__CLEAR_PRESSED__", clear_pressed)
            .replace("__PANEL_BG__", panel_bg)
            .replace("__PANEL_BORDER__", panel_border)
            .replace("__CLEAR_DISABLED_BG__", clear_disabled_bg)
            .replace("__CLEAR_DISABLED_FG__", clear_disabled_fg)
        )
        self.setStyleSheet(style)
        for card in getattr(self, "_cards", {}).values():
            try:
                card._apply_styles()
            except Exception:
                log_exception("falha opcional ignorada")

    def _refresh_connector_layout(self):
        if hasattr(self, "grid_widget") and self.grid_widget is not None:
            self.grid_widget.updateGeometry()
            self.grid_widget._relayout()

    def _build_connectors(self):
        self._connectors: Dict[str, ConnectorConfig] = {}
        self._cards: Dict[str, ConnectorCard] = {}

        def register(config: ConnectorConfig):
            self._connectors[config.key] = config
            card = ConnectorCard(config, self.grid_widget)
            card.triggered.connect(self._on_card_triggered)
            self.grid_widget.add_item(card)
            self._cards[config.key] = card

        register(
            ConnectorConfig(
                key="excel",
                title="Excel",
                caption="Arquivos XLSX e XLS",
                microcopy="",
                accent="#CDEFE0",
                icon_text="X",
                handler=self._handle_excel,
                description="Planilhas tabulares com uma ou várias abas.",
                icon_path=os.path.join(_ICON_DIR, "source_excel.svg"),
                keywords="excel xlsx xls planilha arquivo tabela",
            )
        )
        register(
            ConnectorConfig(
                key="postgresql",
                title="PostgreSQL",
                caption="Tabelas e views",
                microcopy="",
                accent="#DCEBFF",
                icon_text="PG",
                handler=self._handle_postgresql_database,
                description="Servidor PostgreSQL muito comum em ambientes GIS e BI.",
                icon_path=os.path.join(_ICON_DIR, "source_postgresql.svg"),
                keywords="postgresql postgres servidor banco dados relacional",
            )
        )
        register(
            ConnectorConfig(
                key="postgis",
                title="PostGIS",
                caption="Camadas e tabelas espaciais",
                microcopy="",
                accent="#DDF6E8",
                icon_text="GIS",
                handler=self._handle_postgis_database,
                description="Acesso a bases geoespaciais corporativas com PostgreSQL/PostGIS.",
                icon_path=os.path.join(_ICON_DIR, "source_postgis.svg"),
                keywords="postgis espacial geometria servidor postgres qgis",
            )
        )
        register(
            ConnectorConfig(
                key="sqlserver",
                title="SQL Server",
                caption="Dados corporativos",
                microcopy="",
                accent="#E8EEFF",
                icon_text="SQL",
                handler=self._handle_sqlserver_database,
                description="Conector para ambientes Microsoft SQL Server.",
                icon_path=os.path.join(_ICON_DIR, "source_sqlserver.svg"),
                keywords="sql server mssql servidor banco microsoft",
            )
        )
        register(
            ConnectorConfig(
                key="oracle",
                title="Oracle",
                caption="Ambientes corporativos",
                microcopy="",
                accent="#FFF0E7",
                icon_text="ORA",
                handler=self._handle_oracle_database,
                description="Conector para bases Oracle quando o driver QOCI estiver disponível.",
                icon_path=os.path.join(_ICON_DIR, "source_oracle.svg"),
                keywords="oracle servidor banco corporativo",
            )
        )
        register(
            ConnectorConfig(
                key="mysql",
                title="MySQL",
                caption="Aplicações e serviços",
                microcopy="",
                accent="#EEF7FF",
                icon_text="MY",
                handler=self._handle_mysql_database,
                description="Conector para bases MySQL quando o driver QMYSQL estiver disponível.",
                icon_path=os.path.join(_ICON_DIR, "source_mysql.svg"),
                keywords="mysql mariadb servidor banco aplicacao",
            )
        )
        register(
            ConnectorConfig(
                key="gsheets",
                title="Google Sheets",
                caption="Planilhas web públicas",
                microcopy="",
                accent="#F4FFF6",
                icon_text="GS",
                handler=self._handle_google_sheets,
                description="Ideal para tabelas compartilhadas por URL pública.",
                icon_path=os.path.join(_ICON_DIR, "source_gsheets.svg"),
                keywords="google sheets web nuvem url publica planilha",
            )
        )
        register(
            ConnectorConfig(
                key="delimited",
                title="CSV / TXT",
                caption="Arquivos delimitados",
                microcopy="",
                accent="#FFF1D8",
                icon_text="CSV",
                handler=self._handle_delimited_file,
                description="Importe arquivos tabulares simples com pré-visualização.",
                icon_path=os.path.join(_ICON_DIR, "source_csv.svg"),
                keywords="csv txt delimitado separado virgula ponto e virgula texto",
            )
        )
        register(
            ConnectorConfig(
                key="geopackage",
                title="GeoPackage",
                caption="Camadas vetoriais",
                microcopy="",
                accent="#E8F6EC",
                icon_text="GPKG",
                handler=self._handle_geopackage,
                description="Abra dados vetoriais de um arquivo GeoPackage diretamente no plugin.",
                icon_path=os.path.join(_ICON_DIR, "source_geopackage.svg"),
                keywords="geopackage gpkg camada espacial geometria vetor qgis",
            )
        )
        register(
            ConnectorConfig(
                key="clipboard",
                title="Área de transferência",
                caption="Colar tabela copiada",
                microcopy="",
                accent="#F4ECFF",
                icon_text="CLP",
                handler=self._handle_clipboard,
                description="Útil para colar rapidamente dados copiados de outras ferramentas.",
                icon_path=os.path.join(_ICON_DIR, "source_clipboard.svg"),
                keywords="clipboard colar copiar area de transferencia rapido",
            )
        )

    def _register_shortcuts(self):
        shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        shortcut_open.activated.connect(self._handle_excel)
        shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        shortcut_refresh.activated.connect(self._populate_recents)

    def refresh_recents(self):
        """Public helper to refresh the recent connections list."""
        self._recents = self._load_recents()
        self._populate_recents()

    # ------------------------------------------------------------------ Recents
    def _load_recents(self) -> List[Dict]:
        raw = self.settings.value(RECENTS_SETTINGS_KEY, "")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[:8]
        except Exception:
            log_exception("falha opcional ignorada")
        return []

    def _save_recents(self):
        try:
            self.settings.setValue(RECENTS_SETTINGS_KEY, json.dumps(self._recents))
        except Exception:
            log_exception("falha opcional ignorada")

    def _populate_recents(self):
        self.recents_list.clear()
        if not self._recents:
            self.recents_placeholder.setVisible(True)
            self.recents_list.setVisible(False)
            self.clear_recent_btn.setEnabled(False)
            return

        self.recents_placeholder.setVisible(False)
        self.recents_list.setVisible(True)
        self.clear_recent_btn.setEnabled(True)

        for item in self._recents:
            qitem = QListWidgetItem()
            title = item.get("display_name") or item.get("source_name") or "Fonte sem nome"
            connector = item.get("connector", "-")
            ts = self._format_timestamp(item.get("timestamp"))
            qitem.setText(f"{title}\n{connector} • {ts}")
            qitem.setData(Qt.UserRole, item)
            self.recents_list.addItem(qitem)

        self._apply_runtime_i18n()

    def _store_recent(self, descriptor: Dict):
        descriptor = dict(descriptor)
        descriptor["timestamp"] = descriptor.get("timestamp") or QDateTime.currentDateTime().toString(Qt.ISODate)
        key = descriptor.get("id") or descriptor.get("source_path") or descriptor.get("display_name")

        self._recents = [item for item in self._recents if item.get("id") != key][:7]
        descriptor["id"] = key
        self._recents.insert(0, descriptor)
        self._save_recents()
        self._populate_recents()

    def _clear_recents(self):
        self._recents = []
        self._save_recents()
        self._populate_recents()

    def _open_recent(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        connector = data.get("connector")
        if connector == "Excel":
            path = data.get("source_path")
            sheet = data.get("sheet_name")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, "Recentes", "Arquivo não está mais disponível.")
                return
            df = self._read_excel(path, sheet)
            self._finalize_import(
                df,
                {
                    "connector": "Excel",
                    "display_name": os.path.basename(path),
                    "source_path": path,
                    "sheet_name": sheet,
                },
            )
        elif connector in ("CSV", "Parquet"):
            path = data.get("source_path")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, "Recentes", "Arquivo não está mais disponível.")
                return
            options = data.get("options") or {}
            df = self._read_delimited(path, options)
            if df is None:
                return
            meta = {
                "connector": connector,
                "display_name": os.path.basename(path),
                "source_path": path,
                "options": options,
            }
            self._finalize_import(df, meta)
        elif connector == "GeoPackage":
            path = data.get("source_path")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, "Recentes", "Arquivo não está mais disponível.")
                return
            self._import_geopackage_path(path)
        else:
            QMessageBox.information(
                self,
                "Recentes",
                "Conexões deste tipo precisam ser configuradas novamente.",
            )

    # ------------------------------------------------------------------ Saved connections
    def _load_saved_connections(self) -> List[Dict]:
        raw = self.settings.value(SAVED_CONNECTIONS_KEY, "")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            log_exception("falha opcional ignorada")
        return []

    def _save_connections(self):
        try:
            connection_registry.replace_saved_connections(self._saved_connections, persist=True)
        except Exception:
            try:
                secured = [secure_connection_payload(conn, name=str(conn.get("name") or "Summarizer")) for conn in self._saved_connections]
                self.settings.setValue(SAVED_CONNECTIONS_KEY, json.dumps(secured))
            except Exception:
                log_exception("falha opcional ignorada")

    def _on_registry_connections_changed(self):
        latest = connection_registry.saved_connections()
        if latest == self._saved_connections:
            return
        self._saved_connections = latest
        self._mirror_all_connections_to_browser()

    def _mirror_all_connections_to_browser(self):
        for conn in self._saved_connections:
            self._mirror_connection_in_browser(conn)

    def _mirror_connection_in_browser(self, connection: Optional[Dict]):
        if not connection:
            return
        driver = (connection.get("driver") or "").lower()
        if driver in ("postgresql", "postgres", "postgis"):
            prefix = "/PostgreSQL/connections"
            provider_key = "postgres"
        elif driver in ("sql server", "mssql"):
            prefix = "/MSSQL/connections"
            provider_key = "mssql"
        else:
            return
        conn_name = self._normalize_connection_name(
            connection.get("name")
            or f"{connection.get('database', 'Summarizer')}_{connection.get('user', '').strip() or 'user'}"
        )
        base = f"{prefix}/{conn_name}"
        secure_connection = secure_connection_payload(connection, name=conn_name)
        password = secure_connection.get("password", "")
        authcfg = str(secure_connection.get("authcfg") or "")
        save_password = bool(password) and not authcfg
        save_username = bool(connection.get("user", ""))
        settings = QSettings()
        settings.setValue(f"{prefix}/selected", conn_name)
        settings.setValue(f"{base}/service", secure_connection.get("service", ""))
        settings.setValue(f"{base}/host", secure_connection.get("host", ""))
        settings.setValue(f"{base}/port", secure_connection.get("port") or 0)
        settings.setValue(f"{base}/database", secure_connection.get("database", ""))
        settings.setValue(f"{base}/username", secure_connection.get("user", ""))
        if save_password:
            settings.setValue(f"{base}/password", password)
        else:
            settings.remove(f"{base}/password")
        settings.setValue(f"{base}/authcfg", authcfg)
        settings.setValue(f"{base}/sslmode", connection.get("sslmode", "SslDisable"))
        settings.setValue(f"{base}/publicOnly", False)
        settings.setValue(f"{base}/geometryColumnsOnly", False)
        settings.setValue(f"{base}/dontResolveType", False)
        settings.setValue(f"{base}/allowGeometrylessTables", True)
        settings.setValue(f"{base}/saveUsername", save_username)
        settings.setValue(f"{base}/savePassword", save_password)
        settings.setValue(f"{base}/estimatedMetadata", False)
        settings.setValue(f"{base}/projectsInDatabase", False)
        settings.setValue(f"{base}/metadataInDatabase", False)
        settings.sync()
        self._notify_browser_connections_changed(provider_key)

    def _notify_browser_connections_changed(self, provider_key: str):
        browser_model_getter = getattr(self.iface, "browserModel", None)
        if browser_model_getter is None:
            return
        model = browser_model_getter() if callable(browser_model_getter) else browser_model_getter
        if not model:
            return
        try:
            model.addRootItems()
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            model.connectionsChanged(provider_key)
            model.refresh()
        except Exception:
            log_exception("falha opcional ignorada")

    def _normalize_connection_name(self, raw: str) -> str:
        if not raw:
            return "Summarizer_Connection"
        sanitized = re.sub(r"[^0-9A-Za-z_]+", "_", raw).strip("_")
        return sanitized or "Summarizer_Connection"

    def open_connections_manager(self):
        dialog = SlimDialogBase(
            self, geometry_key="Summarizer/integration/savedConnections"
        )
        dialog.setWindowTitle(_rt("Gerenciar conexões salvas"))
        dialog.resize(520, 320)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        info = QLabel(
            _rt(
                "Conexões ficam salvas localmente neste computador utilizando QSettings. "
                "Remova entradas que não usa mais para manter suas credenciais seguras."
            ),
            dialog,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        list_widget = QListWidget(dialog)
        for conn in self._saved_connections:
            label = conn.get("name") or f"{conn.get('driver')} • {conn.get('database')}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, conn)
            list_widget.addItem(item)
        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)
        layout.addWidget(list_widget, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        remove_btn = button_box.addButton(_rt("Remover"), QDialogButtonBox.ActionRole)
        remove_btn.setEnabled(False)
        layout.addWidget(button_box)

        def _current_connection():
            item = list_widget.currentItem()
            if not item:
                return None
            return item.data(Qt.UserRole)

        def update_state_from_selection():
            conn = _current_connection()
            has_selection = conn is not None
            remove_btn.setEnabled(has_selection)

        def remove_selected():
            conn = _current_connection()
            if not conn:
                return
            self._saved_connections = [c for c in self._saved_connections if c != conn]
            row = list_widget.currentRow()
            item = list_widget.takeItem(row)
            del item
            self._save_connections()
            update_state_from_selection()

        list_widget.currentItemChanged.connect(lambda *_: update_state_from_selection())
        remove_btn.clicked.connect(remove_selected)
        button_box.rejected.connect(dialog.reject)

        update_state_from_selection()
        _apply_i18n_widgets(dialog)
        dialog.exec_()

    # ------------------------------------------------------------------ Connectors
    def _on_card_triggered(self, key: str):
        config = self._connectors.get(key)
        if config is None:
            return
        config.handler()

    def _handle_excel(self):
        dialog = ExcelImportDialog(
            parent=self,
            last_dir=self.settings.value("integ/last_excel_dir", ""),
        )
        if dialog.exec_() == QDialog.Accepted:
            df, metadata = dialog.result()
            if metadata.get("source_path"):
                self.settings.setValue(
                    "integ/last_excel_dir", os.path.dirname(metadata["source_path"])
                )
            self._finalize_import(df, metadata)

    def _open_database_dialog(self, preferred_driver: Optional[str] = None):
        dialog = DatabaseImportDialog(
            self,
            self._saved_connections,
            browser_sync_callback=self._mirror_connection_in_browser,
            preferred_driver=preferred_driver or "PostgreSQL",
        )
        if dialog.exec_() == QDialog.Accepted:
            df, metadata, connection_meta, session_connection = dialog.result()
            self._finalize_import(df, metadata)
            if session_connection:
                connection_registry.register_runtime_connection(session_connection)
                self._mirror_connection_in_browser(session_connection)
            if connection_meta:
                fingerprint = connection_meta.get("fingerprint")
                self._saved_connections = [
                    conn for conn in self._saved_connections if conn.get("fingerprint") != fingerprint
                ]
                self._saved_connections.insert(0, connection_meta)
                self._save_connections()
                self._mirror_connection_in_browser(connection_meta)
            fingerprint = (
                (connection_meta or {}).get("fingerprint")
                or (session_connection or {}).get("fingerprint")
            )

    def _handle_sql_database(self):
        self._open_database_dialog()

    def _handle_postgresql_database(self):
        self._open_database_dialog("PostgreSQL")

    def _handle_postgis_database(self):
        self._open_database_dialog("PostGIS")

    def _handle_sqlserver_database(self):
        self._open_database_dialog("SQL Server")

    def _handle_oracle_database(self):
        self._open_database_dialog("Oracle")

    def _handle_mysql_database(self):
        self._open_database_dialog("MySQL")

    def _handle_clipboard(self):
        dialog = ClipboardImportDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            df, metadata = dialog.result()
            self._finalize_import(df, metadata)

    def _handle_delimited_file(self):
        dialog = DelimitedFileDialog(
            parent=self,
            last_dir=self.settings.value("integ/last_csv_dir", ""),
        )
        if dialog.exec_() == QDialog.Accepted:
            df, metadata = dialog.result()
            if metadata.get("source_path"):
                self.settings.setValue(
                    "integ/last_csv_dir", os.path.dirname(metadata["source_path"])
                )
            self._finalize_import(df, metadata)

    def _handle_geopackage(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar GeoPackage",
            self.settings.value("integ/last_gpkg_dir", ""),
            "GeoPackage (*.gpkg)",
        )
        if not path:
            return
        self.settings.setValue("integ/last_gpkg_dir", os.path.dirname(path))
        self._import_geopackage_path(path)

    def _import_geopackage_path(self, path: str):
        layer = QgsVectorLayer(path, os.path.basename(path), "ogr")
        if not layer or not layer.isValid():
            QMessageBox.warning(self, "GeoPackage", "Não foi possível abrir o arquivo informado.")
            return

        columns = [field.name() for field in layer.fields()]
        rows = []
        for feature in layer.getFeatures():
            row = {columns[idx]: feature.attributes()[idx] for idx in range(len(columns))}
            if feature.hasGeometry():
                row["__geometry_wkt"] = feature.geometry().asWkt()
            rows.append(row)
        df = pd.DataFrame(rows)

        self._finalize_import(
            df,
            {
                "connector": "GeoPackage",
                "display_name": os.path.basename(path),
                "source_path": path,
                "record_count": len(df),
                "has_geometry": layer.isSpatial(),
            },
        )

    def _handle_google_sheets(self):
        dialog = GoogleSheetsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            df, metadata = dialog.result()
            self._finalize_import(df, metadata)

    def _show_extended_connectors(self):
        dialog = ExtendedConnectorsDialog(self._connectors, self)
        dialog.exec_()

    # ------------------------------------------------------------------ Helpers
    def _finalize_import(self, df: pd.DataFrame, metadata: Dict):
        if df is None or df.empty:
            QMessageBox.information(self, _rt("Conexão"), _rt("Nenhum dado encontrado para carregar."))
            return
        metadata = dict(metadata)
        metadata.setdefault("import_target", "project")
        metadata.setdefault("record_count", len(df))
        metadata.setdefault("timestamp", QDateTime.currentDateTime().toString(Qt.ISODate))
        try:
            descriptor = self.host.register_integration_dataframe(df, metadata)
            if descriptor and descriptor.get("layer_id"):
                self._store_recent(descriptor)
                self._toast_success(
                    _rt("Dados carregados: {count} linhas.", count=descriptor.get("record_count", len(df)))
                )
                return
            SlimMessageDialog(
                _rt("Conexão"),
                _rt("Os dados foram lidos, mas a camada não entrou no projeto do QGIS."),
                parent=self,
                accept_label=_rt("OK"),
                geometry_key="Summarizer/integration/importWarning",
            ).exec_()
        except Exception as exc:  # pragma: no cover - runtime safeguard
            QMessageBox.critical(self, _rt("Conexão"), _rt("Falha ao enviar dados para o plugin: {exc}", exc=exc))

    def _toast_success(self, message: str):
        bar = getattr(self.iface, "messageBar", None)
        if callable(bar):
            try:
                self.iface.messageBar().pushSuccess(_rt("Conexão"), message)
                return
            except Exception:
                log_exception("falha opcional ignorada")
        QMessageBox.information(self, _rt("Conexão"), message)

    def _format_timestamp(self, ts: Optional[str]) -> str:
        if not ts:
            return "-"
        try:
            dt = QDateTime.fromString(ts, Qt.ISODate)
            if dt.isValid():
                return dt.toString("dd/MM/yyyy HH:mm")
        except Exception:
            log_exception("falha opcional ignorada")
        return ts

    # Excel helper used by recents
    def _read_excel(self, path: str, sheet: Optional[str]) -> pd.DataFrame:
        try:
            return pd.read_excel(path, sheet_name=sheet)
        except Exception as exc:
            QMessageBox.warning(self, "Excel", f"Não foi possível ler o arquivo: {exc}")
            return pd.DataFrame()

    def _read_delimited(self, path: str, options: Dict) -> Optional[pd.DataFrame]:
        try:
            if path.lower().endswith(".parquet") or options.get("format") == "Parquet":
                return pd.read_parquet(path)
            delimiter = options.get("delimiter")
            encoding = options.get("encoding") or "utf-8"
            if delimiter == "tab":
                delimiter = "\t"
            elif delimiter == "auto" or not delimiter:
                delimiter = self._detect_delimiter(path, encoding)
            return pd.read_csv(path, sep=delimiter, encoding=encoding)
        except Exception as exc:
            QMessageBox.warning(self, "Importar", f"Não foi possível ler o arquivo: {exc}")
            return None

    def _detect_delimiter(self, path: str, encoding: str) -> str:
        try:
            with open(path, "r", encoding=encoding, errors="ignore") as handle:
                sample = handle.readline()
        except Exception:
            return ","
        if "\t" in sample:
            return "\t"
        if sample.count(";") >= sample.count(","):
            return ";"
        return ","


# ---------------------------------------------------------------------- Dialogs
class ExcelImportDialog(SlimDialogBase):
    def __init__(self, parent: QWidget, last_dir: str):
        super().__init__(parent, geometry_key="Summarizer/integration/excelDialog")
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self.last_dir = last_dir or ""
        self.setWindowTitle("Importar dados do Excel")
        self.resize(640, 540)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText("Selecione o arquivo Excel…")
        browse_btn = QPushButton(_rt("Procurar…"), self)
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(browse_btn, 0)
        layout.addLayout(row)

        self.sheet_combo = QComboBox(self)
        self.sheet_combo.setEnabled(False)
        layout.addWidget(self.sheet_combo)

        self.preview_table = QTableWidget(self)
        layout.addWidget(self.preview_table, 1)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        _apply_walker_dialog_buttons(primary=[load_btn], secondary=[preview_btn, cancel_btn, browse_btn])
        layout.addWidget(buttons)

        preview_btn.clicked.connect(self._preview)
        load_btn.clicked.connect(self._load)
        cancel_btn.clicked.connect(self.reject)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            _rt("Selecionar arquivo Excel"),
            self.last_dir,
            "Excel (*.xlsx *.xls);;Todos (*.*)",
        )
        if path:
            self.path_edit.setText(path)
            self._populate_sheets(path)

    def _populate_sheets(self, path: str):
        try:
            excel = pd.ExcelFile(path)
        except Exception as exc:
            QMessageBox.warning(self, "Excel", f"Não foi possível abrir o arquivo: {exc}")
            return
        self.sheet_combo.clear()
        self.sheet_combo.addItems(excel.sheet_names)
        self.sheet_combo.setEnabled(True)

    def _preview(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.information(self, "Excel", "Selecione um arquivo.")
            return
        sheet = self.sheet_combo.currentText() or None
        try:
            df = pd.read_excel(path, sheet_name=sheet, nrows=PREVIEW_ROW_LIMIT)
        except Exception as exc:
            QMessageBox.warning(self, "Excel", f"Falha na pré-visualização: {exc}")
            return
        self._fill_preview(df)

    def _fill_preview(self, df: pd.DataFrame):
        self.preview_table.clear()
        self.preview_table.setRowCount(min(PREVIEW_ROW_LIMIT, len(df.index)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(min(PREVIEW_ROW_LIMIT, len(df.index))):
            for c, column in enumerate(df.columns):
                value = df.iloc[r][column]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.preview_table.resizeColumnsToContents()

    def _load(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Excel", "Selecione um arquivo.")
            return
        sheet = self.sheet_combo.currentText() or None
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception as exc:
            QMessageBox.critical(self, "Excel", f"Erro ao carregar: {exc}")
            return
        self._df = df
        self._metadata = {
            "connector": "Excel",
            "display_name": os.path.basename(path),
            "source_path": path,
            "sheet_name": sheet,
        }
        self.accept()

    def result(self) -> Tuple[pd.DataFrame, Dict]:
        return self._df, self._metadata


class DelimitedFileDialog(SlimDialogBase):
    def __init__(self, parent: QWidget, last_dir: str):
        super().__init__(parent, geometry_key="Summarizer/integration/delimitedDialog")
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self.last_dir = last_dir or ""
        self.setWindowTitle(_rt("Importar arquivo CSV/Parquet"))
        self.resize(640, 540)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText(_rt("Selecione o arquivo CSV ou Parquet…"))
        browse_btn = QPushButton(_rt("Procurar…"), self)
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(browse_btn, 0)
        layout.addLayout(row)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel(_rt("Delimitador:"), self))
        self.delimiter_combo = QComboBox(self)
        self.delimiter_combo.addItems([_rt("Automático"), ";", ",", "Tab"])
        options_row.addWidget(self.delimiter_combo)
        options_row.addWidget(QLabel(_rt("Codificação:"), self))
        self.encoding_combo = QComboBox(self)
        self.encoding_combo.addItems(["UTF-8", "ISO-8859-1", "Windows-1252"])
        options_row.addWidget(self.encoding_combo)
        layout.addLayout(options_row)

        self.preview_table = QTableWidget(self)
        layout.addWidget(self.preview_table, 1)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        _apply_walker_dialog_buttons(primary=[load_btn], secondary=[preview_btn, cancel_btn, browse_btn])
        layout.addWidget(buttons)

        preview_btn.clicked.connect(self._preview)
        load_btn.clicked.connect(self._load)
        cancel_btn.clicked.connect(self.reject)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            _rt("Selecionar arquivo"),
            self.last_dir,
            _rt("Arquivos de dados (*.csv *.txt *.parquet);;CSV (*.csv);;Parquet (*.parquet);;Todos (*.*)"),
        )
        if path:
            self.path_edit.setText(path)

    def _preview(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.information(self, _rt("Importar"), _rt("Selecione o arquivo."))
            return
        try:
            df = self._read_file(path, preview=True)
        except Exception as exc:
            QMessageBox.warning(self, _rt("Importar"), _rt("Falha ao pré-visualizar: {exc}", exc=exc))
            return
        self._fill_preview(df)

    def _load(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, _rt("Importar"), _rt("Selecione o arquivo."))
            return
        try:
            df = self._read_file(path, preview=False)
        except Exception as exc:
            QMessageBox.critical(self, _rt("Importar"), _rt("Falha ao carregar: {exc}", exc=exc))
            return

        delimiter = self.delimiter_combo.currentText()
        if delimiter == "Automático":
            delimiter_key = "auto"
        elif delimiter == "Tab":
            delimiter_key = "tab"
        else:
            delimiter_key = delimiter

        self._df = df
        self._metadata = {
            "connector": "CSV" if path.lower().endswith(".csv") else "Parquet",
            "display_name": os.path.basename(path),
            "source_path": path,
            "options": {
                "delimiter": delimiter_key,
                "encoding": self.encoding_combo.currentText(),
                "format": "Parquet" if path.lower().endswith(".parquet") else "CSV",
            },
        }
        self.accept()

    def _read_file(self, path: str, preview: bool) -> pd.DataFrame:
        if path.lower().endswith(".parquet"):
            df = pd.read_parquet(path)
        else:
            delimiter = self.delimiter_combo.currentText()
            if delimiter == "Automático":
                delimiter = self._detect_delimiter(path)
            elif delimiter == "Tab":
                delimiter = "\t"
            encoding = self.encoding_combo.currentText()
            df = pd.read_csv(path, sep=delimiter, encoding=encoding)
        if preview:
            return df.head(PREVIEW_ROW_LIMIT)
        return df

    def _detect_delimiter(self, path: str) -> str:
        encoding = self.encoding_combo.currentText()
        try:
            with open(path, "r", encoding=encoding, errors="ignore") as handle:
                sample = handle.readline()
        except Exception:
            return ","
        if "\t" in sample:
            return "\t"
        if sample.count(";") >= sample.count(","):
            return ";"
        return ","

    def _fill_preview(self, df: pd.DataFrame):
        self.preview_table.clear()
        self.preview_table.setRowCount(min(PREVIEW_ROW_LIMIT, len(df.index)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(min(PREVIEW_ROW_LIMIT, len(df.index))):
            for c, column in enumerate(df.columns):
                value = df.iloc[r][column]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.preview_table.resizeColumnsToContents()

    def result(self) -> Tuple[pd.DataFrame, Dict]:
        return self._df, self._metadata


class ClipboardImportDialog(SlimDialogBase):
    def __init__(self, parent: QWidget):
        super().__init__(parent, geometry_key="Summarizer/integration/clipboardDialog")
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self.setWindowTitle(_rt("Colar dados"))
        self.resize(600, 480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info = QLabel(
            _rt(
                "Cole dados tabulares abaixo. Detectamos automaticamente se o separador é tabulação, vírgula ou ponto e vírgula."
            ),
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.text_edit = QPlainTextEdit(self)
        layout.addWidget(self.text_edit, 1)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        _apply_walker_dialog_buttons(primary=[load_btn], secondary=[preview_btn, cancel_btn])
        layout.addWidget(buttons)

        self.preview_table = QTableWidget(self)
        layout.addWidget(self.preview_table, 1)

        preview_btn.clicked.connect(self._preview)
        load_btn.clicked.connect(self._load)
        cancel_btn.clicked.connect(self.reject)

    def _preview(self):
        df = self._parse_text()
        if df is None:
            return
        self._fill_preview(df.head(PREVIEW_ROW_LIMIT))

    def _load(self):
        df = self._parse_text()
        if df is None:
            return
        self._df = df
        self._metadata = {
            "connector": "Clipboard",
            "display_name": "Dados colados",
            "record_count": len(df),
        }
        self.accept()

    def _parse_text(self) -> Optional[pd.DataFrame]:
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, _rt("Colar"), _rt("Nenhum dado encontrado."))
            return None
        delimiter = self._detect_delimiter(text)
        try:
            from io import StringIO

            df = pd.read_csv(StringIO(text), sep=delimiter)
        except Exception as exc:
            QMessageBox.warning(self, _rt("Colar"), _rt("Não foi possível interpretar os dados: {exc}", exc=exc))
            return None
        return df

    def _detect_delimiter(self, text: str) -> str:
        first_line = text.splitlines()[0]
        if "\t" in first_line:
            return "\t"
        if first_line.count(";") >= first_line.count(","):
            return ";"
        return ","

    def _fill_preview(self, df: pd.DataFrame):
        self.preview_table.clear()
        self.preview_table.setRowCount(min(PREVIEW_ROW_LIMIT, len(df.index)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(min(PREVIEW_ROW_LIMIT, len(df.index))):
            for c, column in enumerate(df.columns):
                value = df.iloc[r][column]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.preview_table.resizeColumnsToContents()

    def result(self) -> Tuple[pd.DataFrame, Dict]:
        return self._df, self._metadata


class _WalkerSslModePicker(QFrame):
    """Small in-dialog dropdown used to avoid native combo popup corners."""

    changed = pyqtSignal(str)
    _WIDTH = 90
    _POPUP_WIDTH = 116

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WalkerSslPicker")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(self._WIDTH, 36)
        self._options = ["Disable", "Prefer", "Require"]
        self._current = "Disable"
        self._popup: Optional[QFrame] = None
        self._items: List[QToolButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.button = QToolButton(self)
        self.button.setObjectName("WalkerSslButton")
        self.button.setText(self._current)
        self.button.setIcon(self._chevron_icon())
        self.button.setIconSize(QSize(12, 12))
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setLayoutDirection(Qt.RightToLeft)
        self.button.clicked.connect(self._toggle_popup)
        layout.addWidget(self.button, 1)

    def currentText(self) -> str:
        return self._current

    def setCurrentText(self, text: str):
        value = str(text or "").strip()
        if value not in self._options:
            return
        self._current = value
        self.button.setText(self._current)
        self._refresh_items()
        self.changed.emit(value)

    def hidePopup(self):
        if self._popup is not None:
            self._popup.hide()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeEventFilter(self)
            except Exception:
                log_exception("falha opcional ignorada")

    def eventFilter(self, watched, event):
        popup = self._popup
        if popup is None or not popup.isVisible():
            return super().eventFilter(watched, event)
        if event.type() == QEvent.MouseButtonPress:
            try:
                point = event.globalPos()
                picker_rect = self.rect()
                picker_top_left = self.mapToGlobal(picker_rect.topLeft())
                picker_rect.moveTopLeft(picker_top_left)
                popup_rect = popup.rect()
                popup_top_left = popup.mapToGlobal(popup_rect.topLeft())
                popup_rect.moveTopLeft(popup_top_left)
                if not picker_rect.contains(point) and not popup_rect.contains(point):
                    self.hidePopup()
            except Exception:
                log_exception("falha opcional ignorada")
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hidePopup()
            return True
        return super().eventFilter(watched, event)

    def _chevron_icon(self) -> QIcon:
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#6B7280"), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(3, 5, 6, 8)
        painter.drawLine(6, 8, 9, 5)
        painter.end()
        return QIcon(pixmap)

    def _toggle_popup(self):
        popup = self._ensure_popup()
        if popup.isVisible():
            self.hidePopup()
            return
        self._show_popup()

    def _ensure_popup(self) -> QFrame:
        if self._popup is not None:
            return self._popup
        parent = self.window() or self.parentWidget() or self
        popup = QFrame(parent)
        popup.setObjectName("WalkerSslDropdown")
        popup.setAttribute(Qt.WA_StyledBackground, True)
        popup.setFixedSize(self._POPUP_WIDTH, 92)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        for option in self._options:
            item = QToolButton(popup)
            item.setObjectName("WalkerSslDropdownItem")
            item.setText(option)
            item.setCheckable(True)
            item.clicked.connect(lambda checked=False, value=option: self._select(value))
            layout.addWidget(item)
            self._items.append(item)
        popup.hide()
        self._popup = popup
        self._refresh_items()
        return popup

    def _show_popup(self):
        popup = self._ensure_popup()
        parent = popup.parentWidget()
        if parent is None:
            return
        point = self.mapToGlobal(self.rect().bottomLeft())
        point.setY(point.y() + 4)
        local = parent.mapFromGlobal(point)
        popup.move(local)
        popup.raise_()
        popup.show()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _select(self, value: str):
        self.setCurrentText(value)
        self.hidePopup()

    def _refresh_items(self):
        for item in self._items:
            is_current = item.text() == self._current
            item.setChecked(is_current)
            item.setProperty("current", is_current)
            item.style().unpolish(item)
            item.style().polish(item)


class _WalkerDatabaseTitleIcon(QWidget):
    """Database icon with a connection status dot."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("WalkerDatabaseTitleIcon")
        self.setFixedSize(24, 22)
        self._connected = False

    def setConnected(self, connected: bool):  # noqa: N802 - Qt naming style
        self._connected = bool(connected)
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#111827"), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        top = QRectF(2.5, 3.0, 12.0, 5.6)
        body = QRectF(2.5, 3.0, 12.0, 14.5)
        painter.drawEllipse(top)
        painter.drawLine(QPointF(body.left(), top.center().y()), QPointF(body.left(), body.bottom() - 2.7))
        painter.drawLine(QPointF(body.right(), top.center().y()), QPointF(body.right(), body.bottom() - 2.7))
        painter.drawArc(QRectF(body.left(), body.bottom() - 5.4, body.width(), 5.4), 180 * 16, 180 * 16)

        if self._connected:
            painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
            painter.setBrush(QColor("#22C55E"))
            painter.drawEllipse(QRectF(14.0, 12.0, 8.0, 8.0))


class DatabaseImportDialog(SlimDialogBase):
    def __init__(
        self,
        parent: QWidget,
        saved_connections: List[Dict],
        browser_sync_callback: Optional[Callable[[Dict], None]] = None,
        preferred_driver: Optional[str] = None,
    ):
        super().__init__(parent, geometry_key="Summarizer/integration/databaseDialog")
        self._walker_overlay: Optional[QFrame] = None
        self.settings = QSettings()
        self.saved_connections = saved_connections or []
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self._connection_meta: Optional[Dict] = None
        self._session_connection: Optional[Dict] = None
        self._browser_sync_callback = browser_sync_callback
        self._last_params: Dict[str, Dict] = self._load_last_params()
        self._suspend_defaults = False
        self._preferred_driver = preferred_driver or "PostgreSQL"
        self._active_saved_fingerprint = ""
        self.setWindowTitle(_rt("Connect to PostgreSQL"))
        self.setObjectName("WalkerDatabaseDialog")
        self.setWindowFlags(_walker_database_dialog_flags())
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(500, 430)
        self._build_ui()
        harmonize_widget_fonts(self)
        self._apply_runtime_i18n()
        self._apply_walker_dialog_style()
        apply_windows_rounded_corners(self)

    def _apply_runtime_i18n(self):
        try:
            _apply_i18n_widgets(self)
        except Exception:
            log_exception("falha opcional ignorada")

    def showEvent(self, event):
        super().showEvent(event)
        self._hide_walker_overlay()
        self._walker_overlay = _show_walker_modal_overlay(self)
        self.raise_()
        _center_dialog_on_parent(self)
        harmonize_widget_fonts(self)
        self._apply_runtime_i18n()
        self._apply_walker_dialog_style()
        apply_windows_rounded_corners(self)
        QTimer.singleShot(0, lambda: apply_windows_rounded_corners(self))
        QTimer.singleShot(0, self._ensure_walker_dialog_visible)

    def closeEvent(self, event):
        self._hide_walker_overlay()
        super().closeEvent(event)

    def hideEvent(self, event):
        self._hide_walker_overlay()
        super().hideEvent(event)

    def _hide_walker_overlay(self):
        overlay = getattr(self, "_walker_overlay", None)
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
            self._walker_overlay = None

    def _ensure_walker_dialog_visible(self):
        if not self.isVisible():
            return
        try:
            self.setWindowOpacity(1.0)
            self.raise_()
            self.activateWindow()
            panel = getattr(self, "_walker_panel", None)
            if panel is not None:
                panel.show()
                panel.raise_()
                panel.update()
            self.update()
        except Exception:
            log_exception("falha opcional ignorada")

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        panel = QFrame(self)
        panel.setObjectName("WalkerDatabasePanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        self._walker_panel = panel
        root_layout.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(8)

        self.connection_status_icon = _WalkerDatabaseTitleIcon(self)
        header.addWidget(self.connection_status_icon, 0, Qt.AlignVCenter)

        self.title_label = QLabel(_rt("Connect to PostgreSQL"), self)
        self.title_label.setObjectName("WalkerDatabaseTitle")
        header.addWidget(self.title_label, 1, Qt.AlignVCenter)

        close_btn = QToolButton(self)
        close_btn.setObjectName("WalkerDialogCloseButton")
        close_btn.setText("×")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignTop)
        layout.addLayout(header)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        def _field_label(text: str) -> QLabel:
            label = QLabel(_rt(text).rstrip(":"), self)
            label.setObjectName("WalkerDatabaseLabel")
            return label

        self.driver_combo = QComboBox(self)
        self.driver_combo.addItems(["PostgreSQL", "PostGIS", "SQL Server", "Oracle", "MySQL"])
        if self._preferred_driver in {"PostgreSQL", "PostGIS", "SQL Server", "Oracle", "MySQL"}:
            self.driver_combo.setCurrentText(self._preferred_driver)
        self.driver_combo.currentTextChanged.connect(self._on_driver_changed)
        self.driver_combo.setVisible(False)

        self.host_edit = QLineEdit(self)
        self.host_edit.setPlaceholderText("servidor.empresa.com")
        self.host_label = _field_label("Host")
        form.addWidget(self.host_label, 0, 0)
        form.addWidget(self.host_edit, 1, 0, 1, 2)

        self.port_edit = QLineEdit(self)
        self.port_edit.setPlaceholderText("5432 ou 1433…")
        self.port_label = _field_label("Port")
        form.addWidget(self.port_label, 0, 2)
        form.addWidget(self.port_edit, 1, 2, 1, 2)

        self.database_edit = QLineEdit(self)
        self.database_label = _field_label("Database")
        form.addWidget(self.database_label, 2, 0)
        form.addWidget(self.database_edit, 3, 0, 1, 4)

        self.user_edit = QLineEdit(self)
        self.user_label = _field_label("Username")
        form.addWidget(self.user_label, 4, 0)
        form.addWidget(self.user_edit, 5, 0, 1, 2)

        self.password_edit = QLineEdit(self)
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_label = _field_label("Password")
        form.addWidget(self.password_label, 4, 2)
        form.addWidget(self.password_edit, 5, 2, 1, 2)

        self.ssl_label = _field_label("SSL Mode")
        self.ssl_combo = _WalkerSslModePicker(self)
        form.addWidget(self.ssl_label, 6, 0)
        form.addWidget(self.ssl_combo, 7, 0)

        self.use_ssl_box = QCheckBox(_rt("Use SSL"), self)
        self.use_ssl_box.setObjectName("WalkerUseSslCheck")
        form.addWidget(self.use_ssl_box, 7, 0)

        self.remember_box = QCheckBox(_rt("Salvar conexão"), self)
        self.remember_box.setObjectName("WalkerSaveConnectionCheck")
        form.addWidget(self.remember_box, 7, 1, Qt.AlignVCenter)

        self.delete_connection_btn = QPushButton(_rt("Excluir conexão"), self)
        self.delete_connection_btn.setObjectName("WalkerDeleteConnectionButton")
        self.delete_connection_btn.clicked.connect(self._delete_saved_connection)
        self.delete_connection_btn.setVisible(False)
        form.addWidget(self.delete_connection_btn, 7, 2, 1, 2, Qt.AlignRight | Qt.AlignVCenter)

        for field in (self.host_edit, self.port_edit, self.database_edit, self.user_edit, self.password_edit):
            field.textEdited.connect(lambda *_: self._set_connection_status(False))
        self.ssl_combo.changed.connect(lambda *_: self._set_connection_status(False))
        self.use_ssl_box.toggled.connect(lambda *_: self._set_connection_status(False))

        layout.addLayout(form)

        saved_row = QHBoxLayout()
        self.saved_combo = QComboBox(self)
        self.saved_combo.addItem(_rt("Carregar conexão salva…"))
        for item in self.saved_connections:
            label = item.get("name") or f"{item.get('driver')} • {item.get('database')}"
            self.saved_combo.addItem(label, item)
        self.saved_combo.currentIndexChanged.connect(self._apply_saved)
        saved_row.addWidget(self.saved_combo, 1)

        self.test_btn = QPushButton(_rt("Testar conexão"), self)
        self.test_btn.clicked.connect(self._test_connection)
        saved_row.addWidget(self.test_btn, 0)

        self.browser_sync_btn = QPushButton(_rt("Mostrar no Navegador"), self)
        self.browser_sync_btn.setToolTip(_rt("Força o nó 'Summarizer' a exibir esta conexão."))
        self.browser_sync_btn.clicked.connect(self._force_browser_sync)
        saved_row.addWidget(self.browser_sync_btn, 0)
        self.saved_combo.setVisible(False)
        self.test_btn.setVisible(False)
        self.browser_sync_btn.setVisible(False)
        layout.addLayout(saved_row)

        self.tables_combo = QComboBox(self)
        self.tables_combo.setPlaceholderText(_rt("Selecione uma tabela…"))
        self.tables_combo.setVisible(False)
        layout.addWidget(self.tables_combo)

        self.preview_table = QTableWidget(self)
        self.preview_table.setMinimumHeight(84)
        self.preview_table.setVisible(False)
        layout.addWidget(self.preview_table, 1)
        layout.addStretch(1)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ActionRole)
        self.load_btn = buttons.addButton(_rt("Connect"), QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        cancel_btn.setText(_rt("Cancel"))
        _apply_walker_dialog_buttons(
            primary=[self.load_btn],
            secondary=[preview_btn, cancel_btn, self.test_btn, self.browser_sync_btn],
        )
        preview_btn.setVisible(False)
        buttons.setObjectName("WalkerDatabaseButtons")
        layout.addWidget(buttons)

        preview_btn.clicked.connect(lambda: self._retrieve(preview=True))
        self.load_btn.clicked.connect(lambda: self._retrieve(preview=False))
        cancel_btn.clicked.connect(self.reject)

        self._apply_driver_defaults()
        self._apply_driver_ui()
        self._apply_initial_saved_connection()

    def _apply_walker_dialog_style(self):
        self.setStyleSheet(
            """
            QDialog#WalkerDatabaseDialog {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
            }
            QFrame#WalkerDatabasePanel {
                background: #FFFFFF;
                border: none;
                border-radius: 14px;
            }
            QLabel#WalkerDatabaseTitle {
                color: #111827;
                font-size: 17px;
                font-weight: 600;
            }
            QLabel#WalkerDatabaseTitleIcon {
                background: transparent;
            }
            QLabel#WalkerDatabaseLabel {
                color: #1F2937;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
            QLineEdit,
            QComboBox {
                min-height: 34px;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 0 12px;
                background: #FFFFFF;
                color: #111827;
                font-size: 12px;
            }
            QLineEdit:focus,
            QComboBox:focus {
                border: 2px solid #9CA3AF;
                padding: 0 11px;
                background: #FFFFFF;
            }
            QComboBox::drop-down {
                width: 26px;
                border: none;
            }
            QFrame#WalkerSslPicker {
                min-width: 90px;
                max-width: 90px;
                min-height: 34px;
                max-height: 34px;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #FFFFFF;
            }
            QFrame#WalkerSslPicker:focus {
                border: 2px solid #9CA3AF;
            }
            QToolButton#WalkerSslButton {
                border: none;
                background: #FFFFFF;
                color: #111827;
                font-size: 12px;
                font-weight: 400;
                padding: 0 8px 0 10px;
                text-align: left;
            }
            QToolButton#WalkerSslButton:hover,
            QToolButton#WalkerSslButton:pressed {
                background: #FFFFFF;
            }
            QFrame#WalkerSslDropdown {
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                background: #FFFFFF;
            }
            QCheckBox#WalkerUseSslCheck,
            QCheckBox#WalkerSaveConnectionCheck {
                color: #111827;
                font-size: 12px;
                font-weight: 400;
                background: transparent;
            }
            QCheckBox#WalkerUseSslCheck::indicator,
            QCheckBox#WalkerSaveConnectionCheck::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #9CA3AF;
                border-radius: 3px;
                background: #FFFFFF;
            }
            QCheckBox#WalkerUseSslCheck::indicator:checked,
            QCheckBox#WalkerSaveConnectionCheck::indicator:checked {
                background: #111111;
                border-color: #111111;
            }
            QToolButton#WalkerSslDropdownItem {
                min-height: 28px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #111827;
                font-size: 12px;
                font-weight: 400;
                padding: 0 10px;
                text-align: left;
            }
            QToolButton#WalkerSslDropdownItem:hover,
            QToolButton#WalkerSslDropdownItem[current="true"] {
                background: #F3F4F6;
            }
            QTableWidget {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background: #FFFFFF;
                gridline-color: #EEF2F7;
                color: #111827;
                font-size: 11px;
            }
            QPushButton {
                min-width: 82px;
                min-height: 34px;
                border-radius: 7px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#SlimPrimaryButton {
                background: #111111;
                border: 1px solid #111111;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton#SlimPrimaryButton:hover {
                background: #262626;
                border-color: #262626;
            }
            QPushButton#SlimSecondaryButton {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                color: #111827;
            }
            QPushButton#SlimSecondaryButton:hover {
                background: #F9FAFB;
                border-color: #D1D5DB;
            }
            QPushButton#WalkerDeleteConnectionButton {
                min-width: 100px;
                min-height: 26px;
                border-radius: 7px;
                padding: 0 10px;
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                color: #991B1B;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#WalkerDeleteConnectionButton:hover {
                background: #FEF2F2;
                border-color: #FCA5A5;
            }
            QToolButton#WalkerDialogCloseButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                border: none;
                border-radius: 6px;
                background: transparent;
                color: #6B7280;
                font-size: 16px;
            }
            QToolButton#WalkerDialogCloseButton:hover {
                background: #F3F4F6;
                color: #111827;
            }
            """
        )

    def _apply_initial_saved_connection(self):
        current_driver = self.driver_combo.currentText() or self._preferred_driver
        for index in range(1, self.saved_combo.count()):
            data = self.saved_combo.itemData(index)
            if not isinstance(data, dict):
                continue
            saved_driver = str(data.get("source_driver") or data.get("driver") or "")
            if saved_driver == current_driver or (saved_driver == "PostgreSQL" and current_driver == "PostGIS"):
                self.saved_combo.setCurrentIndex(index)
                self._apply_saved(index)
                return

    def _apply_saved(self, index: int):
        if index <= 0:
            return
        data = self.saved_combo.itemData(index)
        if not isinstance(data, dict):
            return
        data = reveal_connection_payload(data)
        self._active_saved_fingerprint = str(data.get("fingerprint") or "")
        self._suspend_defaults = True
        try:
            self.driver_combo.setCurrentText(data.get("driver", "PostgreSQL"))
            self.host_edit.setText(data.get("host", ""))
            self.port_edit.setText(str(data.get("port", "")))
            self.database_edit.setText(data.get("database", ""))
            self.user_edit.setText(data.get("user", ""))
            self.password_edit.setText(data.get("password", ""))
        finally:
            self._suspend_defaults = False
        self.remember_box.setChecked(True)
        self.delete_connection_btn.setVisible(bool(self._active_saved_fingerprint))
        self._refresh_connection_status_from_fields()

    def _delete_saved_connection(self):
        fingerprint = str(self._active_saved_fingerprint or "").strip()
        if not fingerprint:
            return
        confirm = QMessageBox.question(
            self,
            _rt("Excluir conexão"),
            _rt("Excluir esta conexão salva?"),
        )
        if confirm != QMessageBox.Yes:
            return
        _forget_connected_database_params(self._params())
        connection_registry.remove_connection(fingerprint)
        self.saved_connections = [
            conn for conn in self.saved_connections if str(conn.get("fingerprint") or "") != fingerprint
        ]
        for index in range(self.saved_combo.count() - 1, 0, -1):
            data = self.saved_combo.itemData(index)
            if isinstance(data, dict) and str(data.get("fingerprint") or "") == fingerprint:
                self.saved_combo.removeItem(index)
        self._active_saved_fingerprint = ""
        self.saved_combo.setCurrentIndex(0)
        self.remember_box.setChecked(False)
        self.delete_connection_btn.setVisible(False)
        self.tables_combo.clear()
        self.tables_combo.setVisible(False)
        if hasattr(self, "load_btn"):
            self.load_btn.setText(_rt("Connect"))
        self._set_connection_status(False)
        self._notify_parent_database_status()

    def _notify_parent_database_status(self):
        widget = self.parentWidget()
        while widget is not None:
            refresh = getattr(widget, "_refresh_model_database_status", None)
            if callable(refresh):
                refresh()
                return
            widget = widget.parentWidget()

    def _set_connection_status(self, connected: bool):
        icon = getattr(self, "connection_status_icon", None)
        if icon is not None:
            icon.setConnected(connected)

    def _connection_status_key(self, params: Optional[Dict] = None) -> str:
        return _connection_status_key_from_params(params or self._params())

    def _remember_connected_connection(self, params: Dict, tables: Optional[List[str]] = None):
        key = self._connection_status_key(params)
        _mark_connected_database_params(params, tables)
        self._set_connection_status(bool(key))

    def _refresh_connection_status_from_fields(self):
        key = self._connection_status_key()
        connected = bool(key and key in _CONNECTED_DATABASE_KEYS)
        self._set_connection_status(connected)
        if connected:
            self._restore_connected_tables(key)

    def _current_table_names(self) -> List[str]:
        return [
            str(self.tables_combo.itemText(index) or "")
            for index in range(self.tables_combo.count())
            if str(self.tables_combo.itemText(index) or "").strip()
        ]

    def _restore_connected_tables(self, key: str):
        tables = _CONNECTED_DATABASE_TABLES.get(key) or []
        if not tables:
            return
        self.tables_combo.blockSignals(True)
        try:
            self.tables_combo.clear()
            for table in tables:
                self.tables_combo.addItem(table)
        finally:
            self.tables_combo.blockSignals(False)
        self.tables_combo.setVisible(True)
        if hasattr(self, "load_btn"):
            self.load_btn.setText(_rt("Carregar"))
        if self.height() < 472:
            self.setFixedSize(500, 472)
            _center_dialog_on_parent(self)

    def _params(self) -> Dict:
        driver = self.driver_combo.currentText()
        try:
            port = int(self.port_edit.text().strip())
        except ValueError:
            port = self._default_port_for_driver(driver)
        normalized_driver = "PostgreSQL" if driver == "PostGIS" else driver
        params = {
            "driver": normalized_driver,
            "source_driver": driver,
            "host": self.host_edit.text().strip(),
            "port": port,
            "database": self.database_edit.text().strip(),
            "user": self.user_edit.text().strip(),
            "password": self.password_edit.text(),
            "ssl_mode": self.ssl_combo.currentText().strip().lower(),
            "use_ssl": self.use_ssl_box.isChecked(),
        }
        if not params["password"]:
            connected = _CONNECTED_DATABASE_PARAMS.get(self._connection_status_key(params))
            if connected and connected.get("password"):
                params["password"] = connected.get("password")
        return params

    def _default_port_for_driver(self, driver: str) -> int:
        mapping = {
            "PostgreSQL": 5432,
            "PostGIS": 5432,
            "SQL Server": 1433,
            "Oracle": 1521,
            "MySQL": 3306,
        }
        return int(mapping.get(driver, 5432))

    def _load_last_params(self) -> Dict[str, Dict]:
        raw = self.settings.value(LAST_DB_PARAMS_KEY, "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            log_exception("falha opcional ignorada")
        return {}

    def _remember_last_params(self, params: Dict):
        driver = params.get("driver")
        source_driver = params.get("source_driver")
        if not driver:
            return
        record = {
            "host": params.get("host", ""),
            "port": params.get("port", 0),
            "database": params.get("database", ""),
            "user": params.get("user", ""),
            "password": params.get("password", ""),
        }
        self._last_params[driver] = record
        if source_driver:
            self._last_params[source_driver] = record
        try:
            persisted = {
                key: {k: v for k, v in value.items() if k != "password"}
                for key, value in self._last_params.items()
            }
            self.settings.setValue(LAST_DB_PARAMS_KEY, json.dumps(persisted))
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_driver_defaults(self):
        driver = self.driver_combo.currentText()
        params = self._last_params.get(driver)
        self._suspend_defaults = True
        try:
            if params:
                self.host_edit.setText(params.get("host", ""))
                self.port_edit.setText(str(params.get("port", "")))
                self.database_edit.setText(params.get("database", ""))
                self.user_edit.setText(params.get("user", ""))
                self.password_edit.setText(params.get("password", ""))
            else:
                self.port_edit.setText(str(self._default_port_for_driver(driver)))
        finally:
            self._suspend_defaults = False
        self._apply_driver_ui()
        self._refresh_connection_status_from_fields()

    def _apply_driver_ui(self):
        driver = self.driver_combo.currentText() or "PostgreSQL"
        title = _rt("Connect to {driver}", driver=driver)
        self.setWindowTitle(title)
        if hasattr(self, "title_label"):
            self.title_label.setText(title)

        database_label = "Database"
        database_placeholder = "Database name"
        host_placeholder = "localhost"
        port_placeholder = str(self._default_port_for_driver(driver))
        ssl_mode_visible = driver in {"PostgreSQL", "PostGIS"}
        use_ssl_visible = driver == "MySQL"
        if driver == "Oracle":
            database_label = "Service / SID"
            database_placeholder = "Service name or SID"
        elif driver == "SQL Server":
            database_placeholder = "Database name"
        elif driver == "PostGIS":
            database_placeholder = "Spatial database name"

        self.host_edit.setPlaceholderText(host_placeholder)
        self.port_edit.setPlaceholderText(port_placeholder)
        self.database_label.setText(_rt(database_label))
        self.database_edit.setPlaceholderText(_rt(database_placeholder))
        self.ssl_label.setVisible(ssl_mode_visible)
        self.ssl_combo.setVisible(ssl_mode_visible)
        self.use_ssl_box.setVisible(use_ssl_visible)
        if not ssl_mode_visible:
            self.ssl_combo.hidePopup()

    def _on_driver_changed(self, *_):
        self._set_connection_status(False)
        self._apply_driver_ui()
        if self._suspend_defaults:
            return
        self._apply_driver_defaults()

    def _build_connection_payload(self, params: Dict) -> Dict:
        payload = {
            "driver": params.get("source_driver") or params.get("driver"),
            "host": params.get("host"),
            "port": params.get("port"),
            "database": params.get("database"),
            "user": params.get("user"),
            "password": params.get("password"),
            "authcfg": params.get("authcfg", ""),
            "source_driver": params.get("source_driver") or params.get("driver"),
            "ssl_mode": params.get("ssl_mode"),
            "use_ssl": params.get("use_ssl"),
        }
        payload = secure_connection_payload(payload, name=str(params.get("display_name") or "Summarizer"))
        payload["name"] = f"{payload.get('database')} ({payload.get('driver')})"
        payload["fingerprint"] = f"{payload.get('driver')}::{payload.get('host')}::{payload.get('database')}::{payload.get('user')}"
        return payload

    def _test_connection(self):
        params = self._params()
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            ok, db_or_error = self._create_connection(params)
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            QMessageBox.information(self, _rt("Conexão"), _rt("Conexão estabelecida com sucesso."))
            self._remember_last_params(params)
            self._populate_tables(db_or_error, params["driver"])
            self._remember_connected_connection(params, self._current_table_names())
            db_or_error.close()
        else:
            self._set_connection_status(False)
            QMessageBox.warning(self, _rt("Conexão"), db_or_error)

    def _create_connection(self, params: Dict) -> Tuple[bool, object]:
        if QSqlDatabase is None:
            return False, _rt("QtSql não está disponível nesta instalação.")

        conn_name = f"integ_{id(self)}_{QDateTime.currentMSecsSinceEpoch()}"
        driver = params.get("driver")
        available_drivers = set(QSqlDatabase.drivers())

        if driver == "PostgreSQL":
            if "QPSQL" not in available_drivers:
                return False, _rt("Driver PostgreSQL (QPSQL) não está disponível nesta instalação.")
            db = QSqlDatabase.addDatabase("QPSQL", conn_name)
            db.setHostName(params.get("host"))
            db.setPort(params.get("port") or 5432)
            db.setDatabaseName(params.get("database"))
            db.setUserName(params.get("user"))
            db.setPassword(params.get("password"))
            ssl_mode = str(params.get("ssl_mode") or "").strip()
            if ssl_mode:
                db.setConnectOptions(f"sslmode={ssl_mode}")
        elif driver == "SQL Server":
            if "QODBC" not in available_drivers:
                return False, _rt("Driver SQL Server (QODBC) não está disponível nesta instalação.")
            db = QSqlDatabase.addDatabase("QODBC", conn_name)
            connection_string = (
                "Driver={ODBC Driver 17 for SQL Server};"
                f"Server={params.get('host')},{params.get('port') or 1433};"
                f"Database={params.get('database')};"
                f"Uid={params.get('user')};"
                f"Pwd={params.get('password')};"
            )
            db.setDatabaseName(connection_string)
        elif driver == "Oracle":
            if "QOCI" not in available_drivers:
                return False, _rt("Driver Oracle (QOCI) não está disponível nesta instalação.")
            db = QSqlDatabase.addDatabase("QOCI", conn_name)
            db.setHostName(params.get("host"))
            db.setPort(params.get("port") or 1521)
            db.setDatabaseName(params.get("database"))
            db.setUserName(params.get("user"))
            db.setPassword(params.get("password"))
        elif driver == "MySQL":
            if "QMYSQL" not in available_drivers:
                return False, _rt("Driver MySQL (QMYSQL) não está disponível nesta instalação.")
            db = QSqlDatabase.addDatabase("QMYSQL", conn_name)
            db.setHostName(params.get("host"))
            db.setPort(params.get("port") or 3306)
            db.setDatabaseName(params.get("database"))
            db.setUserName(params.get("user"))
            db.setPassword(params.get("password"))
            if params.get("use_ssl"):
                db.setConnectOptions("CLIENT_SSL=1")
        else:
            return False, _rt("Conector de banco de dados não suportado nesta instalação.")

        if not db.open():
            error = db.lastError().text()
            db = None
            return False, error or _rt("Falha ao abrir a conexão.")
        return True, db

    def _populate_tables(self, db, driver: str):
        self.tables_combo.clear()
        if QSqlQuery is None:
            return
        query = QSqlQuery(db)
        if driver == "PostgreSQL":
            query.exec_(
                "SELECT table_schema || '.' || table_name "
                "FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "ORDER BY 1"
            )
        elif driver == "SQL Server":
            query.exec_(
                "SELECT TABLE_SCHEMA + '.' + TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY 1"
            )
        elif driver == "Oracle":
            query.exec_(
                "SELECT OWNER || '.' || TABLE_NAME "
                "FROM ALL_TABLES "
                "ORDER BY 1"
            )
        else:
            query.exec_(
                "SELECT CONCAT(TABLE_SCHEMA, '.', TABLE_NAME) "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY 1"
            )
        while query.next():
            self.tables_combo.addItem(query.value(0))

    def _quote_table_name(self, table_name: str, driver: str) -> Optional[str]:
        value = str(table_name or "").strip()
        if not value:
            return None
        available = {
            str(self.tables_combo.itemText(index) or "").strip()
            for index in range(self.tables_combo.count())
        }
        if value not in available:
            return None
        parts = [part.strip() for part in value.split(".") if part.strip()]
        if len(parts) not in (1, 2):
            return None
        if driver in ("PostgreSQL", "Oracle"):
            quoted_parts = []
            for part in parts:
                quoted_parts.append('"{}"'.format(part.replace('"', '""')))
            return ".".join(quoted_parts)
        if driver == "MySQL":
            return ".".join(f"`{part.replace('`', '``')}`" for part in parts)
        return ".".join(f'[{part.replace("]", "]]")}]' for part in parts)

    def _split_table_name(self, table_name: str) -> Tuple[str, str]:
        value = str(table_name or "").strip()
        parts = [part.strip() for part in value.split(".") if part.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return "", parts[0]
        return "", ""

    def _detect_postgres_geometry(self, db, table_name: str) -> Dict:
        schema, name = self._split_table_name(table_name)
        if not name or QSqlQuery is None:
            return {}
        if not schema:
            schema = "public"
        safe_schema = schema.replace("'", "''")
        safe_name = name.replace("'", "''")
        query = QSqlQuery(db)
        sql = (
            "SELECT f_geometry_column, srid, type "
            "FROM public.geometry_columns "
            f"WHERE f_table_schema = '{safe_schema}' "
            f"AND f_table_name = '{safe_name}' "
            "LIMIT 1"
        )
        if not query.exec_(sql):
            return {}
        if not query.next():
            return {}
        return {
            "schema": schema,
            "table_name": name,
            "geometry_column": str(query.value(0) or ""),
            "srid": int(query.value(1) or 0),
            "geometry_type": str(query.value(2) or ""),
        }

    def _build_select_sql(self, quoted_table: str, driver: str, preview: bool) -> str:
        if not preview:
            # Table identifiers are selected from metadata and quoted per driver.
            return f"SELECT * FROM {quoted_table}"  # nosec B608
        if driver == "PostgreSQL":
            return f"SELECT * FROM {quoted_table} LIMIT 120"  # nosec B608
        if driver == "Oracle":
            return f"SELECT * FROM {quoted_table} WHERE ROWNUM <= 120"  # nosec B608
        if driver == "MySQL":
            return f"SELECT * FROM {quoted_table} LIMIT 120"  # nosec B608
        return f"SELECT TOP 120 * FROM {quoted_table}"  # nosec B608

    def _retrieve(self, preview: bool):
        params = self._params()
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            ok, db_or_error = self._create_connection(params)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            self._set_connection_status(False)
            QMessageBox.warning(self, _rt("Importar"), db_or_error)
            return
        db = db_or_error
        self._remember_last_params(params)
        try:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            if self.tables_combo.count() == 0:
                self._populate_tables(db, params["driver"])
            self._remember_connected_connection(params, self._current_table_names())
            if not preview and not self.tables_combo.isVisible():
                self.tables_combo.setVisible(True)
                self.setFixedSize(500, 472)
                if hasattr(self, "load_btn"):
                    self.load_btn.setText(_rt("Carregar"))
                _center_dialog_on_parent(self)
                return
            table = self.tables_combo.currentText()
            if not table:
                QMessageBox.information(self, _rt("Importar"), _rt("Selecione uma tabela."))
                return

            quoted_table = self._quote_table_name(table, params["driver"])
            if not quoted_table:
                QMessageBox.warning(
                    self,
                    _rt("Importar"),
                    _rt("Selecione uma tabela válida carregada da conexão."),
                )
                return
            sql = self._build_select_sql(quoted_table, params["driver"], preview)

            query = QSqlQuery(db)
            if not query.exec_(sql):
                QMessageBox.warning(self, _rt("Importar"), query.lastError().text())
                return

            record = query.record()
            columns = [record.fieldName(i) for i in range(record.count())]
            rows = []
            while query.next():
                rows.append([query.value(i) for i in range(record.count())])
            df = pd.DataFrame(rows, columns=columns)

            if preview:
                self._fill_preview(df)
            else:
                spatial_meta = {}
                source_driver = params.get("source_driver") or params["driver"]
                if source_driver in ("PostgreSQL", "PostGIS"):
                    spatial_meta = self._detect_postgres_geometry(db, table)
                secure_connection = self._build_connection_payload(params)
                self._df = df
                self._metadata = {
                    "connector": source_driver,
                    "display_name": table,
                    "database": params["database"],
                    "host": params["host"],
                    "table_name": spatial_meta.get("table_name") or self._split_table_name(table)[1],
                    "schema": spatial_meta.get("schema") or self._split_table_name(table)[0],
                    "geometry_column": spatial_meta.get("geometry_column", ""),
                    "geometry_type": spatial_meta.get("geometry_type", ""),
                    "db_connection": secure_connection,
                }
                self._session_connection = secure_connection
                if self.remember_box.isChecked():
                    self._connection_meta = dict(self._session_connection)
                self.accept()
        finally:
            QApplication.restoreOverrideCursor()
            db.close()

    def _fill_preview(self, df: pd.DataFrame):
        self.preview_table.setVisible(True)
        self.tables_combo.setVisible(True)
        self.setFixedSize(500, 520)
        _center_dialog_on_parent(self)
        self.preview_table.clear()
        self.preview_table.setRowCount(min(PREVIEW_ROW_LIMIT, len(df.index)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(min(PREVIEW_ROW_LIMIT, len(df.index))):
            for c, column in enumerate(df.columns):
                value = df.iloc[r][column]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.preview_table.resizeColumnsToContents()

    def result(self) -> Tuple[pd.DataFrame, Dict, Optional[Dict], Optional[Dict]]:
        return self._df, self._metadata, self._connection_meta, self._session_connection

    def _force_browser_sync(self):
        params = self._params()
        if not params.get("host") or not params.get("database") or not params.get("user"):
            QMessageBox.information(
                self,
                _rt("Navegador"),
                _rt("Informe host, banco e usuário antes de sincronizar com o Navegador."),
            )
            return
        payload = self._build_connection_payload(params)
        connection_registry.register_runtime_connection(payload)
        if self._browser_sync_callback:
            self._browser_sync_callback(payload)
        QMessageBox.information(
            self,
            _rt("Navegador"),
            _rt(
                "Conexão enviada para o Navegador.\nExpanda 'PostgreSQL' (ou 'Summarizer', se disponível) para visualizar."
            ),
        )


class GoogleSheetsDialog(SlimDialogBase):
    def __init__(self, parent: QWidget):
        super().__init__(parent, geometry_key="Summarizer/integration/googleSheetsDialog")
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self.setWindowTitle(_rt("Importar dados do Google Sheets"))
        self.resize(560, 360)
        self._build_ui()
        self._apply_runtime_i18n()

    def _apply_runtime_i18n(self):
        try:
            _apply_i18n_widgets(self)
        except Exception:
            log_exception("falha opcional ignorada")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_runtime_i18n()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info = QLabel(
            "Informe a URL pública da planilha (ex.: https://docs.google.com/spreadsheets/d/ID/export?format=csv&gid=0).",
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("URL pública…")
        layout.addWidget(self.url_edit)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        _apply_walker_dialog_buttons(primary=[load_btn], secondary=[preview_btn, cancel_btn])
        layout.addWidget(buttons)

        self.preview_table = QTableWidget(self)
        layout.addWidget(self.preview_table, 1)

        preview_btn.clicked.connect(lambda: self._retrieve(preview=True))
        load_btn.clicked.connect(lambda: self._retrieve(preview=False))
        cancel_btn.clicked.connect(self.reject)

    def _retrieve(self, preview: bool):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, _rt("Google Sheets"), _rt("Informe a URL da planilha."))
            return
        try:
            df = pd.read_csv(url)
        except Exception as exc:
            QMessageBox.warning(self, _rt("Google Sheets"), _rt("Falha ao baixar dados: {exc}", exc=exc))
            return
        if preview:
            self._fill_preview(df.head(PREVIEW_ROW_LIMIT))
        else:
            self._df = df
            self._metadata = {
                "connector": "Google Sheets",
                "display_name": "Google Sheets",
                "source_path": url,
            }
            self.accept()

    def _fill_preview(self, df: pd.DataFrame):
        self.preview_table.clear()
        self.preview_table.setRowCount(min(PREVIEW_ROW_LIMIT, len(df.index)))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(min(PREVIEW_ROW_LIMIT, len(df.index))):
            for c, column in enumerate(df.columns):
                value = df.iloc[r][column]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if pd.isna(value) else str(value)))
        self.preview_table.resizeColumnsToContents()

    def result(self) -> Tuple[pd.DataFrame, Dict]:
        return self._df, self._metadata


class ExtendedConnectorsDialog(SlimDialogBase):
    def __init__(self, connectors: Dict[str, ConnectorConfig], parent: QWidget):
        super().__init__(parent, geometry_key="Summarizer/integration/extendedConnectors")
        self.setWindowTitle("Catálogo de fontes disponíveis")
        self.resize(760, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info = QLabel(
            "Lista completa de fontes suportadas pelo plugin. Algumas exigem configuração adicional, mas todas refletem cenários úteis para o ecossistema QGIS.",
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        lst = QListWidget(self)
        category_labels = {
            "files": "Arquivos",
            "database": "Banco de dados",
            "spatial": "Espacial",
            "web": "Web",
            "quick": "Rápido",
            "primary": "Geral",
        }
        for config in connectors.values():
            category = category_labels.get(config.category, "Geral")
            item = QListWidgetItem(f"[{category}] {config.title} • {config.microcopy}")
            item.setToolTip(config.description or config.caption)
            lst.addItem(item)
        layout.addWidget(lst, 1)

        close_btn = QDialogButtonBox(QDialogButtonBox.Close, self)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)
        _apply_i18n_widgets(self)
