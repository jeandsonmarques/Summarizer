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
from qgis.PyQt.QtGui import QColor, QCursor, QFontMetrics, QIcon, QKeySequence, QPainter, QPen, QPixmap
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
    QPlainTextEdit,
    QPushButton,
    QShortcut,
    QScrollArea,
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
from .utils.fonts import _qfont_weight, harmonize_widget_fonts, ui_font, ui_font_stack
from .utils.i18n_runtime import apply_widget_translations as _apply_i18n_widgets, tr_text as _rt
from .utils.resources import svg_icon
from .utils.security_utils import reveal_connection_payload, secure_connection_payload
from .utils.window_theme import apply_windows_rounded_corners
from .walker_dialogs import WalkerMessageBox as QMessageBox, apply_walker_combo

from .utils.logging_utils import log_exception
_ICON_DIR = os.path.join(os.path.dirname(__file__), "resources", "icons")


def _is_dark_theme() -> bool:
    try:
        return str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower() == "dark"
    except Exception:
        return False


def _qt_member(owner, enum_name: str, member_name: str):
    enum_owner = getattr(owner, enum_name, None)
    if enum_owner is not None and hasattr(enum_owner, member_name):
        return getattr(enum_owner, member_name)
    return getattr(owner, member_name)


def _qt_alignment(*member_names: str):
    result = None
    for member_name in member_names:
        member = _qt_member(Qt, "AlignmentFlag", member_name)
        result = member if result is None else result | member
    return result


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
        query.exec(
            "SELECT table_schema || '.' || table_name "
            "FROM information_schema.tables "
            "WHERE table_type = 'BASE TABLE' "
            "ORDER BY 1"
        )
    elif driver == "SQL Server":
        query.exec(
            "SELECT TABLE_SCHEMA + '.' + TABLE_NAME "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY 1"
        )
    elif driver == "Oracle":
        query.exec(
            "SELECT OWNER || '.' || TABLE_NAME "
            "FROM ALL_TABLES "
            "ORDER BY 1"
        )
    else:
        query.exec(
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
    list_category: str = "Geral"
    status_text: str = "Disponível"
    action_text: str = "Abrir"


class _ElidedLabel(QLabel):
    """QLabel with stable single-line ellipsis for responsive rows."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(
            _qt_member(QSizePolicy, "Policy", "Expanding"),
            _qt_member(QSizePolicy, "Policy", "Preferred"),
        )
        self.setText(text)

    def setText(self, text):  # noqa: N802 - Qt API name
        self._full_text = "" if text is None else str(text)
        self.setToolTip(self._full_text)
        self._update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        if not hasattr(self, "_full_text"):
            return
        width = max(int(self.width()) - 2, 0)
        if width <= 0:
            QLabel.setText(self, self._full_text)
            return
        metrics = QFontMetrics(self.font())
        QLabel.setText(
            self,
            metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width),
        )


class SourceConnectionItem(QFrame):
    """Horizontal row used by the connection source list."""

    triggered = pyqtSignal(str)

    def __init__(
        self,
        *,
        key: str,
        icon_path: str = "",
        icon_name: str = "",
        icon_text: str = "",
        title: str,
        subtitle: str,
        category: str,
        status: str,
        action_text: str,
        callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.key = key
        self.icon_path = icon_path
        self.icon_name = icon_name
        self.icon_text = icon_text
        self.title = title
        self.subtitle = subtitle
        self.category = category
        self.status = status
        self.action_text = action_text
        self._callback = callback

        self.setObjectName(f"sourceConnection_{key}")
        self.setProperty("role", "sourceRow")
        self.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)
        self.setCursor(_qt_member(Qt, "CursorShape", "PointingHandCursor"))
        self.setFocusPolicy(_qt_member(Qt, "FocusPolicy", "StrongFocus"))
        self.setMinimumHeight(68)
        self.setMaximumHeight(76)
        self.setSizePolicy(
            _qt_member(QSizePolicy, "Policy", "Expanding"),
            _qt_member(QSizePolicy, "Policy", "Fixed"),
        )

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 14, 8)
        layout.setSpacing(12)

        self.icon_label = QLabel(self)
        self.icon_label.setProperty("role", "sourceIcon")
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setAlignment(_qt_alignment("AlignCenter"))
        layout.addWidget(self.icon_label, 0, _qt_alignment("AlignVCenter"))

        text_host = QWidget(self)
        text_host.setObjectName("sourceConnectionText")
        text_host.setProperty("role", "sourceTextHost")
        text_host.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)
        text_host.setSizePolicy(
            _qt_member(QSizePolicy, "Policy", "Expanding"),
            _qt_member(QSizePolicy, "Policy", "Preferred"),
        )
        text_layout = QVBoxLayout(text_host)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        self.title_label = _ElidedLabel(self.title, text_host)
        self.title_label.setProperty("role", "sourceTitle")
        self.title_label.setFont(ui_font(10, _qfont_weight("DemiBold", 63)))
        text_layout.addWidget(self.title_label)

        self.subtitle_label = _ElidedLabel(self.subtitle, text_host)
        self.subtitle_label.setProperty("role", "sourceSubtitle")
        self.subtitle_label.setFont(ui_font(9, _qfont_weight("Normal", 50)))
        text_layout.addWidget(self.subtitle_label)

        layout.addWidget(text_host, 1)

        self.category_label = _ElidedLabel(self.category, self)
        self.category_label.setProperty("role", "sourceMeta")
        self.category_label.setAlignment(_qt_alignment("AlignVCenter", "AlignLeft"))
        self.category_label.setMinimumWidth(128)
        self.category_label.setMaximumWidth(170)
        self.category_label.setFont(ui_font(10, _qfont_weight("Normal", 50)))
        layout.addWidget(self.category_label, 0, _qt_alignment("AlignVCenter"))

        self.status_label = _ElidedLabel(self.status, self)
        self.status_label.setProperty("role", "sourceStatus")
        self.status_label.setAlignment(_qt_alignment("AlignVCenter", "AlignLeft"))
        self.status_label.setMinimumWidth(92)
        self.status_label.setMaximumWidth(120)
        self.status_label.setFont(ui_font(10, _qfont_weight("Normal", 50)))
        layout.addWidget(self.status_label, 0, _qt_alignment("AlignVCenter"))

        self.action_button = QPushButton(self.action_text, self)
        self.action_button.setProperty("role", "sourceAction")
        self.action_button.setCursor(_qt_member(Qt, "CursorShape", "PointingHandCursor"))
        self.action_button.setMinimumSize(0, 0)
        self.action_button.setFixedSize(118, 32)
        self.action_button.setFont(ui_font(9, _qfont_weight("Normal", 50)))
        self.action_button.clicked.connect(self._activate)
        layout.addWidget(self.action_button, 0, _qt_alignment("AlignVCenter"))

    def _apply_styles(self):
        self._apply_icon()
        self.title_label.setText(_rt(self.title))
        self.subtitle_label.setText(_rt(self.subtitle))
        self.category_label.setText(_rt(self.category))
        self.status_label.setText(_rt(self.status))
        self.action_button.setText(_rt(self.action_text))

    def _apply_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            icon = QIcon(self.icon_path)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(QSize(40, 40)))
                return
        if self.icon_name:
            icon = svg_icon(self.icon_name)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(QSize(40, 40)))
                return
        self.icon_label.setText(self.icon_text.upper()[:4])
        self.icon_label.setFont(ui_font(10, _qfont_weight("Bold", 75)))

    def _activate(self):
        self.triggered.emit(self.key)
        if callable(self._callback):
            self._callback()

    def mouseReleaseEvent(self, event):
        if event.button() == _qt_member(Qt, "MouseButton", "LeftButton"):
            self._activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (
            _qt_member(Qt, "Key", "Key_Return"),
            _qt_member(Qt, "Key", "Key_Enter"),
            _qt_member(Qt, "Key", "Key_Space"),
        ):
            self._activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_responsive_state()

    def sync_responsive_state(self):
        width = int(self.width())
        if width <= 0:
            return
        compact = width < 720
        self.category_label.setVisible(not compact)
        self.status_label.setVisible(not compact)
        self.action_button.setFixedWidth(102 if width < 620 else 118)


def _show_walker_modal_overlay(dialog: QDialog) -> Optional[QFrame]:
    parent = dialog.parentWidget()
    if parent is None:
        return None
    host = parent.window() or parent
    overlay = QFrame(host)
    overlay.setObjectName("WalkerModalOverlay")
    overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
    flags = Qt.WindowType.Dialog
    if sys.platform.startswith("win"):
        flags |= Qt.WindowType.FramelessWindowHint
    else:
        flags |= Qt.WindowType.WindowCloseButtonHint
    try:
        flags |= Qt.WindowType.NoDropShadowWindowHint
    except Exception:
        pass
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
        self.setObjectName("integrationPanelPage")
        self.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_scroll = QScrollArea(self)
        self.page_scroll.setObjectName("integrationPageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(_qt_member(QFrame, "Shape", "NoFrame"))
        self.page_scroll.setHorizontalScrollBarPolicy(_qt_member(Qt, "ScrollBarPolicy", "ScrollBarAlwaysOff"))

        page = QWidget(self.page_scroll)
        page.setObjectName("integrationPage")
        page.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 24, 24, 24)
        page_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(5)

        self.title_label = QLabel(_rt("Conexões"), page)
        self.title_label.setProperty("role", "pageTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setFont(ui_font(18, _qfont_weight("DemiBold", 63)))
        header_text.addWidget(self.title_label)

        header_layout.addLayout(header_text, 1)

        page_layout.addLayout(header_layout)

        self.sources_frame = QFrame(page)
        self.sources_frame.setObjectName("sourcesFrame")
        self.sources_frame.setProperty("role", "sourcesSection")
        self.sources_frame.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)
        sources_layout = QVBoxLayout(self.sources_frame)
        sources_layout.setContentsMargins(0, 0, 0, 0)
        sources_layout.setSpacing(12)

        sources_header = QHBoxLayout()
        sources_header.setContentsMargins(0, 0, 0, 0)
        sources_title = QLabel(_rt("Fontes"), self.sources_frame)
        sources_title.setProperty("role", "sectionTitle")
        sources_title.setFont(ui_font(13, _qfont_weight("DemiBold", 63)))
        sources_header.addWidget(sources_title)
        sources_header.addStretch(1)
        sources_layout.addLayout(sources_header)

        self.sources_list = QWidget(self.sources_frame)
        self.sources_list.setObjectName("sourcesList")
        self.source_rows_layout = QVBoxLayout(self.sources_list)
        self.source_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.source_rows_layout.setSpacing(8)
        sources_layout.addWidget(self.sources_list)

        page_layout.addWidget(self.sources_frame)

        self._build_connectors()

        recents_frame = QFrame(page)
        recents_frame.setObjectName("recentsFrame")
        recents_frame.setProperty("role", "sectionFrame")
        recents_frame.setAttribute(_qt_member(Qt, "WidgetAttribute", "WA_StyledBackground"), True)
        recents_layout = QVBoxLayout(recents_frame)
        recents_layout.setContentsMargins(18, 18, 18, 18)
        recents_layout.setSpacing(12)

        recents_header = QHBoxLayout()
        recents_header.setContentsMargins(0, 0, 0, 0)
        recents_header.setSpacing(8)
        recents_title = QLabel(_rt("Recentes"), recents_frame)
        recents_title.setProperty("role", "sectionTitle")
        recents_title.setFont(ui_font(13, _qfont_weight("DemiBold", 63)))
        recents_header.addWidget(recents_title)
        recents_header.addStretch(1)

        self.clear_recent_btn = QPushButton(_rt("Limpar"), recents_frame)
        self.clear_recent_btn.setProperty("role", "recentClear")
        self.clear_recent_btn.setCursor(_qt_member(Qt, "CursorShape", "PointingHandCursor"))
        self.clear_recent_btn.setMinimumSize(0, 0)
        self.clear_recent_btn.setFixedSize(88, 32)
        self.clear_recent_btn.setFont(ui_font(9, _qfont_weight("Normal", 50)))
        self.clear_recent_btn.clicked.connect(self._clear_recents)
        recents_header.addWidget(self.clear_recent_btn)

        recents_layout.addLayout(recents_header)

        self.recents_list = QListWidget(recents_frame)
        self.recents_list.setAlternatingRowColors(False)
        self.recents_list.setSpacing(8)
        self.recents_list.setCursor(_qt_member(Qt, "CursorShape", "PointingHandCursor"))
        self.recents_list.setHorizontalScrollBarPolicy(_qt_member(Qt, "ScrollBarPolicy", "ScrollBarAlwaysOff"))
        self.recents_list.itemActivated.connect(self._open_recent)
        recents_layout.addWidget(self.recents_list)

        self.recents_placeholder = QLabel(_rt("Nenhuma conexão recente..."), recents_frame)
        self.recents_placeholder.setAlignment(_qt_alignment("AlignVCenter", "AlignLeft"))
        self.recents_placeholder.setMinimumHeight(56)
        self.recents_placeholder.setProperty("role", "emptyRecent")
        recents_layout.addWidget(self.recents_placeholder)

        page_layout.addWidget(recents_frame)
        page_layout.addStretch(1)

        self.page_scroll.setWidget(page)
        root.addWidget(self.page_scroll, 1)

        self._apply_panel_styles()
        self._apply_runtime_i18n()

    def _apply_panel_styles(self):
        style_template = """
            QWidget#integrationPanelPage,
            QWidget#integrationPage {
                background: #f8fafc;
            }
            QScrollArea#integrationPageScroll {
                background: #f8fafc;
                border: none;
            }
            QScrollArea#integrationPageScroll > QWidget > QWidget {
                background: #f8fafc;
            }
            QFrame[role="sourcesSection"] {
                background: transparent;
                border: none;
            }
            QFrame[role="sectionFrame"] {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QFrame[role="sourceRow"] {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
            }
            QFrame[role="sourceRow"]:hover {
                background: #f9fafb;
            }
            QLabel {
                font-family: %s;
            }
            QLabel[role="pageTitle"] {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 18px;
                font-weight: 600;
            }
            QLabel[role="sectionTitle"] {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel[role="sourceIcon"] {
                background: transparent;
                border: none;
                color: #111827;
            }
            QWidget[role="sourceTextHost"] {
                background: transparent;
                border: none;
            }
            QLabel[role="sourceTitle"] {
                background: transparent;
                border: none;
                color: #111827;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel[role="sourceSubtitle"] {
                background: transparent;
                border: none;
                color: #6b7280;
                font-size: 11px;
            }
            QLabel[role="sourceMeta"],
            QLabel[role="sourceStatus"] {
                background: transparent;
                border: none;
                color: #4b5563;
                font-size: 11px;
            }
            QLabel[role="emptyRecent"] {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                color: #6b7280;
                padding: 0px 14px;
                font-size: 12px;
            }
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
                padding: 0px;
                font-family: %s;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 10px 14px;
                margin: 0px;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background: #ffffff;
                color: #111827;
            }
            QListWidget::item:selected {
                background: #f3f4f6;
                border: 1px solid #d1d5db;
                color: #111827;
            }
            QListWidget::item:hover {
                background: #f9fafb;
            }
            QPushButton[role="sourceAction"],
            QPushButton[role="recentClear"] {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                border-radius: 5px;
                padding: 0px 14px;
                font-family: %s;
                font-size: 12px;
                font-weight: 400;
                min-height: 30px;
                max-height: 32px;
            }
            QPushButton[role="sourceAction"]:hover,
            QPushButton[role="recentClear"]:hover {
                background: #f3f4f6;
            }
            QPushButton[role="sourceAction"]:pressed,
            QPushButton[role="recentClear"]:pressed {
                background: #e5e7eb;
            }
            QPushButton[role="sourceAction"]:disabled,
            QPushButton[role="recentClear"]:disabled {
                background: #f9fafb;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            """
        style = style_template % (
            ui_font_stack(),
            ui_font_stack(),
            ui_font_stack(),
        )
        self.setStyleSheet(style)
        for row in getattr(self, "_rows", {}).values():
            try:
                row._apply_styles()
                row.sync_responsive_state()
            except Exception:
                log_exception("falha opcional ignorada")

    def _refresh_connector_layout(self):
        for row in getattr(self, "_rows", {}).values():
            try:
                row.sync_responsive_state()
            except Exception:
                log_exception("falha opcional ignorada")

    def add_connection_row(
        self,
        *,
        key: str,
        icon_path: str,
        icon_text: str,
        title: str,
        subtitle: str,
        category: str,
        status: str,
        action_text: str,
        callback: Callable[[], None],
        icon_name: str = "",
    ) -> SourceConnectionItem:
        row = SourceConnectionItem(
            key=key,
            icon_path=icon_path,
            icon_name=icon_name,
            icon_text=icon_text,
            title=title,
            subtitle=subtitle,
            category=category,
            status=status,
            action_text=action_text,
            callback=callback,
            parent=self.sources_list,
        )
        self.source_rows_layout.addWidget(row)
        self._rows[key] = row
        return row

    def _build_connectors(self):
        self._connectors: Dict[str, ConnectorConfig] = {}
        self._rows: Dict[str, SourceConnectionItem] = {}
        self._cards: Dict[str, SourceConnectionItem] = {}

        def register(config: ConnectorConfig):
            self._connectors[config.key] = config
            row = self.add_connection_row(
                key=config.key,
                icon_path=config.icon_path,
                icon_name=config.icon_name,
                icon_text=config.icon_text,
                title=config.title,
                subtitle=config.caption,
                category=config.list_category,
                status=config.status_text,
                action_text=config.action_text,
                callback=lambda key=config.key: self._on_card_triggered(key),
            )
            self._cards[config.key] = row

        register(
            ConnectorConfig(
                key="excel",
                title="Excel",
                caption="XLSX e XLS",
                microcopy="Arquivos locais",
                accent="#CDEFE0",
                icon_text="X",
                handler=self._handle_excel,
                category="files",
                description="Planilhas tabulares com uma ou várias abas.",
                icon_path=os.path.join(_ICON_DIR, "source_excel.svg"),
                keywords="excel xlsx xls planilha arquivo tabela",
                list_category="Arquivos locais",
                status_text="Disponível",
                action_text="Abrir",
            )
        )
        register(
            ConnectorConfig(
                key="postgresql",
                title="PostgreSQL",
                caption="Tabelas",
                microcopy="Banco de dados",
                accent="#DCEBFF",
                icon_text="PG",
                handler=self._handle_postgresql_database,
                category="database",
                description="Servidor PostgreSQL muito comum em ambientes GIS e BI.",
                icon_path=os.path.join(_ICON_DIR, "source_postgresql.svg"),
                keywords="postgresql postgres servidor banco dados relacional",
                list_category="Banco de dados",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="postgis",
                title="PostGIS",
                caption="Camadas espaciais",
                microcopy="Banco espacial",
                accent="#DDF6E8",
                icon_text="GIS",
                handler=self._handle_postgis_database,
                category="spatial",
                description="Acesso a bases geoespaciais corporativas com PostgreSQL/PostGIS.",
                icon_path=os.path.join(_ICON_DIR, "source_postgis.png"),
                keywords="postgis espacial geometria servidor postgres qgis",
                list_category="Banco espacial",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="sqlserver",
                title="SQL Server",
                caption="Dados SQL",
                microcopy="Banco corporativo",
                accent="#E8EEFF",
                icon_text="SQL",
                handler=self._handle_sqlserver_database,
                category="database",
                description="Conector para ambientes SQL Server.",
                icon_path=os.path.join(_ICON_DIR, "source_sqlserver.svg"),
                keywords="sql server mssql servidor banco",
                list_category="Banco corporativo",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="oracle",
                title="Oracle",
                caption="Banco Oracle",
                microcopy="Banco corporativo",
                accent="#FFF0E7",
                icon_text="ORA",
                handler=self._handle_oracle_database,
                category="database",
                description="Conector para bases Oracle quando o driver QOCI estiver disponível.",
                icon_path=os.path.join(_ICON_DIR, "source_oracle.svg"),
                keywords="oracle servidor banco corporativo",
                list_category="Banco corporativo",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="mysql",
                title="MySQL",
                caption="Banco MySQL",
                microcopy="Banco de dados",
                accent="#EEF7FF",
                icon_text="MY",
                handler=self._handle_mysql_database,
                category="database",
                description="Conector para bases MySQL quando o driver QMYSQL estiver disponível.",
                icon_path=os.path.join(_ICON_DIR, "source_mysql.svg"),
                keywords="mysql mariadb servidor banco aplicacao",
                list_category="Banco de dados",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="gsheets",
                title="Google Sheets",
                caption="Planilhas web",
                microcopy="Planilhas web",
                accent="#F4FFF6",
                icon_text="GS",
                handler=self._handle_google_sheets,
                category="web",
                description="Ideal para tabelas compartilhadas por URL pública.",
                icon_path=os.path.join(_ICON_DIR, "source_gsheets.svg"),
                keywords="google sheets web nuvem url publica planilha",
                list_category="Planilhas web",
                status_text="Disponível",
                action_text="Conectar",
            )
        )
        register(
            ConnectorConfig(
                key="delimited",
                title="CSV / TXT",
                caption="CSV e TXT",
                microcopy="Arquivos delimitados",
                accent="#FFF1D8",
                icon_text="CSV",
                handler=self._handle_delimited_file,
                category="files",
                description="Importe arquivos tabulares simples com pré-visualização.",
                icon_path=os.path.join(_ICON_DIR, "source_csv.svg"),
                keywords="csv txt delimitado separado virgula ponto e virgula texto",
                list_category="Arquivos delimitados",
                status_text="Disponível",
                action_text="Abrir",
            )
        )
        register(
            ConnectorConfig(
                key="geopackage",
                title="GeoPackage",
                caption="Camadas vetoriais",
                microcopy="Camadas vetoriais",
                accent="#E8F6EC",
                icon_text="GPKG",
                handler=self._handle_geopackage,
                category="spatial",
                description="Abra dados vetoriais de um arquivo GeoPackage diretamente no plugin.",
                icon_path=os.path.join(_ICON_DIR, "source_geopackage.svg"),
                keywords="geopackage gpkg camada espacial geometria vetor qgis",
                list_category="Camadas vetoriais",
                status_text="Disponível",
                action_text="Abrir",
            )
        )
        register(
            ConnectorConfig(
                key="clipboard",
                title="Área de transferência",
                caption="Dados copiados",
                microcopy="Dados copiados",
                accent="#F4ECFF",
                icon_text="CLP",
                handler=self._handle_clipboard,
                category="quick",
                description="Útil para colar rapidamente dados copiados de outras ferramentas.",
                icon_path=os.path.join(_ICON_DIR, "source_clipboard.svg"),
                keywords="clipboard colar copiar area de transferencia rapido",
                list_category="Dados copiados",
                status_text="Disponível",
                action_text="Colar",
            )
        )

    def _register_shortcuts(self):
        shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        shortcut_open.activated.connect(self._handle_excel)

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
            qitem.setSizeHint(QSize(0, 64))
            qitem.setData(_qt_member(Qt, "ItemDataRole", "UserRole"), item)
            self.recents_list.addItem(qitem)

        visible_rows = min(max(len(self._recents), 1), 4)
        self.recents_list.setMinimumHeight((visible_rows * 72) + 2)
        self.recents_list.setMaximumHeight((min(len(self._recents), 8) * 72) + 2)
        self._apply_runtime_i18n()

    def _store_recent(self, descriptor: Dict):
        descriptor = dict(descriptor)
        descriptor["timestamp"] = descriptor.get("timestamp") or QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
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
        data = item.data(_qt_member(Qt, "ItemDataRole", "UserRole")) or {}
        connector = data.get("connector")
        if connector == "Excel":
            path = data.get("source_path")
            sheet = data.get("sheet_name")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, _rt("Recentes"), _rt("Arquivo n?o est? mais dispon?vel."))
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
                QMessageBox.warning(self, _rt("Recentes"), _rt("Arquivo n?o est? mais dispon?vel."))
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
                QMessageBox.warning(self, _rt("Recentes"), _rt("Arquivo n?o est? mais dispon?vel."))
                return
            self._import_geopackage_path(path)
        else:
            QMessageBox.information(
                self,
                _rt("Recentes"),
                _rt("Conex?es deste tipo precisam ser configuradas novamente."),
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
        connection_name = connection.get("name")
        if not connection_name:
            connection_name = f"{connection.get('database', 'Summarizer')}_{connection.get('user', '').strip() or 'user'}"
        conn_name = self._normalize_connection_name(connection_name)
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
            item.setData(Qt.ItemDataRole.UserRole, conn)
            list_widget.addItem(item)
        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)
        layout.addWidget(list_widget, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        remove_btn = button_box.addButton(_rt("Remover"), QDialogButtonBox.ButtonRole.ActionRole)
        remove_btn.setEnabled(False)
        layout.addWidget(button_box)

        def _current_connection():
            item = list_widget.currentItem()
            if not item:
                return None
            return item.data(Qt.ItemDataRole.UserRole)

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
        dialog.exec()

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
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
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
            fingerprint = (connection_meta or {}).get("fingerprint")
            if not fingerprint:
                fingerprint = (session_connection or {}).get("fingerprint")

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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            df, metadata = dialog.result()
            self._finalize_import(df, metadata)

    def _handle_delimited_file(self):
        dialog = DelimitedFileDialog(
            parent=self,
            last_dir=self.settings.value("integ/last_csv_dir", ""),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            df, metadata = dialog.result()
            if metadata.get("source_path"):
                self.settings.setValue(
                    "integ/last_csv_dir", os.path.dirname(metadata["source_path"])
                )
            self._finalize_import(df, metadata)

    def _handle_geopackage(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            _rt("Selecionar GeoPackage"),
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
            QMessageBox.warning(self, _rt("GeoPackage"), _rt("Não foi possível abrir o arquivo informado."))
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            df, metadata = dialog.result()
            self._finalize_import(df, metadata)

    def _show_extended_connectors(self):
        dialog = ExtendedConnectorsDialog(self._connectors, self)
        dialog.exec()

    # ------------------------------------------------------------------ Helpers
    def _finalize_import(self, df: pd.DataFrame, metadata: Dict):
        if df is None or df.empty:
            QMessageBox.information(self, _rt("Conexão"), _rt("Nenhum dado encontrado para carregar."))
            return
        metadata = dict(metadata)
        metadata.setdefault("import_target", "project")
        metadata.setdefault("record_count", len(df))
        metadata.setdefault("timestamp", QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate))
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
            dt = QDateTime.fromString(ts, Qt.DateFormat.ISODate)
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
        self.setProperty("forceCenterOnParent", True)
        self._df: Optional[pd.DataFrame] = None
        self._metadata: Dict = {}
        self.last_dir = last_dir or ""
        self.setWindowTitle(_rt("Importar dados do Excel"))
        self.resize(640, 540)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(self)
        self.path_edit.setPlaceholderText(_rt("Selecione o arquivo Excel…"))
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
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ButtonRole.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
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
            QMessageBox.warning(self, _rt("Excel"), _rt("Não foi possível abrir o arquivo: {exc}", exc=exc))
            return
        self.sheet_combo.clear()
        self.sheet_combo.addItems(excel.sheet_names)
        self.sheet_combo.setEnabled(True)

    def _preview(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.information(self, _rt("Excel"), _rt("Selecione um arquivo."))
            return
        sheet = self.sheet_combo.currentText() or None
        try:
            df = pd.read_excel(path, sheet_name=sheet, nrows=PREVIEW_ROW_LIMIT)
        except Exception as exc:
            QMessageBox.warning(self, _rt("Excel"), _rt("Falha na pré-visualização: {exc}", exc=exc))
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
            QMessageBox.warning(self, _rt("Excel"), _rt("Selecione um arquivo."))
            return
        sheet = self.sheet_combo.currentText() or None
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except Exception as exc:
            QMessageBox.critical(self, _rt("Excel"), _rt("Erro ao carregar: {exc}", exc=exc))
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
        self.setProperty("forceCenterOnParent", True)
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
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ButtonRole.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
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
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ButtonRole.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
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
        if event.type() == QEvent.Type.MouseButtonPress:
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
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.hidePopup()
            return True
        return super().eventFilter(watched, event)

    def _chevron_icon(self) -> QIcon:
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#6B7280"), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
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
        popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#111827"), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

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
        try:
            self.setGraphicsEffect(None)
        except Exception:
            log_exception("falha opcional ignorada")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._walker_panel = panel
        root_layout.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(8)

        self.connection_status_icon = _WalkerDatabaseTitleIcon(self)
        header.addWidget(self.connection_status_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(_rt("Connect to PostgreSQL"), self)
        self.title_label.setObjectName("WalkerDatabaseTitle")
        header.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignVCenter)

        close_btn = QToolButton(self)
        close_btn.setObjectName("WalkerDialogCloseButton")
        close_btn.setText("×")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
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
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
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
        form.addWidget(self.remember_box, 7, 1, Qt.AlignmentFlag.AlignVCenter)

        self.delete_connection_btn = QPushButton(_rt("Excluir conexão"), self)
        self.delete_connection_btn.setObjectName("WalkerDeleteConnectionButton")
        self.delete_connection_btn.clicked.connect(self._delete_saved_connection)
        self.delete_connection_btn.setVisible(False)
        form.addWidget(self.delete_connection_btn, 7, 2, 1, 2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ButtonRole.ActionRole)
        self.load_btn = buttons.addButton(_rt("Connect"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
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
        for combo in self.findChildren(QComboBox):
            apply_walker_combo(combo)

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
        if confirm != QMessageBox.StandardButton.Yes:
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
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
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
            query.exec(
                "SELECT table_schema || '.' || table_name "
                "FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' "
                "ORDER BY 1"
            )
        elif driver == "SQL Server":
            query.exec(
                "SELECT TABLE_SCHEMA + '.' + TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY 1"
            )
        elif driver == "Oracle":
            query.exec(
                "SELECT OWNER || '.' || TABLE_NAME "
                "FROM ALL_TABLES "
                "ORDER BY 1"
            )
        else:
            query.exec(
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
        query = QSqlQuery(db)
        query.prepare(
            "SELECT f_geometry_column, srid, type "
            "FROM public.geometry_columns "
            "WHERE f_table_schema = ? "
            "AND f_table_name = ? "
            "LIMIT 1"
        )
        query.addBindValue(schema)
        query.addBindValue(name)
        if not query.exec():
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
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
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
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
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
            if not query.exec(sql):
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
        self.setProperty("forceCenterOnParent", True)
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
        self.url_edit.setPlaceholderText(_rt("URL pública…"))
        layout.addWidget(self.url_edit)

        buttons = QDialogButtonBox(self)
        preview_btn = buttons.addButton(_rt("Pré-visualizar"), QDialogButtonBox.ButtonRole.ActionRole)
        load_btn = buttons.addButton(_rt("Carregar"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
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
        self.setWindowTitle(_rt("Catálogo de fontes disponíveis"))
        self.resize(760, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        info = QLabel(
            _rt("Lista completa de fontes suportadas pelo plugin. Algumas exigem configuração adicional, mas todas refletem cenários úteis para o ecossistema QGIS."),
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

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)
        _apply_i18n_widgets(self)
