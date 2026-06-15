# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import QObject, QRect, QRectF, QSize, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QColor, QFontMetrics, QIcon, QKeySequence, QPainter, QPalette, QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QMenu,
    QInputDialog,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSlider,
    QSplitter,
    QToolButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject, QgsVectorLayer

from .dashboard_add_dialog import DashboardAddDialog
from .dashboard_canvas import DashboardCanvas
from .dashboard_models import (
    DashboardChartBinding,
    DashboardChartItem,
    DashboardPage,
    DashboardProject,
    FieldBindingItem,
    ROLE_TOOLTIP,
    ROLE_VALUES,
    ROLE_X_AXIS,
    ROLE_Y_AXIS,
    binding_slot_definitions,
    is_binding_slot_compatible,
    normalize_aggregation,
    normalize_binding_role,
    normalize_chart_type,
    suggest_binding_slot,
)
from .dashboard_page_widget import DashboardPageWidget
from .dashboard_project_store import DashboardProjectStore, PROJECT_EXTENSION
from .field_list_helpers import normalize_field_kind
from .report_view.charts import ChartVisualState
from .model_view.model_builder_panel import (
    build_model_builder_panel,
    build_visual_type_buttons,
    builder_has_selection,
    chart_type_label,
    selected_builder_chart_type_from_buttons,
    set_chart_overflow_expanded,
    visual_type_specs,
)
from .model_view.model_cards import _ModelCardAction, _ModelClockIcon, _ModelRecentCard
from .model_view.model_data_panel import (
    build_model_data_panel,
    desired_data_panel_width,
    field_is_numeric,
    populate_builder_field_list,
    refresh_builder_data_fonts,
    sync_data_panel_chrome,
)
from .database_explorer import DatabaseMetadataService
from .model_view.model_database_panel import ModelDatabasePanel
from .model_view.model_header import build_model_header
from .model_view.model_canvas_style_dialog import (
    apply_canvas_style_to_source_meta,
    default_canvas_style,
    normalize_canvas_style,
    open_canvas_style_dialog,
)
from .walker_dialogs import WalkerMessageBox as QMessageBox, apply_walker_menu
from .model_view.model_project_controller import (
    normalize_loaded_project,
    normalize_project_source_meta,
    project_snapshot_payload,
    snapshot_signature,
    snapshot_state,
)
from .model_view.model_remote_projects import (
    DEFAULT_REMOTE_PROJECT_TABLE,
    ModelRemoteProjectService,
    RemoteProjectRecord,
    RemoteProjectScanResult,
    connection_key as remote_project_connection_key,
    normalize_remote_project_table_target,
)
from .model_view.model_toolbar import (
    toolbar_visuals_should_be_visible,
)
from .model_view.model_theme import (
    _force_model_white_background,
    _is_dark_theme,
    _model_panel_chevron_icon,
    _model_theme_color,
    _model_tinted_svg_icon,
    fill_model_theme_tokens,
)
from .model_view.model_visual_rebuild import (
    build_model_chart_item_from_layer,
    empty_chart_payload,
    rebuild_chart_item_from_binding,
)
from .slim_dialogs import slim_message
from .utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
from .utils.i18n_runtime import tr_text as _rt
from .utils.logging_utils import log_exception
from .visual_format_panel import VisualFormatPanel
from .walker_tooltips import set_walker_tooltip

_MODEL_SIDE_PANEL_COLLAPSED_WIDTH = 40
_MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH = 276
_MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH = 250
_MODEL_VISUAL_SIDE_PANEL_MAX_WIDTH = 360
_MODEL_DATA_PANEL_COLLAPSED_WIDTH = 40
_MODEL_DATABASE_PANEL_DEFAULT_WIDTH = 220
_MODEL_DATABASE_PANEL_MIN_WIDTH = 180
_MODEL_DATABASE_PANEL_MAX_WIDTH = 320
_MODEL_DATA_PANEL_MIN_WIDTH = 120
_MODEL_DATA_PANEL_DEFAULT_WIDTH = 148
_MODEL_DATA_PANEL_MAX_WIDTH = 320
_MODEL_RECENT_CARD_WIDTH = 212
_MODEL_RECENT_CARD_HEIGHT = 238
_MODEL_RECENT_CARD_GAP = 16
_MODEL_RECENT_ROW_GAP = 18
_MODEL_RECENTS_SECTION_HEIGHT = 28 + 16 + _MODEL_RECENT_CARD_HEIGHT
_MODEL_DEFAULT_FONT_SCALE = 0.88
_REMOTE_PROJECT_THREADS_IN_FLIGHT = []


class _ModelVerticalPanelLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("color: #111827; font-size: 12px; font-weight: 500; background: transparent;")

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


class _CurrentPageStackedWidget(QStackedWidget):
    def sizeHint(self):
        current = self.currentWidget()
        if current is not None:
            return current.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        if current is not None:
            return current.minimumSizeHint()
        return super().minimumSizeHint()


class _ModelRemoteProjectsWorker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, connection_meta: Dict, connection_key: str):
        super().__init__()
        self._connection_meta = dict(connection_meta or {})
        self._connection_key = str(connection_key or "")
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def _is_interruption_requested(self) -> bool:
        thread = QThread.currentThread()
        return bool(self._cancel_requested or (thread is not None and thread.isInterruptionRequested()))

    @pyqtSlot()
    def run(self):
        try:
            service = ModelRemoteProjectService(
                self._connection_meta,
                cancel_requested=self._is_interruption_requested,
            )
            result = service.load_recent_projects()
        except Exception as exc:  # pragma: no cover - worker boundary
            result = RemoteProjectScanResult([], False, str(exc or ""))
        self.finished.emit((self._connection_key, result, self._is_interruption_requested()))


def _retain_remote_project_thread(thread, worker):
    entry = (thread, worker)
    _REMOTE_PROJECT_THREADS_IN_FLIGHT.append(entry)

    def _release():
        try:
            _REMOTE_PROJECT_THREADS_IN_FLIGHT.remove(entry)
        except ValueError:
            pass

    thread.finished.connect(_release)


class ModelTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelTabRoot")
        self.setFont(ui_font())
        self._font_enforcer = attach_ui_font_enforcer(self)
        self.store = DashboardProjectStore()
        self.current_project: Optional[DashboardProject] = None
        self.current_path: str = ""
        self._dirty = False
        self._syncing_zoom_controls = False
        self._suspend_canvas_events = False
        self._is_adding_page = False
        self._builder_layers: Dict[str, QgsVectorLayer] = {}
        self._page_widgets: Dict[str, DashboardPageWidget] = {}
        self._selected_page_id: str = ""
        self._single_page_mode = True
        self.canvas: Optional[DashboardCanvas] = None
        self._history_undo: List[Dict[str, object]] = []
        self._history_redo: List[Dict[str, object]] = []
        self._history_current: Optional[Dict[str, object]] = None
        self._history_restoring = False
        self._history_limit = 80
        self._builder_panel_open = False
        self._visual_panel_open = False
        self._visual_side_collapsed = True
        self._visual_side_width = _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH
        self._database_panel_open = False
        self._database_panel_collapsed = False
        self._database_panel_width = _MODEL_DATABASE_PANEL_DEFAULT_WIDTH
        self._builder_database_layer: Optional[QgsVectorLayer] = None
        self._builder_database_layer_id = ""
        self._builder_database_layer_active = False
        self._selecting_database_layer_fields = False
        self._data_panel_collapsed = True
        self._data_panel_width = _MODEL_DATA_PANEL_DEFAULT_WIDTH
        self._toolbar_visuals_compact = False
        self._toolbar_visuals_sync_retries = 0
        self._recents_refresh_pending = False
        self._recents_columns = 0
        self._remote_project_records: List[RemoteProjectRecord] = []
        self._remote_project_loaded_key = ""
        self._remote_project_requested_key = ""
        self._remote_project_pending_meta: Dict = {}
        self._current_remote_project_connection_meta: Dict = {}
        self._remote_project_shutting_down = False
        self._remote_project_thread: Optional[QThread] = None
        self._remote_project_worker: Optional[_ModelRemoteProjectsWorker] = None
        self._builder_selected_item_id: str = ""
        self._builder_field_catalog: Dict[str, List[Dict[str, str]]] = {}
        self._builder_visual_specs = visual_type_specs()
        self.builder_visual_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 4, 3)
        root.setSpacing(4)

        header_parts = build_model_header(
            self,
            configure_toolbar_icon_button=self._configure_toolbar_icon_button,
            build_visual_type_buttons=self._build_visual_type_buttons,
        )
        for name, widget in header_parts.__dict__.items():
            setattr(self, name, widget)
        root.addWidget(self.header, 0)
        root.addWidget(self.filters_bar, 0)

        self.page_strip = None

        self.body_stack = _CurrentPageStackedWidget(self)
        self.body_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.body_stack.setMinimumSize(0, 0)
        root.addWidget(self.body_stack, 1)

        self.empty_page = QWidget(self.body_stack)
        self.empty_page.setObjectName("ModelStartPage")
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(28, 24, 28, 24)
        empty_layout.setSpacing(26)

        self.model_home_actions = QWidget(self.empty_page)
        self.model_home_actions.setObjectName("ModelHomeActions")
        home_actions_layout = QGridLayout(self.model_home_actions)
        home_actions_layout.setContentsMargins(0, 0, 0, 0)
        home_actions_layout.setHorizontalSpacing(16)
        home_actions_layout.setVerticalSpacing(0)

        self.model_new_card = _ModelCardAction(_rt("New"), "", "Walker-New.svg", self.model_home_actions)
        self.model_open_card = _ModelCardAction(_rt("Open"), "", "Walker-Open.svg", self.model_home_actions)
        self.model_import_card = _ModelCardAction(
            _rt("Remote Database"),
            _rt("Connect to remote database sources"),
            "Dataset.svg",
            self.model_home_actions,
        )
        for column, card in enumerate((self.model_new_card, self.model_open_card, self.model_import_card)):
            home_actions_layout.addWidget(card, 0, column)
            home_actions_layout.setColumnStretch(column, 1)
        empty_layout.addWidget(self.model_home_actions, 0)

        self.recents_card = QFrame(self.empty_page)
        self.recents_card.setObjectName("ModelRecentsCard")
        self.recents_card.setAttribute(Qt.WA_StyledBackground, True)
        self.recents_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        recents_layout = QVBoxLayout(self.recents_card)
        recents_layout.setContentsMargins(0, 0, 0, 0)
        recents_layout.setSpacing(16)

        recents_header = QHBoxLayout()
        recents_header.setContentsMargins(0, 0, 0, 0)
        recents_header.setSpacing(7)
        self.recents_clock_icon = _ModelClockIcon(self.recents_card)
        recents_header.addWidget(self.recents_clock_icon, 0, Qt.AlignVCenter)
        recents_title = QLabel(_rt("Recent Panels"))
        recents_title.setObjectName("ModelRecentsTitle")
        recents_header.addWidget(recents_title, 0, Qt.AlignVCenter)
        recents_header.addStretch(1)
        recents_layout.addLayout(recents_header)

        self.recents_placeholder = QLabel(_rt("No recent panels found."))
        self.recents_placeholder.setObjectName("ModelRecentsPlaceholder")
        self.recents_placeholder.setWordWrap(True)
        recents_layout.addWidget(self.recents_placeholder)

        self.recents_scroll = QScrollArea(self.recents_card)
        self.recents_scroll.setObjectName("ModelRecentsScroll")
        self.recents_scroll.setWidgetResizable(True)
        self.recents_scroll.setFrameShape(QFrame.NoFrame)
        self.recents_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recents_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.recents_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)
        self.recents_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.recents_container = QWidget(self.recents_scroll)
        self.recents_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.recents_layout = QGridLayout(self.recents_container)
        self.recents_layout.setContentsMargins(0, 0, 0, 0)
        self.recents_layout.setHorizontalSpacing(_MODEL_RECENT_CARD_GAP)
        self.recents_layout.setVerticalSpacing(_MODEL_RECENT_ROW_GAP)
        self.recents_scroll.setWidget(self.recents_container)
        recents_layout.addWidget(self.recents_scroll)

        empty_layout.addWidget(self.recents_card, 0, Qt.AlignTop)

        self.remote_projects_card = QFrame(self.empty_page)
        self.remote_projects_card.setObjectName("ModelRemoteProjectsCard")
        self.remote_projects_card.setAttribute(Qt.WA_StyledBackground, True)
        self.remote_projects_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        remote_projects_layout = QVBoxLayout(self.remote_projects_card)
        remote_projects_layout.setContentsMargins(0, 0, 0, 0)
        remote_projects_layout.setSpacing(16)

        remote_projects_header = QHBoxLayout()
        remote_projects_header.setContentsMargins(0, 0, 0, 0)
        remote_projects_header.setSpacing(7)
        self.remote_projects_icon = QLabel("", self.remote_projects_card)
        self.remote_projects_icon.setObjectName("ModelRemoteProjectsIcon")
        self.remote_projects_icon.setFixedSize(18, 18)
        self.remote_projects_icon.setPixmap(_model_tinted_svg_icon("Dataset.svg", 18).pixmap(18, 18))
        self.remote_projects_icon.setAlignment(Qt.AlignCenter)
        remote_projects_header.addWidget(self.remote_projects_icon, 0, Qt.AlignVCenter)
        remote_projects_title = QLabel(_rt("Database Panels"))
        remote_projects_title.setObjectName("ModelRemoteProjectsTitle")
        remote_projects_header.addWidget(remote_projects_title, 0, Qt.AlignVCenter)
        remote_projects_header.addStretch(1)
        remote_projects_layout.addLayout(remote_projects_header)

        self.remote_projects_placeholder = QLabel(_rt("No database panels found."))
        self.remote_projects_placeholder.setObjectName("ModelRemoteProjectsPlaceholder")
        self.remote_projects_placeholder.setWordWrap(True)
        remote_projects_layout.addWidget(self.remote_projects_placeholder)

        self.remote_projects_scroll = QScrollArea(self.remote_projects_card)
        self.remote_projects_scroll.setObjectName("ModelRemoteProjectsScroll")
        self.remote_projects_scroll.setWidgetResizable(True)
        self.remote_projects_scroll.setFrameShape(QFrame.NoFrame)
        self.remote_projects_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.remote_projects_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.remote_projects_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)
        self.remote_projects_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.remote_projects_container = QWidget(self.remote_projects_scroll)
        self.remote_projects_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.remote_projects_layout = QGridLayout(self.remote_projects_container)
        self.remote_projects_layout.setContentsMargins(0, 0, 0, 0)
        self.remote_projects_layout.setHorizontalSpacing(_MODEL_RECENT_CARD_GAP)
        self.remote_projects_layout.setVerticalSpacing(_MODEL_RECENT_ROW_GAP)
        self.remote_projects_scroll.setWidget(self.remote_projects_container)
        remote_projects_layout.addWidget(self.remote_projects_scroll)

        self.remote_projects_card.setVisible(False)
        empty_layout.addWidget(self.remote_projects_card, 0, Qt.AlignTop)
        empty_layout.addStretch(1)

        self.canvas_page = QWidget(self.body_stack)
        canvas_page_layout = QHBoxLayout(self.canvas_page)
        canvas_page_layout.setContentsMargins(0, 0, 0, 0)
        canvas_page_layout.setSpacing(0)

        self.canvas_splitter = QSplitter(Qt.Horizontal, self.canvas_page)
        self.canvas_splitter.setObjectName("ModelCanvasSplitter")
        self.canvas_splitter.setChildrenCollapsible(False)
        canvas_page_layout.addWidget(self.canvas_splitter, 1)

        self.page_stack = QStackedWidget(self.canvas_splitter)
        self.page_stack.setObjectName("ModelPageStack")
        self.page_stack.currentChanged.connect(self._handle_page_stack_current_changed)
        self.canvas_splitter.addWidget(self.page_stack)

        self.visual_side_panel = QFrame(self.canvas_splitter)
        self.visual_side_panel.setObjectName("ModelVisualSidePanel")
        _force_model_white_background(self.visual_side_panel)
        self.visual_side_panel.setMinimumWidth(_MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH)
        self.visual_side_panel.setMaximumWidth(_MODEL_VISUAL_SIDE_PANEL_MAX_WIDTH)
        visual_side_layout = QVBoxLayout(self.visual_side_panel)
        visual_side_layout.setContentsMargins(8, 8, 8, 8)
        visual_side_layout.setSpacing(6)

        self.visual_tab_bar = QFrame(self.visual_side_panel)
        self.visual_tab_bar.setObjectName("ModelVisualPanelTabBar")
        visual_tab_layout = QHBoxLayout(self.visual_tab_bar)
        visual_tab_layout.setContentsMargins(4, 4, 4, 4)
        visual_tab_layout.setSpacing(4)
        self.visual_data_tab_btn = QPushButton(_rt("Adicionar dados"), self.visual_tab_bar)
        self.visual_data_tab_btn.setObjectName("ModelVisualPanelTabButton")
        self.visual_data_tab_btn.setCheckable(True)
        self.visual_data_tab_btn.setCursor(Qt.PointingHandCursor)
        self.visual_data_tab_btn.setFlat(True)
        self.visual_data_tab_btn.setAutoDefault(False)
        self.visual_data_tab_btn.setDefault(False)
        self.visual_data_tab_btn.setToolTip("")
        self.visual_data_tab_btn.setStatusTip("")
        self.visual_data_tab_btn.setWhatsThis("")
        self.visual_data_tab_btn.clicked.connect(lambda checked=False: self._set_visual_side_tab("build"))
        visual_tab_layout.addWidget(self.visual_data_tab_btn, 1)
        self.visual_format_tab_btn = QPushButton(_rt("Formatar visual"), self.visual_tab_bar)
        self.visual_format_tab_btn.setObjectName("ModelVisualPanelTabButton")
        self.visual_format_tab_btn.setCheckable(True)
        self.visual_format_tab_btn.setCursor(Qt.PointingHandCursor)
        self.visual_format_tab_btn.setFlat(True)
        self.visual_format_tab_btn.setAutoDefault(False)
        self.visual_format_tab_btn.setDefault(False)
        self.visual_format_tab_btn.setToolTip("")
        self.visual_format_tab_btn.setStatusTip("")
        self.visual_format_tab_btn.setWhatsThis("")
        self.visual_format_tab_btn.clicked.connect(lambda checked=False: self._set_visual_side_tab("format"))
        visual_tab_layout.addWidget(self.visual_format_tab_btn, 1)
        self.visual_side_toggle_btn = QToolButton(self.visual_tab_bar)
        self.visual_side_toggle_btn.setObjectName("ModelSidePanelToggle")
        self.visual_side_toggle_btn.setAutoRaise(True)
        self.visual_side_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.visual_side_toggle_btn.setFixedSize(22, 22)
        self.visual_side_toggle_btn.clicked.connect(self._toggle_visual_side_panel)
        visual_tab_layout.addWidget(self.visual_side_toggle_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
        visual_side_layout.addWidget(self.visual_tab_bar, 0)

        self.visual_side_stack = QStackedWidget(self.visual_side_panel)
        self.visual_side_stack.setObjectName("ModelVisualSideStack")
        _force_model_white_background(self.visual_side_stack)
        self.builder_panel = self._build_chart_builder_panel(self.visual_side_stack)
        self.visual_side_stack.addWidget(self.builder_panel)
        self.visual_panel = VisualFormatPanel(self.visual_side_stack)
        self.visual_panel.setMinimumWidth(_MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH)
        self.visual_panel.setMaximumWidth(16777215)
        self.visual_panel.closeRequested.connect(lambda: self._set_visual_panel_open(False))
        self.visual_side_stack.addWidget(self.visual_panel)
        visual_side_layout.addWidget(self.visual_side_stack, 1)
        self.visual_side_collapsed_rail = QFrame(self.visual_side_panel)
        self.visual_side_collapsed_rail.setObjectName("ModelSidePanelCollapsedRail")
        self.visual_side_collapsed_rail.hide()
        visual_rail_layout = QVBoxLayout(self.visual_side_collapsed_rail)
        visual_rail_layout.setContentsMargins(2, 6, 2, 6)
        visual_rail_layout.setSpacing(8)
        self.visual_side_collapsed_btn = QToolButton(self.visual_side_collapsed_rail)
        self.visual_side_collapsed_btn.setObjectName("ModelSidePanelToggle")
        self.visual_side_collapsed_btn.setAutoRaise(True)
        self.visual_side_collapsed_btn.setCursor(Qt.PointingHandCursor)
        self.visual_side_collapsed_btn.setFixedSize(22, 22)
        self.visual_side_collapsed_btn.setStyleSheet(
            "QToolButton#ModelSidePanelToggle { background: transparent; border: none; padding: 0px; }"
        )
        self.visual_side_collapsed_btn.clicked.connect(self._toggle_visual_side_panel)
        visual_rail_layout.addWidget(self.visual_side_collapsed_btn, 0, Qt.AlignHCenter | Qt.AlignTop)
        self.visual_side_collapsed_title = _ModelVerticalPanelLabel(_rt("Visualizações"), self.visual_side_collapsed_rail)
        self.visual_side_collapsed_title.setObjectName("ModelSidePanelCollapsedTitle")
        visual_rail_layout.addWidget(self.visual_side_collapsed_title, 0, Qt.AlignHCenter | Qt.AlignTop)
        visual_rail_layout.addStretch(1)
        visual_side_layout.addWidget(self.visual_side_collapsed_rail, 1)
        self._active_visual_side_tab = "build"
        self._apply_visual_tab_button_styles()
        self._sync_visual_side_tab_buttons()
        self._sync_visual_side_panel_chrome()
        self._apply_visual_side_panel_styles()
        self.visual_side_panel.setVisible(False)
        self.canvas_splitter.addWidget(self.visual_side_panel)

        self.database_panel = self._build_database_panel(self.canvas_splitter)
        self.model_database_panel = self.database_panel
        self.database_panel.setMinimumWidth(_MODEL_DATABASE_PANEL_MIN_WIDTH)
        self.database_panel.setMaximumWidth(_MODEL_DATABASE_PANEL_MAX_WIDTH)
        self.database_panel.setVisible(False)
        self.canvas_splitter.addWidget(self.database_panel)

        self.data_panel = self._build_data_panel(self.canvas_splitter)
        self.data_panel.setMinimumWidth(_MODEL_DATA_PANEL_MIN_WIDTH)
        self.data_panel.setMaximumWidth(_MODEL_DATA_PANEL_MAX_WIDTH)
        self.data_panel.setVisible(False)
        self.canvas_splitter.addWidget(self.data_panel)
        self._sync_database_panel_chrome()
        self._sync_data_panel_chrome()
        self._apply_builder_panel_theme_overrides()
        self.canvas_splitter.setStretchFactor(0, 1)
        self.canvas_splitter.setStretchFactor(1, 0)
        self.canvas_splitter.setStretchFactor(2, 0)
        self.canvas_splitter.setStretchFactor(3, 0)
        self.canvas_splitter.setSizes([
            900,
            _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH,
            0,
            _MODEL_DATA_PANEL_DEFAULT_WIDTH,
        ])
        try:
            toolbar_layout = self.toolbar_strip.layout() if hasattr(self, "toolbar_strip") else None
            if toolbar_layout is not None and hasattr(toolbar_layout, "removeWidget"):
                toolbar_layout.removeWidget(self.clear_filters_btn)
        except Exception:
            log_exception("falha opcional ignorada")
        self.clear_filters_btn.setParent(self.canvas_page)
        self.clear_filters_btn.setVisible(False)
        self.clear_filters_btn.raise_()

        self.body_stack.addWidget(self.empty_page)
        self.body_stack.addWidget(self.canvas_page)

        self.footer_bar = QFrame(self)
        self.footer_bar.setObjectName("ModelFooterBar")
        self.footer_bar.setAttribute(Qt.WA_StyledBackground, True)
        self.footer_bar.setFixedHeight(42)
        self.footer_bar.setVisible(False)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(0, 3, 0, 3)
        footer_layout.setSpacing(6)

        footer_layout.addStretch(1)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ModelZoomLabel")
        footer_layout.addWidget(self.zoom_label, 0)
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setObjectName("ModelZoomButton")
        self.zoom_out_btn.setFixedSize(20, 16)
        footer_layout.addWidget(self.zoom_out_btn, 0)
        self.zoom_reset_btn = QPushButton("100%")
        self.zoom_reset_btn.setObjectName("ModelZoomButton")
        self.zoom_reset_btn.setFixedSize(40, 16)
        footer_layout.addWidget(self.zoom_reset_btn, 0)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setObjectName("ModelZoomSlider")
        self.zoom_slider.setRange(60, 200)
        self.zoom_slider.setSingleStep(5)
        self.zoom_slider.setPageStep(15)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFocusPolicy(Qt.NoFocus)
        footer_layout.addWidget(self.zoom_slider, 0)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("ModelZoomButton")
        self.zoom_in_btn.setFixedSize(20, 16)
        footer_layout.addWidget(self.zoom_in_btn, 0)
        root.addWidget(self.footer_bar, 0)

        self.new_btn.clicked.connect(self.new_project)
        self.open_btn.clicked.connect(self.open_project)
        self.model_new_card.clicked.connect(self.new_project)
        self.model_open_card.clicked.connect(self.open_project)
        self.model_import_card.clicked.connect(self._open_model_database_menu)
        self.save_btn.clicked.connect(self.save_project)
        self.save_as_btn.clicked.connect(lambda: self.save_project(save_as=True))
        self.export_btn.clicked.connect(self.export_project)
        self.undo_btn.clicked.connect(self._undo_last_action)
        self.redo_btn.clicked.connect(self._redo_last_action)
        self.create_chart_btn.toggled.connect(self._handle_create_chart_toggle)
        self.format_visual_btn.toggled.connect(self._handle_format_visual_toggle)
        self.database_fields_btn.toggled.connect(self._handle_database_panel_toggle)
        self.data_fields_btn.toggled.connect(self._handle_data_fields_toggle)
        self.settings_btn.clicked.connect(self._open_canvas_style_settings)
        self.clear_filters_btn.clicked.connect(self._clear_model_filters)
        self.zoom_out_btn.clicked.connect(self._zoom_canvas_out)
        self.zoom_reset_btn.clicked.connect(self._zoom_canvas_reset)
        self.zoom_in_btn.clicked.connect(self._zoom_canvas_in)
        self.zoom_slider.valueChanged.connect(self._zoom_slider_changed)
        self.edit_mode_btn.toggled.connect(self.set_edit_mode)
        self.mode_toggle.toggled.connect(self._handle_mode_toggle)
        self.close_project_btn.clicked.connect(self.close_project)
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.activated.connect(self._undo_last_action)
        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._shortcut_redo.activated.connect(self._redo_last_action)
        self._shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_redo_alt.activated.connect(self._redo_last_action)
        try:
            from .browser_integration import connection_registry

            connection_registry.connectionsChanged.connect(self._refresh_model_database_status)
        except Exception:
            log_exception("falha opcional ignorada")
        QTimer.singleShot(0, self._auto_connect_saved_model_databases)

        self.setStyleSheet(
            """
            QWidget#ModelTabRoot {
                background: #FFFFFF;
            }
            QWidget#ModelStartPage,
            QWidget#ModelHomeActions,
            QWidget#ModelRecentCardContent {
                background: #FFFFFF;
            }
            QFrame#ModelHeader {
                background: transparent;
                border: none;
            }
            QFrame#ModelToolbarStrip {
                background: #FFFFFF;
                border: 1px solid #D6D9E0;
                border-radius: 8px;
            }
            QFrame#ModelToolbarSeparator {
                min-width: 1px;
                max-width: 1px;
                margin: 4px 6px;
                background: #E5E7EB;
            }
            QFrame#ModelToolbarVisualTypes {
                background: transparent;
                border: none;
            }
            QToolButton#ModelVisualOverflowButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 30px;
                max-height: 30px;
                border: 1px solid #D1D5DB;
                border-radius: 5px;
                background: #FFFFFF;
                color: #475569;
                padding: 0px;
            }
            QToolButton#ModelVisualOverflowButton:hover {
                background: #F8FAFC;
                border-color: #CBD5E1;
                color: #111827;
            }
            QToolButton#ModelVisualOverflowButton:pressed,
            QToolButton#ModelVisualOverflowButton:checked {
                background: #F1F5F9;
                border-color: #CBD5E1;
                color: #111827;
            }
            QWidget#ModelModeSwitchWrap {
                background: transparent;
            }
            QLabel#ModelModeStateLabel {
                color: #374151;
                font-size: 11px;
                font-weight: 400;
            }
            QLabel#ModelModeStateLabel[modeState="preview"] {
                color: #6B7280;
            }
            QWidget#ModelModeToggle {
                background: transparent;
            }
            QLabel#ModelHint,
            QLabel#ModelRecentsPlaceholder,
            QLabel#ModelRemoteProjectsPlaceholder {
                color: #6B7280;
                font-size: 12px;
            }
            QFrame#ModelFiltersBar {
                background: #F8FAFC;
                border: 1px solid #D6D9E0;
                border-radius: 12px;
            }
            QLabel#ModelFiltersLabel {
                color: #374151;
                font-size: 12px;
            }
            QFrame#ModelRecentsCard,
            QFrame#ModelRemoteProjectsCard {
                background: #FFFFFF;
                border: none;
                border-radius: 0px;
            }
            QScrollArea#ModelRecentsScroll,
            QScrollArea#ModelRemoteProjectsScroll,
            QScrollArea#ModelRecentsScroll > QWidget,
            QScrollArea#ModelRemoteProjectsScroll > QWidget,
            QScrollArea#ModelRecentsScroll > QWidget > QWidget,
            QScrollArea#ModelRemoteProjectsScroll > QWidget > QWidget {
                background: transparent;
                border: none;
            }
            QFrame#ModelFooterBar {
                background: #FFFFFF;
                border-top: 1px solid #E5E7EB;
            }
            QWidget#ModelPageStrip {
                background: transparent;
            }
            QScrollArea#ModelPageStripScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#ModelPageStripContent {
                background: transparent;
            }
            QWidget#ModelPageStripTab {
                background: transparent;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                margin-right: 2px;
                color: #6B7280;
                font-size: 12px;
                font-weight: 500;
            }
            QWidget#ModelPageStripTab:hover {
                background: #F8FAFC;
                color: #111827;
            }
            QWidget#ModelPageStripTab[selected="true"] {
                color: #111827;
                font-weight: 600;
                border-bottom-color: #5B4CF0;
                background: transparent;
            }
            QLabel#ModelPageStripTabTitle {
                color: #6B7280;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#ModelPageStripTabTitle[selected="true"] {
                color: #111827;
                font-weight: 600;
            }
            QLineEdit#ModelPageStripTabEdit {
                min-height: 22px;
                border: 1px solid #818CF8;
                border-radius: 6px;
                padding: 0 6px;
                background: #FFFFFF;
                color: #111827;
                font-size: 12px;
            }
            QToolButton#ModelPageStripTabMenu,
            QToolButton#ModelPageStripTabClose,
            QToolButton#ModelPageStripNavButton {
                min-width: 16px;
                min-height: 16px;
                border: none;
                background: transparent;
                color: #6B7280;
                font-size: 12px;
                padding: 0px;
            }
            QToolButton#ModelPageStripTabMenu:hover,
            QToolButton#ModelPageStripTabClose:hover,
            QToolButton#ModelPageStripNavButton:hover {
                color: #111827;
                background: #F3F4F6;
                border-radius: 6px;
            }
            QToolButton#ModelPageStripAddButton {
                min-height: 24px;
                min-width: 66px;
                padding: 0 10px;
                color: #4B5563;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 500;
            }
            QToolButton#ModelPageStripAddButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
                color: #111827;
            }
            QToolButton#ModelPageStripAddButton:pressed {
                background: #E5E7EB;
            }
            QFrame#ModelBuilderPanel {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
            QFrame#ModelVisualSidePanel {
                background: #FFFFFF;
                border: 1px solid #DCE3EC;
                border-radius: 2px;
            }
            QFrame#ModelVisualSidePanel QWidget,
            QFrame#ModelVisualSidePanel QFrame,
            QFrame#ModelVisualSidePanel QScrollArea,
            QFrame#ModelVisualSidePanel QAbstractScrollArea,
            QFrame#ModelVisualSidePanel QAbstractScrollArea::viewport {
                background-color: #FFFFFF;
            }
            QFrame#ModelVisualSidePanel QWidget,
            QFrame#ModelVisualSidePanel QFrame,
            QFrame#ModelVisualSidePanel QScrollArea,
            QFrame#ModelVisualSidePanel QAbstractScrollArea,
            QFrame#ModelVisualSidePanel QAbstractScrollArea::viewport {
                background-color: #FFFFFF;
            }
            QFrame#ModelVisualSidePanel[collapsed="true"] {
                border-color: #E2E8F0;
            }
            QSplitter#ModelCanvasSplitter {
                background: transparent;
            }
            QSplitter#ModelCanvasSplitter::handle {
                background: transparent;
                width: 8px;
                margin: 0px 2px;
            }
            QSplitter#ModelCanvasSplitter::handle:hover {
                background: #E2E8F0;
            }
            QFrame#ModelVisualPanelTabBar {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 2px;
            }
            QFrame#ModelSidePanelCollapsedRail {
                background: transparent;
                border: none;
            }
            QLabel#ModelSidePanelCollapsedTitle {
                color: #111827;
                font-size: 8pt;
                font-weight: 500;
                background: transparent;
            }
            QToolButton#ModelSidePanelToggle,
            QToolButton#ModelDataPanelToggle {
                border: none;
                background: transparent;
                color: #475569;
                font-size: 14px;
                font-weight: 500;
                padding: 0px;
            }
            QToolButton#ModelSidePanelToggle:hover,
            QToolButton#ModelDataPanelToggle:hover {
                background: #F1F5F9;
                border-radius: 4px;
                color: #111827;
            }
            QStackedWidget#ModelVisualSideStack {
                background: #FFFFFF;
                border: none;
            }
            QStackedWidget#ModelVisualSideStack > QWidget {
                background: #FFFFFF;
            }
            QPushButton#ModelVisualPanelTabButton {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                color: #334155;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton#ModelVisualPanelTabButton:hover {
                background: #F8FAFC;
                border-color: #D7DEE8;
            }
            QPushButton#ModelVisualPanelTabButton:checked {
                background: #F3F4F6;
                border-color: #D1D5DB;
            }
            QScrollArea#ModelBuilderScroll {
                border: none;
                background: #FFFFFF;
            }
            QWidget#ModelBuilderScrollViewport {
                background: #FFFFFF;
            }
            QWidget#ModelBuilderHost {
                background: #FFFFFF;
            }
            QLabel#ModelBuilderTitle {
                color: #0F172A;
                font-size: 14px;
                font-weight: 500;
            }
            QLabel#ModelBuilderHint {
                color: #64748B;
                font-size: 11px;
                font-weight: 400;
            }
            QFrame#ModelBuilderSection {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 6px;
            }
            QFrame#ModelBuilderPlainSection {
                background: #FFFFFF;
                border: none;
                border-radius: 0px;
            }
            QFrame#ModelBuilderVisualsSection {
                background: #FFFFFF;
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 6px;
            }
            QFrame#ModelBuilderVisualsSection:hover {
                border-color: rgba(17, 24, 39, 0.14);
            }
            QFrame#ModelBuilderSoftDividerSection {
                background: #FFFFFF;
                border: 1px solid #E5EAF1;
                border-radius: 5px;
            }
            QFrame#ModelBuilderFieldsPanel {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 2px;
            }
            QFrame#ModelBuilderDataPanel {
                background: #FFFFFF;
                border: 1px solid rgba(15, 23, 42, 0.06);
                border-radius: 2px;
            }
            QFrame#ModelBuilderDataPanel QWidget,
            QFrame#ModelBuilderDataPanel QFrame,
            QFrame#ModelBuilderDataPanel QListWidget,
            QFrame#ModelBuilderDataPanel QAbstractScrollArea,
            QFrame#ModelBuilderDataPanel QAbstractScrollArea::viewport {
                background-color: #FFFFFF;
            }
            QWidget#ModelDataPanelBody {
                background: #FFFFFF;
            }
            QWidget#ModelDataFieldsBody {
                background: #FFFFFF;
            }
            QFrame#ModelBuilderDataSection {
                background: #FFFFFF;
                border: none;
            }
            QFrame#ModelBuilderDataPanel QLabel#ModelBuilderTitle {
                color: #4B5563;
                font-size: 12px;
                font-weight: 500;
            }
            QFrame#ModelBuilderDataPanel QLabel#ModelBuilderFieldLabel {
                color: #6B7280;
                font-size: 10px;
                font-weight: 400;
            }
            QFrame#ModelBuilderDataPanel QComboBox#ModelBuilderCombo {
                min-height: 28px;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 11px;
            }
            QFrame#ModelBuilderFieldsHeader {
                background: #FFFFFF;
                border: none;
                border-bottom: 1px solid rgba(15, 23, 42, 0.06);
            }
            QLabel#ModelBuilderSectionTitle {
                color: #0F172A;
                font-size: 11px;
                font-weight: 500;
            }
            QToolButton#ModelVisualTypeButton {
                min-width: 32px;
                max-width: 32px;
                min-height: 30px;
                max-height: 30px;
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                color: #475569;
                padding: 0px;
                font-size: 10px;
                font-weight: 500;
            }
            QToolButton#ModelVisualTypeButton:hover {
                background: #F3F4F6;
                border-color: rgba(17, 24, 39, 0.10);
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #F3F4F6;
                color: #111827;
                border-color: rgba(17, 24, 39, 0.14);
            }
            QToolButton#ModelVisualTypeButton:checked:hover {
                background: #E5E7EB;
                color: #111827;
                border-color: rgba(17, 24, 39, 0.18);
            }
            QFrame#ModelBuilderEmptyState {
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QFrame#ModelBuilderEmptyStateCard {
                background: #F3F4F6;
                background-color: #F3F4F6;
                border: none;
                border-radius: 2px;
            }
            QLabel#ModelBuilderEmptyStateTitle {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#ModelBuilderEmptyStateLabel {
                color: #334155;
                font-size: 12px;
                font-weight: 400;
                background: transparent;
            }
            QToolButton#ModelBuilderEmptyStateClose {
                background: transparent;
                border: none;
                color: #334155;
                padding: 0px;
                font-size: 18px;
                font-weight: 300;
            }
            QToolButton#ModelBuilderEmptyStateClose:hover {
                background: #E5E7EB;
                border-radius: 2px;
            }
            QListWidget#ModelBuilderFieldList {
                border: 1px solid rgba(17, 24, 39, 0.06);
                border-radius: 6px;
                background: #FFFFFF;
                color: #0F172A;
                padding: 4px;
                outline: 0;
                font-size: 12px;
            }
            QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList {
                border-radius: 2px;
                padding: 2px;
                font-size: 11px;
            }
            QWidget#ModelBuilderFieldListViewport {
                background: #FFFFFF;
            }
            QListWidget#ModelBuilderFieldList::item {
                padding: 2px 6px;
                margin: 0;
                border-radius: 2px;
            }
            QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList::item {
                min-height: 22px;
                padding: 2px 5px;
            }
            QListWidget#ModelBuilderFieldList::item:hover {
                background: rgba(17, 24, 39, 0.035);
            }
            QListWidget#ModelBuilderFieldList::item:selected {
                background: rgba(81, 96, 116, 0.12);
                color: #111827;
            }
            QLabel#ModelBuilderFieldLabel {
                color: #6B7280;
                font-size: 11px;
                font-weight: 400;
            }
            QFrame#ModelBindingSlot {
                background: #FFFFFF;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 4px;
                min-height: 42px;
            }
            QFrame#ModelBindingSlot[filled="true"] {
                border-color: rgba(148, 163, 184, 0.36);
                background: #FFFFFF;
            }
            QFrame#ModelBindingSlot[dropActive="true"] {
                border-color: rgba(96, 165, 250, 0.45);
                background: rgba(239, 246, 255, 0.55);
            }
            QLabel#ModelBindingSlotLabel {
                color: #475569;
                font-size: 10px;
                font-weight: 500;
            }
            QFrame#ModelBindingSlotChips {
                background: transparent;
            }
            QFrame#ModelBindingFieldChip {
                background: #FFFFFF;
                border: 1px solid rgba(148, 163, 184, 0.42);
                border-radius: 3px;
                min-height: 22px;
                max-height: 24px;
            }
            QLabel#ModelBindingFieldBadge {
                background: #EEF2FF;
                color: #334155;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 2px;
                min-width: 24px;
                max-width: 26px;
                min-height: 16px;
                font-size: 8px;
                font-weight: 600;
            }
            QLabel#ModelBindingFieldName {
                color: #111827;
                font-size: 10px;
                font-weight: 400;
                min-width: 0px;
            }
            QLabel#ModelBindingSlotValue {
                color: #94A3B8;
                font-size: 9px;
                font-weight: 400;
            }
            QComboBox#ModelBindingAggregationCombo {
                min-height: 18px;
                max-height: 18px;
                min-width: 58px;
                max-width: 58px;
                border: 1px solid rgba(148, 163, 184, 0.32);
                border-radius: 2px;
                padding: 0 2px;
                background: #F8FAFC;
                color: #334155;
                font-size: 9px;
            }
            QToolButton#ModelBindingSlotRemove {
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                padding: 0;
            }
            QToolButton#ModelBindingSlotRemove:hover {
                background: rgba(239, 68, 68, 0.08);
                border-color: rgba(239, 68, 68, 0.20);
            }
            QToolButton#ModelBindingSlotMove {
                min-width: 14px;
                max-width: 14px;
                min-height: 16px;
                max-height: 16px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                color: #64748B;
                padding: 0;
                font-size: 9px;
            }
            QToolButton#ModelBindingSlotMove:hover {
                background: #F1F5F9;
                border-color: rgba(148, 163, 184, 0.24);
            }
            QComboBox#ModelBuilderCombo,
            QLineEdit#ModelBuilderLineEdit,
            QSpinBox#ModelBuilderSpin {
                min-height: 23px;
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 2px;
                padding: 2px 6px;
                background: rgba(255, 255, 255, 0.96);
                color: #111827;
                font-size: 11px;
            }
            QComboBox#ModelBuilderCombo:focus,
            QLineEdit#ModelBuilderLineEdit:focus,
            QSpinBox#ModelBuilderSpin:focus {
                border-color: rgba(81, 96, 116, 0.48);
            }
            QSpinBox#ModelBuilderSpin::up-button,
            QSpinBox#ModelBuilderSpin::down-button {
                width: 14px;
                background: #F8FAFC;
                border-left: 1px solid #E2E8F0;
            }
            QSpinBox#ModelBuilderSpin::up-button {
                border-top-right-radius: 6px;
                border-bottom: 1px solid #E2E8F0;
            }
            QSpinBox#ModelBuilderSpin::down-button {
                border-bottom-right-radius: 6px;
            }
            QSpinBox#ModelBuilderSpin::up-button:hover,
            QSpinBox#ModelBuilderSpin::down-button:hover {
                background: #EEF2F7;
            }
            QPushButton#ModelBuilderPrimaryButton {
                border: 1px solid rgba(17, 24, 39, 0.08);
                border-radius: 2px;
                background: #FFFFFF;
                color: #111827;
                padding: 4px 8px;
                min-height: 24px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton#ModelBuilderPrimaryButton:hover {
                background: #FFFFFF;
                border-color: rgba(17, 24, 39, 0.12);
            }
            QLabel#ModelRecentsTitle,
            QLabel#ModelRemoteProjectsTitle {
                color: #111827;
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#ModelRecentsClockIcon,
            QLabel#ModelRemoteProjectsIcon {
                color: #6B7280;
                font-size: 22px;
                font-weight: 400;
            }
            QLabel#ModelZoomLabel {
                color: #6B7280;
                font-size: 9px;
                font-weight: 500;
            }
            QSlider#ModelZoomSlider {
                background: transparent;
                min-height: 10px;
            }
            QSlider#ModelZoomSlider::groove:horizontal {
                height: 2px;
                background: #E5E7EB;
                border-radius: 1px;
            }
            QSlider#ModelZoomSlider::sub-page:horizontal {
                background: #C7D2FE;
                border-radius: 1px;
            }
            QSlider#ModelZoomSlider::handle:horizontal {
                width: 8px;
                margin: -4px 0;
                border-radius: 3px;
                background: #6366F1;
                border: 1px solid #4F46E5;
            }
            QSlider#ModelZoomSlider::handle:horizontal:hover {
                background: #4F46E5;
            }
            QPushButton#ModelActionButton {
                min-height: 28px;
                padding: 0 10px;
                color: #374151;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-weight: 400;
            }
            QPushButton#ModelActionButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton#ModelActionButton:pressed {
                background: #E5E7EB;
            }
            QPushButton#ModelToolbarButton,
            QToolButton#ModelToolbarButton {
                min-height: 30px;
                padding: 0 4px;
                color: #111827;
                background: transparent;
                border: none;
                border-radius: 6px;
                font-weight: 400;
            }
            QPushButton#ModelToolbarButton:hover,
            QToolButton#ModelToolbarButton:hover {
                background: #F3F4F6;
                color: #111827;
            }
            QPushButton#ModelToolbarButton:checked,
            QToolButton#ModelToolbarButton:checked {
                background: #F3F4F6;
                color: #111827;
            }
            QPushButton#ModelToolbarButton:checked:hover,
            QToolButton#ModelToolbarButton:checked:hover {
                background: #E5E7EB;
                color: #111827;
            }
            QPushButton#ModelToolbarButton:pressed,
            QToolButton#ModelToolbarButton:pressed {
                background: #F3F4F6;
                color: #111827;
            }
            QPushButton#ModelToolbarButton[toolbarMode="icon"],
            QToolButton#ModelToolbarButton[toolbarMode="icon"] {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
            }
            QPushButton#ModelToolbarButton[toolbarMode="label"] {
                min-width: 78px;
                max-width: 78px;
                min-height: 30px;
                max-height: 30px;
                padding: 0 10px;
                text-align: left;
            }
            QPushButton#ModelToolbarButton[toolbarMode="database"] {
                min-width: 116px;
                max-width: 136px;
                min-height: 30px;
                max-height: 30px;
                padding: 0 9px 0 7px;
                text-align: left;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#ModelZoomButton {
                min-height: 16px;
                color: #374151;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 5px;
                font-size: 9px;
                font-weight: 500;
                padding: 0;
            }
            QPushButton#ModelZoomButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton#ModelZoomButton:pressed {
                background: #E5E7EB;
            }
            QFrame#ModelActionCard,
            QFrame#ModelRecentCard {
                background: #FFFFFF;
                border: 1px solid #E1E5EA;
                border-radius: 10px;
            }
            QFrame#ModelActionCard:hover,
            QFrame#ModelRecentCard:hover {
                background: #F7F7F7;
                border-color: #D5DAE1;
            }
            QFrame#ModelRecentCardPreview {
                background: #F5F5F5;
                border: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QLabel#ModelRecentCardIcon {
                background: transparent;
                border: none;
            }
            QLabel#ModelActionCardIcon {
                background: transparent;
                border: none;
            }
            QLabel#ModelActionCardTitle {
                color: #111827;
                font-size: 15px;
                font-weight: 400;
            }
            QLabel#ModelRecentCardTitle {
                color: #111827;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#ModelActionCardText,
            QLabel#ModelRecentCardText {
                color: #6B7280;
                font-size: 12px;
                font-weight: 400;
            }
            """
        )
        self._apply_dark_theme_overlay()
        self._refresh_theme_icons()

        self._refresh_recents()
        self._refresh_builder_layers()
        self._sync_mode_switch_state(bool(self.edit_mode_btn.isChecked()))
        self._refresh_ui_state()
        self._reset_history()
        harmonize_widget_fonts(self)
        project = QgsProject.instance()
        try:
            project.layersAdded.connect(lambda *_: self._refresh_builder_layers())
            project.layersRemoved.connect(lambda *_: self._refresh_builder_layers())
            project.layerWillBeRemoved.connect(lambda *_: self._refresh_builder_layers())
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_dark_theme_overlay(self):
        if not hasattr(self, "_base_model_stylesheet"):
            self._base_model_stylesheet = self.styleSheet() or ""
        if not _is_dark_theme():
            if self.styleSheet() != self._base_model_stylesheet:
                self.setStyleSheet(self._base_model_stylesheet)
            return
        self.setStyleSheet(self._base_model_stylesheet)
        overlay = """
            QWidget#ModelTabRoot {
                background: #0B1020;
                color: #F8FAFC;
            }
            QWidget#ModelStartPage,
            QWidget#ModelHomeActions,
            QWidget#ModelRecentCardContent {
                background: #0B1020;
                color: #F8FAFC;
            }
            QFrame#ModelToolbarStrip,
            QFrame#ModelRecentsCard,
            QFrame#ModelRemoteProjectsCard,
            QFrame#ModelFooterBar,
            QFrame#ModelActionCard,
            QFrame#ModelRecentCard,
            QFrame#ModelFiltersBar {
                background: #111827;
                border-color: #334155;
                color: #F8FAFC;
            }
            QFrame#ModelToolbarSeparator,
            QSlider#ModelZoomSlider::groove:horizontal {
                background: #334155;
            }
            QLabel#ModelModeStateLabel,
            QLabel#ModelFiltersLabel,
            QLabel#ModelActionCardTitle,
            QLabel#ModelRemoteProjectsTitle,
            QLabel#ModelRecentCardTitle,
            QLabel#ModelPageStripTabTitle[selected="true"] {
                color: #F8FAFC;
            }
            QLabel#ModelHint,
            QLabel#ModelRecentsPlaceholder,
            QLabel#ModelRemoteProjectsPlaceholder,
            QLabel#ModelActionCardText,
            QLabel#ModelRecentCardText,
            QLabel#ModelPageStripTabTitle,
            QWidget#ModelPageStripTab,
            QToolButton#ModelPageStripTabMenu,
            QToolButton#ModelPageStripTabClose,
            QToolButton#ModelPageStripNavButton {
                color: #CBD5E1;
            }
            QWidget#ModelPageStripTab:hover,
            QToolButton#ModelPageStripTabMenu:hover,
            QToolButton#ModelPageStripTabClose:hover,
            QToolButton#ModelPageStripNavButton:hover,
            QPushButton#ModelToolbarButton:hover,
            QToolButton#ModelToolbarButton:hover,
            QPushButton#ModelActionButton:hover,
            QPushButton#ModelZoomButton:hover {
                background: #F3F4F6;
                color: #111827;
                border-color: #D1D5DB;
            }
            QPushButton#ModelToolbarButton,
            QToolButton#ModelToolbarButton,
            QPushButton#ModelActionButton,
            QPushButton#ModelZoomButton,
            QLineEdit#ModelPageStripTabEdit {
                background: #172033;
                color: #F8FAFC;
                border-color: #334155;
            }
            QPushButton#ModelToolbarButton:checked,
            QToolButton#ModelToolbarButton:checked,
            QPushButton#ModelToolbarButton:checked:hover,
            QToolButton#ModelToolbarButton:checked:hover,
            QPushButton#ModelToolbarButton:pressed,
            QToolButton#ModelToolbarButton:pressed,
            QPushButton#ModelActionButton:pressed,
            QPushButton#ModelZoomButton:pressed {
                background: #F3F4F6;
                color: #111827;
                border-color: #D1D5DB;
            }
            QLabel#ModelActionCardIcon {
                background: transparent;
                border-color: transparent;
            }
            QFrame#ModelRecentCardPreview {
                background: #172033;
                border-color: #334155;
            }
        """
        self.setStyleSheet(f"{self._base_model_stylesheet}\n{overlay}")
        self._refresh_theme_icons()

    def _refresh_theme_icons(self):
        for button in (
            getattr(self, "undo_btn", None),
            getattr(self, "redo_btn", None),
            getattr(self, "new_btn", None),
            getattr(self, "open_btn", None),
            getattr(self, "save_btn", None),
            getattr(self, "save_as_btn", None),
            getattr(self, "export_btn", None),
            getattr(self, "create_chart_btn", None),
            getattr(self, "format_visual_btn", None),
            getattr(self, "database_fields_btn", None),
            getattr(self, "data_fields_btn", None),
            getattr(self, "edit_mode_btn", None),
            getattr(self, "settings_btn", None),
            getattr(self, "close_project_btn", None),
            getattr(self, "visual_side_toggle_btn", None),
            getattr(self, "visual_side_collapsed_btn", None),
            getattr(self, "data_panel_toggle_btn", None),
            getattr(self, "data_panel_collapsed_btn", None),
        ):
            if button is None:
                continue
            icon_name = button.property("modelIconName")
            if not icon_name:
                continue
            try:
                icon_size = int(button.property("modelIconSize") or button.iconSize().width() or 18)
                icon_color = str(button.property("modelIconColor") or "")
                button.setIcon(_model_tinted_svg_icon(str(icon_name), icon_size, icon_color))
                button.setIconSize(QSize(icon_size, icon_size))
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
            except Exception:
                log_exception("falha opcional ignorada")
        for button in getattr(self, "builder_visual_buttons", {}).values():
            if button is None:
                continue
            icon_name = button.property("modelIconName")
            if not icon_name:
                continue
            try:
                icon_size = int(button.property("modelIconSize") or button.iconSize().width() or 15)
                normal_icon = _model_tinted_svg_icon(str(icon_name), icon_size)
                checked_icon = _model_tinted_svg_icon(str(icon_name), icon_size)
                button._model_icon_normal = normal_icon
                button._model_icon_checked = checked_icon
                button.setIcon(checked_icon if button.isCheckable() and button.isChecked() else normal_icon)
                button.setIconSize(QSize(icon_size, icon_size))
            except Exception:
                log_exception("falha opcional ignorada")
        if getattr(self, "data_panel_icon", None) is not None:
            self.data_panel_icon.setPixmap(_model_tinted_svg_icon("Layers.svg", 14).pixmap(14, 14))
        if getattr(self, "data_fields_btn", None) is not None:
            try:
                self.data_fields_btn.setIcon(_model_tinted_svg_icon("Layers.svg", 20))
                self.data_fields_btn.setIconSize(QSize(20, 20))
            except Exception:
                log_exception("falha opcional ignorada")
        self._sync_database_toolbar_button()

    def _build_visual_type_buttons(
        self,
        parent: QWidget,
        layout,
        *,
        button_size: int = 24,
        icon_size: int = 15,
        fixed_chart_types=None,
        overflow_enabled: bool = False,
    ):
        self.builder_visual_buttons = build_visual_type_buttons(
            parent,
            layout,
            self._builder_visual_specs,
            self._select_visual_type_from_builder,
            button_size=button_size,
            icon_size=icon_size,
            fixed_chart_types=fixed_chart_types,
            overflow_enabled=overflow_enabled,
        )

    def _apply_visual_side_panel_styles(self):
        style = """
            QFrame#ModelVisualSidePanel {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 2px;
            }
            QFrame#ModelVisualPanelTabBar {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 2px;
            }
            QPushButton#ModelVisualPanelTabButton {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 2px;
                background: transparent;
                color: __MUTED__;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton#ModelVisualPanelTabButton:hover {
                background: __HOVER__;
                border-color: __BORDER__;
            }
            QPushButton#ModelVisualPanelTabButton:checked {
                background: #F3F4F6;
                border-color: #D1D5DB;
                color: __TEXT__;
            }
            QFrame#ModelBuilderPanel {
                background: __SURFACE__;
                border: none;
            }
            QStackedWidget#ModelVisualSideStack,
            QStackedWidget#ModelVisualSideStack > QWidget {
                background: __SURFACE__;
                border: none;
            }
            QScrollArea#ModelBuilderScroll,
            QWidget#ModelBuilderScrollViewport,
            QWidget#ModelBuilderHost {
                background: __SURFACE__;
                border: none;
            }
            QFrame#ModelBuilderPlainSection {
                background: __SURFACE__;
                border: none;
            }
            QFrame#ModelBuilderVisualsSection {
                background: __SURFACE__;
                border: 1px solid __BORDER_SOFT__;
                border-radius: 6px;
            }
            QFrame#ModelBuilderVisualsSection:hover {
                border-color: __BORDER__;
            }
            QFrame#ModelBuilderSoftDividerSection {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 5px;
            }
            QToolButton#ModelVisualTypeButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: __MUTED__;
                padding: 0px;
            }
            QToolButton#ModelVisualTypeButton:hover {
                background: __HOVER__;
                border-color: __BORDER_SOFT__;
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #F3F4F6;
                color: #111827;
                border-color: __BORDER_SOFT__;
            }
            QToolButton#ModelVisualTypeButton:checked:hover {
                background: __HOVER__;
                color: #111827;
                border-color: __BORDER__;
            }
            QFrame#ModelBindingSlot {
                background: __SURFACE_2__;
                border: 1px solid __BORDER_SOFT__;
                border-radius: 4px;
                min-height: 42px;
            }
            QFrame#ModelBindingSlot[filled="true"] {
                border-color: __BORDER__;
                background: __SURFACE_2__;
            }
            QFrame#ModelBindingFieldChip {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 3px;
                min-height: 22px;
                max-height: 24px;
            }
            QLabel#ModelBindingFieldBadge {
                background: __CHECKED__;
                color: __TEXT__;
                border: 1px solid __BORDER__;
                border-radius: 2px;
                min-width: 24px;
                max-width: 26px;
                min-height: 16px;
                font-size: 8px;
                font-weight: 600;
            }
            QLabel#ModelBindingFieldName,
            QLabel#ModelBindingSlotValue,
            QLabel#ModelBindingSlotLabel {
                font-size: 9px;
            }
            QLabel#ModelBindingFieldName {
                min-width: 0px;
            }
            QLabel#ModelBindingSlotValue {
                color: __MUTED__;
                font-weight: 400;
            }
        """
        self.visual_side_panel.setStyleSheet(fill_model_theme_tokens(style))
        self._apply_builder_panel_theme_overrides()
        self._refresh_theme_icons()

    def _apply_builder_panel_theme_overrides(self):
        style = fill_model_theme_tokens(
            """
            QScrollArea#ModelBuilderScroll,
            QWidget#ModelBuilderScrollViewport,
            QWidget#ModelBuilderHost,
            QWidget#ModelBuilderBottomSpacer,
            QFrame#ModelBuilderPanel,
            QFrame#ModelBuilderVisualsSection,
            QFrame#ModelBuilderSoftDividerSection,
            QFrame#ModelBuilderPlainSection,
            QFrame#ModelBuilderDataPanel,
            QFrame#ModelDataPanelCollapsedRail,
            QFrame#ModelSidePanelCollapsedRail,
            QFrame#ModelBuilderDataPanel QWidget,
            QFrame#ModelBuilderDataPanel QFrame,
            QFrame#ModelBuilderDataPanel QAbstractScrollArea,
            QFrame#ModelBuilderDataPanel QAbstractScrollArea::viewport,
            QWidget#ModelDataPanelHeader,
            QWidget#ModelDataPanelBody,
            QWidget#ModelDataFieldsBody,
            QFrame#ModelBuilderDataSection {
                background: __SURFACE__;
                background-color: __SURFACE__;
                color: __TEXT__;
            }
            QFrame#ModelBuilderVisualsSection,
            QFrame#ModelBuilderSoftDividerSection,
            QFrame#ModelBuilderDataPanel {
                border: 1px solid __BORDER__;
                border-radius: 2px;
            }
            QFrame#ModelDataPanelCollapsedRail,
            QFrame#ModelSidePanelCollapsedRail {
                border: none;
                border-radius: 0px;
                background: __SURFACE__;
                background-color: __SURFACE__;
            }
            QFrame#ModelBuilderEmptyState {
                background: transparent;
                background-color: transparent;
                border: none;
            }
            QFrame#ModelBuilderEmptyStateCard {
                background: #F3F4F6;
                background-color: #F3F4F6;
                border: none;
                border-radius: 2px;
            }
            QFrame#ModelBuilderEmptyStateCard QLabel {
                color: #334155;
                background: transparent;
                border: none;
            }
            QLabel#ModelBuilderEmptyStateTitle {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#ModelBuilderEmptyStateLabel {
                color: #334155;
                font-size: 12px;
                font-weight: 400;
            }
            QToolButton#ModelBuilderEmptyStateClose {
                background: transparent;
                border: none;
                color: #334155;
                padding: 0px;
                font-size: 18px;
                font-weight: 300;
            }
            QToolButton#ModelBuilderEmptyStateClose:hover {
                background: #E5E7EB;
                border-radius: 2px;
            }
            QLabel#ModelBuilderTitle,
            QLabel#ModelBuilderSectionTitle {
                color: __TEXT__;
                background: transparent;
                font-weight: 500;
            }
            QLabel#ModelBuilderHint,
            QLabel#ModelBuilderFieldLabel,
            QLabel#ModelDataPanelCollapsedTitle,
            QLabel#ModelBindingSlotLabel,
            QLabel#ModelBindingSlotValue {
                color: __MUTED__;
                background: transparent;
            }
            QLabel#ModelDataPanelCollapsedTitle,
            QLabel#ModelSidePanelCollapsedTitle {
                color: __TEXT__;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
            }
            QFrame#ModelBuilderDataPanel QLabel#ModelBuilderTitle {
                color: __TEXT__;
                font-size: 12px;
                font-weight: 500;
            }
            QFrame#ModelBuilderDataPanel QLabel#ModelBuilderFieldLabel {
                color: __MUTED__;
                font-size: 10px;
                font-weight: 400;
            }
            QListWidget#ModelBuilderFieldList {
                background: __SURFACE_2__;
                color: __TEXT__;
                border: 1px solid __BORDER__;
                border-radius: 2px;
                padding: 2px;
                outline: 0;
            }
            QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList {
                font-size: 11px;
            }
            QWidget#ModelBuilderFieldListViewport {
                background: __SURFACE_2__;
            }
            QListWidget#ModelBuilderFieldList::item {
                background: transparent;
                color: __TEXT__;
                border: none;
                padding: 4px 6px;
                margin: 0px;
            }
            QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList::item {
                min-height: 22px;
                padding: 2px 5px;
            }
            QListWidget#ModelBuilderFieldList::item:hover {
                background: __HOVER__;
                color: __TEXT__;
            }
            QListWidget#ModelBuilderFieldList::item:selected {
                background: __CHECKED__;
                color: __TEXT__;
            }
            QComboBox#ModelBuilderCombo,
            QLineEdit#ModelBuilderLineEdit,
            QSpinBox#ModelBuilderSpin,
            QComboBox#ModelBindingAggregationCombo {
                background: __SURFACE_2__;
                color: __TEXT__;
                border: 1px solid __BORDER__;
                border-radius: 2px;
                selection-background-color: __CHECKED__;
                selection-color: __TEXT__;
            }
            QFrame#ModelBuilderDataPanel QComboBox#ModelBuilderCombo {
                min-height: 28px;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 11px;
            }
            QComboBox#ModelBindingAggregationCombo {
                min-width: 58px;
                max-width: 58px;
                min-height: 18px;
                max-height: 18px;
                padding: 0 2px;
            }
            QComboBox#ModelBuilderCombo:hover,
            QLineEdit#ModelBuilderLineEdit:hover,
            QSpinBox#ModelBuilderSpin:hover,
            QComboBox#ModelBindingAggregationCombo:hover {
                background: __HOVER__;
                border-color: __CHECKED_BORDER__;
            }
            QFrame#ModelBindingSlot {
                background: __SURFACE_2__;
                border: 1px solid __BORDER__;
                border-radius: 4px;
            }
            QFrame#ModelBindingSlot[filled="true"] {
                background: __SURFACE_2__;
                border-color: __CHECKED_BORDER__;
            }
            QFrame#ModelBindingFieldChip {
                background: __SURFACE__;
                border: 1px solid __BORDER__;
                border-radius: 3px;
                min-height: 22px;
                max-height: 24px;
            }
            QLabel#ModelBindingFieldBadge {
                background: __CHECKED__;
                color: __TEXT__;
                border: 1px solid __CHECKED_BORDER__;
                border-radius: 2px;
                min-width: 24px;
                max-width: 26px;
            }
            QLabel#ModelBindingFieldName {
                color: __TEXT__;
                background: transparent;
                min-width: 0px;
            }
            QToolButton#ModelVisualTypeButton,
            QToolButton#ModelBindingSlotMove,
            QToolButton#ModelBindingSlotRemove,
            QToolButton#ModelSidePanelToggle,
            QToolButton#ModelDataPanelToggle {
                background: transparent;
                border: 1px solid transparent;
                color: __TEXT__;
            }
            QToolButton#ModelVisualTypeButton:hover,
            QToolButton#ModelBindingSlotMove:hover,
            QToolButton#ModelSidePanelToggle:hover,
            QToolButton#ModelDataPanelToggle:hover {
                background: transparent;
                border-color: transparent;
                color: __TEXT__;
            }
            QFrame#ModelBuilderVisualsSection QToolButton#ModelVisualTypeButton:hover,
            QFrame#ModelBuilderVisualsSection QToolButton#ModelBindingSlotMove:hover {
                background: __HOVER__;
                border-color: __BORDER__;
            }
            QToolButton#ModelBindingSlotRemove:hover {
                background: rgba(239, 68, 68, 0.08);
                border-color: rgba(239, 68, 68, 0.20);
            }
            QToolButton#ModelVisualTypeButton:checked {
                background: #F3F4F6;
                border-color: __BORDER_SOFT__;
                color: #111827;
            }
            QToolButton#ModelVisualTypeButton:checked:hover {
                background: __HOVER__;
                border-color: __BORDER__;
                color: #111827;
            }
            """
        )
        for widget in (
            getattr(self, "builder_panel", None),
            getattr(self, "visual_side_stack", None),
            getattr(self, "data_panel", None),
        ):
            if widget is None:
                continue
            try:
                widget.setStyleSheet(style)
            except Exception:
                log_exception("falha opcional ignorada")
        for name in (
            "ModelBuilderScroll",
            "ModelBuilderScrollViewport",
            "ModelBuilderHost",
            "ModelBuilderBottomSpacer",
            "ModelBuilderVisualsSection",
            "ModelBuilderSoftDividerSection",
            "ModelBuilderDataPanel",
            "ModelDataPanelCollapsedRail",
            "ModelSidePanelCollapsedRail",
            "ModelDataPanelHeader",
            "ModelDataPanelBody",
            "ModelDataFieldsBody",
            "ModelBuilderDataSection",
            "ModelBuilderFieldList",
            "ModelBuilderFieldListViewport",
        ):
            for widget in self.findChildren(QWidget, name):
                try:
                    palette = widget.palette()
                    palette.setColor(QPalette.Window, QColor(_model_theme_color("surface")))
                    palette.setColor(QPalette.Base, QColor(_model_theme_color("surface_2")))
                    palette.setColor(QPalette.AlternateBase, QColor(_model_theme_color("surface")))
                    palette.setColor(QPalette.Text, QColor(_model_theme_color("text")))
                    palette.setColor(QPalette.WindowText, QColor(_model_theme_color("text")))
                    widget.setPalette(palette)
                    widget.setAutoFillBackground(True)
                    widget.setStyleSheet(style)
                except Exception:
                    log_exception("falha opcional ignorada")
        label_style = (
            "background: transparent; "
            f"color: {_model_theme_color('muted')}; "
            "font-weight: 400;"
        )
        title_style = (
            "background: transparent; "
            f"color: {_model_theme_color('text')}; "
            "font-weight: 500;"
        )
        for name, style_text in (
            ("ModelBuilderSectionTitle", title_style),
            ("ModelBindingSlotValue", label_style),
            ("ModelDataPanelCollapsedTitle", title_style),
            ("ModelSidePanelCollapsedTitle", title_style),
        ):
            for label in self.findChildren(QLabel, name):
                try:
                    label.setStyleSheet(style_text)
                except Exception:
                    log_exception("falha opcional ignorada")
        self._apply_visual_tab_button_styles()
        self._apply_collapsed_panel_chrome()

    def _apply_collapsed_panel_chrome(self):
        surface = _model_theme_color("surface")
        text = _model_theme_color("text")
        button_style = f"""
            QToolButton#ModelSidePanelToggle,
            QToolButton#ModelDataPanelToggle,
            QToolButton#ModelDatabasePanelToggle,
            QToolButton {{
                background: transparent;
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: {text};
                padding: 0px;
                font-size: 16px;
                font-weight: 500;
            }}
            QToolButton#ModelSidePanelToggle:hover,
            QToolButton#ModelDataPanelToggle:hover,
            QToolButton#ModelDatabasePanelToggle:hover,
            QToolButton:hover,
            QToolButton:pressed {{
                background: {_model_theme_color("hover")};
                background-color: {_model_theme_color("hover")};
                border: 1px solid {_model_theme_color("border")};
                color: {text};
            }}
        """
        rail_style = f"background: {surface}; background-color: {surface}; border: none; border-radius: 0px;"
        label_style = f"background: transparent; color: {text}; font-size: 12px; font-weight: 500;"

        for rail_name in (
            "visual_side_collapsed_rail",
            "data_panel_collapsed_rail",
            "database_panel.collapsed_rail",
        ):
            if "." in rail_name:
                owner_name, attr_name = rail_name.split(".", 1)
                rail = getattr(getattr(self, owner_name, None), attr_name, None)
            else:
                rail = getattr(self, rail_name, None)
            if rail is None:
                continue
            try:
                rail.setStyleSheet(rail_style)
            except Exception:
                log_exception("falha opcional ignorada")

        for button_name in (
            "visual_side_toggle_btn",
            "visual_side_collapsed_btn",
            "data_panel_toggle_btn",
            "data_panel_collapsed_btn",
            "database_panel.toggle_btn",
            "database_panel.collapsed_btn",
        ):
            if "." in button_name:
                owner_name, attr_name = button_name.split(".", 1)
                button = getattr(getattr(self, owner_name, None), attr_name, None)
            else:
                button = getattr(self, button_name, None)
            if button is None:
                continue
            try:
                button.setAutoRaise(True)
                button.setFixedSize(22, 22)
                button.setStyleSheet(button_style)
                button.style().unpolish(button)
                button.style().polish(button)
            except Exception:
                log_exception("falha opcional ignorada")

        for label_name in (
            "visual_side_collapsed_title",
            "data_panel_collapsed_title",
            "database_panel.collapsed_title",
        ):
            if "." in label_name:
                owner_name, attr_name = label_name.split(".", 1)
                label = getattr(getattr(self, owner_name, None), attr_name, None)
            else:
                label = getattr(self, label_name, None)
            if label is None:
                continue
            try:
                label.setStyleSheet(label_style)
                label.updateGeometry()
                label.update()
            except Exception:
                log_exception("falha opcional ignorada")

    def _apply_visual_tab_button_styles(self):
        style = """
            QPushButton#ModelVisualPanelTabButton {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid transparent;
                border-radius: 2px;
                background-color: transparent;
                color: __MUTED__;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
                text-align: center;
            }
            QPushButton#ModelVisualPanelTabButton:hover {
                background-color: __HOVER__;
                border-color: __BORDER__;
                color: __TEXT__;
            }
            QPushButton#ModelVisualPanelTabButton:checked,
            QPushButton#ModelVisualPanelTabButton:checked:hover {
                background-color: #F3F4F6;
                border-color: #D1D5DB;
                color: __TEXT__;
            }
            QPushButton#ModelVisualPanelTabButton:pressed {
                background-color: #E5E7EB;
                border-color: #D1D5DB;
                color: __TEXT__;
            }
        """
        style = fill_model_theme_tokens(style)
        for button in (
            getattr(self, "visual_data_tab_btn", None),
            getattr(self, "visual_format_tab_btn", None),
        ):
            if button is None:
                continue
            button.setStyleSheet(style)
            try:
                button.style().unpolish(button)
                button.style().polish(button)
            except Exception:
                log_exception("falha opcional ignorada")

    def _build_chart_builder_panel(self, parent: QWidget) -> QFrame:
        parts = build_model_builder_panel(
            parent,
            visual_specs=self._builder_visual_specs,
            on_value_changed=self._on_builder_value_changed,
            on_binding_controls_changed=self._update_selected_visual_binding_controls,
            on_field_dropped=self._apply_dropped_field_to_selected_visual,
            on_remove_requested=self._remove_selected_visual_slot_field,
            on_aggregation_changed=self._change_selected_visual_slot_aggregation,
            on_move_requested=self._move_selected_visual_slot_field,
        )
        self.builder_empty_label = parts.builder_empty_label
        self.builder_construct_card = parts.builder_construct_card
        self.builder_selected_visual_label = parts.builder_selected_visual_label
        self._builder_selection_widgets = parts.builder_selection_widgets
        self.builder_binding_slots = parts.builder_binding_slots
        self.builder_format_card = parts.builder_format_card
        self.builder_option_labels = parts.builder_option_labels
        self.builder_agg_combo = parts.builder_agg_combo
        self.builder_topn_spin = parts.builder_topn_spin
        self.builder_title_edit = parts.builder_title_edit
        self.builder_dimension_combo = parts.builder_dimension_combo
        self.builder_value_combo = parts.builder_value_combo
        return parts.panel

    def _build_data_panel(self, parent: QWidget) -> QFrame:
        parts = build_model_data_panel(
            parent,
            toggle_data_panel=self._toggle_data_panel,
            on_builder_layer_changed=self._on_builder_layer_changed,
            handle_field_list_activation=self._handle_field_list_activation,
            vertical_label_cls=_ModelVerticalPanelLabel,
        )
        for name, widget in parts.__dict__.items():
            if name == "panel":
                continue
            setattr(self, name, widget)
        self._refresh_model_database_status()
        return parts.panel

    def _build_database_panel(self, parent: QWidget) -> QFrame:
        panel = ModelDatabasePanel(parent)
        panel.objectActivated.connect(self._handle_model_database_object_activated)
        panel.toggleRequested.connect(self._toggle_database_panel)
        return panel

    def showEvent(self, event):
        super().showEvent(event)
        harmonize_widget_fonts(self)
        refresh_builder_data_fonts(self)
        self._refresh_theme_icons()
        self._schedule_toolbar_visuals_strip_visibility()
        self._position_clear_filters_button()

    def _suggested_role_for_group(self, group: str) -> str:
        mapping = {
            "dimension": ROLE_X_AXIS,
            "measure": ROLE_VALUES,
            "date": ROLE_X_AXIS,
            "other": ROLE_TOOLTIP,
        }
        return mapping.get(str(group or "").strip().lower(), ROLE_X_AXIS)

    def _slot_values_for_binding(self, binding: DashboardChartBinding, slot_name: str) -> List[FieldBindingItem]:
        role = normalize_binding_role(slot_name)
        return list(binding.normalized().bindings.get(role) or [])

    def _selected_canvas_item(self) -> Optional[DashboardChartItem]:
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return None
        return active_canvas.selected_item()

    def _selected_canvas_item_widget(self):
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return None
        return active_canvas.selected_item_widget()

    def _replace_canvas_item(self, updated_item: DashboardChartItem, *, page_id: Optional[str] = None, select: bool = True):
        active_widget = self._active_page_widget()
        if active_widget is None:
            return
        if page_id and str(active_widget.page_id or "").strip() != str(page_id or "").strip():
            active_widget = self._page_widget_for_id(page_id)
        if active_widget is None:
            return
        canvas = active_widget.canvas
        items = canvas.items()
        replaced = False
        for index, item in enumerate(items):
            if str(item.item_id or "") == str(updated_item.item_id or ""):
                items[index] = updated_item.clone()
                replaced = True
                break
        if not replaced:
            return
        canvas.update_items(items, canvas.visual_links(), canvas.chart_relations())
        if select:
            canvas.select_item(updated_item.item_id, emit_signal=True)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _create_blank_visual_from_type(self, chart_type: str):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        item_id = uuid.uuid4().hex
        binding = DashboardChartBinding(
            chart_id=item_id,
            chart_type=str(chart_type or "bar").strip().lower(),
            aggregation="count",
            top_n=max(1, int(self.builder_topn_spin.value() or 12)),
        ).normalized()
        item = DashboardChartItem(
            item_id=item_id,
            origin="model_builder_v2",
            payload=empty_chart_payload(chart_type, title=""),
            visual_state=ChartVisualState(
                chart_type=str(chart_type or "bar").strip().lower(),
                font_scale=_MODEL_DEFAULT_FONT_SCALE,
            ),
            binding=binding,
            title="",
            subtitle=_rt("Arraste campos para configurar este visual"),
            source_meta={"builder_version": "v2", "empty_visual": True},
        )
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()
        self._set_builder_panel_open(True, focus=False)
        self._expand_data_panel_for_new_chart()
        self._sync_builder_selection_state()

    def _select_visual_type_from_builder(self, chart_type: str):
        normalized_type = normalize_chart_type(chart_type)
        item = self._selected_canvas_item()
        if item is None:
            self._create_blank_visual_from_type(normalized_type)
            return
        binding = item.binding.normalized()
        binding.chart_type = normalized_type
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is None:
            return
        updated_item.visual_state.chart_type = normalized_type
        self._replace_canvas_item(updated_item, select=True)
        self._set_builder_panel_open(True, focus=False)
        self._sync_builder_selection_state()

    def _refresh_builder_field_lists(self, layer: Optional[QgsVectorLayer]):
        self._builder_field_catalog = populate_builder_field_list(self, layer)
        self._sync_data_panel_width_to_content()

    def _text_width(self, metrics: QFontMetrics, text: str) -> int:
        if hasattr(metrics, "horizontalAdvance"):
            return int(metrics.horizontalAdvance(text))
        return int(metrics.width(text))

    def _sync_data_panel_width_to_content(self):
        if not hasattr(self, "data_panel"):
            return
        self._data_panel_width = desired_data_panel_width(
            self.builder_fields_list,
            self.builder_layer_combo,
            minimum_width=_MODEL_DATA_PANEL_MIN_WIDTH,
            maximum_width=_MODEL_DATA_PANEL_MAX_WIDTH,
            default_width=_MODEL_DATA_PANEL_DEFAULT_WIDTH,
        )
        self._sync_data_panel_chrome()
        self._ensure_canvas_splitter_sizes()

    def _reset_model_side_panels_collapsed(self):
        self._visual_side_collapsed = True
        self._data_panel_collapsed = True
        if hasattr(self, "visual_side_panel"):
            self._sync_visual_side_panel_chrome()
        if hasattr(self, "data_panel"):
            self._sync_data_panel_chrome()
        self._ensure_canvas_splitter_sizes()

    def _expand_data_panel_for_new_chart(self):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        if not (bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page):
            return
        self._data_panel_collapsed = False
        if not getattr(self, "_data_panel_width", 0):
            self._data_panel_width = _MODEL_DATA_PANEL_DEFAULT_WIDTH
        self._set_data_panel_available(True)
        self._sync_data_panel_chrome()
        self._ensure_canvas_splitter_sizes()

    def _toggle_data_panel(self):
        self._set_data_panel_collapsed(not bool(getattr(self, "_data_panel_collapsed", False)))

    def _set_data_panel_collapsed(self, collapsed: bool):
        if not getattr(self, "_data_panel_collapsed", False):
            sizes = self.canvas_splitter.sizes() if hasattr(self, "canvas_splitter") else []
            if len(sizes) >= 4 and sizes[3] > _MODEL_DATA_PANEL_COLLAPSED_WIDTH:
                self._data_panel_width = min(
                    _MODEL_DATA_PANEL_MAX_WIDTH,
                    max(_MODEL_DATA_PANEL_MIN_WIDTH, int(sizes[3])),
                )
        elif not getattr(self, "_data_panel_width", 0):
            self._data_panel_width = _MODEL_DATA_PANEL_DEFAULT_WIDTH
        self._data_panel_collapsed = bool(collapsed)
        self._set_data_panel_available(True)
        self._sync_data_panel_chrome()
        self._ensure_canvas_splitter_sizes()
        self._schedule_clear_filters_button_position()

    def _sync_data_fields_button_state(self):
        button = getattr(self, "data_fields_btn", None)
        if button is None:
            return
        data_panel = getattr(self, "data_panel", None)
        data_panel_visible = bool(data_panel is not None and data_panel.isVisible())
        checked = all(
            (
                data_panel is not None,
                data_panel_visible,
                not getattr(self, "_data_panel_collapsed", False),
            )
        )
        button.blockSignals(True)
        try:
            button.setChecked(checked)
        finally:
            button.blockSignals(False)

    def _set_data_panel_available(self, available: bool):
        if not hasattr(self, "data_panel"):
            return
        self.data_panel.setVisible(bool(available))
        if available:
            self._sync_data_panel_chrome()
        self._sync_data_fields_button_state()

    def _handle_database_panel_toggle(self, checked: bool):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        available = bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page
        if not available:
            self._sync_database_fields_button_state()
            return
        self._database_panel_open = bool(checked)
        if self._database_panel_open:
            self._database_panel_collapsed = False
        self._set_database_panel_available(self._database_panel_open)
        if self._database_panel_open:
            self._refresh_model_database_status()
        self._ensure_canvas_splitter_sizes()

    def _toggle_database_panel(self):
        if not getattr(self, "_database_panel_open", False):
            self._database_panel_open = True
            self._database_panel_collapsed = False
        else:
            if not getattr(self, "_database_panel_collapsed", False):
                sizes = self.canvas_splitter.sizes() if hasattr(self, "canvas_splitter") else []
                if len(sizes) >= 4 and sizes[2] > _MODEL_SIDE_PANEL_COLLAPSED_WIDTH:
                    self._database_panel_width = min(
                        _MODEL_DATABASE_PANEL_MAX_WIDTH,
                        max(_MODEL_DATABASE_PANEL_MIN_WIDTH, int(sizes[2])),
                    )
            self._database_panel_collapsed = not bool(getattr(self, "_database_panel_collapsed", False))
        self._set_database_panel_available(True)
        if self._database_panel_open and not self._database_panel_collapsed:
            self._refresh_model_database_status()
        self._ensure_canvas_splitter_sizes()

    def _set_database_panel_available(self, available: bool):
        panel = getattr(self, "database_panel", None)
        if panel is None:
            return
        panel.setVisible(bool(available))
        if available:
            self._sync_database_panel_chrome()
        self._sync_database_fields_button_state()

    def _sync_database_fields_button_state(self):
        button = getattr(self, "database_fields_btn", None)
        panel = getattr(self, "database_panel", None)
        if button is None:
            return
        checked = bool(panel is not None and panel.isVisible() and getattr(self, "_database_panel_open", False))
        button.blockSignals(True)
        try:
            button.setChecked(checked)
        finally:
            button.blockSignals(False)
        self._sync_database_toolbar_button()

    def _sync_database_toolbar_button(self, connection_meta: Optional[Dict] = None, connected: Optional[bool] = None):
        button = getattr(self, "database_fields_btn", None)
        if button is None:
            return
        meta = dict(connection_meta or self._current_model_database_connection_meta() or {})
        if connected is None:
            connected = bool(meta)
        label = self._database_toolbar_label(meta)
        try:
            button.setText(label)
            button.setIcon(self._database_toolbar_icon(bool(connected)))
            button.setIconSize(QSize(20, 20))
            set_walker_tooltip(button, _rt("Banco de dados: {name}", name=label))
            button.setStatusTip(_rt("Banco de dados: {name}", name=label))
        except Exception:
            log_exception("falha opcional ignorada")

    def _database_toolbar_label(self, connection_meta: Dict) -> str:
        for key in ("driver", "provider", "type", "database", "name"):
            value = str(connection_meta.get(key) or "").strip()
            if value:
                return value
        return _rt("Banco")

    def _database_toolbar_icon(self, connected: bool) -> QIcon:
        base_icon = _model_tinted_svg_icon("Dataset.svg", 20)
        pixmap = base_icon.pixmap(20, 20)
        if bool(connected):
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#22C55E"))
            painter.drawEllipse(13, 1, 6, 6)
            painter.end()
        return QIcon(pixmap)

    def _sync_database_panel_chrome(self):
        panel = getattr(self, "database_panel", None)
        if panel is None:
            return
        collapsed = bool(getattr(self, "_database_panel_collapsed", False))
        panel.setMinimumWidth(_MODEL_SIDE_PANEL_COLLAPSED_WIDTH if collapsed else _MODEL_DATABASE_PANEL_MIN_WIDTH)
        panel.setMaximumWidth(_MODEL_SIDE_PANEL_COLLAPSED_WIDTH if collapsed else _MODEL_DATABASE_PANEL_MAX_WIDTH)
        if hasattr(panel, "set_collapsed"):
            panel.set_collapsed(collapsed)
        if collapsed and hasattr(panel, "release_catalog"):
            panel.release_catalog(keep_groups=True)
        self._apply_collapsed_panel_chrome()
        self._sync_database_fields_button_state()

    def _sync_data_panel_chrome(self):
        sync_data_panel_chrome(
            self,
            collapsed_width=_MODEL_DATA_PANEL_COLLAPSED_WIDTH,
            min_width=_MODEL_DATA_PANEL_MIN_WIDTH,
            max_width=_MODEL_DATA_PANEL_MAX_WIDTH,
        )
        self._apply_collapsed_panel_chrome()
        self._sync_data_fields_button_state()

    def _active_selected_binding(self) -> Optional[DashboardChartBinding]:
        item = self._selected_canvas_item()
        if item is None:
            return None
        return item.binding.normalized()

    def _sync_visual_type_button_states(self, buttons, active_chart_type: str = ""):
        normalized_active = normalize_chart_type(active_chart_type) if active_chart_type else ""
        buttons = [button for button in list(buttons or []) if button is not None]
        group = None
        if buttons:
            parent_widget = buttons[0].parentWidget()
            group = getattr(parent_widget, "_model_visual_button_group", None)
        previous_exclusive = None
        if group is not None:
            try:
                previous_exclusive = bool(group.exclusive())
                group.setExclusive(False)
            except Exception:
                group = None
                previous_exclusive = None
        try:
            for button in buttons:
                try:
                    button_chart_type = normalize_chart_type(str(button.property("visualType") or ""))
                    should_check = bool(normalized_active and button_chart_type == normalized_active)
                    button.blockSignals(True)
                    try:
                        button.setChecked(should_check)
                        button.setIcon(
                            getattr(button, "_model_icon_checked", None)
                            if should_check
                            else getattr(button, "_model_icon_normal", None)
                        )
                    finally:
                        button.blockSignals(False)
                except Exception:
                    log_exception("falha opcional ignorada")
        finally:
            if group is not None and previous_exclusive is not None:
                try:
                    group.setExclusive(previous_exclusive)
                except Exception:
                    log_exception("falha opcional ignorada")

    def _sync_builder_selection_state(self):
        item = self._selected_canvas_item()
        binding = item.binding.normalized() if item is not None else None
        buttons = list(getattr(self, "builder_visual_buttons", {}).values())
        buttons_container = buttons[0].parentWidget() if buttons else None
        toolbar_buttons = self._toolbar_visual_type_buttons()
        toolbar_container = toolbar_buttons[0].parentWidget() if toolbar_buttons else None
        button_containers = [container for container in (buttons_container, toolbar_container) if container is not None]
        for container in button_containers:
            try:
                container.setUpdatesEnabled(False)
            except Exception:
                log_exception("falha opcional ignorada")
        if not builder_has_selection(item, binding):
            self._builder_selected_item_id = ""
            if hasattr(self, "builder_empty_label"):
                self.builder_empty_label.setVisible(True)
            if hasattr(self, "builder_construct_card"):
                self.builder_construct_card.setVisible(False)
            if hasattr(self, "builder_format_card"):
                self.builder_format_card.setVisible(False)
            self.builder_selected_visual_label.setText(_rt("Selecione um visual para começar."))
            self._sync_visual_type_button_states(buttons, "")
            self._sync_visual_type_button_states(toolbar_buttons, "")
            for widget in list(getattr(self, "_builder_selection_widgets", []) or []):
                widget.setVisible(False)
            for slot in self.builder_binding_slots.values():
                slot.set_value("")
            self.builder_agg_combo.setEnabled(False)
            self.builder_topn_spin.setEnabled(False)
            self.builder_title_edit.setEnabled(False)
            for container in button_containers:
                try:
                    container.setUpdatesEnabled(True)
                    container.update()
                except Exception:
                    log_exception("falha opcional ignorada")
            return
        self._builder_selected_item_id = str(item.item_id or "")
        if hasattr(self, "builder_empty_label"):
            self.builder_empty_label.setVisible(False)
        if hasattr(self, "builder_construct_card"):
            self.builder_construct_card.setVisible(True)
        if hasattr(self, "builder_format_card"):
            self.builder_format_card.setVisible(True)
        active_chart_type = normalize_chart_type(binding.chart_type or getattr(item.visual_state, "chart_type", ""))
        layer_name = binding.source_name or _rt("Sem camada")
        visual_label = chart_type_label(binding.chart_type or getattr(item.visual_state, "chart_type", "bar"))
        self.builder_selected_visual_label.setText(_rt("{visual} · {layer}", visual=visual_label, layer=layer_name))
        for widget in list(getattr(self, "_builder_selection_widgets", []) or []):
            widget.setVisible(True)
        slot_defs = binding_slot_definitions(binding.chart_type or getattr(item.visual_state, "chart_type", "bar"))
        visible_slots = {str(slot.get("name") or "") for slot in slot_defs}
        labels_by_slot = {str(slot.get("name") or ""): str(slot.get("label") or "") for slot in slot_defs}
        for slot_name, slot in self.builder_binding_slots.items():
            slot.setVisible(slot_name in visible_slots)
            if slot_name in visible_slots:
                label = labels_by_slot.get(slot_name) or slot_name
                slot.set_label(_rt(label))
                slot.set_values(
                    self._slot_values_for_binding(binding, slot_name),
                    placeholder=_rt("Opcional"),
                    source_item_id=item.item_id,
                )
        self.builder_agg_combo.setEnabled(True)
        self.builder_topn_spin.setEnabled(True)
        self.builder_title_edit.setEnabled(True)
        self.builder_agg_combo.setVisible(True)
        label = self.builder_option_labels.get("aggregation")
        if label is not None:
            label.setVisible(True)
        topn_visible = active_chart_type not in {"card", "kpi", "gauge", "scatter"}
        self.builder_topn_spin.setVisible(topn_visible)
        label = self.builder_option_labels.get("top_n")
        if label is not None:
            label.setVisible(topn_visible)
        label = self.builder_option_labels.get("title")
        if label is not None:
            label.setVisible(True)
        agg_index = self.builder_agg_combo.findData(binding.aggregation or "count")
        if agg_index < 0:
            agg_index = self.builder_agg_combo.findData("count")
        self.builder_agg_combo.blockSignals(True)
        self.builder_agg_combo.setCurrentIndex(max(0, agg_index))
        self.builder_agg_combo.blockSignals(False)
        self.builder_topn_spin.blockSignals(True)
        self.builder_topn_spin.setValue(max(1, int(binding.top_n or 12)))
        self.builder_topn_spin.blockSignals(False)
        self.builder_title_edit.blockSignals(True)
        self.builder_title_edit.setText(str(binding.title_override or item.title or ""))
        self.builder_title_edit.blockSignals(False)
        self._sync_visual_type_button_states(buttons, active_chart_type)
        self._sync_visual_type_button_states(toolbar_buttons, active_chart_type)
        for container in button_containers:
            try:
                container.setUpdatesEnabled(True)
                container.update()
            except Exception:
                log_exception("falha opcional ignorada")

    def _selected_layer(self) -> Optional[QgsVectorLayer]:
        return self._current_builder_layer()

    def _current_builder_layer(self) -> Optional[QgsVectorLayer]:
        database_layer = getattr(self, "_builder_database_layer", None)
        if bool(getattr(self, "_builder_database_layer_active", False)):
            if isinstance(database_layer, QgsVectorLayer) and database_layer.isValid():
                return database_layer
        try:
            layer = self.builder_layer_combo.currentLayer()
        except Exception:
            layer = None
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            return layer
        layer_id = str(getattr(self.builder_layer_combo, "currentData", lambda: "")() or "")
        return self._builder_layers.get(layer_id)

    def _current_builder_layer_id(self) -> str:
        layer = self._current_builder_layer()
        if layer is not None:
            return str(layer.id() or "")
        return ""

    def _current_builder_chart_type(self) -> str:
        item = self._selected_canvas_item()
        if item is not None:
            binding = item.binding.normalized() if item.binding is not None else None
            selected_type = normalize_chart_type(
                (binding.chart_type if binding is not None else "") or getattr(item.visual_state, "chart_type", "")
            )
            if selected_type:
                return selected_type
        return selected_builder_chart_type_from_buttons(getattr(self, "builder_visual_buttons", {}))

    def _field_binding_item_from_payload(self, role: str, payload: Dict[str, object], order: int = 0) -> Optional[FieldBindingItem]:
        field_name = str(payload.get("field_name") or payload.get("field") or "").strip()
        if not field_name:
            return None
        field_kind = normalize_field_kind(str(payload.get("field_kind") or payload.get("field_group") or "unknown"))
        aggregation = normalize_aggregation("", field_kind, role)
        return FieldBindingItem(
            field=field_name,
            display_name=str(payload.get("display_name") or field_name).strip() or field_name,
            type=field_kind,
            aggregation=aggregation,
            role=role,
            order=order,
        ).normalized(role, order)

    def _apply_field_payload_to_binding(self, binding: DashboardChartBinding, slot_name: str, payload: Dict[str, object]) -> DashboardChartBinding:
        slot_name = normalize_binding_role(slot_name)
        field_name = str(payload.get("field_name") or "").strip()
        field_group = str(payload.get("field_group") or "other").strip().lower() or "other"
        layer_id = str(payload.get("layer_id") or "").strip()
        layer_name = str(payload.get("layer_name") or "").strip()
        source_slot = normalize_binding_role(str(payload.get("source_slot") or "").strip())
        source_item_id = str(payload.get("source_item_id") or "").strip()
        if not field_name:
            return binding.normalized()
        updated = binding.normalized()
        updated.source_id = layer_id or updated.source_id
        updated.source_name = layer_name or updated.source_name
        if not updated.chart_type:
            updated.chart_type = "bar"
        if not slot_name or slot_name == "auto":
            slot_name = suggest_binding_slot(updated.chart_type, field_group, updated)
        if not slot_name or not is_binding_slot_compatible(updated.chart_type, slot_name, field_group):
            self.builder_selected_visual_label.setText(_rt("Campo incompativel com este slot"))
            return updated.normalized()
        current_bindings = {
            role: [item.normalized(role, index) for index, item in enumerate(list(items or []))]
            for role, items in dict(updated.bindings or {}).items()
        }
        if source_slot and source_item_id and source_item_id == str(updated.chart_id or "") and source_slot != slot_name:
            current_bindings[source_slot] = [
                item.normalized(source_slot, index)
                for index, item in enumerate(list(current_bindings.get(source_slot) or []))
                if item.field != field_name
            ]
        role_items = list(current_bindings.get(slot_name) or [])
        item = self._field_binding_item_from_payload(slot_name, payload, len(role_items))
        if item is None:
            return updated.normalized()
        if any(existing.field.lower() == item.field.lower() for existing in role_items):
            return updated.normalized()
        slot_def = next((slot for slot in binding_slot_definitions(updated.chart_type) if str(slot.get("name") or "") == slot_name), {})
        if not bool(slot_def.get("multiple", True)):
            role_items = []
        role_items.append(item)
        current_bindings[slot_name] = role_items
        updated.bindings = current_bindings
        return updated.normalized()

    def _remove_binding_slot_value(self, binding: DashboardChartBinding, slot_name: str, field_name: str = "") -> DashboardChartBinding:
        updated = binding.normalized()
        slot_name = normalize_binding_role(slot_name)
        field_name = str(field_name or "").strip()
        role_items = list(updated.bindings.get(slot_name) or [])
        if field_name:
            role_items = [item for item in role_items if item.field != field_name]
        else:
            role_items = []
        updated.bindings[slot_name] = [item.normalized(slot_name, index) for index, item in enumerate(role_items)]
        return updated.normalized()

    def _change_binding_slot_aggregation(self, binding: DashboardChartBinding, slot_name: str, field_name: str, aggregation: str) -> DashboardChartBinding:
        updated = binding.normalized()
        role = normalize_binding_role(slot_name)
        items = []
        for index, item in enumerate(list(updated.bindings.get(role) or [])):
            if item.field == field_name:
                item = FieldBindingItem(item.field, item.display_name, item.type, aggregation, role, index).normalized(role, index)
            items.append(item.normalized(role, index))
        updated.bindings[role] = items
        return updated.normalized()

    def _move_binding_slot_field(self, binding: DashboardChartBinding, slot_name: str, field_name: str, delta: int) -> DashboardChartBinding:
        updated = binding.normalized()
        role = normalize_binding_role(slot_name)
        items = list(updated.bindings.get(role) or [])
        current = next((index for index, item in enumerate(items) if item.field == field_name), -1)
        if current < 0:
            return updated
        target = max(0, min(len(items) - 1, current + int(delta or 0)))
        if target == current:
            return updated
        item = items.pop(current)
        items.insert(target, item)
        updated.bindings[role] = [item.normalized(role, index) for index, item in enumerate(items)]
        return updated.normalized()

    def _update_selected_visual_binding_controls(self):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = item.binding.normalized()
        binding.aggregation = str(self.builder_agg_combo.currentData() or "count").strip().lower() or "count"
        binding.top_n = max(1, int(self.builder_topn_spin.value()))
        binding.title_override = str(self.builder_title_edit.text() or "").strip()
        for role in (ROLE_VALUES, ROLE_Y_AXIS):
            items = list(binding.bindings.get(role) or [])
            if items:
                first = items[0]
                items[0] = FieldBindingItem(first.field, first.display_name, first.type, binding.aggregation, first.role, first.order).normalized(first.role, first.order)
                binding.bindings[role] = items
                break
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _apply_dropped_field_to_selected_visual(self, slot_name: str, payload):
        item = self._selected_canvas_item()
        if item is None or not isinstance(payload, dict):
            return
        binding = self._apply_field_payload_to_binding(item.binding, slot_name, payload)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _remove_selected_visual_slot_field(self, slot_name: str, field_name: str = ""):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._remove_binding_slot_value(item.binding, slot_name, field_name)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _change_selected_visual_slot_aggregation(self, slot_name: str, field_name: str, aggregation: str):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._change_binding_slot_aggregation(item.binding, slot_name, field_name, aggregation)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _move_selected_visual_slot_field(self, slot_name: str, field_name: str, delta: int):
        item = self._selected_canvas_item()
        if item is None:
            return
        binding = self._move_binding_slot_field(item.binding, slot_name, field_name, delta)
        updated_item = self._rebuild_chart_item_from_binding(item, binding)
        if updated_item is not None:
            self._replace_canvas_item(updated_item)

    def _handle_field_list_activation(self, payload):
        if not isinstance(payload, dict):
            return
        binding = self._active_selected_binding() or DashboardChartBinding(chart_type="bar")
        suggested = suggest_binding_slot(binding.chart_type or "bar", str(payload.get("field_group") or "other"), binding)
        self._apply_dropped_field_to_selected_visual(suggested, payload)

    def _refresh_builder_layers(self):
        previous_layer_id = self._current_builder_layer_id()
        selected_binding = self._active_selected_binding()
        if selected_binding is not None and selected_binding.source_id:
            previous_layer_id = str(selected_binding.source_id or previous_layer_id)
        self._builder_layers = {}
        self.builder_layer_combo.blockSignals(True)
        project = QgsProject.instance()
        for layer in list(project.mapLayers().values()):
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                continue
            self._builder_layers[layer.id()] = layer
        database_layer = getattr(self, "_builder_database_layer", None)
        if isinstance(database_layer, QgsVectorLayer) and database_layer.isValid():
            self._builder_layers[database_layer.id()] = database_layer
        if previous_layer_id and previous_layer_id in self._builder_layers:
            try:
                self.builder_layer_combo.setLayer(self._builder_layers[previous_layer_id])
            except Exception:
                log_exception("falha opcional ignorada")
        self.builder_layer_combo.blockSignals(False)
        self._on_builder_layer_changed()
        self._sync_builder_selection_state()

    def _on_builder_layer_changed(self, *_args):
        if _args and not bool(getattr(self, "_selecting_database_layer_fields", False)):
            self._builder_database_layer_active = False
            self._set_builder_source_hint("")
            self._set_builder_database_source_display("")
        layer = self._current_builder_layer()
        self.builder_dimension_combo.blockSignals(True)
        self.builder_value_combo.blockSignals(True)
        self.builder_dimension_combo.clear()
        self.builder_value_combo.clear()
        self.builder_value_combo.addItem(_rt("Contagem"), "__count__")
        if layer is not None:
            for field_def in list(layer.fields()):
                field_name = str(field_def.name() or "").strip()
                if not field_name:
                    continue
                self.builder_dimension_combo.addItem(field_name, field_name)
                if field_is_numeric(field_def):
                    self.builder_value_combo.addItem(field_name, field_name)
        self.builder_dimension_combo.blockSignals(False)
        self.builder_value_combo.blockSignals(False)
        self._refresh_builder_field_lists(layer)
        self._on_builder_value_changed()
        selected_item = self._selected_canvas_item()
        if selected_item is not None:
            binding = selected_item.binding.normalized()
            if layer is not None and binding.source_id != layer.id():
                binding.source_id = layer.id()
                binding.source_name = layer.name()
                updated_item = self._rebuild_chart_item_from_binding(selected_item, binding)
                if updated_item is not None:
                    self._replace_canvas_item(updated_item)

    def _on_builder_value_changed(self):
        value_key = str(self.builder_value_combo.currentData() or "__count__")
        preferred = "count" if value_key == "__count__" else "sum"
        index = self.builder_agg_combo.findData(preferred)
        if index >= 0:
            self.builder_agg_combo.setCurrentIndex(index)

    def _rebuild_chart_item_from_binding(self, item: DashboardChartItem, binding: DashboardChartBinding) -> Optional[DashboardChartItem]:
        if item is None:
            return None
        updated_binding = binding.normalized()
        layer = self._builder_layers.get(str(updated_binding.source_id or ""))
        if layer is None:
            layer = self._selected_layer()
        return rebuild_chart_item_from_binding(item, updated_binding, layer)

    def _toolbar_button_icon(self, button, icon_name: str, icon_size: int, icon_color: str = ""):
        color = str(icon_color or "")
        return _model_tinted_svg_icon(icon_name, icon_size, color)

    def _configure_toolbar_icon_button(self, button, icon_name: str, tooltip: str, icon_size: int = 20, icon_color: str = ""):
        button.setProperty("toolbarMode", "icon")
        button.setProperty("modelIconName", icon_name)
        button.setProperty("modelIconSize", int(icon_size))
        button.setProperty("modelIconColor", str(icon_color or ""))
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        set_walker_tooltip(button, tooltip)
        button.setStatusTip(tooltip)
        try:
            button.setAccessibleName(tooltip)
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            button.setText("")
        except Exception:
            log_exception("falha opcional ignorada")
        icon = self._toolbar_button_icon(button, icon_name, icon_size, icon_color)
        if not icon.isNull():
            button.setIcon(icon)
        button.setIconSize(QSize(icon_size, icon_size))
        try:
            button.toggled.connect(
                lambda checked, b=button, name=icon_name, size=icon_size, color=icon_color: b.setIcon(
                    _model_tinted_svg_icon(name, size, color)
                )
            )
        except Exception:
            log_exception("falha opcional ignorada")
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setAutoRaise(False)

    def _configure_toolbar_text_icon_button(self, button, icon_name: str, text: str, tooltip: str, icon_size: int = 20, icon_color: str = ""):
        self._configure_toolbar_icon_button(button, icon_name, tooltip, icon_size=icon_size, icon_color=icon_color)
        button.setProperty("toolbarMode", "label")
        try:
            button.setText(text)
        except Exception:
            log_exception("falha opcional ignorada")

    def _create_toolbar_separator(self, parent: QWidget) -> QFrame:
        separator = QFrame(parent)
        separator.setObjectName("ModelToolbarSeparator")
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        return separator

    def _sync_toolbar_separator_visibility(self):
        visual_strip = getattr(self, "toolbar_visuals_strip", None)
        visual_types_visible = bool(visual_strip is not None and visual_strip.isVisible())
        for separator, visible in (
            (getattr(self, "visual_types_leading_separator", None), visual_types_visible),
            (getattr(self, "visual_types_trailing_separator", None), False),
        ):
            if separator is not None:
                separator.setVisible(bool(visible))

    def _toolbar_visual_type_buttons(self) -> List[QToolButton]:
        visual_strip = getattr(self, "toolbar_visuals_strip", None)
        if visual_strip is None:
            return []
        layout = visual_strip.layout()
        if layout is None:
            return []
        buttons: List[QToolButton] = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QToolButton) and str(widget.property("visualType") or "").strip():
                buttons.append(widget)
        return buttons

    def _toolbar_visual_controls(self) -> List[QToolButton]:
        visual_strip = getattr(self, "toolbar_visuals_strip", None)
        if visual_strip is None:
            return []
        layout = visual_strip.layout()
        if layout is None:
            return []
        controls: List[QToolButton] = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, QToolButton):
                controls.append(widget)
        return controls

    def _sync_toolbar_visuals_strip_visibility(self):
        visual_strip = getattr(self, "toolbar_visuals_strip", None)
        if visual_strip is None:
            return
        has_project = self.current_project is not None
        edit_enabled = bool(self.edit_mode_btn.isChecked())
        base_visible = toolbar_visuals_should_be_visible(
            has_project=has_project,
            edit_enabled=edit_enabled,
            create_chart_checked=bool(self.create_chart_btn.isChecked()),
            builder_panel_open=bool(getattr(self, "_builder_panel_open", False)),
            visual_panel_open=bool(getattr(self, "_visual_panel_open", False)),
        )
        buttons = self._toolbar_visual_controls()
        if not base_visible or not buttons:
            try:
                set_chart_overflow_expanded(visual_strip, False)
            except Exception:
                log_exception("falha opcional ignorada")
            for button in buttons:
                button.setVisible(False)
            visual_strip.setVisible(False)
            self._sync_toolbar_separator_visibility()
            for widget in (visual_strip, getattr(self, "toolbar_strip", None), self):
                if widget is not None:
                    try:
                        widget.updateGeometry()
                    except Exception:
                        log_exception("falha opcional ignorada")
            return

        self._toolbar_visuals_sync_retries = 0
        for button in buttons:
            if not bool(button.property("overflowExtra")):
                button.setVisible(True)
        set_chart_overflow_expanded(visual_strip, bool(getattr(visual_strip, "_model_visual_overflow_expanded", False)))
        visual_strip.setVisible(True)
        self._sync_toolbar_separator_visibility()
        for widget in (visual_strip, getattr(self, "toolbar_strip", None), self):
            if widget is not None:
                try:
                    widget.updateGeometry()
                except Exception:
                    log_exception("falha opcional ignorada")

    def _schedule_toolbar_visuals_strip_visibility(self):
        try:
            QTimer.singleShot(0, self._sync_toolbar_visuals_strip_visibility)
        except Exception:
            self._sync_toolbar_visuals_strip_visibility()

    def _normalized_canvas_style(self, style: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        return normalize_canvas_style(style, base=default_canvas_style())

    def _default_canvas_style(self) -> Dict[str, object]:
        return default_canvas_style()

    def _project_canvas_style(self) -> Dict[str, object]:
        if self.current_project is None:
            return default_canvas_style()
        source_meta = dict(getattr(self.current_project, "source_meta", {}) or {})
        return self._normalized_canvas_style(source_meta.get("canvas_style"))

    def _apply_canvas_style_to_widget(self, widget: Optional[DashboardPageWidget], style: Dict[str, object]):
        if widget is None or not hasattr(widget, "canvas"):
            return
        canvas_style = self._normalized_canvas_style(style)
        try:
            widget.canvas.set_canvas_style(
                background_color=canvas_style["background"],
                grid_color=canvas_style["grid_color"],
                show_grid=canvas_style["show_grid"],
                grid_size=canvas_style["grid_size"],
                grid_opacity=canvas_style["grid_opacity"],
            )
        except Exception:
            log_exception("falha opcional ignorada")

    def _apply_canvas_style_to_pages(
        self,
        style: Optional[Dict[str, object]] = None,
        *,
        persist: bool = False,
        mark_dirty: bool = False,
        record_history: bool = False,
    ):
        canvas_style = self._normalized_canvas_style(style if style is not None else self._project_canvas_style())
        if persist and self.current_project is not None:
            source_meta = dict(getattr(self.current_project, "source_meta", {}) or {})
            self.current_project.source_meta = apply_canvas_style_to_source_meta(source_meta, canvas_style)
        for widget in self._page_widgets_in_order():
            self._apply_canvas_style_to_widget(widget, canvas_style)
        if self.current_project is not None and mark_dirty:
            self._dirty = True
        if record_history:
            self._commit_history_if_changed()
        self._refresh_ui_state()

    def _normalize_project_source_meta(self, source_meta: Optional[Dict[str, object]]) -> Dict[str, object]:
        return normalize_project_source_meta(source_meta, canvas_style_normalizer=self._normalized_canvas_style)

    def _normalize_loaded_project(self, project: DashboardProject) -> DashboardProject:
        return normalize_loaded_project(
            project,
            page_title_provider=self._page_display_title,
            canvas_style_normalizer=self._normalized_canvas_style,
        )

    def _open_canvas_style_settings(self):
        if self.current_project is None:
            return
        style = self._project_canvas_style()
        updated = open_canvas_style_dialog(self, style)
        if updated is None:
            return
        self._apply_canvas_style_to_pages(updated, persist=True, mark_dirty=True, record_history=True)

    def _project_snapshot_payload(self) -> Optional[Dict[str, object]]:
        if self.current_project is None:
            return None
        try:
            self._sync_project_from_pages(self._current_page_id())
        except Exception:
            log_exception("falha opcional ignorada")
        return project_snapshot_payload(self.current_project, page_title_provider=self._page_display_title)

    def _snapshot_state(self) -> Dict[str, object]:
        return snapshot_state(self._project_snapshot_payload(), self.current_path, self._dirty)

    def _snapshot_signature(self, snapshot: Optional[Dict[str, object]]) -> str:
        return snapshot_signature(snapshot)

    def _reset_history(self):
        self._history_undo.clear()
        self._history_redo.clear()
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _commit_history_if_changed(self):
        if self._history_restoring:
            return
        current_snapshot = self._snapshot_state()
        if self._history_current is None:
            self._history_current = current_snapshot
            self._update_undo_redo_buttons()
            return
        if self._snapshot_signature(current_snapshot) == self._snapshot_signature(self._history_current):
            self._update_undo_redo_buttons()
            return
        self._history_undo.append(self._history_current)
        if len(self._history_undo) > self._history_limit:
            self._history_undo = self._history_undo[-self._history_limit:]
        self._history_current = current_snapshot
        self._history_redo.clear()
        self._update_undo_redo_buttons()

    def _restore_history_snapshot(self, snapshot: Dict[str, object]):
        payload = dict(snapshot or {})
        project_payload = payload.get("project")
        self._history_restoring = True
        self._suspend_canvas_events = True
        try:
            if project_payload is None:
                self.current_project = None
                self.current_path = ""
                self._dirty = False
                self._selected_page_id = ""
                self._clear_page_widgets()
                self._clear_page_tab_buttons()
                self.canvas = None
            else:
                project = DashboardProject.from_dict(project_payload)
                self.current_project = project
                raw_path = str(payload.get("path") or "")
                self.current_path = self.store.normalize_path(raw_path) if raw_path else ""
                self._dirty = bool(payload.get("dirty"))
                self._selected_page_id = ""
                self._rebuild_page_stack(project.active_page_id or (project.pages[0].page_id if project.pages else ""))
                self.edit_mode_btn.blockSignals(True)
                try:
                    self.edit_mode_btn.setChecked(bool(project.edit_mode))
                finally:
                    self.edit_mode_btn.blockSignals(False)
                self.set_edit_mode(bool(project.edit_mode))
                self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
                self._refresh_builder_layers()
                self._refresh_ui_state()
        finally:
            self._suspend_canvas_events = False
            self._history_restoring = False

    def _undo_last_action(self):
        if not self._history_undo:
            return
        current_snapshot = self._history_current or self._snapshot_state()
        target_snapshot = self._history_undo.pop()
        self._history_redo.append(current_snapshot)
        self._restore_history_snapshot(target_snapshot)
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _redo_last_action(self):
        if not self._history_redo:
            return
        current_snapshot = self._history_current or self._snapshot_state()
        target_snapshot = self._history_redo.pop()
        self._history_undo.append(current_snapshot)
        self._restore_history_snapshot(target_snapshot)
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        has_project = self.current_project is not None
        can_undo = has_project and bool(self._history_undo)
        can_redo = has_project and bool(self._history_redo)
        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)

    def _page_widgets_in_order(self) -> List[DashboardPageWidget]:
        widgets: List[DashboardPageWidget] = []
        if not hasattr(self, "page_stack"):
            return widgets
        for index in range(self.page_stack.count()):
            widget = self.page_stack.widget(index)
            if isinstance(widget, DashboardPageWidget):
                widgets.append(widget)
        return widgets

    def _page_widget_for_id(self, page_id: str) -> Optional[DashboardPageWidget]:
        key = str(page_id or "").strip()
        if not key:
            return None
        widget = self._page_widgets.get(key)
        if widget is not None:
            return widget
        for candidate in self._page_widgets.values():
            if getattr(candidate, "page_id", "") == key:
                return candidate
        for candidate in self._page_widgets.values():
            try:
                if candidate.page_id == key:
                    return candidate
            except Exception:
                log_exception("falha opcional ignorada")
                continue
        return None

    def _clear_page_tab_buttons(self):
        if self.page_strip is not None:
            self.page_strip.clear_pages()

    def _scroll_page_tabs(self, delta: int):
        if self.page_strip is not None:
            self.page_strip.scroll_by(delta)

    def _ensure_page_button_visible(self, page_id: str):
        if self.page_strip is not None:
            self.page_strip.ensure_page_visible(page_id)

    def _select_page_button(self, page_id: str):
        target_id = str(page_id or "").strip()
        self._selected_page_id = target_id
        if self.page_strip is not None:
            self.page_strip.set_active_page(target_id)

    def _handle_page_tabs_moved(self, from_index: int, to_index: int):
        if self.current_project is None or self.page_strip is None:
            return
        order = list(self.page_strip.page_ids() or [])
        if not order:
            return
        if len(order) != len(self._page_widgets):
            self._rebuild_page_stack(self._current_page_id())
            return
        existing_widgets = dict(self._page_widgets)
        current_id = self._current_page_id() or self.current_project.active_page_id or order[0]
        self._suspend_canvas_events = True
        try:
            if hasattr(self, "page_stack"):
                while self.page_stack.count():
                    widget = self.page_stack.widget(0)
                    self.page_stack.removeWidget(widget)
            ordered_widgets: Dict[str, DashboardPageWidget] = {}
            for page_id in order:
                widget = existing_widgets.pop(page_id, None)
                if widget is None:
                    continue
                self.page_stack.addWidget(widget)
                ordered_widgets[page_id] = widget
            for widget in list(existing_widgets.values()):
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except Exception:
                    log_exception("falha opcional ignorada")
            self._page_widgets = ordered_widgets
            self._selected_page_id = str(current_id or "").strip()
            self._set_active_page(str(current_id or ""), sync_project=False, update_tabs=True)
            self._sync_project_from_pages(str(current_id or ""))
        finally:
            self._suspend_canvas_events = False
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_page_stack_current_changed(self, index: int):
        if self._suspend_canvas_events or index < 0:
            return
        widget = self.page_stack.widget(index) if hasattr(self, "page_stack") else None
        if not isinstance(widget, DashboardPageWidget):
            return
        self.canvas = widget.canvas
        self._selected_page_id = str(widget.page_id or "").strip()
        if self.page_strip is not None:
            self.page_strip.set_active_page(widget.page_id)
        if self.current_project is not None:
            self.current_project.active_page_id = str(widget.page_id or "").strip()
            try:
                self.current_project.set_active_page(widget.page_id)
            except Exception:
                log_exception("falha opcional ignorada")
        try:
            self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
        except Exception:
            log_exception("falha opcional ignorada")
        self._update_filters_bar()

    def _page_index_from_id(self, page_id: str) -> int:
        if self.current_project is None:
            return -1
        target_id = str(page_id or "").strip()
        for index, page in enumerate(list(self.current_project.pages or [])):
            if str(page.page_id or "").strip() == target_id:
                return index
        return -1

    def _current_page_id(self) -> str:
        if hasattr(self, "page_stack") and self.page_stack.count() > 0:
            candidate = self.page_stack.currentWidget()
            if isinstance(candidate, DashboardPageWidget):
                return str(candidate.page_id or "").strip()
        if self.current_project is not None:
            current_id = str(self.current_project.active_page_id or "").strip()
            if current_id:
                return current_id
        if self._selected_page_id:
            return str(self._selected_page_id).strip()
        return ""

    def _active_page_widget(self) -> Optional[DashboardPageWidget]:
        current_id = self._current_page_id()
        if current_id:
            widget = self._page_widget_for_id(current_id)
            if widget is not None:
                return widget
        if hasattr(self, "page_stack") and self.page_stack.count() > 0:
            candidate = self.page_stack.currentWidget()
            if isinstance(candidate, DashboardPageWidget):
                return candidate
        return None

    def _active_canvas(self) -> Optional[DashboardCanvas]:
        widget = self._active_page_widget()
        if widget is None:
            return None
        return widget.canvas

    def _sync_active_canvas_alias(self):
        self.canvas = self._active_canvas()
        widget = self._active_page_widget()
        if widget is not None:
            try:
                self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
            except Exception:
                log_exception("falha opcional ignorada")

    def _page_display_title(self, index: int) -> str:
        return _rt("Pagina {index}", index=max(1, int(index or 1)))

    def _create_page_widget(self, page: DashboardPage) -> DashboardPageWidget:
        widget = DashboardPageWidget(page, self.page_stack)
        self._apply_canvas_style_to_widget(widget, self._project_canvas_style())
        widget.itemsChanged.connect(lambda page_id, self=self: self._handle_canvas_changed(page_id))
        widget.filtersChanged.connect(
            lambda page_id, summary, self=self: self._handle_canvas_filters_changed(summary, page_id)
        )
        widget.zoomChanged.connect(lambda page_id, zoom, self=self: self._handle_canvas_zoom_changed(zoom, page_id))
        widget.itemSelectionChanged.connect(
            lambda page_id, item_id, item_widget, self=self: self._handle_canvas_item_selection(page_id, item_id, item_widget)
        )
        widget.fieldBindingDropRequested.connect(
            lambda page_id, item_id, slot_name, payload, self=self: self._handle_canvas_field_binding_drop(page_id, item_id, slot_name, payload)
        )
        widget.visualPanelRequested.connect(
            lambda page_id, item_id, self=self: self._handle_canvas_visual_panel_requested(page_id, item_id)
        )
        widget.canvas.emptyCanvasContextMenuRequested.connect(
            lambda pos, page_id=widget.page_id, self=self: self._open_canvas_context_menu(pos, page_id)
        )
        return widget

    def _clear_page_widgets(self):
        if not hasattr(self, "page_stack"):
            self._page_widgets.clear()
            return
        blocked = self.page_stack.blockSignals(True)
        try:
            while self.page_stack.count():
                widget = self.page_stack.widget(0)
                self.page_stack.removeWidget(widget)
        finally:
            self.page_stack.blockSignals(blocked)
        for widget in list(self._page_widgets.values()):
            try:
                widget.setParent(None)
                widget.deleteLater()
            except Exception:
                log_exception("falha opcional ignorada")
        self._page_widgets.clear()

    def _rebuild_page_stack(self, active_page_id: Optional[str] = None):
        if self.current_project is None:
            self._clear_page_widgets()
            return
        pages = [page.normalized() for page in list(self.current_project.pages or [])]
        if not pages:
            pages = [DashboardPage(title=self._page_display_title(1)).normalized()]
        if self._single_page_mode and len(pages) > 1:
            target_id = str(active_page_id or self.current_project.active_page_id or "").strip()
            selected = None
            for page in pages:
                if str(page.page_id or "").strip() == target_id:
                    selected = page.normalized()
                    break
            if selected is None:
                selected = pages[0].normalized()
            pages = [selected]
        self.current_project.pages = pages
        self.current_project.active_page_id = pages[0].page_id
        existing_widgets = dict(self._page_widgets)
        stack_blocked = False
        if hasattr(self, "page_stack"):
            stack_blocked = self.page_stack.blockSignals(True)
            while self.page_stack.count():
                widget = self.page_stack.widget(0)
                self.page_stack.removeWidget(widget)
        self._page_widgets = {}
        try:
            for page in pages:
                widget = existing_widgets.pop(page.page_id, None)
                if widget is None:
                    widget = self._create_page_widget(page)
                else:
                    widget.apply_page(page)
                    widget.set_page_identity(page.page_id, page.title)
                self._page_widgets[widget.page_id] = widget
                self.page_stack.addWidget(widget)
            for widget in list(existing_widgets.values()):
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except Exception:
                    log_exception("falha opcional ignorada")
        finally:
            if hasattr(self, "page_stack"):
                self.page_stack.blockSignals(stack_blocked)
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or pages[0].page_id or "").strip()
        self._refresh_page_tabs(resolved_active_id)
        self._set_active_page(resolved_active_id, sync_project=False, update_tabs=False)

    def _refresh_page_tabs(self, active_page_id: Optional[str] = None):
        if self.page_strip is None:
            return
        pages = list(self.current_project.pages or []) if self.current_project is not None else []
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or "").strip()
        if not resolved_active_id and pages:
            resolved_active_id = str(pages[0].page_id or "").strip()
        page_defs = []
        for index, page in enumerate(pages, start=1):
            title = str(page.title or "").strip() or self._page_display_title(index)
            page_defs.append((str(page.page_id or "").strip(), title))
        self.page_strip.set_pages(page_defs, resolved_active_id)

    def _sync_project_from_pages(self, active_page_id: Optional[str] = None):
        if self.current_project is None:
            return
        pages: List[DashboardPage] = []
        for widget in self._page_widgets_in_order():
            try:
                pages.append(widget.page_state())
            except Exception:
                log_exception("falha opcional ignorada")
                continue
        if not pages:
            pages = [DashboardPage(title=self._page_display_title(1)).normalized()]
        if self._single_page_mode and len(pages) > 1:
            target_id = str(active_page_id or self.current_project.active_page_id or "").strip()
            selected = None
            for page in pages:
                if str(page.page_id or "").strip() == target_id:
                    selected = page.normalized()
                    break
            if selected is None:
                selected = pages[0].normalized()
            pages = [selected]
        self.current_project.pages = pages
        resolved_active_id = str(active_page_id or self.current_project.active_page_id or pages[0].page_id or "").strip()
        if not resolved_active_id:
            resolved_active_id = pages[0].page_id
        self.current_project.active_page_id = resolved_active_id
        self.current_project.set_active_page(resolved_active_id)
        self.current_project.edit_mode = bool(self.edit_mode_btn.isChecked())

    def _set_active_page(self, page_id: str, sync_project: bool = True, update_tabs: bool = True):
        if self.current_project is None:
            self.canvas = None
            return
        target_id = str(page_id or "").strip()
        widget = self._page_widget_for_id(target_id)
        if widget is None:
            widget = self._active_page_widget()
        if widget is None:
            return
        if hasattr(self, "page_stack"):
            current_index = self.page_stack.indexOf(widget)
            if current_index >= 0:
                if self.page_stack.currentIndex() != current_index:
                    self.page_stack.setCurrentIndex(current_index)
        self.canvas = widget.canvas
        self._selected_page_id = str(widget.page_id or "").strip()
        self.current_project.active_page_id = str(widget.page_id or "").strip()
        if update_tabs:
            self._select_page_button(widget.page_id)
        try:
            self.current_project.set_active_page(widget.page_id)
        except Exception:
            log_exception("falha opcional ignorada")
        if sync_project:
            self._sync_project_from_pages(widget.page_id)
        try:
            self._sync_zoom_controls(int(round(float(widget.zoom_value() or 1.0) * 100.0)))
        except Exception:
            log_exception("falha opcional ignorada")

    def _page_state_by_id(self, page_id: str) -> Optional[DashboardPage]:
        key = str(page_id or "").strip()
        if not key or self.current_project is None:
            return None
        for page in list(self.current_project.pages or []):
            if str(page.page_id or "").strip() == key:
                return page
        return None

    def _add_page(self, checked: bool = False, title: Optional[str] = None, activate: bool = True):
        if self._single_page_mode:
            return
        if self._is_adding_page:
            return
        self._is_adding_page = True
        try:
            if self.current_project is None:
                # Creating the first page must stop here; otherwise we create
                # one blank project page and immediately add a second one.
                self._create_blank_project(_rt("Novo painel"))
                return
            if self.current_project is None:
                return
            current_count = len(list(self.current_project.pages or []))
            page_title = str(title or "").strip() or self._page_display_title(current_count + 1)
            page = DashboardPage(title=page_title).normalized()
            widget = self._create_page_widget(page)
            self._page_widgets[widget.page_id] = widget
            self.page_stack.addWidget(widget)
            self.current_project.pages = list(self.current_project.pages or []) + [page]
            self.current_project.active_page_id = page.page_id
            if activate:
                self._refresh_page_tabs(page.page_id)
                self._set_active_page(page.page_id, sync_project=True, update_tabs=False)
            else:
                self._refresh_page_tabs(self.current_project.active_page_id)
                self._sync_project_from_pages(self.current_project.active_page_id)
            self._dirty = True
            self._commit_history_if_changed()
            self._refresh_ui_state()
        finally:
            self._is_adding_page = False

    def _delete_current_page(self):
        self._delete_page_by_id(self._current_page_id())

    def _delete_page_by_id(self, page_id: str):
        if self._single_page_mode:
            return
        page_index = self._page_index_from_id(page_id)
        if page_index < 0 and self.page_strip is not None:
            try:
                order = list(self.page_strip.page_ids() or [])
            except Exception:
                order = []
            if order and self.current_project is not None and len(order) == len(list(self.current_project.pages or [])):
                try:
                    page_index = order.index(str(page_id or "").strip())
                except Exception:
                    page_index = -1
        if page_index < 0 or self.current_project is None:
            return
        pages = list(self.current_project.pages or [])
        if len(pages) <= 1:
            slim_message(self, _rt("Model"), _rt("O painel precisa manter ao menos uma pagina."))
            return
        pages.pop(page_index)
        self.current_project.pages = pages
        next_index = min(page_index, len(pages) - 1)
        next_page = pages[next_index]
        self.current_project.active_page_id = next_page.page_id
        self._selected_page_id = next_page.page_id
        self._dirty = True
        self._rebuild_page_stack(next_page.page_id)
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _rename_page_by_id(self, page_id: str, title: str):
        if self.current_project is None:
            return
        page = self._page_state_by_id(page_id)
        new_title = str(title or "").strip()
        if page is None or not new_title:
            return
        page.title = new_title
        widget = self._page_widget_for_id(page.page_id)
        if widget is not None:
            widget.set_page_identity(page.page_id, new_title)
        if self.page_strip is not None:
            self.page_strip.update_page_title(page.page_id, new_title)
        self._sync_project_from_pages(self._current_page_id() or page.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _build_model_chart_item_from_builder(self) -> Optional[DashboardChartItem]:
        layer = self._current_builder_layer()
        if layer is None or not layer.isValid():
            slim_message(self, _rt("Model"), _rt("Selecione uma camada valida para criar o grafico."))
            return None
        dimension_field = str(self.builder_dimension_combo.currentData() or "").strip()
        if not dimension_field:
            slim_message(self, _rt("Model"), _rt("Selecione o campo de categoria."))
            return None
        value_field = str(self.builder_value_combo.currentData() or "__count__").strip() or "__count__"
        aggregation = str(self.builder_agg_combo.currentData() or "count").strip().lower() or "count"
        chart_type = self._current_builder_chart_type()
        top_n = max(3, int(self.builder_topn_spin.value()))
        title_text = str(self.builder_title_edit.text() or "").strip()
        result = build_model_chart_item_from_layer(
            layer,
            dimension_field=dimension_field,
            value_field=value_field,
            aggregation=aggregation,
            chart_type=chart_type,
            top_n=top_n,
            title_text=title_text,
        )
        if result.error:
            slim_message(self, _rt("Model"), result.error)
            return None
        return result.item

    def _add_chart_from_builder(self):
        item = self._build_model_chart_item_from_builder()
        if item is None:
            return
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()
        self._expand_data_panel_for_new_chart()

    def _open_canvas_context_menu(self, global_pos, page_id: Optional[str] = None):
        menu = apply_walker_menu(QMenu(self))
        add_chart_action = menu.addAction(_rt("Adicionar grafico em branco"))
        open_panel_action = menu.addAction(_rt("Abrir painel de camada"))
        chosen = menu.exec_(global_pos)
        if chosen is add_chart_action:
            self._add_chart_from_builder()
        elif chosen is open_panel_action:
            self._set_builder_panel_open(True, focus=True)

    def _build_action_card(self, title: str, description: str, icon_name: str) -> QWidget:
        card = _ModelCardAction(title, description, icon_name, self)
        return card

    def current_project_name(self) -> str:
        if self.current_project is None:
            return ""
        return str(self.current_project.name or "")

    def request_add_chart(self, snapshot: Dict[str, object]) -> bool:
        chart_title = str(snapshot.get("title") or snapshot.get("payload", {}).get("title", _rt("Grafico")))
        dialog = DashboardAddDialog(
            chart_title,
            has_current_project=self.current_project is not None,
            current_project_name=self.current_project_name(),
            recent_projects=self.store.load_recents(),
            parent=self,
        )
        if dialog.exec_() != dialog.Accepted:
            return False

        selection = dialog.selection()
        mode = selection.get("mode")
        if mode == "new":
            self._create_blank_project(selection.get("name") or _rt("Novo painel"))
        elif mode == "file":
            path = selection.get("path") or ""
            if not path:
                path, _ = QFileDialog.getOpenFileName(
                    self,
                    _rt("Escolher painel salvo"),
                    self.store.default_directory(),
                    f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
                )
            if not path:
                return False
            self.open_project(path)
        elif self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))

        self.add_chart_snapshot(snapshot)
        return True

    def add_chart_snapshot(self, snapshot: Dict[str, object]):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        item = DashboardChartItem.from_chart_snapshot(snapshot)
        active_canvas = self._active_canvas()
        active_widget = self._active_page_widget()
        if active_canvas is None or active_widget is None:
            return
        active_canvas.add_item(item)
        self._sync_project_from_pages(active_widget.page_id)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def new_project(self):
        self._create_blank_project(_rt("Novo painel"))

    def _open_model_database_menu(self):
        self._refresh_model_database_status()
        connection_meta = self._current_model_database_connection_meta()
        connected_drivers = set()
        try:
            from .integration_panel import connected_database_drivers

            connected_drivers = connected_database_drivers()
        except Exception:
            log_exception("falha opcional ignorada")
        menu = apply_walker_menu(QMenu(self))
        menu.setObjectName("ModelDatabaseMenu")
        menu.setStyleSheet(
            """
            QMenu#ModelDatabaseMenu {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu#ModelDatabaseMenu::item {
                min-width: 122px;
                min-height: 28px;
                padding: 4px 10px;
                color: #111827;
                background: transparent;
                border-radius: 6px;
            }
            QMenu#ModelDatabaseMenu::item:selected {
                background: #F3F4F6;
            }
            """
        )
        upload_action = menu.addAction(_rt("Importar painel .pbsdash..."))
        upload_action.setData("__upload_pbsdash__")
        upload_action.setEnabled(bool(connection_meta))
        refresh_action = menu.addAction(_rt("Atualizar paineis do banco"))
        refresh_action.setData("__refresh_remote_projects__")
        refresh_action.setEnabled(bool(connection_meta))
        menu.addSeparator()
        for driver in ("PostgreSQL", "PostGIS", "SQL Server", "Oracle", "MySQL"):
            action = menu.addAction(driver)
            action.setData(driver)
            if driver in connected_drivers:
                action.setIcon(self._database_connected_icon())
        card = getattr(self, "model_import_card", self)
        point = card.mapToGlobal(card.rect().bottomLeft())
        point.setY(point.y() + 4)
        chosen = menu.exec_(point)
        if chosen is None:
            return
        action_data = str(chosen.data() or "PostgreSQL")
        if action_data == "__upload_pbsdash__":
            self._import_model_project_file_to_database()
            return
        if action_data == "__refresh_remote_projects__":
            self._force_refresh_remote_project_records()
            return
        self._open_model_import_dataset(action_data)

    def _refresh_model_database_status(self):
        connection_meta = self._current_model_database_connection_meta()
        try:
            from .integration_panel import connected_database_drivers

            connected = bool(connected_database_drivers()) or bool(connection_meta)
        except Exception:
            log_exception("falha opcional ignorada")
            connected = bool(connection_meta)
        card = getattr(self, "model_import_card", None)
        if hasattr(card, "set_connected"):
            card.set_connected(connected)
        self._sync_database_toolbar_button(connection_meta, connected)
        panel = getattr(self, "model_database_panel", None)
        if panel is not None:
            try:
                if connection_meta:
                    autoload = bool(getattr(self, "_database_panel_open", False) and panel.isVisible())
                    panel.set_connection(connection_meta, autoload=autoload)
                else:
                    panel.clear()
            except Exception:
                log_exception("falha opcional ignorada")
        self._refresh_remote_project_records(connection_meta)

    def _current_model_database_connection_meta(self) -> Dict:
        try:
            from .browser_integration import connection_registry
            from .database_explorer import provider_key_for_driver

            for connection in connection_registry.all_connections():
                if provider_key_for_driver(str(connection.get("driver") or "")):
                    return dict(connection)
        except Exception:
            log_exception("falha opcional ignorada")
        return {}

    def _default_remote_project_table_target(self, connection_meta: Dict) -> str:
        schema = str((connection_meta or {}).get("schema") or "public").strip() or "public"
        return f"{schema}.{DEFAULT_REMOTE_PROJECT_TABLE}"

    def _force_refresh_remote_project_records(self):
        connection_meta = self._current_model_database_connection_meta()
        if not connection_meta:
            slim_message(self, _rt("Model"), _rt("Conecte um banco de dados antes de atualizar os paineis remotos."))
            return
        self._remote_project_loaded_key = ""
        self._remote_project_requested_key = ""
        self._remote_project_records = []
        if self.current_project is None:
            self._refresh_recents()
        self._refresh_remote_project_records(connection_meta)

    def _import_model_project_file_to_database(self):
        connection_meta = self._current_model_database_connection_meta()
        if not connection_meta:
            slim_message(self, _rt("Model"), _rt("Conecte um banco de dados antes de importar o painel."))
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            _rt("Importar painel para o banco"),
            self.store.default_directory(),
            f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
        )
        if not path:
            return
        target_text, accepted = QInputDialog.getText(
            self,
            _rt("Tabela destino"),
            _rt("Informe esquema.tabela para armazenar os paineis:"),
            text=self._default_remote_project_table_target(connection_meta),
        )
        if not accepted:
            return
        schema, table = normalize_remote_project_table_target(
            target_text,
            default_schema=str(connection_meta.get("schema") or "public"),
        )
        try:
            record = ModelRemoteProjectService(connection_meta).save_project_file(path, schema=schema, table=table)
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel importar o painel para o banco: {error}", error=exc))
            return

        existing = [
            item
            for item in list(getattr(self, "_remote_project_records", []) or [])
            if getattr(item, "source_id", "") != getattr(record, "source_id", "")
        ]
        self._remote_project_records = [record] + existing
        self._remote_project_loaded_key = remote_project_connection_key(connection_meta)
        self._remote_project_requested_key = ""
        if self.current_project is None:
            self._refresh_recents()
        slim_message(
            self,
            _rt("Model"),
            _rt("Painel importado para {schema}.{table}.", schema=schema, table=table),
        )

    def _refresh_remote_project_records(self, connection_meta: Dict):
        if getattr(self, "_remote_project_shutting_down", False):
            return
        key = remote_project_connection_key(connection_meta)
        if not key:
            if self._remote_project_records:
                self._remote_project_records = []
                if self.current_project is None:
                    self._refresh_recents()
            self._remote_project_loaded_key = ""
            self._remote_project_requested_key = ""
            self._remote_project_pending_meta = {}
            return
        if key in {self._remote_project_loaded_key, self._remote_project_requested_key}:
            return
        if self._remote_project_thread is not None:
            self._remote_project_pending_meta = dict(connection_meta or {})
            return
        self._remote_project_records = []
        self._remote_project_requested_key = key
        self._remote_project_pending_meta = {}
        if self.current_project is None:
            self._refresh_recents()

        thread = QThread()
        worker = _ModelRemoteProjectsWorker(connection_meta, key)
        worker.moveToThread(thread)
        _retain_remote_project_thread(thread, worker)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_remote_project_scan_result)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_remote_project_worker)
        self._remote_project_thread = thread
        self._remote_project_worker = worker
        thread.start()

    def _handle_remote_project_scan_result(self, payload):
        try:
            key, result, canceled = payload
        except Exception:
            key, result, canceled = "", RemoteProjectScanResult([], False, ""), False
        if canceled or getattr(self, "_remote_project_shutting_down", False):
            return
        if key != self._remote_project_requested_key:
            return
        self._remote_project_loaded_key = key
        self._remote_project_requested_key = ""
        try:
            self._remote_project_records = list(getattr(result, "records", []) or [])
        except Exception:
            self._remote_project_records = []
        if self.current_project is None:
            self._refresh_recents()

    def _clear_remote_project_worker(self):
        self._remote_project_thread = None
        self._remote_project_worker = None
        pending = dict(getattr(self, "_remote_project_pending_meta", {}) or {})
        self._remote_project_pending_meta = {}
        if getattr(self, "_remote_project_shutting_down", False):
            return
        if pending:
            self._refresh_remote_project_records(pending)

    def _stop_remote_project_worker(self, wait_ms: int = 750) -> bool:
        thread = getattr(self, "_remote_project_thread", None)
        worker = getattr(self, "_remote_project_worker", None)
        self._remote_project_pending_meta = {}
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                log_exception("falha opcional ignorada")
            try:
                worker.finished.disconnect(self._handle_remote_project_scan_result)
            except Exception:
                log_exception("falha opcional ignorada")
        if thread is None:
            self._remote_project_worker = None
            return True
        try:
            thread.requestInterruption()
        except Exception:
            log_exception("falha opcional ignorada")
        try:
            thread.quit()
        except Exception:
            log_exception("falha opcional ignorada")
        finished = True
        try:
            if thread.isRunning():
                finished = bool(thread.wait(max(0, int(wait_ms or 0))))
        except Exception:
            finished = False
        if finished:
            self._remote_project_thread = None
            self._remote_project_worker = None
        return finished

    def cleanup(self):
        self._remote_project_shutting_down = True
        self._stop_remote_project_worker(wait_ms=750)

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def open_remote_project(self, record: RemoteProjectRecord):
        payload = dict(getattr(record, "payload", {}) or {})
        if not payload:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel abrir o painel remoto."))
            return
        try:
            project = DashboardProject.from_dict(payload)
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel abrir o painel remoto: {error}", error=exc))
            return
        source_meta = dict(project.source_meta or {})
        source_meta["remote_project"] = {
            "source": "database",
            "connection": str(getattr(record, "connection_label", "") or ""),
            "schema": str(getattr(record, "schema", "") or ""),
            "table": str(getattr(record, "table", "") or ""),
            "row_id": str(getattr(record, "row_id", "") or ""),
            "source_file": str(getattr(record, "source_file", "") or ""),
            "can_edit": bool(getattr(record, "can_edit", False)),
        }
        if not bool(getattr(record, "can_edit", False)):
            project.edit_mode = False
        project.source_meta = self._normalize_project_source_meta(source_meta)
        project = self._normalize_loaded_project(project)
        self._reset_model_side_panels_collapsed()
        self.current_project = project
        self.current_path = ""
        self._current_remote_project_connection_meta = dict(
            getattr(record, "connection_meta", {}) or self._current_model_database_connection_meta()
        )
        self._dirty = False
        self._selected_page_id = ""
        self._rebuild_page_stack(project.active_page_id or (project.pages[0].page_id if project.pages else ""))
        self.edit_mode_btn.blockSignals(True)
        try:
            self.edit_mode_btn.setChecked(bool(project.edit_mode))
        finally:
            self.edit_mode_btn.blockSignals(False)
        self.set_edit_mode(bool(project.edit_mode))
        self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
        self._refresh_builder_layers()
        self._reset_history()
        self._refresh_ui_state()

    def _current_remote_project_meta(self) -> Dict[str, object]:
        if self.current_project is None:
            return {}
        source_meta = getattr(self.current_project, "source_meta", {}) or {}
        if not isinstance(source_meta, dict):
            return {}
        remote_meta = source_meta.get("remote_project")
        if not isinstance(remote_meta, dict):
            return {}
        return dict(remote_meta)

    def _current_project_is_locked_database_project(self) -> bool:
        remote_meta = self._current_remote_project_meta()
        if not remote_meta:
            return False
        if str(remote_meta.get("source") or "").strip().lower() != "database":
            return False
        if self.current_path:
            return False
        return not bool(remote_meta.get("can_edit"))

    def _remote_project_permission_target(self) -> str:
        remote_meta = self._current_remote_project_meta()
        schema = str(remote_meta.get("schema") or "").strip()
        table = str(remote_meta.get("table") or "").strip()
        if schema and table:
            return f"{schema}.{table}"
        if table:
            return table
        return str(remote_meta.get("connection") or "").strip() or _rt("banco de dados")

    def _show_remote_edit_blocked_message(self):
        target = self._remote_project_permission_target()
        slim_message(
            self,
            _rt("Model"),
            _rt(
                "Este painel veio do banco de dados e seu usuario nao tem permissao de edicao em {target}.",
                target=target,
            ),
        )

    def _handle_model_database_object_activated(self, database_object):
        if database_object is None:
            return
        schema = str(getattr(database_object, "schema", "") or "").strip()
        table_name = str(getattr(database_object, "name", "") or "").strip()
        geometry_column = str(getattr(database_object, "geometry_column", "") or "").strip()
        if not table_name:
            return
        layer = self._create_model_database_field_layer(database_object)
        if layer is None or not layer.isValid():
            slim_message(
                self,
                _rt("Banco"),
                _rt("Nao foi possivel consultar os campos desta camada."),
            )
            return
        try:
            layer.setCustomProperty("summarizer/database/schema", schema)
            layer.setCustomProperty("summarizer/database/table", table_name)
            layer.setCustomProperty("summarizer/database/geometry_column", geometry_column)
        except Exception:
            log_exception("falha opcional ignorada")
        self._builder_layers[layer.id()] = layer
        self._builder_database_layer = layer
        self._builder_database_layer_id = str(layer.id() or "")
        self._builder_database_layer_active = True
        self._data_panel_collapsed = False
        self._set_data_panel_available(True)
        source_label = f"{schema}.{table_name}" if schema else table_name
        self._set_builder_source_hint("")
        self._set_builder_database_source_display(source_label)
        try:
            self._selecting_database_layer_fields = True
            self._refresh_builder_field_lists(layer)
            self._on_builder_layer_changed()
        except Exception:
            log_exception("falha opcional ignorada")
        finally:
            self._selecting_database_layer_fields = False
        self._sync_data_panel_chrome()
        self._ensure_canvas_splitter_sizes()

    def _create_model_database_field_layer(self, database_object) -> Optional[QgsVectorLayer]:
        connection_meta = self._current_model_database_connection_meta()
        if not connection_meta:
            return None
        table_name = str(getattr(database_object, "name", "") or "").strip()
        provider_key = str(getattr(database_object, "provider_key", "") or "").strip()
        if provider_key and provider_key != "postgres":
            return None
        try:
            source_uri = str(getattr(database_object, "uri", "") or "").strip()
            if not source_uri:
                source_uri = DatabaseMetadataService.build_object_uri(connection_meta, database_object)
        except Exception:
            log_exception("falha opcional ignorada")
            source_uri = ""
        if not source_uri:
            return None
        try:
            layer = QgsVectorLayer(source_uri, table_name or _rt("Banco"), "postgres")
        except Exception:
            log_exception("falha opcional ignorada")
            return None
        return layer if isinstance(layer, QgsVectorLayer) and layer.isValid() else None

    def _find_project_layer_for_database_object(self, database_object) -> Optional[QgsVectorLayer]:
        schema = str(getattr(database_object, "schema", "") or "").strip().lower()
        table_name = str(getattr(database_object, "name", "") or "").strip().lower()
        geometry_column = str(getattr(database_object, "geometry_column", "") or "").strip().lower()
        if not table_name:
            return None
        for layer in list(QgsProject.instance().mapLayers().values()):
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                continue
            layer_schema = str(layer.customProperty("summarizer/database/schema", "") or "").strip().lower()
            layer_table = str(layer.customProperty("summarizer/database/table", "") or "").strip().lower()
            layer_geom = str(layer.customProperty("summarizer/database/geometry_column", "") or "").strip().lower()
            if layer_table == table_name and (not schema or layer_schema == schema):
                if not geometry_column or not layer_geom or layer_geom == geometry_column:
                    return layer
            source = str(layer.source() or "").lower()
            if table_name in source and (not schema or schema in source):
                if not geometry_column or geometry_column in source:
                    return layer
            if str(layer.name() or "").strip().lower() == table_name:
                return layer
        return None

    def _auto_connect_saved_model_databases(self):
        try:
            from .browser_integration import connection_registry
            from .integration_panel import auto_connect_saved_databases

            saved = connection_registry.saved_connections()
            if saved:
                auto_connect_saved_databases(saved)
        except Exception:
            log_exception("falha opcional ignorada")
        self._refresh_model_database_status()

    def _database_connected_icon(self) -> QIcon:
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#22C55E"))
        painter.drawEllipse(QRectF(3.0, 3.0, 8.0, 8.0))
        painter.end()
        return QIcon(pixmap)

    def _open_model_import_dataset(self, preferred_driver: str = "PostgreSQL"):
        try:
            from .browser_integration import connection_registry
            from .integration_panel import DatabaseImportDialog

            saved = connection_registry.saved_connections()
            dialog = DatabaseImportDialog(self, saved, preferred_driver=preferred_driver)
            result = dialog.exec_()
            self._refresh_model_database_status()
            if result != QDialog.Accepted:
                return
            df, metadata, connection_meta, session_connection = dialog.result()
            host = self.window()
            register = getattr(host, "register_integration_dataframe", None)
            if callable(register) and df is not None and not df.empty:
                register(df, metadata or {"connector": preferred_driver})
            if session_connection:
                connection_registry.register_runtime_connection(session_connection)
            if connection_meta:
                fingerprint = connection_meta.get("fingerprint")
                saved = [
                    conn
                    for conn in connection_registry.saved_connections()
                    if conn.get("fingerprint") != fingerprint
                ]
                saved.insert(0, connection_meta)
                connection_registry.replace_saved_connections(saved, persist=True)
            self._refresh_model_database_status()
            return
        except Exception:
            log_exception("falha opcional ignorada")
        host = self.window()
        for method_name in ("open_get_data_dialog", "show_integration_page"):
            method = getattr(host, method_name, None)
            if callable(method):
                try:
                    method()
                    return
                except Exception:
                    log_exception("falha opcional ignorada")
        parent = self.parent()
        while parent is not None:
            for method_name in ("open_get_data_dialog", "show_integration_page"):
                method = getattr(parent, method_name, None)
                if callable(method):
                    try:
                        method()
                        return
                    except Exception:
                        log_exception("falha opcional ignorada")
            parent = parent.parent()

    def close_project(self):
        if self.current_project is not None and self._dirty:
            answer = QMessageBox.question(
                self,
                _rt("Model"),
                _rt("O painel atual tem alterações não salvas. Deseja salvar antes de fechar?"),
                buttons=QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                defaultButton=QMessageBox.Yes,
            )
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Yes:
                self.save_project()
                if self.current_project is not None and self._dirty:
                    return
        self.current_project = None
        self.current_path = ""
        self._current_remote_project_connection_meta = {}
        self._dirty = False
        self._selected_page_id = ""
        self._suspend_canvas_events = True
        try:
            self._clear_page_widgets()
            self._clear_page_tab_buttons()
            self.canvas = None
        finally:
            self._suspend_canvas_events = False
        self._refresh_builder_layers()
        self._refresh_recents()
        self._reset_history()
        self._refresh_ui_state()

    def _create_blank_project(self, name: str):
        self._reset_model_side_panels_collapsed()
        page = DashboardPage(title=self._page_display_title(1)).normalized()
        self.current_project = DashboardProject(
            name=str(name or _rt("Novo painel")),
            pages=[page],
            active_page_id=page.page_id,
        )
        self._current_remote_project_connection_meta = {}
        self.current_project.edit_mode = bool(self.edit_mode_btn.isChecked())
        self.current_project.source_meta = self._normalize_project_source_meta(
            {"canvas_style": self._default_canvas_style()}
        )
        self.current_path = ""
        self._dirty = False
        self._rebuild_page_stack(page.page_id)
        self._set_active_page(page.page_id, sync_project=False, update_tabs=False)
        self.set_edit_mode(bool(self.edit_mode_btn.isChecked()))
        self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
        self._refresh_builder_layers()
        self._reset_history()
        self._refresh_ui_state()

    def open_project(self, path: Optional[str] = None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                _rt("Abrir painel salvo"),
                self.store.default_directory(),
                f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
            )
        if not path:
            return
        try:
            project = self.store.load_project(path)
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel abrir o painel: {error}", error=exc))
            return
        project = self._normalize_loaded_project(project)
        self._reset_model_side_panels_collapsed()
        self.current_project = project
        self.current_path = self.store.normalize_path(path)
        self._current_remote_project_connection_meta = {}
        self._dirty = False
        self._selected_page_id = ""
        self._rebuild_page_stack(project.active_page_id or (project.pages[0].page_id if project.pages else ""))
        self.edit_mode_btn.blockSignals(True)
        try:
            self.edit_mode_btn.setChecked(bool(project.edit_mode))
        finally:
            self.edit_mode_btn.blockSignals(False)
        self.set_edit_mode(bool(project.edit_mode))
        self._apply_canvas_style_to_pages(self._project_canvas_style(), persist=False, mark_dirty=False, record_history=False)
        self._refresh_builder_layers()
        self._refresh_recents()
        self._reset_history()
        self._refresh_ui_state()

    def import_project(self):
        self.open_project()

    def save_project(self, save_as: bool = False):
        if self.current_project is None:
            self._create_blank_project(_rt("Novo painel"))
        if self.current_project is None:
            return
        active_widget = self._active_page_widget()
        if active_widget is not None:
            self._sync_project_from_pages(active_widget.page_id)
        if not save_as and self._current_project_should_save_to_remote_database():
            self._save_current_project_to_remote_database()
            return
        target_path = self.current_path
        if save_as or not target_path:
            suggested_name = (self.current_project.name or _rt("painel")).strip().replace(" ", "_")
            suggested_path = os.path.join(self.store.default_directory(), suggested_name)
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                _rt("Salvar painel"),
                suggested_path,
                f"Summarizer Dashboard (*{PROJECT_EXTENSION});;JSON (*.json)",
            )
        if not target_path:
            return
        try:
            self.current_path = self.store.save_project(target_path, self.current_project)
            self._current_remote_project_connection_meta = {}
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel salvar o painel: {error}", error=exc))
            return
        self._dirty = False
        self._history_current = self._snapshot_state()
        self._refresh_recents()
        self._update_undo_redo_buttons()
        self._refresh_ui_state()

    def _current_project_should_save_to_remote_database(self) -> bool:
        if self.current_project is None or self.current_path:
            return False
        if not bool(self.edit_mode_btn.isChecked()):
            return False
        remote_meta = self._current_remote_project_meta()
        if str(remote_meta.get("source") or "").strip().lower() != "database":
            return False
        if not bool(remote_meta.get("can_edit")):
            return False
        return bool(str(remote_meta.get("schema") or "").strip() and str(remote_meta.get("table") or "").strip())

    def _remote_project_connection_meta_for_save(self) -> Dict:
        connection_meta = dict(getattr(self, "_current_remote_project_connection_meta", {}) or {})
        if connection_meta:
            return connection_meta
        return self._current_model_database_connection_meta()

    def _replace_remote_project_record(self, record: RemoteProjectRecord):
        schema = str(getattr(record, "schema", "") or "")
        table = str(getattr(record, "table", "") or "")
        row_id = str(getattr(record, "row_id", "") or "")
        source_id = str(getattr(record, "source_id", "") or "")
        updated = []
        for item in list(getattr(self, "_remote_project_records", []) or []):
            same_source = source_id and str(getattr(item, "source_id", "") or "") == source_id
            same_row = (
                row_id
                and str(getattr(item, "schema", "") or "") == schema
                and str(getattr(item, "table", "") or "") == table
                and str(getattr(item, "row_id", "") or "") == row_id
            )
            if same_source or same_row:
                continue
            updated.append(item)
        self._remote_project_records = [record] + updated

    def _save_current_project_to_remote_database(self):
        if self.current_project is None:
            return
        remote_meta = self._current_remote_project_meta()
        schema = str(remote_meta.get("schema") or "").strip()
        table = str(remote_meta.get("table") or "").strip()
        row_id = str(remote_meta.get("row_id") or "").strip()
        source_file = str(remote_meta.get("source_file") or "").strip()
        connection_meta = self._remote_project_connection_meta_for_save()
        if not connection_meta:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel salvar no banco: conexao indisponivel."))
            return
        if not schema or not table:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel salvar no banco: tabela do painel indisponivel."))
            return
        try:
            self.current_project.edit_mode = bool(self.edit_mode_btn.isChecked())
            payload = self.current_project.to_dict()
            record = ModelRemoteProjectService(connection_meta).save_project_payload(
                payload,
                schema=schema,
                table=table,
                source_file=source_file,
                row_id=row_id,
            )
        except Exception as exc:
            slim_message(self, _rt("Model"), _rt("Nao foi possivel salvar o painel no banco: {error}", error=exc))
            return

        source_meta = dict(self.current_project.source_meta or {})
        remote_meta = dict(source_meta.get("remote_project") or {})
        remote_meta.update(
            {
                "source": "database",
                "connection": str(getattr(record, "connection_label", "") or remote_meta.get("connection") or ""),
                "schema": str(getattr(record, "schema", "") or schema),
                "table": str(getattr(record, "table", "") or table),
                "row_id": str(getattr(record, "row_id", "") or row_id),
                "source_file": str(getattr(record, "source_file", "") or source_file),
                "can_edit": bool(getattr(record, "can_edit", False)),
            }
        )
        source_meta["remote_project"] = remote_meta
        self.current_project.source_meta = self._normalize_project_source_meta(source_meta)
        self._current_remote_project_connection_meta = dict(connection_meta or {})
        self._replace_remote_project_record(record)
        self._remote_project_loaded_key = remote_project_connection_key(connection_meta)
        self._dirty = False
        self._history_current = self._snapshot_state()
        self._update_undo_redo_buttons()
        self._refresh_ui_state()
        slim_message(self, _rt("Model"), _rt("Painel salvo no banco de dados."))

    def export_project(self):
        active_canvas = self._active_canvas()
        if active_canvas is None or not active_canvas.has_items():
            slim_message(self, _rt("Model"), _rt("Adicione ao menos um grafico antes de exportar."))
            return
        suggested_name = (self.current_project_name() or _rt("painel_model")).strip().replace(" ", "_")
        suggested_path = os.path.join(self.store.default_directory(), f"{suggested_name}.png")
        path, _ = QFileDialog.getSaveFileName(self, _rt("Exportar painel"), suggested_path, "PNG (*.png)")
        if not path:
            return
        if not active_canvas.export_image(path):
            slim_message(self, _rt("Model"), _rt("Nao foi possivel exportar a imagem do painel."))
            return
        slim_message(self, _rt("Model"), _rt("Painel exportado para:\n{path}", path=path))

    def _sync_mode_switch_state(self, editing_enabled: bool):
        state_text = _rt("Edição") if editing_enabled else _rt("Pré-visualizar")
        self.mode_state_label.setText(state_text)
        self.mode_state_label.setProperty("modeState", "editing" if editing_enabled else "preview")
        self.mode_state_label.style().unpolish(self.mode_state_label)
        self.mode_state_label.style().polish(self.mode_state_label)
        self.mode_toggle.blockSignals(True)
        try:
            self.mode_toggle.setChecked(bool(editing_enabled), animated=False)
        finally:
            self.mode_toggle.blockSignals(False)

    def _handle_mode_toggle(self, checked: bool):
        target = bool(checked)
        self.edit_mode_btn.blockSignals(True)
        try:
            self.edit_mode_btn.setChecked(target)
        finally:
            self.edit_mode_btn.blockSignals(False)
        self.set_edit_mode(target)

    def _sync_visual_side_tab_buttons(self):
        active_tab = str(getattr(self, "_active_visual_side_tab", "build") or "build")
        if active_tab not in {"build", "format"}:
            active_tab = "build"
        if hasattr(self, "visual_side_stack"):
            self.visual_side_stack.setCurrentIndex(1 if active_tab == "format" else 0)
        for button, checked in (
            (getattr(self, "visual_data_tab_btn", None), active_tab == "build"),
            (getattr(self, "visual_format_tab_btn", None), active_tab == "format"),
        ):
            if button is None:
                continue
            button.blockSignals(True)
            try:
                button.setChecked(bool(checked))
            finally:
                button.blockSignals(False)
            if hasattr(self, "_apply_visual_tab_button_styles"):
                self._apply_visual_tab_button_styles()

    def _toggle_visual_side_panel(self):
        if not getattr(self, "_visual_side_collapsed", False):
            sizes = self.canvas_splitter.sizes() if hasattr(self, "canvas_splitter") else []
            if len(sizes) >= 2 and sizes[1] > _MODEL_SIDE_PANEL_COLLAPSED_WIDTH:
                self._visual_side_width = min(
                    _MODEL_VISUAL_SIDE_PANEL_MAX_WIDTH,
                    max(_MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH, int(sizes[1])),
                )
        self._visual_side_collapsed = not bool(getattr(self, "_visual_side_collapsed", False))
        self._sync_visual_side_panel_chrome()
        self._ensure_canvas_splitter_sizes()

    def _set_visual_side_panel_available(self, available: bool):
        if not hasattr(self, "visual_side_panel"):
            return
        self.visual_side_panel.setVisible(bool(available))
        if available:
            self._sync_visual_side_panel_chrome()

    def _sync_visual_side_panel_chrome(self):
        if not hasattr(self, "visual_side_panel"):
            return
        collapsed = bool(getattr(self, "_visual_side_collapsed", False))
        self.visual_side_panel.setMinimumWidth(
            _MODEL_SIDE_PANEL_COLLAPSED_WIDTH if collapsed else _MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH
        )
        self.visual_side_panel.setMaximumWidth(
            _MODEL_SIDE_PANEL_COLLAPSED_WIDTH if collapsed else _MODEL_VISUAL_SIDE_PANEL_MAX_WIDTH
        )
        self.visual_side_panel.setProperty("collapsed", collapsed)
        if hasattr(self, "visual_tab_bar"):
            self.visual_tab_bar.setVisible(not collapsed)
        if hasattr(self, "visual_side_stack"):
            self.visual_side_stack.setVisible(not collapsed)
        if hasattr(self, "visual_data_tab_btn"):
            self.visual_data_tab_btn.setVisible(not collapsed)
        if hasattr(self, "visual_format_tab_btn"):
            self.visual_format_tab_btn.setVisible(not collapsed)
        if hasattr(self, "visual_side_collapsed_rail"):
            self.visual_side_collapsed_rail.setVisible(collapsed)
        if hasattr(self, "visual_side_toggle_btn"):
            self.visual_side_toggle_btn.setVisible(not collapsed)
            self.visual_side_toggle_btn.setArrowType(Qt.NoArrow)
            self.visual_side_toggle_btn.setIcon(_model_panel_chevron_icon("right", 18))
            self.visual_side_toggle_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.visual_side_toggle_btn.setText("›")
            self.visual_side_toggle_btn.setText("")
            self.visual_side_toggle_btn.setFixedSize(22, 22)
            set_walker_tooltip(self.visual_side_toggle_btn, _rt("Recolher visualizações"))
        if hasattr(self, "visual_side_collapsed_btn"):
            self.visual_side_collapsed_btn.setArrowType(Qt.NoArrow)
            self.visual_side_collapsed_btn.setIcon(_model_panel_chevron_icon("left", 18))
            self.visual_side_collapsed_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self.visual_side_collapsed_btn.setText("‹")
            self.visual_side_collapsed_btn.setText("")
            self.visual_side_collapsed_btn.setFixedSize(22, 22)
            set_walker_tooltip(self.visual_side_collapsed_btn, _rt("Expandir visualizações"))
        self._apply_collapsed_panel_chrome()
        try:
            self.visual_side_panel.style().unpolish(self.visual_side_panel)
            self.visual_side_panel.style().polish(self.visual_side_panel)
        except Exception:
            log_exception("falha opcional ignorada")

    def _set_visual_side_tab(self, tab_name: str):
        target = "format" if str(tab_name or "").strip().lower() == "format" else "build"
        if target == "format":
            self._set_visual_panel_open(True, focus=False)
        else:
            self._set_builder_panel_open(True, focus=False)

    def _set_builder_panel_open(self, enabled: bool, *, focus: bool = False):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        requested = bool(enabled)
        can_edit_project = bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None)
        pending_open = requested and can_edit_project and not in_canvas_page
        active = requested and can_edit_project and in_canvas_page
        self._builder_panel_open = bool(active or pending_open)
        if active:
            self._visual_panel_open = False
            self._active_visual_side_tab = "build"
            self._sync_builder_selection_state()
            self._sync_visual_side_tab_buttons()
        self._set_visual_side_panel_available(active or self._visual_panel_open)
        self._set_database_panel_available(self._database_panel_open and can_edit_project and in_canvas_page)
        self._set_data_panel_available(bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self._schedule_clear_filters_button_position()
        self.create_chart_btn.blockSignals(True)
        try:
            if self.create_chart_btn.isChecked() != self._builder_panel_open:
                self.create_chart_btn.setChecked(self._builder_panel_open)
        finally:
            self.create_chart_btn.blockSignals(False)
        self.format_visual_btn.blockSignals(True)
        try:
            if self.format_visual_btn.isChecked() != bool(self._visual_panel_open):
                self.format_visual_btn.setChecked(bool(self._visual_panel_open))
        finally:
            self.format_visual_btn.blockSignals(False)
        if active and focus:
            try:
                self.builder_layer_combo.setFocus(Qt.TabFocusReason)
            except Exception:
                log_exception("falha opcional ignorada")
        self._schedule_toolbar_visuals_strip_visibility()

    def _handle_create_chart_toggle(self, checked: bool):
        self._set_builder_panel_open(bool(checked), focus=bool(checked))
        if checked:
            self._expand_data_panel_for_new_chart()

    def _handle_data_fields_toggle(self, checked: bool):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        available = bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page
        if not available:
            self._sync_data_fields_button_state()
            return
        self._set_data_panel_collapsed(not bool(checked))

    def _ensure_canvas_splitter_sizes(self):
        splitter = getattr(self, "canvas_splitter", None)
        if splitter is None:
            return
        try:
            sizes = list(splitter.sizes())
            total = sum(int(size or 0) for size in sizes)
            if total <= 0 or len(sizes) < 4:
                return
            visual_visible = bool(self.visual_side_panel.isVisible())
            database_visible = bool(self.database_panel.isVisible())
            data_visible = bool(self.data_panel.isVisible())
            if visual_visible and getattr(self, "_visual_side_collapsed", False):
                target_visual = _MODEL_SIDE_PANEL_COLLAPSED_WIDTH
            elif visual_visible:
                preferred_visual_width = getattr(self, "_visual_side_width", _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH)
                preferred_visual = int(preferred_visual_width or _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH)
                target_visual = int(
                    min(max(preferred_visual, _MODEL_VISUAL_SIDE_PANEL_MIN_WIDTH), _MODEL_VISUAL_SIDE_PANEL_MAX_WIDTH)
                )
            else:
                target_visual = 0
            if database_visible and getattr(self, "_database_panel_collapsed", False):
                target_database = _MODEL_SIDE_PANEL_COLLAPSED_WIDTH
            elif database_visible:
                preferred_database_width = getattr(self, "_database_panel_width", _MODEL_DATABASE_PANEL_DEFAULT_WIDTH)
                preferred_database = int(preferred_database_width or _MODEL_DATABASE_PANEL_DEFAULT_WIDTH)
                target_database = int(
                    min(
                        max(preferred_database, _MODEL_DATABASE_PANEL_MIN_WIDTH),
                        _MODEL_DATABASE_PANEL_MAX_WIDTH,
                    )
                )
            else:
                target_database = 0
            if data_visible and getattr(self, "_data_panel_collapsed", False):
                target_data = _MODEL_DATA_PANEL_COLLAPSED_WIDTH
            elif data_visible:
                preferred_data = int(getattr(self, "_data_panel_width", _MODEL_DATA_PANEL_DEFAULT_WIDTH) or _MODEL_DATA_PANEL_DEFAULT_WIDTH)
                target_data = int(min(max(preferred_data, _MODEL_DATA_PANEL_MIN_WIDTH), _MODEL_DATA_PANEL_MAX_WIDTH))
            else:
                target_data = 0
            if visual_visible and not getattr(self, "_visual_side_collapsed", False) and sizes[1] < 180:
                visual_width = getattr(self, "_visual_side_width", _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH)
                target_visual = int(visual_width or _MODEL_VISUAL_SIDE_PANEL_DEFAULT_WIDTH)
            if database_visible and not getattr(self, "_database_panel_collapsed", False) and sizes[2] < _MODEL_DATABASE_PANEL_MIN_WIDTH:
                database_width = getattr(self, "_database_panel_width", _MODEL_DATABASE_PANEL_DEFAULT_WIDTH)
                target_database = int(database_width or _MODEL_DATABASE_PANEL_DEFAULT_WIDTH)
            if data_visible and not getattr(self, "_data_panel_collapsed", False) and sizes[3] < 120:
                target_data = int(getattr(self, "_data_panel_width", _MODEL_DATA_PANEL_DEFAULT_WIDTH) or _MODEL_DATA_PANEL_DEFAULT_WIDTH)
            target_canvas = max(360, total - target_visual - target_database - target_data)
            splitter.setSizes([target_canvas, target_visual, target_database, target_data])
            self._schedule_clear_filters_button_position()
        except Exception:
            log_exception("falha opcional ignorada")

    def _set_visual_panel_open(self, enabled: bool, *, focus: bool = False):
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        active = bool(enabled) and bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page
        self._visual_panel_open = bool(active)
        if active:
            self._builder_panel_open = False
            self._active_visual_side_tab = "format"
            self._sync_visual_side_tab_buttons()
        self._set_visual_side_panel_available(active or self._builder_panel_open)
        self._set_database_panel_available(self._database_panel_open and bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page)
        self._set_data_panel_available(bool(self.edit_mode_btn.isChecked()) and bool(self.current_project is not None) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self._schedule_clear_filters_button_position()
        self.format_visual_btn.blockSignals(True)
        try:
            if self.format_visual_btn.isChecked() != active:
                self.format_visual_btn.setChecked(active)
        finally:
            self.format_visual_btn.blockSignals(False)
        self.create_chart_btn.blockSignals(True)
        try:
            if self.create_chart_btn.isChecked() != self._builder_panel_open:
                self.create_chart_btn.setChecked(self._builder_panel_open)
        finally:
            self.create_chart_btn.blockSignals(False)
        if not active:
            self._sync_visual_side_tab_buttons()
        if not active:
            self.visual_panel.clear_selection()
            return
        item_widget = None
        active_page = self._active_page_widget()
        if active_page is not None:
            item_widget = active_page.canvas.selected_item_widget()
        if item_widget is None:
            self.visual_panel.clear_selection()
            return
        self.visual_panel.set_current_item(item_widget)
        if focus:
            try:
                self.visual_panel.setFocus(Qt.TabFocusReason)
            except Exception:
                log_exception("falha opcional ignorada")

    def _handle_format_visual_toggle(self, checked: bool):
        self._set_visual_panel_open(bool(checked), focus=bool(checked))

    def set_edit_mode(self, enabled: bool):
        requested_enabled = bool(enabled)
        if requested_enabled and self._current_project_is_locked_database_project():
            enabled = False
            self._show_remote_edit_blocked_message()
        else:
            enabled = requested_enabled
        for widget in self._page_widgets_in_order():
            try:
                widget.set_edit_mode(enabled)
            except Exception:
                log_exception("falha opcional ignorada")
                continue
        self.create_chart_btn.setVisible(enabled and self.current_project is not None)
        self.format_visual_btn.setVisible(enabled and self.current_project is not None)
        self.database_fields_btn.setVisible(enabled and self.current_project is not None)
        self.data_fields_btn.setVisible(enabled and self.current_project is not None)
        if not enabled:
            database_panel = getattr(self, "model_database_panel", None)
            if database_panel is not None and hasattr(database_panel, "release_catalog"):
                database_panel.release_catalog(keep_groups=True)
        if enabled and self.current_project is not None:
            self._builder_panel_open = True
            self._visual_panel_open = False
        else:
            self._builder_panel_open = False
            self._visual_panel_open = False
        self._set_builder_panel_open(self._builder_panel_open)
        self._set_visual_panel_open(self._visual_panel_open)
        self._set_database_panel_available(enabled and self.current_project is not None and self._database_panel_open and self.body_stack.currentWidget() is self.canvas_page)
        self._set_data_panel_available(enabled and self.current_project is not None and self.body_stack.currentWidget() is self.canvas_page)
        self._schedule_toolbar_visuals_strip_visibility()
        self._ensure_canvas_splitter_sizes()
        if self.edit_mode_btn.isChecked() != enabled:
            self.edit_mode_btn.blockSignals(True)
            try:
                self.edit_mode_btn.setChecked(enabled)
            finally:
                self.edit_mode_btn.blockSignals(False)
        self._sync_mode_switch_state(enabled)
        if self.current_project is not None:
            self.current_project.edit_mode = enabled
        self._refresh_ui_state()

    def _zoom_canvas_in(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "zoom_in"):
            active_canvas.zoom_in()

    def _zoom_canvas_out(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "zoom_out"):
            active_canvas.zoom_out()

    def _zoom_canvas_reset(self):
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "reset_zoom"):
            active_canvas.reset_zoom()

    def _handle_canvas_zoom_changed(self, zoom: float, page_id: Optional[str] = None):
        if self.current_project is not None and page_id:
            self._sync_project_from_pages(page_id)
        try:
            percent = int(round(float(zoom) * 100.0))
        except Exception:
            percent = 100
        if not page_id or page_id == self._current_page_id():
            self._sync_zoom_controls(percent)

    def _zoom_slider_changed(self, value: int):
        if self._syncing_zoom_controls:
            return
        try:
            zoom_value = max(0.6, min(2.0, float(value) / 100.0))
        except Exception:
            zoom_value = 1.0
        active_canvas = self._active_canvas()
        if hasattr(active_canvas, "set_zoom"):
            active_canvas.set_zoom(zoom_value)

    def _sync_zoom_controls(self, percent: int):
        self._syncing_zoom_controls = True
        try:
            value = max(60, min(200, int(percent)))
            self.zoom_label.setText(f"{value}%")
            if self.zoom_slider.value() != value:
                self.zoom_slider.setValue(value)
        finally:
            self._syncing_zoom_controls = False

    def _update_footer_visibility(self):
        self.footer_bar.setVisible(self.current_project is not None)

    def _update_toolbar_visibility(self):
        has_project = self.current_project is not None
        show_project_actions = has_project
        for button in (
            self.undo_btn,
            self.redo_btn,
            self.save_btn,
            self.save_as_btn,
            self.export_btn,
            self.edit_mode_btn,
            self.format_visual_btn,
            self.database_fields_btn,
            self.data_fields_btn,
            self.settings_btn,
            self.close_project_btn,
        ):
            button.setVisible(show_project_actions)
        edit_enabled = bool(self.edit_mode_btn.isChecked())
        self.create_chart_btn.setVisible(show_project_actions and edit_enabled)
        self.format_visual_btn.setVisible(show_project_actions and edit_enabled)
        self.database_fields_btn.setVisible(show_project_actions and edit_enabled)
        self.data_fields_btn.setVisible(show_project_actions and edit_enabled)
        self._sync_toolbar_visuals_strip_visibility()
        self.mode_switch_wrap.setVisible(show_project_actions)
        if has_project:
            self._configure_toolbar_icon_button(self.new_btn, "Walker-New.svg", _rt("Novo"))
            self._configure_toolbar_icon_button(self.open_btn, "Walker-Open.svg", _rt("Abrir"))
        else:
            self._configure_toolbar_text_icon_button(self.new_btn, "Walker-New.svg", _rt("Novo"), _rt("Novo"))
            self._configure_toolbar_text_icon_button(self.open_btn, "Walker-Open.svg", _rt("Abrir"), _rt("Abrir"))
        try:
            self.new_btn.style().unpolish(self.new_btn)
            self.new_btn.style().polish(self.new_btn)
            self.open_btn.style().unpolish(self.open_btn)
            self.open_btn.style().polish(self.open_btn)
        except Exception:
            log_exception("falha opcional ignorada")
        self._update_undo_redo_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_toolbar_visuals_strip_visibility()
        self._position_clear_filters_button()
        if getattr(self, "current_project", None) is None:
            columns = self._recent_columns_for_width(self._available_recents_width())
            if columns != getattr(self, "_recents_columns", 0):
                self._schedule_recents_refresh()

    def _handle_canvas_changed(self, page_id: Optional[str] = None):
        if self._suspend_canvas_events:
            return
        if self.current_project is not None:
            self._sync_project_from_pages(page_id or self._current_page_id())
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_canvas_filters_changed(self, summary: Dict[str, object], page_id: Optional[str] = None):
        if self.current_project is not None:
            self._sync_project_from_pages(page_id or self._current_page_id())
        if not page_id or page_id == self._current_page_id():
            self._update_filters_bar(summary)
        self._dirty = True
        self._commit_history_if_changed()
        self._refresh_ui_state()

    def _handle_canvas_item_selection(self, page_id: str, item_id: str, item_widget):
        if page_id and page_id != self._current_page_id():
            return
        self._sync_builder_selection_state()
        if not self.visual_side_panel.isVisible():
            return
        if item_widget is None:
            self.visual_panel.clear_selection()
            return
        self.visual_panel.set_current_item(item_widget)

    def _set_builder_source_hint(self, text: str):
        label = getattr(self, "builder_source_hint", None)
        if label is None:
            return
        clean_text = str(text or "").strip()
        label.setText(clean_text)
        label.setToolTip(clean_text)
        label.setVisible(bool(clean_text))

    def _set_builder_database_source_display(self, text: str):
        display = getattr(self, "builder_database_source_display", None)
        clean_text = str(text or "").strip()
        if display is not None:
            display.setText(clean_text)
            display.setToolTip(clean_text)
            display.setVisible(bool(clean_text))

    def _handle_canvas_field_binding_drop(self, page_id: str, item_id: str, slot_name: str, payload):
        if page_id and page_id != self._current_page_id():
            self._set_active_page(page_id, sync_project=True, update_tabs=True)
        active_canvas = self._active_canvas()
        if active_canvas is None:
            return
        active_canvas.select_item(item_id, emit_signal=True)
        self._sync_builder_selection_state()
        self._apply_dropped_field_to_selected_visual(slot_name, payload)

    def _handle_canvas_visual_panel_requested(self, page_id: str, item_id: str):
        if page_id and page_id != self._current_page_id():
            self._set_active_page(page_id, sync_project=True, update_tabs=True)
        active_page = self._active_page_widget()
        if active_page is not None and item_id:
            active_page.canvas.select_item(item_id, emit_signal=False)
            item_widget = active_page.canvas.selected_item_widget()
            if item_widget is not None:
                self.visual_panel.set_current_item(item_widget)
        self._set_visual_panel_open(True, focus=False)

    def _update_filters_bar(self, summary: Optional[Dict[str, object]] = None):
        active_canvas = self._active_canvas()
        if summary is None and active_canvas is not None:
            summary = active_canvas.interaction_manager.active_filters_summary()
        summary = summary or {"items": [], "count": 0}
        items = list(summary.get("items") or [])
        if not items:
            self.filters_label.clear()
            self.clear_filters_btn.setVisible(False)
            self.filters_bar.setVisible(False)
            return
        self.filters_label.clear()
        self.clear_filters_btn.setVisible(True)
        self.filters_bar.setVisible(False)
        self._position_clear_filters_button()

    def _clear_model_filters(self):
        try:
            active_canvas = self._active_canvas()
            if active_canvas is not None:
                active_canvas.clear_filters()
        except Exception:
            log_exception("falha opcional ignorada")

    def _position_clear_filters_button(self):
        button = getattr(self, "clear_filters_btn", None)
        splitter = getattr(self, "canvas_splitter", None)
        page_stack = getattr(self, "page_stack", None)
        canvas_page = getattr(self, "canvas_page", None)
        if button is None or page_stack is None or canvas_page is None:
            return
        if not button.isVisible():
            return
        try:
            button.adjustSize()
            button.resize(button.sizeHint())
            splitter_sizes = list(splitter.sizes()) if splitter is not None else []
            canvas_width = int(splitter_sizes[0] if splitter_sizes else (page_stack.width() or 0) or 0)
            btn_w = button.width() or button.sizeHint().width()
            x = max(12, canvas_width - btn_w - 12)
            y = max(8, page_stack.geometry().top() + 8)
            button.move(x, y)
            button.raise_()
            button.show()
        except Exception:
            log_exception("falha opcional ignorada")

    def _schedule_clear_filters_button_position(self):
        try:
            for delay in (0, 40, 120):
                QTimer.singleShot(delay, self._position_clear_filters_button)
        except Exception:
            self._position_clear_filters_button()

    def _schedule_recents_refresh(self):
        if getattr(self, "_recents_refresh_pending", False):
            return
        self._recents_refresh_pending = True
        for delay in (0, 80, 180):
            QTimer.singleShot(delay, self._run_scheduled_recents_refresh)

    def _run_scheduled_recents_refresh(self):
        self._recents_refresh_pending = False
        if getattr(self, "current_project", None) is None:
            self._refresh_recents()

    def _available_recents_width(self) -> int:
        candidates = []
        for widget in (
            getattr(self, "recents_scroll", None),
            getattr(self, "remote_projects_scroll", None),
            getattr(self, "model_home_actions", None),
            getattr(self, "empty_page", None),
        ):
            if widget is None:
                continue
            try:
                width = int(widget.width())
            except Exception:
                width = 0
            if width > 0:
                candidates.append(width)
        try:
            viewport = self.recents_scroll.viewport()
            if viewport is not None and int(viewport.width()) > 0:
                candidates.append(int(viewport.width()))
        except Exception:
            log_exception("falha opcional ignorada")
        width = max(candidates or [0])
        try:
            if width == int(self.empty_page.width() or 0) and width > 56:
                width -= 56
        except Exception:
            log_exception("falha opcional ignorada")
        return max(0, width)

    def _recent_columns_for_width(self, width: int) -> int:
        try:
            available = int(width or 0)
        except Exception:
            available = 0
        min_reliable_width = (_MODEL_RECENT_CARD_WIDTH * 2) + _MODEL_RECENT_CARD_GAP
        card_stride = _MODEL_RECENT_CARD_WIDTH + _MODEL_RECENT_CARD_GAP
        if available < min_reliable_width:
            return 4
        return max(
            1,
            min(
                4,
                (available + _MODEL_RECENT_CARD_GAP) // card_stride,
            ),
        )

    def _recent_display_timestamp(self, recent: Dict[str, object], path: str) -> str:
        raw_value = str(recent.get("updated_at") or "").strip()
        parsed = None
        if raw_value:
            try:
                parsed = datetime.fromisoformat(raw_value)
            except Exception:
                parsed = None
        if parsed is None and path:
            try:
                parsed = datetime.fromtimestamp(os.path.getmtime(path))
            except Exception:
                parsed = None
        if parsed is None:
            return str(path or "")
        try:
            return parsed.strftime("%d/%m/%Y, %H:%M:%S")
        except Exception:
            return str(path or "")

    def _remote_project_description(self, record: RemoteProjectRecord) -> str:
        parts = []
        source = str(getattr(record, "connection_label", "") or "").strip()
        schema = str(getattr(record, "schema", "") or "").strip()
        table = str(getattr(record, "table", "") or "").strip()
        table_label = f"{schema}.{table}" if schema and table else table
        if source:
            parts.append(source)
        if table_label:
            parts.append(table_label)
        timestamp = self._remote_project_timestamp(record)
        if timestamp:
            parts.append(timestamp)
        return " - ".join(parts)

    def _remote_project_timestamp(self, record: RemoteProjectRecord) -> str:
        raw_value = str(getattr(record, "updated_at", "") or "").strip()
        if not raw_value:
            return ""
        try:
            parsed = datetime.fromisoformat(raw_value)
        except Exception:
            parsed = None
        if parsed is None:
            return raw_value
        try:
            return parsed.strftime("%d/%m/%Y, %H:%M:%S")
        except Exception:
            return raw_value

    def _refresh_recents(self):
        while self.recents_layout.count():
            item = self.recents_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        local_recents = self.store.load_recents()
        if not local_recents:
            self.recents_placeholder.setVisible(True)
            self.recents_scroll.setVisible(False)
            self.recents_container.setFixedHeight(0)
            self.recents_card.setFixedHeight(58)
            self._recents_columns = self._recent_columns_for_width(self._available_recents_width())
            self._refresh_remote_project_cards()
            return

        self.recents_placeholder.setVisible(False)
        self.recents_scroll.setVisible(True)
        self.recents_container.setVisible(True)
        self.recents_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)
        self.recents_card.setFixedHeight(_MODEL_RECENTS_SECTION_HEIGHT)
        columns = self._recent_columns_for_width(self._available_recents_width())
        self._recents_columns = columns
        rows = max(1, (len(local_recents) + columns - 1) // columns)
        for index, recent in enumerate(local_recents):
            path = str(recent.get("path") or "")
            name = str(os.path.splitext(os.path.basename(path))[0] or recent.get("name") or "")
            card = _ModelRecentCard(
                name,
                self._recent_display_timestamp(recent, path),
                self.recents_container,
            )
            card.clicked.connect(lambda selected_path=path: self.open_project(selected_path))
            row = index // columns
            column = index % columns
            self.recents_layout.addWidget(card, row, column, Qt.AlignLeft | Qt.AlignTop)
        for column in range(columns):
            self.recents_layout.setColumnStretch(column, 0)
        cards_height = rows * _MODEL_RECENT_CARD_HEIGHT + max(0, rows - 1) * _MODEL_RECENT_ROW_GAP
        self.recents_container.setFixedHeight(cards_height)
        try:
            self.recents_scroll.verticalScrollBar().setValue(0)
        except Exception:
            log_exception("falha opcional ignorada")
        self._refresh_remote_project_cards()

    def _refresh_remote_project_cards(self):
        remote_layout = getattr(self, "remote_projects_layout", None)
        if remote_layout is None:
            return
        while remote_layout.count():
            item = remote_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        remote_recents = list(getattr(self, "_remote_project_records", []) or [])
        remote_card = getattr(self, "remote_projects_card", None)
        if not remote_recents:
            if remote_card is not None:
                remote_card.setVisible(False)
                remote_card.setFixedHeight(0)
            self.remote_projects_container.setFixedHeight(0)
            return

        if remote_card is not None:
            remote_card.setVisible(True)
        self.remote_projects_placeholder.setVisible(False)
        self.remote_projects_scroll.setVisible(True)
        self.remote_projects_container.setVisible(True)
        self.remote_projects_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)
        columns = self._recent_columns_for_width(self._available_recents_width())
        rows = max(1, (len(remote_recents) + columns - 1) // columns)
        for index, record in enumerate(remote_recents):
            card = _ModelRecentCard(
                str(getattr(record, "name", "") or _rt("Painel remoto")),
                self._remote_project_description(record),
                self.remote_projects_container,
            )
            card.clicked.connect(lambda selected_record=record: self.open_remote_project(selected_record))
            row = index // columns
            column = index % columns
            remote_layout.addWidget(card, row, column, Qt.AlignLeft | Qt.AlignTop)
        for column in range(columns):
            remote_layout.setColumnStretch(column, 0)
        cards_height = rows * _MODEL_RECENT_CARD_HEIGHT + max(0, rows - 1) * _MODEL_RECENT_ROW_GAP
        self.remote_projects_container.setFixedHeight(cards_height)
        section_height = 28 + 16 + min(_MODEL_RECENT_CARD_HEIGHT, cards_height)
        self.remote_projects_card.setFixedHeight(section_height)
        try:
            self.remote_projects_scroll.verticalScrollBar().setValue(0)
        except Exception:
            log_exception("falha opcional ignorada")

    def _refresh_ui_state(self):
        has_project = self.current_project is not None
        self.body_stack.setCurrentWidget(self.canvas_page if has_project else self.empty_page)
        in_canvas_page = self.body_stack.currentWidget() is self.canvas_page
        if hasattr(self, "header"):
            self.header.setVisible(has_project)
        if getattr(self, "page_strip", None) is not None:
            self.page_strip.setVisible(has_project)
        if has_project:
            active_id = self.current_project.active_page_id or (self.current_project.pages[0].page_id if self.current_project.pages else "")
            active_widget = self._active_page_widget()
            if active_widget is None or str(active_widget.page_id or "").strip() != str(active_id or "").strip():
                self._set_active_page(active_id, sync_project=False, update_tabs=True)
            else:
                self.canvas = active_widget.canvas
                self._select_page_button(active_id)
                try:
                    self._sync_zoom_controls(int(round(float(active_widget.zoom_value() or 1.0) * 100.0)))
                except Exception:
                    log_exception("falha opcional ignorada")
        else:
            self.canvas = None
        self.new_btn.setVisible(True)
        self.open_btn.setVisible(True)
        self._update_toolbar_visibility()
        self.close_project_btn.setVisible(has_project)
        self._set_builder_panel_open(self._builder_panel_open)
        self._set_visual_panel_open(self._visual_panel_open)
        self._set_database_panel_available(has_project and bool(self.edit_mode_btn.isChecked()) and self._database_panel_open and in_canvas_page)
        self._set_data_panel_available(has_project and bool(self.edit_mode_btn.isChecked()) and in_canvas_page)
        self._ensure_canvas_splitter_sizes()
        self._sync_builder_selection_state()
        self._update_footer_visibility()
        self._update_filters_bar()
        self.filters_bar.setVisible(bool(self.edit_mode_btn.isChecked()) and self.filters_bar.isVisible())
        self._sync_mode_switch_state(bool(self.edit_mode_btn.isChecked()))
        self._update_undo_redo_buttons()
        if not has_project:
            self._schedule_recents_refresh()
