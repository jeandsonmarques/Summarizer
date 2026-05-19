# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from functools import partial
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas.api import types as ptypes
from qgis.PyQt.QtCore import QByteArray, QEvent, QItemSelection, QItemSelectionModel, QRegExp, QSettings, QSize, QTimer, Qt, QSortFilterProxyModel, QVariant
from qgis.PyQt.QtGui import QCursor, QColor, QFont, QIcon, QKeySequence, QPainter, QPalette, QPixmap, QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QLayout,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.core import QgsMessageLog, QgsProject, QgsVectorLayer, Qgis

from .palette import TYPOGRAPHY
from .pivot import (
    aggregate_series as _pivot_aggregate_series,
    flatten_pandas_columns as _pivot_flatten_pandas_columns,
    format_header_tuple as _pivot_format_header_tuple,
    normalize_field_token as _pivot_normalize_field_token,
    pandas_aggfunc_name as _pivot_pandas_aggfunc_name,
    resolve_available_field_name as _pivot_resolve_available_field_name,
)
from .pivot.pivot_models import PivotExportSpec
from .pivot.pivot_export import export_dataframes_to_excel
from .pivot_view.pivot_theme import (
    apply_styles as _pivot_apply_styles,
    enforce_filters_surface_backgrounds as _pivot_enforce_filters_surface_backgrounds,
    refresh_toolbar_chrome as _pivot_refresh_toolbar_chrome,
)
from .pivot_view.pivot_field_panel import (
    _PivotFieldListDelegate,
    _PivotFieldSourceListWidget,
    _SummarySourceCard,
    _VerticalPanelLabel,
    clear_field_search as _pivot_clear_field_search,
    detect_numeric_candidates as _pivot_detect_numeric_candidates,
    desired_fields_panel_width as _pivot_desired_fields_panel_width,
    filter_field_list as _pivot_filter_field_list,
    handle_field_double_click as _pivot_handle_field_double_click,
    populate_field_panel as _pivot_populate_field_panel,
    sync_fields_panel_width_to_content as _pivot_sync_fields_panel_width_to_content,
)
from .pivot_view.pivot_area_panel import (
    add_field_to_area as _pivot_add_field_to_area,
    add_selected_field_to_area as _pivot_add_selected_field_to_area,
    area_combo as _pivot_area_combo,
    area_label as _pivot_area_label,
    area_list as _pivot_area_list,
    build_area_panels as _pivot_build_area_panels,
    clear_area as _pivot_clear_area,
    create_area_chip_widget as _pivot_create_area_chip_widget,
    handle_filter_panel_drop_event as _pivot_handle_filter_panel_drop_event,
    move_selected_area_field as _pivot_move_selected_area_field,
    placeholder_item as _pivot_placeholder_item,
    refresh_active_area_styles as _pivot_refresh_active_area_styles,
    refresh_area_item_widgets as _pivot_refresh_area_item_widgets,
    remove_area_field_by_key as _pivot_remove_area_field_by_key,
    remove_selected_area_field as _pivot_remove_selected_area_field,
    selected_area_specs as _pivot_selected_area_specs,
    set_last_active_area as _pivot_set_last_active_area,
    take_area_field_by_key as _pivot_take_area_field_by_key,
)
from .pivot_view.pivot_export_controller import export_pivot_table as _pivot_export_pivot_table
from .pivot_view.pivot_layer_io import (
    build_export_layer_dataframe as _pivot_build_export_layer_dataframe,
    build_layer_dataframe_from_pivot_config as _pivot_build_layer_dataframe_from_pivot_config,
    build_layer_dataframe_from_request as _pivot_build_layer_dataframe_from_request,
    export_to_gpkg as _pivot_export_to_gpkg,
    resolve_layer_field_name as _pivot_resolve_layer_field_name,
)
from .pivot_view.pivot_settings_dialog import (
    open_table_settings_dialog as _pivot_open_table_settings_dialog,
)
from .pivot_view.pivot_state_controller import (
    apply_saved_configuration as _pivot_apply_saved_configuration,
    commit_history_if_changed as _pivot_commit_history_if_changed,
    configuration_key_from_metadata as _pivot_configuration_key_from_metadata,
    field_spec_from_field_name as _pivot_field_spec_from_field_name,
    get_current_configuration as _pivot_get_current_configuration,
    get_current_pivot_result as _pivot_get_current_pivot_result,
    get_summary_metadata as _pivot_get_summary_metadata,
    get_visible_pivot_dataframe as _pivot_get_visible_pivot_dataframe,
    redo_last_action as _pivot_redo_last_action,
    reset_history_state as _pivot_reset_history_state,
    restore_default_summary_layout as _pivot_restore_default_summary_layout,
    restore_saved_configuration_for_metadata as _pivot_restore_saved_configuration_for_metadata,
    undo_last_action as _pivot_undo_last_action,
)
from .pivot_view.pivot_excel_export import (
    try_create_native_excel_pivot as _pivot_try_create_native_excel_pivot,
)
from .pivot_view.pivot_switch import PivotSwitch
from .pivot_view.pivot_table_controller import (
    compute_dataframe_pivot as _pivot_compute_dataframe_pivot,
    compute_layer_backed_pivot as _pivot_compute_layer_backed_pivot,
)
from .pivot_view.pivot_table_renderer import populate_table as _pivot_populate_table
from .pivot_view.pivot_toolbar import (
    build_state_labels as _pivot_build_state_labels,
    build_toolbar as _pivot_build_toolbar,
    configure_toolbar_button as _pivot_configure_toolbar_button,
    configure_toolbar_icon_button as _pivot_configure_toolbar_icon_button,
    polish_toolbar_button as _pivot_polish_toolbar_button,
    update_undo_redo_buttons as _pivot_update_undo_redo_buttons,
)
from .slim_dialogs import slim_message
from .utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
from .utils.i18n_runtime import apply_widget_translations as _apply_i18n_widgets, tr_text as _rt
from .report_view.pivot import (
    PivotEngine,
    PivotExportService,
    PivotFieldSpec,
    PivotRequest,
    PivotSelectionBridge,
    PivotValidationError,
)


from .utils.logging_utils import log_exception

class _PivotFilterProxy(QSortFilterProxyModel):
    """Proxy that supports global search plus per-column filters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._global_regexp = QRegExp()
        self._column_filters: Dict[int, QRegExp] = {}
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if model is None:
            return True
        column_count = model.columnCount()

        if not self._global_regexp.isEmpty():
            matched = False
            for col in range(column_count):
                idx = model.index(source_row, col, source_parent)
                value = str(model.data(idx) or "")
                if self._global_regexp.indexIn(value) != -1:
                    matched = True
                    break
            if not matched:
                return False

        for col, rx in self._column_filters.items():
            if rx.isEmpty():
                continue
            if col >= column_count:
                continue
            idx = model.index(source_row, col, source_parent)
            value = str(model.data(idx) or "")
            if rx.indexIn(value) == -1:
                return False
        return True

    def set_global_filter(self, text: str):
        self._global_regexp = QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString)
        self.invalidateFilter()

    def set_column_filter(self, column: int, text: str):
        if not text:
            self._column_filters.pop(column, None)
        else:
            self._column_filters[column] = QRegExp(
                text, Qt.CaseInsensitive, QRegExp.FixedString
            )
        self.invalidateFilter()


_SIDEBAR_COLLAPSED_KEY = "Summarizer/pivot/sidebarCollapsed"
_SIDEBAR_WIDTH_KEY = "Summarizer/pivot/sidebarWidth"
_SIDEBAR_COLLAPSED_WIDTH = 52
_SIDEBAR_MIN_WIDTH = 304
_SIDEBAR_DEFAULT_WIDTH = 320
_SIDEBAR_MAX_WIDTH = 420
_INK_COLOR = "#252B33"
_TOOLS_PANEL_COLLAPSED_WIDTH = 40
_TOOLS_FIELDS_MIN_WIDTH = 120
_TOOLS_FIELDS_DEFAULT_WIDTH = 148
_TOOLS_FIELDS_MAX_WIDTH = 320
_TOOLS_FILTERS_MIN_WIDTH = 164
_TOOLS_FILTERS_DEFAULT_WIDTH = 188
_TOOLS_FILTERS_MAX_WIDTH = 280

_TOOLBAR_SVG_ICONS = {
    "search": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M21 21L15.8033 15.8033M15.8033 15.8033C17.1605 14.4461 18 12.5711 18 10.5C18 6.35786 14.6421 3 10.5 3C6.35786 3 3 6.35786 3 10.5C3 14.6421 6.35786 18 10.5 18C12.5711 18 14.4461 17.1605 15.8033 15.8033Z" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "clear": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14.7404 9L14.3942 18M9.60577 18L9.25962 9M19.2276 5.79057C19.5696 5.84221 19.9104 5.89747 20.25 5.95629M19.2276 5.79057L18.1598 19.6726C18.0696 20.8448 17.0921 21.75 15.9164 21.75H8.08357C6.90786 21.75 5.93037 20.8448 5.8402 19.6726L4.77235 5.79057M19.2276 5.79057C18.0812 5.61744 16.9215 5.48485 15.75 5.39432M3.75 5.95629C4.08957 5.89747 4.43037 5.84221 4.77235 5.79057M4.77235 5.79057C5.91878 5.61744 7.07849 5.48485 8.25 5.39432M15.75 5.39432V4.47819C15.75 3.29882 14.8393 2.31423 13.6606 2.27652C13.1092 2.25889 12.5556 2.25 12 2.25C11.4444 2.25 10.8908 2.25889 10.3394 2.27652C9.16065 2.31423 8.25 3.29882 8.25 4.47819V5.39432M15.75 5.39432C14.5126 5.2987 13.262 5.25 12 5.25C10.738 5.25 9.48744 5.2987 8.25 5.39432" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "undo": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M9 7.5H15.75C18.6495 7.5 21 9.8505 21 12.75C21 15.6495 18.6495 18 15.75 18H9.75" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M9 7.5L12 4.5M9 7.5L12 10.5" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "redo": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M15 7.5H8.25C5.3505 7.5 3 9.8505 3 12.75C3 15.6495 5.3505 18 8.25 18H14.25" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M15 7.5L12 4.5M15 7.5L12 10.5" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "dashboard": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10.5 6C6.35786 6 3 9.35786 3 13.5C3 17.6421 6.35786 21 10.5 21C14.6421 21 18 17.6421 18 13.5H10.5V6Z" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M13.5 10.5H21C21 6.35786 17.6421 3 13.5 3V10.5Z" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "export": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M3 16.5V18.75C3 19.9926 4.00736 21 5.25 21H18.75C19.9926 21 21 19.9926 21 18.75V16.5M16.5 12L12 16.5M12 16.5L7.5 12M12 16.5V3" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "fields": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M20.25 6.375C20.25 8.65317 16.5563 10.5 12 10.5C7.44365 10.5 3.75 8.65317 3.75 6.375M20.25 6.375C20.25 4.09683 16.5563 2.25 12 2.25C7.44365 2.25 3.75 4.09683 3.75 6.375M20.25 6.375V17.625C20.25 19.9032 16.5563 21.75 12 21.75C7.44365 21.75 3.75 19.9032 3.75 17.625V6.375M20.25 6.375V10.125M3.75 6.375V10.125M20.25 10.125V13.875C20.25 16.1532 16.5563 18 12 18C7.44365 18 3.75 16.1532 3.75 13.875V10.125M20.25 10.125C20.25 12.4032 16.5563 14.25 12 14.25C7.44365 14.25 3.75 12.4032 3.75 10.125" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "field_text": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.5 4.5H15L19.5 9V19.125C19.5 20.1605 18.6605 21 17.625 21H7.875C6.83947 21 6 20.1605 6 19.125V6.375C6 5.33947 6.83947 4.5 7.875 4.5H7.5Z" stroke="__COLOR__" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M9 12H16.5M9 15.75H16.5" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round"/>
</svg>""",
    "field_numeric": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.25 4.5L6.75 19.5M15.75 4.5L14.25 19.5M4.5 9.75H18.75M3.75 14.25H18" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "filter_panel": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4.5 6H19.5L13.5 13.0312V18.75L10.5 17.25V13.0312L4.5 6Z" stroke="__COLOR__" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "source_map": """<svg width="56" height="56" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14 18.5L22 14.5L32.5 17.8L42 13.8V37.5L32.5 41.5L22 38.2L14 42.2V18.5Z" stroke="__COLOR__" stroke-width="2" stroke-linejoin="round"/>
<path d="M22 14.5V38.2" stroke="__COLOR__" stroke-width="2" stroke-linecap="round"/>
<path d="M32.5 17.8V41.5" stroke="__COLOR__" stroke-width="2" stroke-linecap="round"/>
</svg>""",
    "source_sheet": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="16" y="12" width="32" height="40" rx="7" fill="__ACCENT__" fill-opacity="0.14"/>
<path d="M23 12H41L48 19V45C48 48.866 44.866 52 41 52H23C19.134 52 16 48.866 16 45V19C16 15.134 19.134 12 23 12Z" stroke="__COLOR__" stroke-width="2.2" stroke-linejoin="round"/>
<path d="M24 26H40M24 33H40M24 40H40M32 19V47" stroke="__COLOR__" stroke-width="2.2" stroke-linecap="round"/>
</svg>""",
    "source_postgres": """<svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="6" y="6" width="60" height="60" rx="18" fill="#EEF5FF"/>
<ellipse cx="36" cy="24" rx="14" ry="6" fill="#2F80D7"/>
<path d="M22 24V42.5C22 45.8137 28.268 48.5 36 48.5C43.732 48.5 50 45.8137 50 42.5V24" fill="#2F80D7" fill-opacity="0.16"/>
<path d="M22 24V42.5C22 45.8137 28.268 48.5 36 48.5C43.732 48.5 50 45.8137 50 42.5V24" stroke="#2F80D7" stroke-width="1.8"/>
<ellipse cx="36" cy="24" rx="14" ry="6" stroke="#2F80D7" stroke-width="1.8"/>
<path d="M22 33.5C22 36.8137 28.268 39.5 36 39.5C43.732 39.5 50 36.8137 50 33.5" stroke="#2F80D7" stroke-width="1.8"/>
<path d="M22 42.5C22 45.8137 28.268 48.5 36 48.5C43.732 48.5 50 45.8137 50 42.5" stroke="#2F80D7" stroke-width="1.8"/>
<circle cx="48.5" cy="21.5" r="4.5" fill="#F4C84E"/>
<path d="M46.5 21.5H50.5" stroke="#7A5800" stroke-width="1.5" stroke-linecap="round"/>
<path d="M48.5 19.5V23.5" stroke="#7A5800" stroke-width="1.5" stroke-linecap="round"/>
</svg>""",
    "back_arrow": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14.5 6L8.5 12L14.5 18" stroke="__COLOR__" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "summary_sheet": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M6.75 3.75H14.25L18.75 8.25V20.25H6.75V3.75Z" stroke="__COLOR__" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M14.25 3.75V8.25H18.75" stroke="__COLOR__" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M9 11.25H16.5M9 14.25H16.5M9 17.25H16.5M11.25 9.75V18.75M14.25 9.75V18.75" stroke="__COLOR__" stroke-width="1.25" stroke-linecap="round"/>
</svg>""",
    "summary_image": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="4.5" y="5.25" width="15" height="13.5" rx="1.75" stroke="__COLOR__" stroke-width="1.6"/>
<circle cx="8.75" cy="9.25" r="1.25" stroke="__COLOR__" stroke-width="1.5"/>
<path d="M6.75 16.75L10.25 13.25L12.75 15.75L15.25 12.75L17.75 16.75" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "summary_edit": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5.25 18.75L9 18L18 9L15 6L6 15L5.25 18.75Z" stroke="__COLOR__" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M13.75 7.25L16.75 10.25" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round"/>
</svg>""",
    "summary_settings": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 8.25C14.0711 8.25 15.75 9.92893 15.75 12C15.75 14.0711 14.0711 15.75 12 15.75C9.92893 15.75 8.25 14.0711 8.25 12C8.25 9.92893 9.92893 8.25 12 8.25Z" stroke="__COLOR__" stroke-width="1.6"/>
<path d="M12 3.75V5.25M12 18.75V20.25M20.25 12H18.75M5.25 12H3.75M17.8336 6.16637L16.773 7.22703M7.22703 16.773L6.16637 17.8336M17.8336 17.8336L16.773 16.773M7.22703 7.22703L6.16637 6.16637" stroke="__COLOR__" stroke-width="1.6" stroke-linecap="round"/>
</svg>""",
}


def _svg_icon_from_template(svg_template: str, size: int = 16, color_map: Optional[Dict[int, str]] = None) -> QIcon:
    icon = QIcon()
    mode_colors = color_map or {
        QIcon.Normal: "#6b7280",
        QIcon.Active: _INK_COLOR,
        QIcon.Selected: _INK_COLOR,
        QIcon.Disabled: "#c7cdd6",
    }
    for mode, color in mode_colors.items():
        svg_data = QByteArray(svg_template.replace("__COLOR__", color).encode("utf-8"))
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


class PivotTableWidget(QWidget):
    """Excel-inspired compact pivot table with column filters and field list."""

    SUPPORTED_AGGREGATORS = [
        ("Soma", "sum"),
        ("Media", "average"),
        ("Contagem", "count"),
        ("Maximo", "max"),
        ("Minimo", "min"),
        ("Mediana", "median"),
        ("Valores unicos", "unique"),
        ("Variancia", "variance"),
        ("Desvio padrao", "stddev"),
    ]

    EXPORT_FILTERS = "CSV (*.csv);;Excel (*.xlsx);;GeoPackage (*.gpkg)"

    def __init__(self, iface=None, parent=None, host=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)
        base_ui_font = ui_font()
        base_ui_font.setPixelSize(int(TYPOGRAPHY.get("font_body_px", 13)))
        base_ui_font.setWeight(QFont.Normal)
        self.setFont(base_ui_font)
        self._font_enforcer = attach_ui_font_enforcer(self)
        self.iface = iface
        self._host = host
        self.raw_df: pd.DataFrame = pd.DataFrame()
        self.filtered_df: pd.DataFrame = pd.DataFrame()
        self.pivot_df: pd.DataFrame = pd.DataFrame()
        self.column_dtypes: Dict[str, str] = {}
        self.numeric_candidates: List[str] = []
        self.column_filter_editors: List[QLineEdit] = []
        self._block_updates = False
        self._current_metadata: Dict[str, str] = {}
        self.toolbar_layout: Optional[QHBoxLayout] = None
        self._external_auto_checkbox: Optional[QCheckBox] = None
        self._external_dashboard_button: Optional[QPushButton] = None
        self.auto_update_check: Optional[QCheckBox] = None
        self._current_summary_data: Dict[str, Any] = {}
        self._current_layer = None
        self._current_pivot_request = None
        self._current_pivot_result = None
        self._display_row_keys: List[tuple] = []
        self._display_column_keys: List[tuple] = []
        self._pivot_data_column_offset = 0
        self._row_header_depth = 1
        self._last_active_area = "row"
        self._sidebar_collapsed = False
        self._sidebar_last_width = _SIDEBAR_DEFAULT_WIDTH
        self._tools_panels_hidden = False
        self._tools_fields_width = _TOOLS_FIELDS_DEFAULT_WIDTH
        self._tools_builder_width = _TOOLS_FILTERS_DEFAULT_WIDTH
        self._fields_panel_collapsed = False
        self._filters_panel_collapsed = False
        self._context_in_fields_panel = False
        self._entry_layer_selection_active = False
        self._welcome_selected_source: Optional[str] = None
        self._layer_combo_widget = None
        self._field_specs_by_key: Dict[str, PivotFieldSpec] = {}
        self._saved_configurations: Dict[str, Dict[str, Any]] = {}
        self._history_undo: List[Dict[str, Any]] = []
        self._history_redo: List[Dict[str, Any]] = []
        self._history_current: Optional[Dict[str, Any]] = None
        self._history_restoring = False
        self._history_limit = 80
        self._table_row_height = 30
        self._table_alternating_rows = True
        self._table_header_compact = True
        self.pivot_engine = PivotEngine(iface=iface, logger=QgsMessageLog)
        self.pivot_selection_bridge = PivotSelectionBridge(iface)
        self.pivot_export_service = PivotExportService()

        self._build_ui()
        self._configure_compact_sizing()
        self._apply_styles()
        self._enforce_filters_surface_backgrounds()
        self._apply_theming_tokens()
        harmonize_widget_fonts(self)
        self._load_sidebar_state()
        self._apply_sidebar_visibility(not self._sidebar_collapsed, persist=False)
        self._set_content_mode(True)
        self._apply_runtime_i18n()

    def _apply_runtime_i18n(self):
        try:
            _apply_i18n_widgets(self)
        except Exception:
            log_exception("falha opcional ignorada")

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_runtime_i18n()

    def minimumSizeHint(self):
        return QSize(640, 300)

    def sizeHint(self):
        return QSize(1040, 520)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.setObjectName("summaryPivotRoot")
        section_title_px = int(TYPOGRAPHY.get("font_secondary_px", 12))
        body_text_px = int(TYPOGRAPHY.get("font_secondary_px", 12))
        helper_text_px = int(TYPOGRAPHY.get("font_caption_px", 11))
        section_title_font = ui_font()
        section_title_font.setPixelSize(section_title_px)
        section_title_font.setWeight(QFont.Medium)
        body_text_font = ui_font()
        body_text_font.setPixelSize(body_text_px)
        body_text_font.setWeight(QFont.Normal)
        helper_text_font = ui_font()
        helper_text_font.setPixelSize(helper_text_px)
        helper_text_font.setWeight(QFont.Normal)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 3)
        root.setSpacing(4)
        root.setSizeConstraint(QLayout.SetNoConstraint)

        self.context_bar = QWidget()
        self.context_bar.setObjectName("summaryContextBar")
        self.context_layout = QVBoxLayout(self.context_bar)
        self.context_layout.setContentsMargins(0, 0, 0, 0)
        self.context_layout.setSpacing(2)

        self.context_layer_row = QHBoxLayout()
        self.context_layer_row.setContentsMargins(0, 0, 0, 0)
        self.context_layer_row.setSpacing(5)

        self.context_label = QLabel("Camada")
        self.context_label.setObjectName("summaryContextLabel")
        self.context_label.setFont(helper_text_font)
        self.context_layer_row.addWidget(self.context_label, 0, Qt.AlignVCenter)

        self.layer_combo_host = QFrame()
        self.layer_combo_host.setObjectName("summaryLayerHost")
        layer_host_layout = QHBoxLayout(self.layer_combo_host)
        layer_host_layout.setContentsMargins(0, 0, 0, 0)
        layer_host_layout.setSpacing(0)
        self.layer_combo_placeholder = QLabel("Nenhuma camada selecionada")
        self.layer_combo_placeholder.setObjectName("summaryLayerPlaceholder")
        self.layer_combo_placeholder.setFont(helper_text_font)
        layer_host_layout.addWidget(self.layer_combo_placeholder)
        self.context_layer_row.addWidget(self.layer_combo_host, 1)

        self.context_layout.addLayout(self.context_layer_row)

        self._build_state_labels(
            context_layout=self.context_layout,
            selection_layout=None,
            helper_text_font=helper_text_font,
        )

        self.initial_state_frame = QFrame()
        self.initial_state_frame.setObjectName("summaryInitialState")
        initial_layout = QVBoxLayout(self.initial_state_frame)
        initial_layout.setContentsMargins(36, 24, 36, 20)
        initial_layout.setSpacing(0)

        self.initial_welcome_wrap = QWidget(self.initial_state_frame)
        self.initial_welcome_wrap.setObjectName("summaryWelcomeWrap")
        self.initial_welcome_wrap.setMinimumWidth(600)
        self.initial_welcome_wrap.setMaximumWidth(720)
        self.initial_welcome_wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        welcome_layout = QVBoxLayout(self.initial_welcome_wrap)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.setSpacing(12)

        self.initial_state_title = QLabel("Adicionar dados ao seu relatório")
        self.initial_state_title.setObjectName("summaryWelcomeTitle")
        self.initial_state_title.setMinimumWidth(600)
        self.initial_state_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.initial_state_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        welcome_title_font = ui_font()
        welcome_title_font.setPixelSize(26)
        welcome_title_font.setWeight(QFont.DemiBold)
        self.initial_state_title.setFont(welcome_title_font)
        welcome_layout.addWidget(self.initial_state_title, 0, Qt.AlignLeft)

        self.initial_state_text = QLabel(
            "Escolha uma fonte para começar. Os dados carregados serão exibidos no painel Resumo."
        )
        self.initial_state_text.setObjectName("summaryWelcomeText")
        self.initial_state_text.setMinimumWidth(600)
        self.initial_state_text.setMaximumWidth(720)
        self.initial_state_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.initial_state_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.initial_state_text.setWordWrap(True)
        welcome_text_font = ui_font()
        welcome_text_font.setPixelSize(14)
        welcome_text_font.setWeight(QFont.Normal)
        self.initial_state_text.setFont(welcome_text_font)
        welcome_layout.addWidget(self.initial_state_text, 0, Qt.AlignLeft)

        self.source_cards_host = QWidget(self.initial_welcome_wrap)
        self.source_cards_host.setObjectName("summarySourceCardsHost")
        self.source_cards_host.setMinimumWidth(520)
        self.source_cards_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        source_cards_layout = QHBoxLayout(self.source_cards_host)
        source_cards_layout.setContentsMargins(0, 12, 0, 0)
        source_cards_layout.setSpacing(14)
        source_cards_layout.setAlignment(Qt.AlignLeft)

        self.source_card_group = QButtonGroup(self)
        self.source_card_group.setExclusive(True)
        self.source_cards: Dict[str, _SummarySourceCard] = {}
        source_specs = (
            ("map", "Camada do mapa", "source_map", "Abrir a camada do mapa e iniciar a edição do Resumo."),
        )
        for key, title, icon_key, tooltip_text in source_specs:
            card = _SummarySourceCard(
                title,
                badge_text=None,
                tooltip_text=tooltip_text,
                parent=self.source_cards_host,
            )
            card.clicked.connect(partial(self._handle_source_card_clicked, key))
            self.source_card_group.addButton(card)
            self.source_cards[key] = card
            source_cards_layout.addWidget(card, 0)

        welcome_layout.addWidget(self.source_cards_host, 0, Qt.AlignLeft)

        initial_layout.addWidget(self.initial_welcome_wrap, 0, Qt.AlignTop | Qt.AlignHCenter)
        initial_layout.addStretch(1)

        self._build_toolbar(body_text_font=body_text_font)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.import_sheet_btn.clicked.connect(self._open_spreadsheet_source_menu)
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        self.export_btn.clicked.connect(self._export_pivot_table)
        self.undo_btn.clicked.connect(self._undo_last_action)
        self.redo_btn.clicked.connect(self._redo_last_action)
        self.edit_mode_btn.clicked.connect(self._toggle_sidebar)
        self.settings_btn.clicked.connect(self._open_table_settings_dialog)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("summaryMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.splitterMoved.connect(self._handle_splitter_moved)
        root.addWidget(self.main_splitter, 1)

        self.main_column = QWidget()
        self.main_column.setObjectName("summaryMainColumn")
        self.main_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_column_layout = QVBoxLayout(self.main_column)
        main_column_layout.setContentsMargins(0, 0, 0, 0)
        main_column_layout.setSpacing(4)

        self.controls_zone = QWidget()
        self.controls_zone.setObjectName("summaryControlsZone")
        self.controls_layout = QVBoxLayout(self.controls_zone)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(3)
        self.controls_layout.addWidget(self.context_bar)
        self.controls_layout.addWidget(self.toolbar_frame)
        main_column_layout.addWidget(self.controls_zone, 0)

        self.content_zone = QWidget()
        self.content_zone.setObjectName("summaryContentZone")
        self.content_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_zone_layout = QVBoxLayout(self.content_zone)
        self.content_zone_layout.setContentsMargins(0, 0, 0, 0)
        self.content_zone_layout.setSpacing(0)
        self.content_zone_layout.addWidget(self.initial_state_frame, 1)
        main_column_layout.addWidget(self.content_zone, 1)

        self.analytics_splitter = QSplitter(Qt.Horizontal)
        self.analytics_splitter.setObjectName("summaryAnalyticsSplitter")
        self.analytics_splitter.setChildrenCollapsible(False)
        self.analytics_splitter.setHandleWidth(6)
        self.analytics_splitter.setOpaqueResize(False)
        self.analytics_splitter.splitterMoved.connect(self._handle_analytics_splitter_moved)
        self.content_zone_layout.addWidget(self.analytics_splitter, 1)

        self.fields_panel = QFrame()
        self.fields_panel.setObjectName("summaryFieldsPanel")
        self.fields_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.fields_panel.setMinimumWidth(_TOOLS_FIELDS_MIN_WIDTH)
        self.fields_panel.setMaximumWidth(_TOOLS_FIELDS_MAX_WIDTH)
        self.fields_panel_layout = QVBoxLayout(self.fields_panel)
        self.fields_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.fields_panel_layout.setSpacing(6)
        self.fields_panel_header = QWidget(self.fields_panel)
        self.fields_panel_header.setObjectName("summaryPanelHeader")
        self.fields_panel_header_layout = QHBoxLayout(self.fields_panel_header)
        self.fields_panel_header_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_panel_header_layout.setSpacing(6)
        self.fields_panel_icon = QLabel(self.fields_panel_header)
        self.fields_panel_icon.setObjectName("summaryPanelIcon")
        self.fields_panel_header_layout.addWidget(self.fields_panel_icon, 0, Qt.AlignVCenter)
        self.fields_panel_title = QLabel(_rt("Campos"))
        self.fields_panel_title.setObjectName("summaryPanelTitle")
        self.fields_panel_title.setFont(section_title_font)
        self.fields_panel_title.setStyleSheet("color: #475467; font-weight: 500;")
        self.fields_panel_header_layout.addWidget(self.fields_panel_title, 1, Qt.AlignVCenter)
        self.fields_panel_toggle_btn = QToolButton(self.fields_panel_header)
        self.fields_panel_toggle_btn.setObjectName("summaryPanelToggle")
        self.fields_panel_toggle_btn.setAutoRaise(True)
        self.fields_panel_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.fields_panel_toggle_btn.setFixedSize(22, 22)
        self.fields_panel_toggle_btn.clicked.connect(self._toggle_fields_panel)
        self.fields_panel_header_layout.addWidget(
            self.fields_panel_toggle_btn, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.fields_panel_layout.addWidget(self.fields_panel_header)
        self.fields_panel_body = QWidget(self.fields_panel)
        self.fields_panel_body.setObjectName("summaryPanelBody")
        self.fields_panel_body_layout = QVBoxLayout(self.fields_panel_body)
        self.fields_panel_body_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_panel_body_layout.setSpacing(6)
        self.fields_context_card = QWidget(self.fields_panel)
        self.fields_context_card.setObjectName("summaryFieldsContextCard")
        self.fields_context_layout = QVBoxLayout(self.fields_context_card)
        self.fields_context_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_context_layout.setSpacing(3)
        self.fields_panel_body_layout.addWidget(self.fields_context_card, 0)
        self.fields_panel_layout.addWidget(self.fields_panel_body, 1)
        self.fields_panel_collapsed_rail = QFrame(self.fields_panel)
        self.fields_panel_collapsed_rail.setObjectName("summaryPanelCollapsedRail")
        self.fields_panel_collapsed_rail.hide()
        fields_rail_layout = QVBoxLayout(self.fields_panel_collapsed_rail)
        fields_rail_layout.setContentsMargins(2, 6, 2, 6)
        fields_rail_layout.setSpacing(8)
        self.fields_panel_collapsed_btn = QToolButton(self.fields_panel_collapsed_rail)
        self.fields_panel_collapsed_btn.setObjectName("summaryPanelToggle")
        self.fields_panel_collapsed_btn.setAutoRaise(True)
        self.fields_panel_collapsed_btn.setCursor(Qt.PointingHandCursor)
        self.fields_panel_collapsed_btn.setFixedSize(22, 22)
        self.fields_panel_collapsed_btn.clicked.connect(self._toggle_fields_panel)
        fields_rail_layout.addWidget(self.fields_panel_collapsed_btn, 0, Qt.AlignHCenter | Qt.AlignTop)
        self.fields_panel_collapsed_title = _VerticalPanelLabel(_rt("Campos"), self.fields_panel_collapsed_rail)
        self.fields_panel_collapsed_title.setObjectName("summaryPanelCollapsedTitle")
        fields_rail_layout.addWidget(self.fields_panel_collapsed_title, 0, Qt.AlignHCenter | Qt.AlignTop)
        fields_rail_layout.addStretch(1)
        self.fields_panel_layout.addWidget(self.fields_panel_collapsed_rail, 1)
        self.analytics_splitter.addWidget(self.fields_panel)

        self.filters_panel = QFrame()
        self.filters_panel.setObjectName("summaryFiltersPanel")
        self.filters_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.filters_panel.setMinimumWidth(_TOOLS_FILTERS_MIN_WIDTH)
        self.filters_panel.setMaximumWidth(_TOOLS_FILTERS_MAX_WIDTH)
        self.filters_panel_layout = QVBoxLayout(self.filters_panel)
        self.filters_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.filters_panel_layout.setSpacing(6)
        self.filters_panel_header = QWidget(self.filters_panel)
        self.filters_panel_header.setObjectName("summaryPanelHeader")
        self.filters_panel_header_layout = QHBoxLayout(self.filters_panel_header)
        self.filters_panel_header_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_panel_header_layout.setSpacing(6)
        self.filters_panel_icon = QLabel(self.filters_panel_header)
        self.filters_panel_icon.setObjectName("summaryPanelIcon")
        self.filters_panel_header_layout.addWidget(self.filters_panel_icon, 0, Qt.AlignVCenter)
        self.filter_area_title = QLabel(_rt("Filtros"))
        self.filter_area_title.setObjectName("summaryPanelTitle")
        self.filter_area_title.setFont(section_title_font)
        self.filter_area_title.setStyleSheet("color: #475467; font-weight: 500;")
        self.filters_panel_header_layout.addWidget(self.filter_area_title, 1, Qt.AlignVCenter)
        self.filters_panel_toggle_btn = QToolButton(self.filters_panel_header)
        self.filters_panel_toggle_btn.setObjectName("summaryPanelToggle")
        self.filters_panel_toggle_btn.setAutoRaise(True)
        self.filters_panel_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.filters_panel_toggle_btn.setFixedSize(22, 22)
        self.filters_panel_toggle_btn.clicked.connect(self._toggle_filters_panel)
        self.filters_panel_header_layout.addWidget(
            self.filters_panel_toggle_btn, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.filters_panel_layout.addWidget(self.filters_panel_header)
        self.filters_panel_body = QWidget(self.filters_panel)
        self.filters_panel_body.setObjectName("summaryPanelBody")
        self.filters_panel_body_layout = QVBoxLayout(self.filters_panel_body)
        self.filters_panel_body_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_panel_body_layout.setSpacing(6)
        self.filters_panel_layout.addWidget(self.filters_panel_body, 1)

        self.filters_builder_scroll = QScrollArea(self.filters_panel)
        self.filters_builder_scroll.setObjectName("summaryFiltersScroll")
        self.filters_builder_scroll.setWidgetResizable(True)
        self.filters_builder_scroll.setFrameShape(QScrollArea.NoFrame)
        self.filters_builder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.filters_builder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.filters_builder_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.filters_builder_scroll.viewport().setObjectName("summaryFiltersViewport")
        self.filters_panel_body_layout.addWidget(self.filters_builder_scroll, 1)

        self.filters_builder_content = QWidget()
        self.filters_builder_content.setObjectName("summaryFiltersBuilderContent")
        self.filters_builder_content.setAttribute(Qt.WA_StyledBackground, True)
        self.filters_builder_scroll.setWidget(self.filters_builder_content)
        self.filters_builder_layout = QVBoxLayout(self.filters_builder_content)
        self.filters_builder_layout.setContentsMargins(0, 0, 0, 0)
        self.filters_builder_layout.setSpacing(10)
        for drop_target in (
            self.filters_panel,
            self.filters_panel_body,
            self.filters_builder_scroll,
            self.filters_builder_scroll.viewport(),
            self.filters_builder_content,
        ):
            drop_target.setAcceptDrops(True)
            drop_target.installEventFilter(self)
        self.filters_panel_collapsed_rail = QFrame(self.filters_panel)
        self.filters_panel_collapsed_rail.setObjectName("summaryPanelCollapsedRail")
        self.filters_panel_collapsed_rail.hide()
        filters_rail_layout = QVBoxLayout(self.filters_panel_collapsed_rail)
        filters_rail_layout.setContentsMargins(2, 6, 2, 6)
        filters_rail_layout.setSpacing(8)
        self.filters_panel_collapsed_btn = QToolButton(self.filters_panel_collapsed_rail)
        self.filters_panel_collapsed_btn.setObjectName("summaryPanelToggle")
        self.filters_panel_collapsed_btn.setAutoRaise(True)
        self.filters_panel_collapsed_btn.setCursor(Qt.PointingHandCursor)
        self.filters_panel_collapsed_btn.setFixedSize(22, 22)
        self.filters_panel_collapsed_btn.clicked.connect(self._toggle_filters_panel)
        filters_rail_layout.addWidget(self.filters_panel_collapsed_btn, 0, Qt.AlignHCenter | Qt.AlignTop)
        self.filters_panel_collapsed_title = _VerticalPanelLabel(_rt("Filtros"), self.filters_panel_collapsed_rail)
        self.filters_panel_collapsed_title.setObjectName("summaryPanelCollapsedTitle")
        filters_rail_layout.addWidget(self.filters_panel_collapsed_title, 0, Qt.AlignHCenter | Qt.AlignTop)
        filters_rail_layout.addStretch(1)
        self.filters_panel_layout.addWidget(self.filters_panel_collapsed_rail, 1)
        self.analytics_splitter.addWidget(self.filters_panel)

        # -- Left (table) -------------------------------------------------
        self.table_container = QWidget()
        self.table_container.setObjectName("summaryTablePane")
        self.table_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_container.setMinimumSize(360, 0)
        left_layout = QVBoxLayout(self.table_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.table_card = QFrame()
        self.table_card.setObjectName("summaryTableCard")
        table_card_layout = QVBoxLayout(self.table_card)
        table_card_layout.setContentsMargins(8, 8, 8, 8)
        table_card_layout.setSpacing(4)

        self.table_model = QStandardItemModel(self)
        self.proxy_model = _PivotFilterProxy(self)
        self.proxy_model.setSourceModel(self.table_model)

        self.table_stack = QStackedWidget()
        self.table_stack.setObjectName("summaryTableStack")

        self.empty_state_frame = QFrame()
        self.empty_state_frame.setObjectName("summaryEmptyState")
        empty_layout = QVBoxLayout(self.empty_state_frame)
        empty_layout.setContentsMargins(24, 20, 24, 20)
        empty_layout.setSpacing(6)
        self.empty_state_title = QLabel(_rt("Adicione campos em Linhas ou Colunas para começar"))
        self.empty_state_title.setObjectName("summaryEmptyTitle")
        empty_title_font = ui_font()
        empty_title_font.setPixelSize(body_text_px)
        empty_title_font.setWeight(QFont.Medium)
        self.empty_state_title.setFont(empty_title_font)
        empty_layout.addWidget(self.empty_state_title)
        self.empty_state_text = QLabel(_rt("Nenhum resultado para a configuração atual."))
        self.empty_state_text.setObjectName("summaryEmptyText")
        self.empty_state_text.setWordWrap(True)
        self.empty_state_text.setFont(helper_text_font)
        empty_layout.addWidget(self.empty_state_text)
        empty_layout.addStretch(1)
        self.table_stack.addWidget(self.empty_state_frame)

        self.table_page = QWidget()
        table_page_layout = QVBoxLayout(self.table_page)
        table_page_layout.setContentsMargins(0, 0, 0, 0)
        table_page_layout.setSpacing(0)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_view.setMinimumSize(0, 0)
        self.table_view.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.setFocusPolicy(Qt.NoFocus)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_view.clicked.connect(self._handle_table_cell_clicked)
        self.table_view.customContextMenuRequested.connect(self._open_table_context_menu)
        self.table_view.installEventFilter(self)
        self.table_view.viewport().installEventFilter(self)
        self.table_view.verticalHeader().sectionClicked.connect(self._handle_row_header_clicked)
        self.table_view.horizontalHeader().sectionClicked.connect(self._handle_column_header_clicked)
        table_page_layout.addWidget(self.table_view, 1)
        self.table_stack.addWidget(self.table_page)
        self.table_stack.setCurrentWidget(self.empty_state_frame)
        table_card_layout.addWidget(self.table_stack, 1)

        self.selection_summary_bar = QFrame()
        self.selection_summary_bar.setObjectName("summaryTableFooter")
        selection_layout = QHBoxLayout(self.selection_summary_bar)
        selection_layout.setContentsMargins(2, 0, 2, 0)
        selection_layout.setSpacing(6)
        self._build_state_labels(
            context_layout=self.context_layout,
            selection_layout=selection_layout,
            helper_text_font=helper_text_font,
        )
        self.selection_summary_label = QLabel("Selecione celulas para ver soma e contagem.")
        self.selection_summary_label.setObjectName("summarySelectionLabel")
        self.selection_summary_label.setFont(helper_text_font)
        selection_layout.addWidget(self.selection_summary_label, 0)
        table_card_layout.addWidget(self.selection_summary_bar)

        left_layout.addWidget(self.table_card, 1)

        self.analytics_splitter.addWidget(self.table_container)
        self.analytics_splitter.setStretchFactor(0, 18)
        self.analytics_splitter.setStretchFactor(1, 16)
        self.analytics_splitter.setStretchFactor(2, 66)
        self.analytics_splitter.setSizes([_TOOLS_FIELDS_DEFAULT_WIDTH, _TOOLS_FILTERS_DEFAULT_WIDTH, 720])
        self.main_splitter.addWidget(self.main_column)

        # -- Right (field list) ------------------------------------------
        self.side_panel = QFrame()
        self.side_panel.setObjectName("summarySidebarPanel")
        self.side_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.side_panel.setMinimumSize(0, 0)
        side_panel_layout = QVBoxLayout(self.side_panel)
        side_panel_layout.setContentsMargins(0, 0, 0, 0)
        side_panel_layout.setSpacing(0)

        self.sidebar_header = QFrame(self.side_panel)
        self.sidebar_header.setObjectName("summarySidebarHeader")
        self.sidebar_header.setMinimumHeight(42)
        self.sidebar_header_layout = QHBoxLayout(self.sidebar_header)
        self.sidebar_header_layout.setContentsMargins(16, 8, 12, 8)
        self.sidebar_header_layout.setSpacing(6)

        self.sidebar_title = QLabel("Construtor")
        self.sidebar_title.setObjectName("summarySidebarTitle")
        self.sidebar_header_layout.addWidget(self.sidebar_title, 1)

        self.sidebar_toggle_inner_btn = QToolButton(self.sidebar_header)
        self.sidebar_toggle_inner_btn.setObjectName("summarySidebarToggle")
        self.sidebar_toggle_inner_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle_inner_btn.setAutoRaise(True)
        self.sidebar_toggle_inner_btn.setFixedSize(28, 28)
        self.sidebar_toggle_inner_btn.clicked.connect(self._toggle_sidebar_from_panel)
        self.sidebar_header_layout.addWidget(self.sidebar_toggle_inner_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
        side_panel_layout.addWidget(self.sidebar_header, 0)

        self.builder_scroll = QScrollArea(self.side_panel)
        self.builder_scroll.setWidgetResizable(True)
        self.builder_scroll.setFrameShape(QScrollArea.NoFrame)
        self.builder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.builder_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.builder_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        side_panel_layout.addWidget(self.builder_scroll, 1)

        self.builder_content = QWidget()
        self.builder_content.setObjectName("summaryBuilderContent")
        self.builder_content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.builder_scroll.setWidget(self.builder_content)

        right_layout = QVBoxLayout(self.builder_content)
        right_layout.setContentsMargins(16, 12, 16, 16)
        right_layout.setSpacing(16)

        self.field_search = None

        self.fields_list = _PivotFieldSourceListWidget(owner=self)
        self.fields_list.setObjectName("summaryFieldsList")
        self.fields_list.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.fields_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.fields_list.itemDoubleClicked.connect(self._handle_field_double_click)
        self.fields_list.setUniformItemSizes(True)
        self.fields_list.setSpacing(1)
        self.fields_list.setMinimumHeight(0)
        self.fields_list.setMaximumHeight(16777215)
        self.fields_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fields_list.setIconSize(QSize(14, 14))
        self.fields_list.setItemDelegate(_PivotFieldListDelegate(self.fields_list))
        self.fields_panel_body_layout.addWidget(self.fields_list, 1)

        self._build_area_panels(
            section_title_font=section_title_font,
            helper_text_font=helper_text_font,
            body_text_font=body_text_font,
        )

        self.advanced_group = QGroupBox("Avançado")
        self.advanced_group.setObjectName("summaryAdvancedGroup")
        self.advanced_group.setProperty("filterSectionCard", True)
        self.advanced_group.setAttribute(Qt.WA_StyledBackground, True)
        self.advanced_group.setFlat(True)
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.advanced_group.setFont(section_title_font)
        self.advanced_group.toggled.connect(self._on_advanced_toggled)
        advanced_layout = QVBoxLayout(self.advanced_group)
        advanced_layout.setContentsMargins(8, 18, 8, 8)
        advanced_layout.setSpacing(8)

        self.advanced_value_label = QLabel("Campo de valor")
        self.advanced_value_label.setFont(helper_text_font)
        self.value_field_combo = QComboBox()
        self.value_field_combo.setFixedHeight(32)
        self.value_field_combo.setFont(body_text_font)
        self.value_field_combo.currentIndexChanged.connect(self._on_value_field_changed)
        self.advanced_value_label.hide()
        self.value_field_combo.setVisible(False)

        self.only_selected_label = QLabel(_rt("Apenas selecionadas"))
        self.only_selected_label.setObjectName("summaryFieldLabel")
        self.only_selected_label.setFont(body_text_font)
        self.only_selected_check = PivotSwitch()
        self.only_selected_check.setObjectName("summaryAdvancedCheck")
        self.only_selected_check.toggled.connect(self._maybe_refresh)

        only_selected_row = QHBoxLayout()
        only_selected_row.setContentsMargins(0, 0, 0, 0)
        only_selected_row.setSpacing(8)
        only_selected_row.addWidget(self.only_selected_label, 1)
        only_selected_row.addWidget(self.only_selected_check, 0, Qt.AlignRight | Qt.AlignVCenter)
        advanced_layout.addLayout(only_selected_row)

        self.include_nulls_label = QLabel(_rt("Incluir nulos"))
        self.include_nulls_label.setObjectName("summaryFieldLabel")
        self.include_nulls_label.setFont(body_text_font)
        self.include_nulls_check = PivotSwitch()
        self.include_nulls_check.setObjectName("summaryAdvancedCheck")
        self.include_nulls_check.toggled.connect(self._maybe_refresh)

        include_nulls_row = QHBoxLayout()
        include_nulls_row.setContentsMargins(0, 0, 0, 0)
        include_nulls_row.setSpacing(8)
        include_nulls_row.addWidget(self.include_nulls_label, 1)
        include_nulls_row.addWidget(self.include_nulls_check, 0, Qt.AlignRight | Qt.AlignVCenter)
        advanced_layout.addLayout(include_nulls_row)
        self.filters_builder_layout.addWidget(self.advanced_group)
        self.filters_builder_layout.addStretch(1)

        self.filters_panel_footer = QFrame(self.filters_panel)
        self.filters_panel_footer.setObjectName("summaryFiltersFooter")
        self.filters_panel_footer.setMinimumHeight(56)
        footer_layout = QVBoxLayout(self.filters_panel_footer)
        footer_layout.setContentsMargins(8, 8, 8, 8)
        footer_layout.setSpacing(0)

        self.apply_btn = QPushButton(_rt("Atualizar"))
        self.apply_btn.setObjectName("summaryPrimaryButton")
        self.apply_btn.setFixedHeight(34)
        button_font = ui_font()
        button_font.setPixelSize(body_text_px)
        button_font.setWeight(QFont.Medium)
        self.apply_btn.setFont(button_font)
        self.apply_btn.clicked.connect(self.refresh)
        footer_layout.addWidget(self.apply_btn)
        self.filters_panel_body_layout.addWidget(self.filters_panel_footer, 0)

        self.main_splitter.addWidget(self.side_panel)
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setSizes([760, _SIDEBAR_DEFAULT_WIDTH])
        self.side_panel.setMinimumWidth(_SIDEBAR_MIN_WIDTH)
        self.side_panel.setMaximumWidth(_SIDEBAR_MAX_WIDTH)
        self.side_panel.hide()
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.activated.connect(self._undo_last_action)
        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._shortcut_redo.activated.connect(self._redo_last_action)
        self._shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_redo_alt.activated.connect(self._redo_last_action)
        self._shortcut_copy = QShortcut(QKeySequence.Copy, self.table_view)
        self._shortcut_copy.activated.connect(self._copy_selected_cells_to_clipboard)
        self._shortcut_copy_headers = QShortcut(QKeySequence("Ctrl+Shift+C"), self.table_view)
        self._shortcut_copy_headers.activated.connect(
            lambda: self._copy_selected_cells_to_clipboard(include_headers=True)
        )
        self._refresh_toolbar_chrome()
        self._reset_history_state()
        self._set_content_mode(False)

    def _configure_compact_sizing(self):
        for widget in (
            self,
            self.table_view,
            self.fields_list,
            self.filter_fields_list,
            self.row_fields_list,
            self.column_fields_list,
            self.value_fields_list,
            self.advanced_group,
        ):
            try:
                widget.setMinimumHeight(0)
            except Exception:
                log_exception("falha opcional ignorada")

    def _load_sidebar_state(self):
        settings = QSettings()
        collapsed = settings.value(_SIDEBAR_COLLAPSED_KEY, False, type=bool)
        width = settings.value(_SIDEBAR_WIDTH_KEY, _SIDEBAR_DEFAULT_WIDTH, type=int)
        try:
            width = int(width)
        except Exception:
            width = _SIDEBAR_DEFAULT_WIDTH
        self._sidebar_collapsed = bool(collapsed)
        self._sidebar_last_width = self._clamp_sidebar_width(width)

    def _persist_sidebar_state(self):
        settings = QSettings()
        settings.setValue(_SIDEBAR_COLLAPSED_KEY, self._sidebar_collapsed)
        if not self._sidebar_collapsed and self.main_splitter is not None:
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > _SIDEBAR_COLLAPSED_WIDTH:
                self._sidebar_last_width = self._clamp_sidebar_width(sizes[1])
        settings.setValue(_SIDEBAR_WIDTH_KEY, int(self._sidebar_last_width))

    def _toggle_sidebar(self, checked: bool):
        self._apply_tools_panels_visibility(bool(checked))
        self._commit_history_if_changed()

    def _toggle_sidebar_from_panel(self):
        self._apply_tools_panels_visibility(self._tools_panels_hidden)
        self._commit_history_if_changed()

    def _clamp_sidebar_width(self, width: int) -> int:
        try:
            numeric_width = int(width)
        except Exception:
            numeric_width = _SIDEBAR_DEFAULT_WIDTH
        return max(_SIDEBAR_MIN_WIDTH, min(_SIDEBAR_MAX_WIDTH, numeric_width))

    def _sync_sidebar_chrome(self, visible: bool):
        expanded = bool(visible)
        if hasattr(self, "sidebar_header_layout"):
            if expanded:
                self.sidebar_header_layout.setContentsMargins(16, 8, 12, 8)
                self.sidebar_header_layout.setAlignment(self.sidebar_toggle_inner_btn, Qt.AlignRight | Qt.AlignVCenter)
            else:
                self.sidebar_header_layout.setContentsMargins(10, 8, 10, 8)
                self.sidebar_header_layout.setAlignment(self.sidebar_toggle_inner_btn, Qt.AlignHCenter | Qt.AlignVCenter)

        if hasattr(self, "sidebar_title"):
            self.sidebar_title.setVisible(expanded)

        if hasattr(self, "builder_scroll"):
            self.builder_scroll.setVisible(expanded)

        if hasattr(self, "sidebar_footer"):
            self.sidebar_footer.setVisible(expanded)

        if hasattr(self, "sidebar_toggle_inner_btn"):
            self.sidebar_toggle_inner_btn.setArrowType(Qt.LeftArrow if expanded else Qt.RightArrow)
            self.sidebar_toggle_inner_btn.setToolTip(
                "Recolher construtor" if expanded else "Expandir construtor"
            )

        if hasattr(self, "side_panel"):
            self.side_panel.setProperty("collapsed", not expanded)
            self.side_panel.style().unpolish(self.side_panel)
            self.side_panel.style().polish(self.side_panel)

    def _create_area_chip_widget(self, area: str, field_spec: PivotFieldSpec) -> QWidget:
        return _pivot_create_area_chip_widget(
            self,
            area,
            field_spec,
            icon_factory=_svg_icon_from_template,
            toolbar_icons=_TOOLBAR_SVG_ICONS,
        )

    def _refresh_area_item_widgets(self, area: str):
        _pivot_refresh_area_item_widgets(self, area)

    def _toggle_fields_panel(self):
        if hasattr(self, "analytics_splitter") and not self._fields_panel_collapsed:
            sizes = self.analytics_splitter.sizes()
            if len(sizes) >= 1 and sizes[0] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                self._tools_fields_width = int(sizes[0])
        self._fields_panel_collapsed = not self._fields_panel_collapsed
        self._apply_tools_panels_visibility(not self._tools_panels_hidden)
        self._commit_history_if_changed()

    def _toggle_filters_panel(self):
        if hasattr(self, "analytics_splitter") and not self._filters_panel_collapsed:
            sizes = self.analytics_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                self._tools_builder_width = int(sizes[1])
        self._filters_panel_collapsed = not self._filters_panel_collapsed
        self._apply_tools_panels_visibility(not self._tools_panels_hidden)
        self._commit_history_if_changed()

    def _sync_tools_panel_chrome(self):
        panels = (
            (
                getattr(self, "fields_panel", None),
                getattr(self, "fields_panel_header", None),
                getattr(self, "fields_panel_body", None),
                getattr(self, "fields_panel_collapsed_rail", None),
                getattr(self, "fields_panel_toggle_btn", None),
                getattr(self, "fields_panel_collapsed_btn", None),
                getattr(self, "_fields_panel_collapsed", False),
                _TOOLS_FIELDS_MIN_WIDTH,
                _TOOLS_FIELDS_MAX_WIDTH,
                _rt("Campos"),
            ),
            (
                getattr(self, "filters_panel", None),
                getattr(self, "filters_panel_header", None),
                getattr(self, "filters_panel_body", None),
                getattr(self, "filters_panel_collapsed_rail", None),
                getattr(self, "filters_panel_toggle_btn", None),
                getattr(self, "filters_panel_collapsed_btn", None),
                getattr(self, "_filters_panel_collapsed", False),
                _TOOLS_FILTERS_MIN_WIDTH,
                _TOOLS_FILTERS_MAX_WIDTH,
                _rt("Filtros"),
            ),
        )

        for panel, header, body, rail, header_btn, rail_btn, collapsed, min_width, max_width, title in panels:
            if panel is None:
                continue
            if header is not None:
                header.setVisible(not collapsed)
            if body is not None:
                body.setVisible(not collapsed)
            if rail is not None:
                rail.setVisible(collapsed)
            panel.setMinimumWidth(_TOOLS_PANEL_COLLAPSED_WIDTH if collapsed else min_width)
            panel.setMaximumWidth(_TOOLS_PANEL_COLLAPSED_WIDTH if collapsed else max_width)
            panel.setProperty("collapsed", collapsed)
            if header_btn is not None:
                header_btn.setArrowType(Qt.NoArrow)
                header_btn.setText("‹")
                header_btn.setToolTip(f"Recolher {title}")
            if rail_btn is not None:
                rail_btn.setArrowType(Qt.NoArrow)
                rail_btn.setText("›")
                rail_btn.setToolTip(f"Expandir {title}")
            try:
                panel.style().unpolish(panel)
                panel.style().polish(panel)
            except Exception:
                log_exception("falha opcional ignorada")

    def _handle_analytics_splitter_moved(self, pos: int, index: int):
        if getattr(self, "_tools_panels_hidden", False) or not hasattr(self, "analytics_splitter"):
            return
        sizes = self.analytics_splitter.sizes()
        if len(sizes) >= 3:
            if not getattr(self, "_fields_panel_collapsed", False) and sizes[0] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                self._tools_fields_width = int(sizes[0])
            if not getattr(self, "_filters_panel_collapsed", False) and sizes[1] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                self._tools_builder_width = int(sizes[1])

    def _apply_tools_panels_visibility(self, visible: bool):
        self._tools_panels_hidden = not visible
        if hasattr(self, "sidebar_toggle_btn"):
            self.sidebar_toggle_btn.blockSignals(True)
            self.sidebar_toggle_btn.setChecked(bool(visible))
            self.sidebar_toggle_btn.blockSignals(False)
        self._refresh_toolbar_chrome()

        if hasattr(self, "fields_panel"):
            self.fields_panel.setVisible(visible)
        if hasattr(self, "filters_panel"):
            self.filters_panel.setVisible(visible)
        self._sync_tools_panel_chrome()

        if hasattr(self, "analytics_splitter"):
            sizes = self.analytics_splitter.sizes()
            total_width = sum(size for size in sizes if size > 0)
            if total_width <= 0:
                total_width = max(int(self.analytics_splitter.width() or 0), 1040)

            if visible:
                fields_width = (
                    _TOOLS_PANEL_COLLAPSED_WIDTH
                    if getattr(self, "_fields_panel_collapsed", False)
                    else max(_TOOLS_FIELDS_MIN_WIDTH, int(getattr(self, "_tools_fields_width", _TOOLS_FIELDS_DEFAULT_WIDTH) or _TOOLS_FIELDS_DEFAULT_WIDTH))
                )
                builder_width = (
                    _TOOLS_PANEL_COLLAPSED_WIDTH
                    if getattr(self, "_filters_panel_collapsed", False)
                    else max(_TOOLS_FILTERS_MIN_WIDTH, int(getattr(self, "_tools_builder_width", _TOOLS_FILTERS_DEFAULT_WIDTH) or _TOOLS_FILTERS_DEFAULT_WIDTH))
                )
                table_width = max(1, total_width - fields_width - builder_width)
                self.analytics_splitter.setSizes([fields_width, builder_width, table_width])
            else:
                if len(sizes) >= 3:
                    if sizes[0] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                        self._tools_fields_width = int(sizes[0])
                    if sizes[1] > _TOOLS_PANEL_COLLAPSED_WIDTH:
                        self._tools_builder_width = int(sizes[1])
                self.analytics_splitter.setSizes([0, 0, total_width])

        self._refresh_active_area_styles()

    def _place_context_bar(self, in_fields_panel: bool):
        target_in_fields = bool(in_fields_panel)
        if not hasattr(self, "context_bar"):
            return

        desired_parent = None
        if target_in_fields and hasattr(self, "fields_context_layout"):
            desired_parent = self.fields_context_layout.parentWidget()
        elif hasattr(self, "controls_layout"):
            desired_parent = self.controls_layout.parentWidget()

        if desired_parent is not None and self.context_bar.parent() is desired_parent:
            self._context_in_fields_panel = target_in_fields
            return

        self.context_bar.setParent(None)
        if target_in_fields and hasattr(self, "fields_context_layout"):
            self.fields_context_layout.addWidget(self.context_bar)
        elif hasattr(self, "controls_layout"):
            self.controls_layout.insertWidget(0, self.context_bar)
        self._context_in_fields_panel = target_in_fields

    def _build_toolbar(self, body_text_font):
        _pivot_build_toolbar(
            self,
            body_text_font=body_text_font,
            translate=_rt,
            icon_factory=_svg_icon_from_template,
            toolbar_icons=_TOOLBAR_SVG_ICONS,
            ink_color=_INK_COLOR,
        )

    def _build_state_labels(self, context_layout, selection_layout, helper_text_font):
        _pivot_build_state_labels(
            self,
            context_layout=context_layout,
            selection_layout=selection_layout,
            helper_text_font=helper_text_font,
        )

    def _build_area_panels(self, section_title_font, helper_text_font, body_text_font):
        _pivot_build_area_panels(
            self,
            section_title_font=section_title_font,
            helper_text_font=helper_text_font,
            body_text_font=body_text_font,
            translate=_rt,
            supported_aggregators=self.SUPPORTED_AGGREGATORS,
        )

    def _configure_toolbar_button(self, button: Optional[QPushButton]):
        _pivot_configure_toolbar_button(button)

    def _configure_toolbar_icon_button(self, button: Optional[QPushButton], icon_name: str, tooltip: str, icon_size: int = 18):
        _pivot_configure_toolbar_icon_button(button, icon_name, tooltip, icon_size=icon_size)

    def _polish_toolbar_button(self, button: Optional[QPushButton]):
        _pivot_polish_toolbar_button(button)

    def _reset_history_state(self):
        _pivot_reset_history_state(self)

    def _commit_history_if_changed(self):
        _pivot_commit_history_if_changed(self)

    def _undo_last_action(self):
        _pivot_undo_last_action(self)

    def _redo_last_action(self):
        _pivot_redo_last_action(self)

    def _update_undo_redo_buttons(self):
        _pivot_update_undo_redo_buttons(self)

    def _restore_default_summary_layout(self):
        _pivot_restore_default_summary_layout(self)

    def _open_summary_settings_menu(self):
        menu = QMenu(self)
        fields_text = _rt("Expandir campos") if self._fields_panel_collapsed else _rt("Recolher campos")
        filters_text = _rt("Expandir filtros") if self._filters_panel_collapsed else _rt("Recolher filtros")
        fields_action = menu.addAction(fields_text)
        filters_action = menu.addAction(filters_text)
        menu.addSeparator()
        restore_action = menu.addAction(_rt("Restaurar layout"))
        chosen = menu.exec_(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))
        if chosen == fields_action:
            self._toggle_fields_panel()
        elif chosen == filters_action:
            self._toggle_filters_panel()
        elif chosen == restore_action:
            self._restore_default_summary_layout()
            self._commit_history_if_changed()

    def _open_table_settings_dialog(self):
        _pivot_open_table_settings_dialog(
            self,
            translate=_rt,
            apply_preferences_callback=self._apply_table_preferences,
        )

    def _refresh_toolbar_chrome(self):
        _pivot_refresh_toolbar_chrome(
            self,
            icon_factory=_svg_icon_from_template,
            toolbar_icons=_TOOLBAR_SVG_ICONS,
            translate=_rt,
        )

    def _handle_splitter_moved(self, pos: int, index: int):
        if self._sidebar_collapsed or self.main_splitter is None:
            return
        sizes = self.main_splitter.sizes()
        if len(sizes) >= 2 and sizes[1] > _SIDEBAR_COLLAPSED_WIDTH:
            self._sidebar_last_width = self._clamp_sidebar_width(sizes[1])
            self._persist_sidebar_state()

    def _apply_sidebar_visibility(self, visible: bool, persist: bool = True):
        self._sidebar_collapsed = not visible
        if hasattr(self, "sidebar_toggle_btn"):
            self.sidebar_toggle_btn.blockSignals(True)
            self.sidebar_toggle_btn.setChecked(not visible)
            self.sidebar_toggle_btn.blockSignals(False)
        self._refresh_toolbar_chrome()

        if hasattr(self, "side_panel"):
            self.side_panel.show()
            if visible:
                self.side_panel.setMinimumWidth(_SIDEBAR_MIN_WIDTH)
                self.side_panel.setMaximumWidth(_SIDEBAR_MAX_WIDTH)
            else:
                self.side_panel.setMinimumWidth(_SIDEBAR_COLLAPSED_WIDTH)
                self.side_panel.setMaximumWidth(_SIDEBAR_COLLAPSED_WIDTH)
            self._sync_sidebar_chrome(visible)

        if hasattr(self, "main_splitter"):
            sizes = self.main_splitter.sizes()
            total_width = sum(size for size in sizes if size > 0)
            if total_width <= 0:
                total_width = max(int(self.main_splitter.width() or 0), 760 + _SIDEBAR_DEFAULT_WIDTH)

            if visible:
                sidebar_width = self._clamp_sidebar_width(self._sidebar_last_width or _SIDEBAR_DEFAULT_WIDTH)
                self.main_splitter.setSizes([max(1, total_width - sidebar_width), sidebar_width])
            else:
                if len(sizes) >= 2 and sizes[1] > _SIDEBAR_COLLAPSED_WIDTH:
                    self._sidebar_last_width = self._clamp_sidebar_width(sizes[1])
                self.main_splitter.setSizes(
                    [max(1, total_width - _SIDEBAR_COLLAPSED_WIDTH), _SIDEBAR_COLLAPSED_WIDTH]
                )

        if persist:
            self._persist_sidebar_state()
        self._refresh_active_area_styles()

    def _set_content_mode(self, has_data: bool):
        self._place_context_bar(has_data)
        self.initial_state_frame.setVisible(not has_data)
        show_context = bool(has_data or self._entry_layer_selection_active)
        self.controls_zone.setVisible(show_context)
        self.context_bar.setVisible(has_data or self._entry_layer_selection_active)
        if hasattr(self, "fields_context_card"):
            self.fields_context_card.setVisible(has_data)
        self.toolbar_frame.setVisible(has_data)
        self.analytics_splitter.setVisible(has_data)
        self.table_container.setVisible(has_data)
        self.meta_label.setVisible(has_data)
        self.main_splitter.setVisible(True)
        if hasattr(self, "side_panel"):
            self.side_panel.hide()
            if hasattr(self, "main_splitter"):
                total_width = max(int(self.main_splitter.width() or 0), 760)
                self.main_splitter.setSizes([total_width, 0])
        if has_data:
            self._apply_tools_panels_visibility(not self._tools_panels_hidden)

    def _plugin_host(self):
        if self._host is not None:
            return self._host
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "register_integration_dataframe") or hasattr(parent, "integration_panel"):
                return parent
            parent = parent.parent()
        return None

    def _clear_source_card_selection(self):
        group = getattr(self, "source_card_group", None)
        cards = getattr(self, "source_cards", None) or {}
        if group is not None:
            group.setExclusive(False)
        for card in cards.values():
            card.setChecked(False)
        if group is not None:
            group.setExclusive(True)
        self._welcome_selected_source = None

    def _select_source_card(self, key: Optional[str]):
        cards = getattr(self, "source_cards", None) or {}
        if not key or key not in cards:
            self._clear_source_card_selection()
            return
        self._clear_source_card_selection()
        cards[key].setChecked(True)
        self._welcome_selected_source = key

    def _handle_source_card_clicked(self, key: str):
        self._select_source_card(key)
        self._entry_layer_selection_active = key == "map"
        if key != "map":
            self._set_content_mode(False)
        if key == "map":
            self._open_map_layer_source()
        elif key == "sheet":
            self._open_spreadsheet_source_menu()
        elif key == "postgres":
            self._open_postgres_source()
    def _open_map_layer_source(self):
        self._entry_layer_selection_active = True
        self._set_content_mode(False)
        combo = getattr(self, "_layer_combo_widget", None)
        if combo is not None:
            combo.setFocus(Qt.MouseFocusReason)
            try:
                QTimer.singleShot(0, combo.showPopup)
            except Exception:
                log_exception("falha opcional ignorada")

    def _integration_panel(self):
        host = self._plugin_host()
        return getattr(host, "integration_panel", None) if host is not None else None

    def _open_spreadsheet_source_menu(self):
        panel = self._integration_panel()
        if panel is None:
            slim_message(self, _rt("Resumo"), _rt("O painel de integração ainda não está disponível."))
            return
        menu = QMenu(self)
        excel_action = menu.addAction(_rt("Importar Excel (.xlsx / .xls)"))
        csv_action = menu.addAction(_rt("Importar CSV (.csv)"))
        anchor = getattr(self, "import_sheet_btn", None)
        if anchor is None:
            anchor = (getattr(self, "source_cards", {}) or {}).get("sheet")
        if anchor is not None:
            menu_pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        else:
            menu_pos = QCursor.pos()
        chosen = menu.exec_(menu_pos)
        if chosen == excel_action and hasattr(panel, "_handle_excel"):
            panel._handle_excel()
        elif chosen == csv_action and hasattr(panel, "_handle_delimited_file"):
            panel._handle_delimited_file()

    def _open_postgres_source(self):
        panel = self._integration_panel()
        if panel is None or not hasattr(panel, "_handle_sql_database"):
            slim_message(self, _rt("Resumo"), _rt("O fluxo de PostgreSQL não está disponível no momento."))
            return
        panel._handle_sql_database()

    def show_welcome_message(self):
        self._entry_layer_selection_active = False
        self._clear_source_card_selection()
        self.show_empty_message(
            _rt("Adicionar dados ao seu relatório"),
            _rt("Escolha uma fonte para começar. Os dados carregados serão exibidos no painel Resumo."),
        )
        self._set_content_mode(True)
        self.table_stack.setCurrentWidget(self.empty_state_frame)
        self._apply_runtime_i18n()

    def _apply_styles(self):
        _pivot_apply_styles(self)

    def _enforce_filters_surface_backgrounds(self):
        _pivot_enforce_filters_surface_backgrounds(self)

    # ------------------------------------------------------------------ Data intake
    def set_summary_data(self, summary_data: Dict):
        self._block_updates = True
        try:
            previous_key = _pivot_configuration_key_from_metadata(self._current_metadata)
            if previous_key:
                self._saved_configurations[previous_key] = dict(self.get_current_configuration() or {})

            metadata = summary_data.get("metadata", {}) or {}
            raw = summary_data.get("raw_data") or {}
            columns = raw.get("columns") or []
            rows = raw.get("rows") or []

            df = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame(rows)
            self.raw_df = df
            self.filtered_df = df
            self.column_dtypes = {col: str(df[col].dtype) for col in df.columns}
            self.numeric_candidates = _pivot_detect_numeric_candidates(df, self._is_numeric_column)
            self._current_metadata = metadata
            self._current_summary_data = dict(summary_data or {})
            self._current_layer = self._resolve_current_layer()
            self._current_pivot_request = None
            self._current_pivot_result = None

            self._update_meta_label(metadata, summary_data.get("filter_description"))
            self._populate_field_panel(df)
            _pivot_restore_saved_configuration_for_metadata(self, metadata)
        finally:
            self._block_updates = False

        self._set_content_mode(True)
        self.refresh()
        self._reset_history_state()

    def _update_meta_label(self, metadata: Dict, filter_desc: Optional[str]):
        self.meta_label.setText("")
        self._update_context_summary()

    def set_layer_combo(self, combo: QComboBox):
        if combo is None or not hasattr(self, "layer_combo_host"):
            return
        self._layer_combo_widget = combo
        layout = self.layer_combo_host.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        if combo.parent() is not self.layer_combo_host:
            combo.setParent(self.layer_combo_host)
        combo.setObjectName("summaryLayerCombo")
        combo.setMinimumHeight(28)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(combo)
        combo.setVisible(True)
        combo.show()
        self.layer_combo_host.setVisible(True)
        self.context_bar.setVisible(True)
        if hasattr(self, "controls_zone"):
            self.controls_zone.setVisible(True)
        layout.invalidate()
        self.layer_combo_host.updateGeometry()
        self.context_bar.updateGeometry()

    def _current_filter_description(self) -> str:
        summary_filter = str(self._current_summary_data.get("filter_description") or "").strip()
        metadata_filter = str(self._current_metadata.get("filter_expression") or "").strip()
        return summary_filter or metadata_filter or _rt("Nenhum")

    def _current_metric_label(self) -> str:
        aggregation = str(self.agg_combo.currentData() or "count")
        if aggregation == "count":
            return _rt("Contagem de registros")
        current_text = str(self.value_field_combo.currentText() or "").strip()
        if current_text and current_text != "(Nenhum)":
            return current_text
        metadata_field = str(self._current_metadata.get("field_name") or "").strip()
        return metadata_field or _rt("Contagem de registros")

    def _update_context_summary(self):
        if hasattr(self, "value_area_title"):
            metric_label = self._current_metric_label()
            self.value_area_title.setText(
                _rt("Valores")
                if metric_label == _rt("Contagem de registros")
                else _rt("Valores · {metric_label}", metric_label=metric_label)
            )

    def _populate_field_panel(self, df: pd.DataFrame):
        _pivot_populate_field_panel(
            self,
            df,
            icon_factory=_svg_icon_from_template,
            toolbar_icons=_TOOLBAR_SVG_ICONS,
            translate=_rt,
        )

    def _apply_saved_configuration(self, config: Dict[str, Any]):
        _pivot_apply_saved_configuration(self, config)

    def _field_spec_from_field_name(self, field_name: Optional[str]) -> Optional[PivotFieldSpec]:
        return _pivot_field_spec_from_field_name(self, field_name)

    # ------------------------------------------------------------------ Filters & refresh
    def refresh(self):
        self._apply_filters()
        layer = self._resolve_current_layer()
        self._current_layer = layer
        has_structure = bool(self._selected_area_specs("row") or self._selected_area_specs("column"))
        has_explicit_value = bool(self.value_field_combo.currentData())
        aggregation = str(self.agg_combo.currentData() or "count")
        if layer is not None and not has_structure and not (aggregation != "count" and has_explicit_value):
            self._current_pivot_request = None
            self._current_pivot_result = None
            self.pivot_df = pd.DataFrame()
            self._populate_table()
            return
        if layer is not None:
            self._compute_layer_backed_pivot(layer)
        else:
            self._compute_dataframe_pivot()
        self._populate_table()

    def _apply_filters(self):
        df = self.raw_df
        if df is None or df.empty:
            self.filtered_df = pd.DataFrame()
            return

        filtered = df.copy()
        self.filtered_df = filtered

    def _compute_dataframe_pivot(self):
        _pivot_compute_dataframe_pivot(self)

    def _compute_layer_backed_pivot(self, layer):
        _pivot_compute_layer_backed_pivot(
            self,
            layer,
            pivot_validation_error=PivotValidationError,
            translate=_rt,
        )

    def _populate_table(self):
        _pivot_populate_table(
            self,
            translate=_rt,
            message_log=QgsMessageLog,
            qgis_info=Qgis.Info,
            ui_font_factory=ui_font,
            typography=TYPOGRAPHY,
        )

    def _rebuild_column_filters(self, headers: List[str]):
        return

    # ------------------------------------------------------------------ Events
    def _on_search_text_changed(self, text: str):
        self.proxy_model.set_global_filter(text)
        self._update_status_label()

    def _on_column_filter_changed(self, column: int, text: str):
        self.proxy_model.set_column_filter(column, text)
        self._update_status_label()

    def _on_operation_changed(self, *args):
        aggregation = str(self.agg_combo.currentData() or "count")
        self.advanced_group.blockSignals(True)
        self.advanced_group.setChecked(aggregation != "count")
        self.advanced_group.blockSignals(False)
        self._on_advanced_toggled(aggregation != "count")
        if aggregation != "count":
            self._sync_default_value_field()
            self._sync_value_area_from_combo()
        self._update_status_label()

    def _on_advanced_toggled(self, checked: bool):
        self._update_context_summary()
        self._maybe_refresh()

    def _on_value_field_changed(self, *args):
        self._sync_value_area_from_combo()
        self._update_context_summary()
        self._maybe_refresh()

    def _sync_default_value_field(self):
        if self.value_field_combo.count() == 0:
            return
        if self.value_field_combo.currentData() is not None:
            return
        for candidate in self.numeric_candidates:
            idx = self.value_field_combo.findText(candidate)
            if idx != -1:
                self.value_field_combo.setCurrentIndex(idx)
                return
        if self.value_field_combo.count():
            self.value_field_combo.setCurrentIndex(0)

    def _maybe_refresh(self):
        if self._block_updates:
            return
        auto_on = True
        if isinstance(self.auto_update_check, QCheckBox):
            auto_on = self.auto_update_check.isChecked()
        if auto_on:
            self.refresh()
        self._commit_history_if_changed()

    def _clear_filters(self):
        _pivot_clear_field_search(self)
        self.proxy_model.set_global_filter("")
        self._update_status_label()

    def _filter_field_list(self, text: str):
        _pivot_filter_field_list(self, text)

    def _handle_field_double_click(self, item: QListWidgetItem):
        _pivot_handle_field_double_click(self, item)

    def _handle_table_cell_clicked(self, proxy_index):
        if not proxy_index.isValid():
            return
        self._safe_sync_selection_to_map()
        self._schedule_selection_feedback_refresh()

    def _handle_row_header_clicked(self, proxy_row: int):
        if self._current_pivot_result is None or self._current_layer is None:
            return
        self._select_proxy_row_data_cells(proxy_row)
        proxy_index = self.proxy_model.index(proxy_row, 0)
        if not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        source_row = source_index.row()
        if source_row < 0 or source_row >= len(self._current_pivot_result.matrix):
            return
        self.pivot_selection_bridge.select_row(self._current_layer, self._current_pivot_result.matrix[source_row])
        self._refresh_presentation_after_selection(self._current_layer)
        self._schedule_selection_feedback_refresh()

    def _handle_column_header_clicked(self, proxy_column: int):
        if self._current_pivot_result is None or self._current_layer is None:
            return
        source_column = proxy_column
        if source_column < self._pivot_data_column_offset:
            return
        self._select_proxy_column_data_cells(proxy_column)
        matrix_column = source_column - self._pivot_data_column_offset
        if matrix_column < 0 or matrix_column >= len(self._display_column_keys):
            return
        column_cells = []
        for row_cells in self._current_pivot_result.matrix:
            if matrix_column < len(row_cells):
                column_cells.append(row_cells[matrix_column])
        self.pivot_selection_bridge.select_column(self._current_layer, column_cells)
        self._refresh_presentation_after_selection(self._current_layer)
        self._schedule_selection_feedback_refresh()

    def _select_proxy_row_data_cells(self, proxy_row: int):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return
        last_column = self.proxy_model.columnCount() - 1
        first_data_column = self._pivot_data_column_offset
        if proxy_row < 0 or last_column < first_data_column:
            return
        start = self.proxy_model.index(proxy_row, first_data_column)
        end = self.proxy_model.index(proxy_row, last_column)
        if not start.isValid() or not end.isValid():
            return
        selection = QItemSelection(start, end)
        selection_model.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Select)
        self.table_view.setCurrentIndex(start)

    def _select_proxy_column_data_cells(self, proxy_column: int):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return
        row_count = self.proxy_model.rowCount()
        if row_count <= 0 or proxy_column < self._pivot_data_column_offset:
            return
        start = self.proxy_model.index(0, proxy_column)
        end = self.proxy_model.index(row_count - 1, proxy_column)
        if not start.isValid() or not end.isValid():
            return
        selection = QItemSelection(start, end)
        selection_model.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Select)
        self.table_view.setCurrentIndex(start)

    def _update_status_label(self):
        total = self.table_model.rowCount()
        visible = self.proxy_model.rowCount()
        row_labels = [self._area_list("row").item(i).text() for i in range(self._area_list("row").count())]
        column_labels = [self._area_list("column").item(i).text() for i in range(self._area_list("column").count())]
        parts = [f"Mostrando {visible}/{total} linha(s)"]
        if row_labels:
            parts.append(f"{_rt('Linhas')}: {' / '.join(row_labels)}")
        if column_labels:
            parts.append(f"{_rt('Colunas')}: {' / '.join(column_labels)}")
        self.status_label.setText(" | ".join(parts))
        self._update_context_summary()

    def _connect_selection_summary(self):
        try:
            selection_model = self.table_view.selectionModel()
        except Exception:
            selection_model = None
        if selection_model is None:
            return
        try:
            selection_model.selectionChanged.disconnect(self._on_table_selection_changed)
        except Exception:
            log_exception("falha opcional ignorada")
        selection_model.selectionChanged.connect(self._on_table_selection_changed)

    def _on_table_selection_changed(self, selected, deselected):
        self._schedule_selection_feedback_refresh()

    def eventFilter(self, watched, event):
        filter_drop_targets = {
            getattr(self, "filters_panel", None),
            getattr(self, "filters_panel_body", None),
            getattr(self, "filters_builder_scroll", None),
            getattr(getattr(self, "filters_builder_scroll", None), "viewport", lambda: None)(),
            getattr(self, "filters_builder_content", None),
        }
        if watched in filter_drop_targets and event is not None:
            if self._handle_filter_panel_drop_event(event):
                return True

        if watched in {getattr(self, "table_view", None), getattr(getattr(self, "table_view", None), "viewport", lambda: None)()}:
            if event is not None and event.type() in {
                QEvent.MouseButtonRelease,
                QEvent.KeyRelease,
                QEvent.FocusIn,
                QEvent.FocusOut,
            }:
                self._schedule_selection_feedback_refresh()
        return super().eventFilter(watched, event)

    def _handle_filter_panel_drop_event(self, event) -> bool:
        return _pivot_handle_filter_panel_drop_event(self, event)

    def _schedule_selection_feedback_refresh(self):
        QTimer.singleShot(0, self._refresh_selection_feedback)

    def _refresh_selection_feedback(self):
        try:
            self._update_selection_summary()
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"PivotTableWidget: falha ao atualizar resumo de selecao: {exc}",
                "Summarizer",
                Qgis.Warning,
            )
            if hasattr(self, "selection_summary_label"):
                self.selection_summary_label.setText("Nao foi possivel calcular a selecao atual.")

    def _safe_sync_selection_to_map(self):
        try:
            self._sync_selection_to_map()
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"PivotTableWidget: falha ao sincronizar selecao no mapa: {exc}",
                "Summarizer",
                Qgis.Warning,
            )

    def _sync_selection_to_map(self):
        if self._current_layer is None:
            return
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return

        feature_ids: List[int] = []
        seen = set()
        for proxy_index in selection_model.selectedIndexes():
            if not proxy_index.isValid():
                continue
            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                continue
            if source_index.column() < self._pivot_data_column_offset:
                continue
            raw_ids = self._feature_ids_for_proxy_index(proxy_index, source_index)
            for fid in raw_ids:
                if fid in seen:
                    continue
                seen.add(fid)
                feature_ids.append(fid)
        self.pivot_selection_bridge.select_feature_ids(self._current_layer, feature_ids)
        self._refresh_presentation_after_selection(self._current_layer)

    def _refresh_presentation_after_selection(self, layer: Optional[QgsVectorLayer]):
        controller = self._presentation_controller()
        if controller is None:
            return
        try:
            controller.refresh_after_chart_selection(layer)
        except Exception:
            log_exception("falha opcional ignorada")

    def _presentation_controller(self):
        current = self
        visited = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            for attr in ("presentation_controller", "presentation_map_controller"):
                controller = getattr(current, attr, None)
                if controller is not None:
                    return controller
            parent = None
            try:
                parent = current.parentWidget()
            except Exception:
                parent = None
            if parent is None:
                try:
                    parent = current.parent()
                except Exception:
                    parent = None
            current = parent
        return None

    def _update_selection_summary(self):
        if not hasattr(self, "selection_summary_label"):
            return
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            self.selection_summary_label.setText(_rt("Selecione células para ver soma e contagem."))
            return

        indexes = list(selection_model.selectedIndexes() or [])
        if not indexes:
            self.selection_summary_label.setText(_rt("Selecione células para ver soma e contagem."))
            return

        stats = self._collect_selection_statistics(indexes)
        if stats["selected_count"] == 0:
            self.selection_summary_label.setText(_rt("Selecione células para ver soma e contagem."))
            return

        parts = [
            _rt("Selecionadas: {selected_count} celula(s)", selected_count=stats["selected_count"]),
            _rt("Numericas: {numeric_count}", numeric_count=stats["numeric_count"]),
        ]
        if stats["blank_count"]:
            parts.append(_rt("Vazias: {blank_count}", blank_count=stats["blank_count"]))
        if stats["numeric_count"] > 0:
            parts.extend(
                [
                    _rt("Soma: {value}", value=self._format_selection_number(stats["sum"])),
                    _rt("Media: {value}", value=self._format_selection_number(stats["mean"])),
                    _rt("Min: {value}", value=self._format_selection_number(stats["min"])),
                    _rt("Max: {value}", value=self._format_selection_number(stats["max"])),
                    _rt("Mediana: {value}", value=self._format_selection_number(stats["median"])),
                    _rt("Unicos: {value}", value=self._format_selection_number(stats["unique_count"])),
                ]
            )
        self.selection_summary_label.setText(" | ".join(parts))

    def _collect_selection_statistics(self, indexes: List[Any]) -> Dict[str, Any]:
        numeric_values: List[float] = []
        seen_values = set()
        selected_count = 0
        numeric_count = 0
        blank_count = 0
        for proxy_index in indexes:
            try:
                if not proxy_index.isValid():
                    continue
                if proxy_index.column() < self._pivot_data_column_offset:
                    continue
                selected_count += 1
                raw_value = proxy_index.data(Qt.DisplayRole)
                if raw_value is None or str(raw_value).strip() == "":
                    blank_count += 1
                    continue
                seen_values.add(str(raw_value))
                numeric_value = self._coerce_numeric_summary_value(raw_value)
                if numeric_value is not None:
                    numeric_values.append(numeric_value)
                    numeric_count += 1
            except Exception:
                continue

        if numeric_values:
            series = pd.Series(numeric_values, dtype="float64")
            total_sum = float(series.sum())
            mean_value = float(series.mean())
            min_value = float(series.min())
            max_value = float(series.max())
            median_value = float(series.median())
            unique_count = int(series.nunique(dropna=True))
        else:
            total_sum = float("nan")
            mean_value = float("nan")
            min_value = float("nan")
            max_value = float("nan")
            median_value = float("nan")
            unique_count = 0

        return {
            "selected_count": selected_count,
            "numeric_count": numeric_count,
            "blank_count": blank_count,
            "sum": total_sum,
            "mean": mean_value,
            "min": min_value,
            "max": max_value,
            "median": median_value,
            "unique_count": unique_count,
            "distinct_text_count": len(seen_values),
        }

    def _open_table_context_menu(self, pos):
        menu = QMenu(self)
        copy_action = menu.addAction(_rt("Copiar seleção"))
        copy_headers_action = menu.addAction(_rt("Copiar seleção com cabeçalhos"))
        copy_stats_action = menu.addAction(_rt("Copiar estatísticas"))
        selected = self.table_view.selectionModel()
        if selected is None or not selected.selectedIndexes():
            copy_action.setEnabled(False)
            copy_headers_action.setEnabled(False)
            copy_stats_action.setEnabled(False)

        action = menu.exec_(self.table_view.viewport().mapToGlobal(pos))
        if action == copy_action:
            self._copy_selected_cells_to_clipboard(include_headers=False)
        elif action == copy_headers_action:
            self._copy_selected_cells_to_clipboard(include_headers=True)
        elif action == copy_stats_action:
            self._copy_selection_statistics_to_clipboard()

    def _copy_selected_cells_to_clipboard(self, include_headers: bool = False):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return

        indexes = [
            index
            for index in selection_model.selectedIndexes()
            if index.isValid() and index.column() >= self._pivot_data_column_offset
        ]
        if not indexes:
            return

        rows = sorted({index.row() for index in indexes})
        columns = sorted({index.column() for index in indexes})
        grid: Dict[Tuple[int, int], str] = {}
        for index in indexes:
            value = index.data(Qt.DisplayRole)
            grid[(index.row(), index.column())] = "" if value is None else str(value)

        lines: List[str] = []
        if include_headers:
            header_values = []
            for column in columns:
                header = self.proxy_model.headerData(column, Qt.Horizontal, Qt.DisplayRole)
                header_values.append("" if header is None else str(header))
            lines.append("\t".join(header_values))

        for row in rows:
            row_values = [grid.get((row, column), "") for column in columns]
            lines.append("\t".join(row_values))

        QApplication.clipboard().setText("\n".join(lines))
        if hasattr(self, "selection_summary_label"):
            self.selection_summary_label.setText(
                _rt("Seleção copiada para a área de transferência.")
            )

    def _copy_selection_statistics_to_clipboard(self):
        selection_model = self.table_view.selectionModel()
        if selection_model is None:
            return
        stats = self._collect_selection_statistics(list(selection_model.selectedIndexes() or []))
        if stats["selected_count"] == 0:
            return

        lines = [
            _rt("Selecionadas: {value}", value=stats["selected_count"]),
            _rt("Numericas: {value}", value=stats["numeric_count"]),
        ]
        if stats["blank_count"]:
            lines.append(_rt("Vazias: {value}", value=stats["blank_count"]))
        if stats["numeric_count"] > 0:
            lines.extend(
                [
                    _rt("Soma: {value}", value=self._format_selection_number(stats["sum"])),
                    _rt("Media: {value}", value=self._format_selection_number(stats["mean"])),
                    _rt("Min: {value}", value=self._format_selection_number(stats["min"])),
                    _rt("Max: {value}", value=self._format_selection_number(stats["max"])),
                    _rt("Mediana: {value}", value=self._format_selection_number(stats["median"])),
                ]
            )
        QApplication.clipboard().setText(" | ".join(lines))
        if hasattr(self, "selection_summary_label"):
            self.selection_summary_label.setText(
                _rt("Estatísticas da seleção copiadas.")
            )

    def _format_selection_number(self, value: float) -> str:
        try:
            numeric = float(value)
        except Exception:
            return "-"
        if pd.isna(numeric):
            return "-"
        if abs(numeric - round(numeric)) < 1e-9:
            return f"{int(round(numeric)):,}"
        return f"{numeric:,.2f}"

    def _coerce_numeric_summary_value(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(" ", "")
        if re.match(r"^-?\d+(?:\.\d+)?$", text):
            try:
                return float(text)
            except Exception:
                return None
        if re.match(r"^-?(?:\d{1,3}(?:,\d{3})+)(?:\.\d+)?$", text):
            try:
                return float(text.replace(",", ""))
            except Exception:
                return None
        if re.match(r"^-?(?:\d{1,3}(?:\.\d{3})+)(?:,\d+)?$", text):
            try:
                return float(text.replace(".", "").replace(",", "."))
            except Exception:
                return None
        if "," in text and "." in text:
            cleaned = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
            try:
                return float(cleaned)
            except Exception:
                return None
        if "," in text:
            cleaned = text.replace(",", ".") if (text.count(",") == 1 and len(text.split(",")[-1]) <= 2) else text.replace(",", "")
            try:
                return float(cleaned)
            except Exception:
                return None
        if "." in text:
            if text.count(".") == 1 and len(text.split(".")[-1]) <= 2:
                try:
                    return float(text)
                except Exception:
                    return None
            try:
                return float(text.replace(".", ""))
            except Exception:
                return None
        try:
            return float(text)
        except Exception:
            return None

    def _feature_ids_for_proxy_index(self, proxy_index, source_index=None) -> List[int]:
        payload = proxy_index.data(Qt.UserRole)
        if isinstance(payload, str) and payload.strip():
            ids = [int(part) for part in payload.split(",") if part.strip().isdigit()]
            if ids:
                return ids
        if isinstance(payload, (list, tuple)):
            ids = [int(part) for part in payload if str(part).strip().isdigit()]
            if ids:
                return ids
        if source_index is not None and self._current_pivot_result is not None:
            row_index = source_index.row()
            column_index = source_index.column() - self._pivot_data_column_offset
            if row_index >= 0 and column_index >= 0 and row_index < len(self._current_pivot_result.matrix):
                row_cells = self._current_pivot_result.matrix[row_index]
                if column_index < len(row_cells):
                    cell = row_cells[column_index]
                    feature_ids = getattr(cell, "feature_ids", []) or []
                    return [int(fid) for fid in feature_ids if str(fid).strip().isdigit() or isinstance(fid, int)]
        return []

    def _apply_theming_tokens(self):
        try:
            base_font = ui_font()
            base_font.setPixelSize(int(TYPOGRAPHY.get("font_body_px", 13)))
            base_font.setWeight(QFont.Normal)
            self.table_view.setFont(base_font)
            header_font = ui_font()
            header_font.setPixelSize(int(TYPOGRAPHY.get("font_secondary_px", 12)))
            header_font.setWeight(QFont.Medium)
            self.table_view.horizontalHeader().setFont(header_font)
            dark_mode = str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower() == "dark"
            table_base = QColor("#0B1020" if dark_mode else "#ffffff")
            table_alternate = QColor("#0F172A" if dark_mode else "#fcfcfd")
            table_text = QColor("#F8FAFC" if dark_mode else "#111827")
            table_palette = self.table_view.palette()
            table_palette.setColor(QPalette.Base, table_base)
            table_palette.setColor(QPalette.AlternateBase, table_alternate)
            table_palette.setColor(QPalette.Window, table_base)
            table_palette.setColor(QPalette.Text, table_text)
            table_palette.setColor(QPalette.WindowText, table_text)
            self.table_view.setPalette(table_palette)
            self.table_view.setAutoFillBackground(True)
            viewport = self.table_view.viewport()
            if viewport is not None:
                viewport.setPalette(table_palette)
                viewport.setAutoFillBackground(True)
                viewport.setBackgroundRole(QPalette.Base)
            self.table_view.setAlternatingRowColors(True)
            self.table_view.verticalHeader().setDefaultSectionSize(30)
            self.table_view.horizontalHeader().setMinimumHeight(34)
        except Exception:
            log_exception("falha opcional ignorada")
        self._apply_table_preferences()
        harmonize_widget_fonts(self)

    def _apply_table_preferences(self):
        table = getattr(self, "table_view", None)
        if table is None:
            return
        try:
            row_height = int(getattr(self, "_table_row_height", 30) or 30)
        except Exception:
            row_height = 30
        row_height = max(24, min(52, row_height))
        try:
            table.setAlternatingRowColors(bool(getattr(self, "_table_alternating_rows", True)))
            table.verticalHeader().setDefaultSectionSize(row_height)
            header_height = 30 if bool(getattr(self, "_table_header_compact", True)) else 38
            table.horizontalHeader().setMinimumHeight(header_height)
            table.horizontalHeader().setDefaultSectionSize(max(96, int(table.horizontalHeader().defaultSectionSize() or 96)))
            table.viewport().update()
        except Exception:
            log_exception("falha opcional ignorada")

    def _set_last_active_area(self, area: str):
        _pivot_set_last_active_area(self, area)

    def _refresh_active_area_styles(self):
        _pivot_refresh_active_area_styles(self)

    def _desired_fields_panel_width(self) -> int:
        return _pivot_desired_fields_panel_width(
            self,
            tools_fields_default_width=_TOOLS_FIELDS_DEFAULT_WIDTH,
            tools_fields_min_width=_TOOLS_FIELDS_MIN_WIDTH,
            tools_fields_max_width=_TOOLS_FIELDS_MAX_WIDTH,
        )

    def _sync_fields_panel_width_to_content(self):
        _pivot_sync_fields_panel_width_to_content(
            self,
            tools_panel_collapsed_width=_TOOLS_PANEL_COLLAPSED_WIDTH,
            tools_fields_default_width=_TOOLS_FIELDS_DEFAULT_WIDTH,
            tools_fields_min_width=_TOOLS_FIELDS_MIN_WIDTH,
            tools_fields_max_width=_TOOLS_FIELDS_MAX_WIDTH,
            tools_filters_min_width=_TOOLS_FILTERS_MIN_WIDTH,
            tools_filters_default_width=_TOOLS_FILTERS_DEFAULT_WIDTH,
        )

    def _placeholder_item(self) -> QListWidgetItem:
        return _pivot_placeholder_item(_rt)

    def _refresh_area_placeholder(self, area: str):
        list_widget = self._area_list(area)
        real_items_present = False
        for index in reversed(range(list_widget.count())):
            if list_widget.item(index).data(Qt.UserRole) == "__placeholder__":
                list_widget.takeItem(index)
            else:
                real_items_present = True
        if not real_items_present:
            list_widget.addItem(self._placeholder_item())
            list_widget.setCurrentRow(0)

    def _sync_area_placeholder(self, area: Optional[str] = None):
        names = (area,) if area else ("filter", "row", "column", "value")
        for name in names:
            self._refresh_area_placeholder(name)
            self._refresh_area_item_widgets(name)

    def _sync_value_area_from_combo(self):
        if not hasattr(self, "value_fields_list"):
            return
        self.value_fields_list.clear()
        spec = self._field_spec_from_key(self.value_field_combo.currentData())
        if spec is not None:
            item = QListWidgetItem(spec.display_name)
            item.setData(Qt.UserRole, self._register_field_spec(spec))
            self.value_fields_list.addItem(item)
            self.value_fields_list.setCurrentItem(item)
        self._sync_area_placeholder("value")

    def _resolve_current_layer(self):
        metadata = dict(self._current_metadata or {})
        layer_id = metadata.get("layer_id") or ""
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is not None:
                return layer
        layer_name = metadata.get("layer_name") or ""
        if layer_name:
            matches = QgsProject.instance().mapLayersByName(layer_name)
            if matches:
                return matches[0]
        return None

    def _register_field_spec(self, field_spec: PivotFieldSpec) -> str:
        key = f"{field_spec.source_type}:{field_spec.field_name}:{field_spec.geometry_op or ''}"
        self._field_specs_by_key[key] = field_spec
        return key

    def _field_spec_from_key(self, spec_key: Optional[str]) -> Optional[PivotFieldSpec]:
        if not spec_key:
            return None
        return self._field_specs_by_key.get(spec_key)

    def _field_name_from_key(self, spec_key: Optional[str]) -> Optional[str]:
        field_spec = self._field_spec_from_key(spec_key)
        if field_spec is None or field_spec.source_type != "attribute":
            return None
        return field_spec.field_name

    def _area_combo(self, area: str) -> QComboBox:
        return _pivot_area_combo(self, area)

    def _area_list(self, area: str) -> QListWidget:
        return _pivot_area_list(self, area)

    def _area_label(self, area: str) -> str:
        return _pivot_area_label(area, _rt)

    def _selected_area_specs(self, area: str) -> List[PivotFieldSpec]:
        return _pivot_selected_area_specs(self, area)

    def _add_selected_field_to_area(self, area: str, auto_refresh: bool = True):
        return _pivot_add_selected_field_to_area(self, area, auto_refresh)

    def _add_field_to_area(self, area: str, field_spec: Optional[PivotFieldSpec], auto_refresh: bool = True):
        return _pivot_add_field_to_area(self, area, field_spec, auto_refresh=auto_refresh)

    def _remove_selected_area_field(self, area: str):
        _pivot_remove_selected_area_field(self, area)

    def _remove_area_field_by_key(self, area: str, spec_key: str):
        _pivot_remove_area_field_by_key(self, area, spec_key)

    def _take_area_field_by_key(self, area: str, spec_key: str):
        return _pivot_take_area_field_by_key(self, area, spec_key)

    def _move_selected_area_field(self, area: str, offset: int):
        _pivot_move_selected_area_field(self, area, offset)

    def _clear_area(self, area: str):
        _pivot_clear_area(self, area)

    def _ensure_default_row_area(self):
        if self.row_fields_list.count() > 0:
            return
        if self.raw_df is None or self.raw_df.empty:
            return
        candidate = next(
            (column for column in self.raw_df.columns if not self._is_numeric_column(self.raw_df[column])),
            self.raw_df.columns[0],
        )
        spec_key = None
        for index in range(self.row_field_combo.count()):
            spec = self._field_spec_from_key(self.row_field_combo.itemData(index))
            if spec is not None and spec.field_name == candidate:
                spec_key = self.row_field_combo.itemData(index)
                break
        self._add_field_to_area("row", self._field_spec_from_key(spec_key), auto_refresh=False)

    def _show_inline_message(self, message: str, level: str = "info"):
        self.status_label.setText(message)

    def _build_pivot_request(self, layer) -> PivotRequest:
        row_fields = self._selected_area_specs("row")
        column_fields = self._selected_area_specs("column")
        value_field = self._value_field_for_current_aggregation()
        aggregation = str(self.agg_combo.currentData() or "count")
        request = PivotRequest(
            layer_id=layer.id(),
            filter_expression=str((self._current_metadata or {}).get("filter_expression") or ""),
            row_fields=row_fields,
            column_fields=column_fields,
            value_field=value_field,
            aggregation=aggregation,
            only_selected=self.only_selected_check.isChecked(),
            include_nulls=self.include_nulls_check.isChecked(),
            include_percentages=True,
            include_totals=True,
        )
        return request

    def _value_field_for_current_aggregation(self) -> Optional[PivotFieldSpec]:
        aggregation = str(self.agg_combo.currentData() or "count")
        if aggregation == "count":
            return None
        if self.value_field_combo.currentData():
            spec = self._field_spec_from_key(self.value_field_combo.currentData())
            if spec is not None:
                return spec
        for candidate in self.numeric_candidates:
            if self._is_identifier_like_field(candidate):
                continue
            for index in range(self.value_field_combo.count()):
                spec = self._field_spec_from_key(self.value_field_combo.itemData(index))
                if spec is not None and spec.field_name == candidate:
                    spec = self._field_spec_from_key(self.value_field_combo.itemData(index))
                    if spec is not None:
                        return spec
        for index in range(self.value_field_combo.count()):
            spec = self._field_spec_from_key(self.value_field_combo.itemData(index))
            if spec is not None and spec.source_type in {"attribute", "geometry"}:
                return spec
        return None

    def _pivot_result_to_dataframe(self, result) -> pd.DataFrame:
        if result is None:
            return pd.DataFrame()
        metadata = dict(result.metadata or {})
        row_fields = list(metadata.get("row_fields") or [])
        row_depth = max(len(row_fields), max((len(key) for key in result.row_headers), default=0), 1)
        headers = []
        for index in range(row_depth):
            if index < len(row_fields):
                headers.append(str(row_fields[index]))
            elif row_depth == 1:
                headers.append("Linha")
            else:
                headers.append(f"Linha {index + 1}")

        records = []
        for row_index, row_key in enumerate(result.row_headers or [()]):
            record = {}
            row_values = list(row_key)
            while len(row_values) < row_depth:
                row_values.append("")
            for header, value in zip(headers, row_values[:row_depth]):
                record[header] = value
            for column_index, column_key in enumerate(result.column_headers or [()]):
                column_label = self._format_header_tuple(column_key)
                cell = (
                    result.matrix[row_index][column_index]
                    if row_index < len(result.matrix) and column_index < len(result.matrix[row_index])
                    else None
                )
                record[column_label] = getattr(cell, "raw_value", None)
            if result.row_totals:
                record["Total"] = result.row_totals.get(row_key)
            records.append(record)
        return pd.DataFrame(records)

    def _aggregate_series(self, series: pd.Series, agg_func: str):
        return _pivot_aggregate_series(series, agg_func, include_nulls=self.include_nulls_check.isChecked())

    def _pandas_aggfunc_name(self, agg_func: str) -> str:
        return _pivot_pandas_aggfunc_name(agg_func)

    def _map_variant_to_data_type(self, variant_type: int) -> str:
        if variant_type in {
            QVariant.Int,
            QVariant.UInt,
            QVariant.LongLong,
            QVariant.ULongLong,
            QVariant.Double,
        }:
            return "numeric"
        if variant_type in {QVariant.Date, QVariant.DateTime, QVariant.Time}:
            return "date"
        if variant_type == QVariant.Bool:
            return "bool"
        return "text"

    def _format_header_tuple(self, values: tuple) -> str:
        return _pivot_format_header_tuple(values)

    def _flatten_pandas_columns(self, df: pd.DataFrame, synthetic_row: bool = False) -> pd.DataFrame:
        return _pivot_flatten_pandas_columns(df, synthetic_row=synthetic_row)

    # ------------------------------------------------------------------ Public API
    def get_visible_pivot_dataframe(self) -> pd.DataFrame:
        return _pivot_get_visible_pivot_dataframe(self)

    def get_current_configuration(self) -> Dict[str, Any]:
        return _pivot_get_current_configuration(self)

    def get_summary_metadata(self) -> Dict[str, str]:
        return _pivot_get_summary_metadata(self)

    def get_current_pivot_result(self):
        return _pivot_get_current_pivot_result(self)

    def set_auto_update_checkbox(self, checkbox: QCheckBox):
        """
        Place an external auto-update checkbox inside the toolbar,
        wiring it to reuse the widget for refresh gating.
        """
        if checkbox is None:
            return

        if checkbox.parent() is not self:
            checkbox.setParent(self)

        if self.toolbar_strip_layout is not None:
            if self._external_auto_checkbox is not None:
                self.toolbar_strip_layout.removeWidget(self._external_auto_checkbox)
                self._external_auto_checkbox.setVisible(False)
            checkbox.setObjectName("summaryAutoUpdateCheck")
            checkbox.setMinimumHeight(28)
            checkbox.setContentsMargins(0, 0, 0, 0)
            check_font = ui_font()
            check_font.setPixelSize(int(TYPOGRAPHY.get("font_secondary_px", 12)))
            check_font.setWeight(QFont.Normal)
            checkbox.setFont(check_font)
            self.toolbar_strip_layout.addSpacing(10)
            self.toolbar_strip_layout.addWidget(checkbox)
            checkbox.setVisible(True)
        self.auto_update_check = checkbox
        self._external_auto_checkbox = checkbox
        harmonize_widget_fonts(checkbox)
        self._refresh_toolbar_chrome()

    def add_dashboard_button(self, button: QPushButton):
        """Insert the dashboard trigger into the icon toolbar."""
        if button is None or self.toolbar_strip_layout is None:
            return

        if button.parent() is not self:
            button.setParent(self)
        button.setObjectName("summaryToolbarButton")
        button.setProperty("toolbarMode", "icon")
        button.setProperty("iconOnly", True)
        button.setFixedSize(30, 30)
        target_index = self.toolbar_strip_layout.indexOf(self.edit_mode_btn)
        insert_index = target_index if target_index != -1 else self.toolbar_strip_layout.count()
        self.toolbar_strip_layout.insertWidget(insert_index, button)
        button.setVisible(True)
        self._external_dashboard_button = button
        self._refresh_toolbar_chrome()

    def clear_all_filters(self):
        """Expose filter reset so external buttons can reuse it."""
        self._clear_filters()

    def show_empty_message(self, title: str, text: str):
        self.raw_df = pd.DataFrame()
        self.filtered_df = pd.DataFrame()
        self.pivot_df = pd.DataFrame()
        self._current_summary_data = {}
        self._current_metadata = {}
        self._current_pivot_request = None
        self._current_pivot_result = None
        self.meta_label.setText("")
        self.status_label.setText("")
        self.selection_summary_label.setText(_rt("Selecione células para ver soma e contagem."))
        self.empty_state_title.setText(title)
        self.empty_state_text.setText(text)
        self.fields_list.clear()
        self.row_fields_list.clear()
        self.column_fields_list.clear()
        self.filter_fields_list.clear()
        self.value_fields_list.clear()
        self._sync_area_placeholder()
        for combo in (
            self.filter_field_combo,
            self.column_field_combo,
            self.row_field_combo,
            self.value_field_combo,
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_rt("(Nenhum)"), None)
            combo.blockSignals(False)
        self.agg_combo.blockSignals(True)
        count_index = self.agg_combo.findData("count")
        if count_index != -1:
            self.agg_combo.setCurrentIndex(count_index)
        self.agg_combo.blockSignals(False)
        self.advanced_group.blockSignals(True)
        self.advanced_group.setChecked(False)
        self.advanced_group.blockSignals(False)
        self.table_model = QStandardItemModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.table_view.setModel(self.proxy_model)
        self._apply_table_preferences()
        self.table_stack.setCurrentWidget(self.empty_state_frame)
        self.initial_state_title.setText(title)
        self.initial_state_text.setText(text)
        self._sync_value_area_from_combo()
        self._update_context_summary()
        self._reset_history_state()
        self._set_content_mode(False)
        self._apply_runtime_i18n()

    # ------------------------------------------------------------------ Helpers
    def _is_identifier_like_field(self, field_name: str) -> bool:
        normalized = (field_name or "").strip().lower()
        return normalized in {"fid", "id", "gid", "objectid", "object_id", "ogc_fid"}

    def _is_numeric_column(self, series: pd.Series) -> bool:
        if ptypes.is_numeric_dtype(series):
            return True
        converted = pd.to_numeric(series, errors="coerce")
        return converted.notna().any()

    # ------------------------------------------------------------------ Export
    def _build_export_pivot_dataframe(self) -> pd.DataFrame:
        if self.proxy_model is None or self.table_view is None:
            return self.get_visible_pivot_dataframe()

        column_indexes = [
            column
            for column in range(self.proxy_model.columnCount())
            if not self.table_view.isColumnHidden(column)
        ]
        if not column_indexes:
            return self.get_visible_pivot_dataframe()

        headers = [
            str(self.proxy_model.headerData(column, Qt.Horizontal) or f"Coluna {column + 1}")
            for column in column_indexes
        ]
        rows: List[List[Any]] = []
        for row in range(self.proxy_model.rowCount()):
            row_values: List[Any] = []
            for column in column_indexes:
                index = self.proxy_model.index(row, column)
                value = self.proxy_model.data(index, Qt.DisplayRole) if index.isValid() else None
                row_values.append("" if value is None else value)
            rows.append(row_values)
        return pd.DataFrame(rows, columns=headers)

    def _normalize_field_token(self, value: Any) -> str:
        return _pivot_normalize_field_token(value)

    def _resolve_available_field_name(
        self,
        field_name: Any,
        available_fields: List[str],
        fallback_candidates: Optional[List[Any]] = None,
    ) -> str:
        return _pivot_resolve_available_field_name(field_name, available_fields, fallback_candidates=fallback_candidates)

    def _resolve_layer_field_name(
        self,
        layer,
        field_name: Any,
        fallback_candidates: Optional[List[Any]] = None,
    ) -> str:
        return _pivot_resolve_layer_field_name(layer, field_name, fallback_candidates=fallback_candidates)

    def _build_layer_dataframe_from_request(
        self,
        layer,
        request: PivotRequest,
        extra_attribute_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        return _pivot_build_layer_dataframe_from_request(
            self,
            layer,
            request,
            extra_attribute_fields=extra_attribute_fields,
        )

    def _build_layer_dataframe_from_pivot_config(
        self,
        layer,
        pivot_config: Dict[str, Any],
    ) -> pd.DataFrame:
        return _pivot_build_layer_dataframe_from_pivot_config(
            self,
            layer,
            pivot_config,
        )

    def _build_export_layer_dataframe(self, pivot_config: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        return _pivot_build_export_layer_dataframe(self, pivot_config)

    def _export_to_excel_with_layer_data(
        self,
        file_path: str,
        pivot_df: pd.DataFrame,
        layer_df: pd.DataFrame,
        pivot_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        if pivot_config is None:
            export_dataframes_to_excel(
                pivot_df,
                layer_df,
                PivotExportSpec(
                    file_path=file_path,
                    pivot_sheet_name="Tabela_Dinamica",
                    data_sheet_name="Dados_Camada",
                    sheet_name="Tabela_Dinamica",
                ),
            )
            return ""
        export_dataframes_to_excel(
            pivot_df,
            layer_df,
            PivotExportSpec(
                file_path=file_path,
                pivot_sheet_name="Tabela_Dinamica",
                data_sheet_name="Dados_Camada",
                sheet_name="Tabela_Dinamica",
                aggregation=str(pivot_config.get("aggregation") or "count"),
                value_field=str(pivot_config.get("value_field") or ""),
                value_label=str(pivot_config.get("value_label") or ""),
                row_fields=list(pivot_config.get("row_fields") or []),
                column_fields=list(pivot_config.get("column_fields") or []),
                filter_fields=list(pivot_config.get("filter_fields") or []),
                metadata=dict(pivot_config or {}),
            ),
        )
        _, note = self._try_create_native_excel_pivot(file_path, layer_df, pivot_config)
        return note

    def _try_create_native_excel_pivot(
        self,
        file_path: str,
        layer_df: pd.DataFrame,
        pivot_config: Dict[str, Any],
    ) -> Tuple[bool, str]:
        return _pivot_try_create_native_excel_pivot(
            file_path,
            layer_df,
            pivot_config,
            translate=_rt,
            resolve_available_field_name=self._resolve_available_field_name,
        )

    def _export_pivot_table(self):
        _pivot_export_pivot_table(self)

    def _export_to_gpkg(self, path: str):
        _pivot_export_to_gpkg(self, path)

