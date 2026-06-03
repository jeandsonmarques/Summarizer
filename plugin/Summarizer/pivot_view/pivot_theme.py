# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

# ruff: noqa: E501
# QSS is copied literally from pivot_table_widget.py in this first extraction.

from __future__ import annotations

from qgis.PyQt.QtCore import QSettings, QSize
from qgis.PyQt.QtGui import QColor, QIcon, QPalette
from qgis.PyQt.QtWidgets import QLineEdit

from ..palette import TYPOGRAPHY
from ..utils.logging_utils import log_exception
from ..utils.resources import svg_icon

INK_COLOR = "#252B33"


def is_dark_theme() -> bool:
    theme_name = str(QSettings().value("Summarizer/uiTheme", "light") or "light").strip().lower()
    return theme_name == "dark"


def refresh_toolbar_chrome(widget, *, icon_factory, toolbar_icons, translate) -> None:
    self = widget
    _svg_icon_from_template = icon_factory
    _TOOLBAR_SVG_ICONS = toolbar_icons
    _rt = translate

    dark_mode = is_dark_theme()
    icon_size = QSize(18, 18)
    icon_normal = "#E5E7EB" if dark_mode else INK_COLOR
    icon_active = "#FFFFFF" if dark_mode else INK_COLOR
    icon_disabled = "#94A3B8" if dark_mode else "#C7CDD6"
    mono_icon_colors = {
        QIcon.Normal: icon_normal,
        QIcon.Active: icon_active,
        QIcon.Selected: icon_active,
        QIcon.Disabled: icon_disabled,
    }
    search_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["search"], size=18, color_map=mono_icon_colors)
    clear_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["clear"], size=18, color_map=mono_icon_colors)
    undo_icon = svg_icon("Walker-Undo.svg")
    redo_icon = svg_icon("Walker-Redo.svg")
    dashboard_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["dashboard"], size=18, color_map=mono_icon_colors)
    edit_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_edit"], size=18, color_map=mono_icon_colors)
    sheet_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_sheet"], size=18, color_map=mono_icon_colors)
    image_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_image"], size=18, color_map=mono_icon_colors)
    settings_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_settings"], size=18, color_map=mono_icon_colors)
    panel_field_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["fields"], size=14, color_map=mono_icon_colors)
    panel_filter_icon = _svg_icon_from_template(_TOOLBAR_SVG_ICONS["filter_panel"], size=14, color_map=mono_icon_colors)
    if hasattr(self, "toolbar_strip") and self.toolbar_strip is not None:
        if dark_mode:
            toolbar_style = """
            QFrame#summaryToolbarStrip {
                background: transparent;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QFrame#summaryToolbarSeparator {
                min-width: 1px;
                max-width: 1px;
                margin: 4px 6px;
                background: rgba(148, 163, 184, 0.22);
                border: none;
            }
            QPushButton#summaryToolbarButton {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
                color: #E5E7EB;
                background: transparent;
                border: none;
                border-radius: 6px;
                text-align: center;
            }
            QPushButton#summaryToolbarButton:hover {
                background: #1F2A3D;
                color: #FFFFFF;
            }
            QPushButton#summaryToolbarButton:checked,
            QPushButton#summaryToolbarButton:pressed {
                background: #312E81;
                color: #FFFFFF;
            }
            QPushButton#summaryToolbarButton:disabled {
                color: #94A3B8;
            }
            QPushButton[variant="secondary"] {
                background: #172033;
                border: 1px solid #334155;
                color: #E5E7EB;
                border-radius: 8px;
                padding: 0 12px;
                min-height: 28px;
            }
            QPushButton[variant="secondary"]:hover {
                background: #1F2A3D;
                border-color: #475569;
                color: #FFFFFF;
            }
            QLineEdit#summarySearch {
                min-height: 28px;
                padding: 0 9px;
                color: #F8FAFC;
                background: #111827;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 400;
                selection-background-color: #1E293B;
                selection-color: #F8FAFC;
            }
            QLineEdit#summarySearch:hover,
            QLineEdit#summarySearch:focus {
                background: #111827;
                border: 1px solid #475569;
            }
            """
        else:
            toolbar_style = """
            QFrame#summaryToolbarStrip {
                background: #FFFFFF;
                border: 1px solid #D6D9E0;
                border-radius: 8px;
            }
            QFrame#summaryToolbarSeparator {
                min-width: 1px;
                max-width: 1px;
                margin: 4px 6px;
                background: #E5E7EB;
                border: none;
            }
            QPushButton#summaryToolbarButton {
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
                color: #111827;
                background: transparent;
                border: none;
                border-radius: 6px;
                text-align: center;
            }
            QPushButton#summaryToolbarButton:hover {
                background: #F3F4F6;
            }
            QPushButton#summaryToolbarButton:checked,
            QPushButton#summaryToolbarButton:pressed {
                background: #E5E7EB;
                color: #111827;
            }
            QPushButton#summaryToolbarButton:disabled {
                color: #C7CDD6;
            }
            QPushButton[variant="secondary"] {
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                color: #111827;
                border-radius: 8px;
                padding: 0 12px;
                min-height: 28px;
            }
            QPushButton[variant="secondary"]:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
            QLineEdit#summarySearch {
                min-height: 28px;
                padding: 0 9px;
                color: #4b5563;
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 400;
            }
            QLineEdit#summarySearch:hover,
            QLineEdit#summarySearch:focus {
                background: #FFFFFF;
                border: 1px solid #9CA3AF;
            }
            """
        self.toolbar_strip.setStyleSheet(toolbar_style)

    if hasattr(self, "search_input") and self.search_input is not None:
        if getattr(self, "_search_icon_action", None) is None:
            self._search_icon_action = self.search_input.addAction(
                search_icon,
                QLineEdit.LeadingPosition,
            )
        else:
            self._search_icon_action.setIcon(search_icon)
        self.search_input.setPlaceholderText(_rt("Buscar"))
        self.search_input.setToolTip(_rt("Pesquisar na tabela"))

    if hasattr(self, "clear_filters_btn") and self.clear_filters_btn is not None:
        self._configure_toolbar_button(self.clear_filters_btn)
        self.clear_filters_btn.setToolTip(_rt("Limpar busca"))
        self.clear_filters_btn.setIcon(clear_icon)
        self.clear_filters_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.clear_filters_btn)

    if hasattr(self, "export_btn") and self.export_btn is not None:
        self._configure_toolbar_button(self.export_btn)
        self.export_btn.setToolTip(_rt("Exportar"))
        self.export_btn.setIcon(image_icon)
        self.export_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.export_btn)

    if hasattr(self, "undo_btn") and self.undo_btn is not None:
        self.undo_btn.setToolTip(_rt("Desfazer (Ctrl+Z)"))
        self.undo_btn.setIcon(undo_icon)
        self.undo_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.undo_btn)

    if hasattr(self, "redo_btn") and self.redo_btn is not None:
        self.redo_btn.setToolTip(_rt("Refazer (Ctrl+Shift+Z)"))
        self.redo_btn.setIcon(redo_icon)
        self.redo_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.redo_btn)

    if hasattr(self, "import_sheet_btn") and self.import_sheet_btn is not None:
        self.import_sheet_btn.setToolTip(_rt("Importar planilha"))
        self.import_sheet_btn.setIcon(sheet_icon)
        self.import_sheet_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.import_sheet_btn)

    if hasattr(self, "sidebar_toggle_btn") and self.sidebar_toggle_btn is not None:
        collapsed = bool(getattr(self, "_tools_panels_hidden", False))
        self._configure_toolbar_button(self.sidebar_toggle_btn)
        self.sidebar_toggle_btn.setToolTip(
            _rt("Mostrar campos e filtros") if collapsed else _rt("Ocultar campos e filtros")
        )
        self.sidebar_toggle_btn.setIcon(edit_icon)
        self.sidebar_toggle_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.sidebar_toggle_btn)

    if hasattr(self, "settings_btn") and self.settings_btn is not None:
        self.settings_btn.setToolTip(_rt("Personalizar tabela"))
        self.settings_btn.setIcon(settings_icon)
        self.settings_btn.setIconSize(icon_size)
        self._polish_toolbar_button(self.settings_btn)

    if self._external_dashboard_button is not None:
        self._configure_toolbar_button(self._external_dashboard_button)
        self._external_dashboard_button.setObjectName("summaryToolbarButton")
        self._external_dashboard_button.setProperty("toolbarMode", "icon")
        self._external_dashboard_button.setProperty("iconOnly", True)
        self._external_dashboard_button.setProperty("toolbarPrimary", False)
        self._external_dashboard_button.setFixedSize(28, 28)
        self._external_dashboard_button.setText("")
        self._external_dashboard_button.setToolTip(_rt("Dashboard interativo"))
        self._external_dashboard_button.setIcon(dashboard_icon)
        self._external_dashboard_button.setIconSize(icon_size)
        self._polish_toolbar_button(self._external_dashboard_button)

    if self._external_auto_checkbox is not None:
        self._external_auto_checkbox.setText(_rt("Auto"))
        self._external_auto_checkbox.setToolTip(_rt("Atualização automática"))

    if hasattr(self, "fields_panel_icon"):
        self.fields_panel_icon.setPixmap(panel_field_icon.pixmap(14, 14))
    if hasattr(self, "filters_panel_icon"):
        self.filters_panel_icon.setPixmap(panel_filter_icon.pixmap(14, 14))
    if hasattr(self, "fields_panel_title"):
        self.fields_panel_title.setText(_rt("Campos"))
    if hasattr(self, "fields_panel_collapsed_title"):
        self.fields_panel_collapsed_title.setText(_rt("Campos"))
    if hasattr(self, "filter_area_title"):
        self.filter_area_title.setText(_rt("Filtros"))
    if hasattr(self, "filters_panel_collapsed_title"):
        self.filters_panel_collapsed_title.setText(_rt("Filtros"))
    self._apply_runtime_i18n()


def apply_styles(widget) -> None:
    self = widget
    dark_mode = is_dark_theme()
    tokens = {
        "__FONT_UI_STACK__": str(
            TYPOGRAPHY.get(
                "font_ui_stack",
                '"Inter", sans-serif',
            )
        ),
        "__FONT_PAGE_TITLE_PX__": str(int(TYPOGRAPHY.get("font_page_title_px", 24))),
        "__FONT_SECTION_TITLE_PX__": str(int(TYPOGRAPHY.get("font_section_title_px", 16))),
        "__FONT_BODY_PX__": str(int(TYPOGRAPHY.get("font_body_px", 13))),
        "__FONT_SECONDARY_PX__": str(int(TYPOGRAPHY.get("font_secondary_px", 12))),
        "__FONT_CAPTION_PX__": str(int(TYPOGRAPHY.get("font_caption_px", 11))),
        "__FONT_BUTTON_PX__": str(int(TYPOGRAPHY.get("font_button_px", 13))),
        "__FONT_WEIGHT_REGULAR__": str(int(TYPOGRAPHY.get("font_weight_regular", 400))),
        "__FONT_WEIGHT_MEDIUM__": str(int(TYPOGRAPHY.get("font_weight_medium", 500))),
        "__FONT_WEIGHT_SEMIBOLD__": str(int(TYPOGRAPHY.get("font_weight_semibold", 600))),
    }
    tokens["__TITLE_PX__"] = str(
        max(int(tokens["__FONT_BODY_PX__"]) + 2, int(tokens["__FONT_SECONDARY_PX__"]) + 3)
    )
    tokens["__WELCOME_TITLE_PX__"] = str(max(int(tokens["__FONT_PAGE_TITLE_PX__"]) + 8, 30))
    tokens["__WELCOME_SUBTITLE_PX__"] = str(max(int(tokens["__FONT_BODY_PX__"]) + 4, 16))
    qss = """
        QWidget#summaryPivotRoot {
            background: #ffffff;
            font-family: __FONT_UI_STACK__;
            font-size: __FONT_BODY_PX__px;
            color: #111827;
        }
        #summaryPivotRoot QWidget#summaryControlsZone,
        #summaryPivotRoot QWidget#summaryContextBar,
        #summaryPivotRoot QWidget#summaryToolbar {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryInitialState {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QWidget#summaryWelcomeWrap {
            background: transparent;
            border: none;
            min-width: 780px;
            max-width: 860px;
        }
        #summaryPivotRoot QLabel#summaryWelcomeTitle {
            color: #111827;
            font-size: __WELCOME_TITLE_PX__px;
            font-weight: __FONT_WEIGHT_SEMIBOLD__;
            letter-spacing: -0.42px;
        }
        #summaryPivotRoot QLabel#summaryWelcomeText {
            color: #475569;
            font-size: __WELCOME_SUBTITLE_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QFrame#summaryEntrySelectionHost {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QWidget#summarySourceCardsHost {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QToolButton#summarySourceCard {
            background: transparent;
            border: none;
            padding: 0;
            color: #111827;
            font-size: __FONT_BODY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
            min-height: 92px;
        }
        #summaryPivotRoot QToolButton#summarySourceCard:hover {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QToolButton#summarySourceCard:checked {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QToolButton#summarySourceCard:pressed {
            background: transparent;
        }
        #summaryPivotRoot QLabel#summarySourceCardBadge {
            background: #F2EEFF;
            color: #6E56CF;
            border: 1px solid rgba(139, 124, 246, 0.24);
            border-radius: 10px;
            padding: 2px 8px;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_SEMIBOLD__;
        }
        #summaryPivotRoot QFrame#summaryTableCard {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.09);
            border-radius: 5px;
        }
        #summaryPivotRoot QSplitter#summaryAnalyticsSplitter {
            background: transparent;
        }
        #summaryPivotRoot QSplitter#summaryMainSplitter {
            background: transparent;
        }
        #summaryPivotRoot QSplitter#summaryMainSplitter::handle {
            background: transparent;
            width: 6px;
            margin: 0;
        }
        #summaryPivotRoot QSplitter#summaryAnalyticsSplitter::handle {
            background: transparent;
            width: 6px;
            margin: 0;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel,
        #summaryPivotRoot QFrame#summaryFiltersPanel {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.055);
            border-radius: 2px;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel[collapsed="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel[collapsed="true"] {
            background: #fbfbfc;
        }
        #summaryPivotRoot QScrollArea#summaryFiltersScroll,
        #summaryPivotRoot QWidget#summaryFiltersViewport,
        #summaryPivotRoot QWidget#summaryFiltersBuilderContent {
            background: #ffffff;
            border: none;
        }
        #summaryPivotRoot QWidget#summaryPanelHeader {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QWidget#summaryPanelBody {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryPanelCollapsedRail {
            background: #fbfbfc;
            border: none;
        }
        #summaryPivotRoot QLabel#summaryPanelCollapsedTitle {
            color: #6b7280;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QToolButton#summaryPanelToggle {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 0px;
            color: #6b7280;
            font-size: 16px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QToolButton#summaryPanelToggle:hover {
            background: rgba(17, 24, 39, 0.045);
            border-color: rgba(17, 24, 39, 0.08);
            color: #111827;
        }
        #summaryPivotRoot QWidget#summaryFieldsContextCard {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QLabel#summaryPanelIcon {
            min-width: 14px;
            max-width: 14px;
            min-height: 14px;
            max-height: 14px;
        }
        #summaryPivotRoot QWidget#summaryFieldsContextCard QLabel#summaryContextLabel {
            color: #6b7280;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QWidget#summaryFieldsContextCard QLabel#summaryMetaLabel {
            color: #8b95a1;
            font-size: __FONT_CAPTION_PX__px;
        }
        #summaryPivotRoot QLabel#summaryPanelTitle {
            color: #4b5563;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
            padding: 0 0 1px 0;
        }
        #summaryPivotRoot QLabel#summaryPanelTitle[activeArea="true"] {
            color: #516074;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel {
            background: #f7f7f8;
            border: none;
            border-left: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 0px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel[collapsed="true"] {
            background: #f2f3f5;
        }
        #summaryPivotRoot QFrame#summarySidebarHeader,
        #summaryPivotRoot QFrame#summarySidebarFooter {
            background: rgba(247, 247, 248, 0.96);
            border: none;
        }
        #summaryPivotRoot QFrame#summarySidebarHeader {
            border-bottom: 1px solid rgba(17, 24, 39, 0.05);
        }
        #summaryPivotRoot QFrame#summarySidebarFooter {
            border-top: 1px solid rgba(17, 24, 39, 0.05);
        }
        #summaryPivotRoot QWidget#summaryBuilderContent {
            background: transparent;
        }
        #summaryPivotRoot QLabel#summaryContextLabel {
            color: #9aa3af;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QLabel#summarySidebarTitle {
            color: #111827;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QToolButton#summarySidebarToggle {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(17, 24, 39, 0.06);
            border-radius: 8px;
            padding: 0px;
            color: #6b7280;
        }
        #summaryPivotRoot QToolButton#summarySidebarToggle:hover {
            background: rgba(17, 24, 39, 0.04);
            border-color: rgba(17, 24, 39, 0.10);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel[collapsed="true"] QFrame#summarySidebarHeader {
            border-bottom: none;
            background: #f2f3f5;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel[collapsed="true"] QToolButton#summarySidebarToggle {
            background: rgba(255, 255, 255, 0.92);
            border-color: rgba(17, 24, 39, 0.10);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLabel#summarySectionTitle {
            color: #6b7280;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
            padding: 1px 0 2px 0;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLabel#summaryAxisTitle,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLabel#summaryAxisTitle {
            color: #374151;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
            padding: 0 0 1px 0;
        }
        #summaryPivotRoot QLabel#summaryMetaLabel,
        #summaryPivotRoot QLabel#summaryStatusLabel,
        #summaryPivotRoot QLabel#summarySelectionLabel,
        #summaryPivotRoot QLabel#summaryLayerPlaceholder,
        #summaryPivotRoot QLabel#summaryEmptyText {
            color: #6b7280;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QLabel#summaryMetaLabel {
            color: #a8b0bb;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLabel#summaryFieldLabel,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLabel#summaryFieldLabel {
            color: #6b7280;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QGroupBox#summaryAdvancedGroup,
        #summaryPivotRoot QGroupBox#summaryAdvancedGroup::title,
        #summaryPivotRoot QCheckBox#summaryAdvancedCheck,
        #summaryPivotRoot QComboBox#summaryOperationCombo {
            font-size: __FONT_SECONDARY_PX__px;
        }
        #summaryPivotRoot QLabel#summaryEmptyTitle {
            color: #111827;
            font-size: __TITLE_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QFrame#summaryLayerHost {
            background: transparent;
            border: none;
            padding: 0px;
        }
        #summaryPivotRoot QLineEdit#summarySearch,
        #summaryPivotRoot QComboBox#summaryLayerCombo {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.06);
            border-radius: 8px;
            padding: 0 9px;
            color: #111827;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QLineEdit#summarySearch,
        #summaryPivotRoot QComboBox#summaryLayerCombo {
            min-height: 28px;
        }
        #summaryPivotRoot QLineEdit#summarySearch {
            padding-right: 8px;
            padding-left: 8px;
            background: rgba(255, 255, 255, 0.92);
        }
        #summaryPivotRoot QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        #summaryPivotRoot QLineEdit#summarySearch:hover,
        #summaryPivotRoot QComboBox#summaryLayerCombo:hover {
            border-color: rgba(17, 24, 39, 0.10);
        }
        #summaryPivotRoot QLineEdit#summarySearch:focus,
        #summaryPivotRoot QComboBox#summaryLayerCombo:focus {
            border: 1px solid rgba(81, 96, 116, 0.55);
            background: #ffffff;
        }
        #summaryPivotRoot QPushButton#summaryPrimaryButton {
            background: #1f2937;
            color: #ffffff;
            border: 1px solid #111827;
            border-radius: 8px;
            padding: 0 14px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QFrame#summaryToolbarStrip {
            background: #FFFFFF;
            border: 1px solid #D6D9E0;
            border-radius: 8px;
        }
        #summaryPivotRoot QFrame#summaryToolbarSeparator {
            min-width: 1px;
            max-width: 1px;
            margin: 4px 6px;
            background: #E5E7EB;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton {
            background: transparent;
            color: #111827;
            border: none;
            border-radius: 6px;
            padding: 0 4px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
            text-align: left;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryToolbarButton {
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            padding: 0px;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryToolbarButton:checked {
            background: #E5E7EB;
            color: #111827;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryToolbarButton:disabled {
            color: #C7CDD6;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton:hover {
            background: #F3F4F6;
            color: #111827;
        }
        #summaryPivotRoot QWidget#summaryToolbar QLineEdit#summarySearch {
            min-height: 28px;
            padding: 0 9px;
            background: transparent;
            border: none;
            border-radius: 7px;
            color: #4b5563;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QWidget#summaryToolbar QLineEdit#summarySearch:hover,
        #summaryPivotRoot QWidget#summaryToolbar QLineEdit#summarySearch:focus {
            background: #F9FAFB;
            border: none;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryPrimaryButton[toolbarPrimary="true"] {
            background: transparent;
            color: #111827;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0 10px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
            text-align: left;
        }
        #summaryPivotRoot QPushButton#summaryPrimaryButton:hover {
            background: #111827;
            border-color: #0b1220;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryPrimaryButton[toolbarPrimary="true"]:hover {
            background: rgba(17, 24, 39, 0.045);
            border-color: rgba(17, 24, 39, 0.08);
            color: #111827;
        }
        #summaryPivotRoot QPushButton#summarySecondaryButton {
            background: transparent;
            color: #111827;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0 10px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
            text-align: left;
        }
        #summaryPivotRoot QPushButton#summaryBackButton {
            background: transparent;
            color: #111827;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0 10px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
            text-align: left;
        }
        #summaryPivotRoot QPushButton#summaryBackButton:hover {
            background: rgba(17, 24, 39, 0.045);
            border-color: rgba(17, 24, 39, 0.08);
        }
        #summaryPivotRoot QPushButton#summarySecondaryButton[iconOnly="true"] {
            padding: 0px;
            min-width: 28px;
            max-width: 28px;
        }
        #summaryPivotRoot QPushButton#summaryGhostButton {
            background: transparent;
            color: #4b5563;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0 10px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
            text-align: left;
        }
        #summaryPivotRoot QPushButton#summaryGhostButton:checked {
            background: rgba(17, 24, 39, 0.055);
            color: #1f2937;
            border: 1px solid rgba(17, 24, 39, 0.10);
        }
        #summaryPivotRoot QCheckBox#summaryAutoUpdateCheck,
        #summaryPivotRoot QCheckBox {
            color: #9aa3af;
            spacing: 5px;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QCheckBox#summaryAutoUpdateCheck {
            padding-left: 8px;
            background: transparent;
            border: none;
            border-radius: 0px;
            outline: none;
        }
        #summaryPivotRoot QCheckBox#summaryAutoUpdateCheck:hover,
        #summaryPivotRoot QCheckBox#summaryAutoUpdateCheck:focus {
            background: transparent;
            border: none;
            outline: none;
        }
        #summaryPivotRoot QCheckBox::indicator {
            width: 12px;
            height: 12px;
            border: 1px solid rgba(17, 24, 39, 0.20);
            border-radius: 3px;
            background: #ffffff;
        }
        #summaryPivotRoot QCheckBox::indicator:checked {
            background: #7b8798;
            border-color: #6b7280;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLabel#summaryAxisTitle[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QLabel#summaryAxisTitle[activeArea="true"] {
            color: #516074;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QWidget[sidebarSection="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QWidget[sidebarSection="true"] {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QWidget[filterSectionCard="true"] {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 2px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit#summaryFieldSearch,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox#summaryOperationCombo,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox#summaryOperationCombo,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLineEdit {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 2px;
            padding: 0 8px;
            color: #111827;
            min-height: 28px;
            selection-background-color: rgba(81, 96, 116, 0.14);
            selection-color: #111827;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit#summaryFieldSearch:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox#summaryOperationCombo:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox#summaryOperationCombo:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLineEdit:hover {
            background: #ffffff;
            border-color: rgba(17, 24, 39, 0.12);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit#summaryFieldSearch:focus,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox#summaryOperationCombo:focus,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox:focus,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit:focus,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox#summaryOperationCombo:focus,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox:focus,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLineEdit:focus {
            background: #ffffff;
            border-color: rgba(81, 96, 116, 0.48);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(17, 24, 39, 0.06);
            border-radius: 10px;
            padding: 5px;
            color: #111827;
            outline: 0;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget[activeArea="true"] {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(81, 96, 116, 0.32);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget::item,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item {
            padding: 8px 10px;
            margin: 1px 0;
            border-radius: 6px;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:hover {
            background: rgba(17, 24, 39, 0.035);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget::item:selected,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:selected {
            background: rgba(81, 96, 116, 0.12);
            color: #111827;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget#summaryFieldsList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryFilterList {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(17, 24, 39, 0.09);
            border-radius: 2px;
            padding: 2px;
            color: #111827;
            outline: 0;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList {
            background: rgba(255, 255, 255, 0.98);
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 2px;
            padding: 4px;
            outline: 0;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList::item,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList::item,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList::item {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList::item:selected,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList::item:selected,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList::item:selected {
            background: transparent;
            color: #111827;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList[activeArea="true"] {
            background: #ffffff;
            border-color: rgba(81, 96, 116, 0.22);
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryFilterList[activeArea="true"] {
            border-color: rgba(81, 96, 116, 0.28);
            background: #ffffff;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item {
            padding: 4px 6px;
            margin: 0;
            border-radius: 2px;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:hover {
            background: rgba(17, 24, 39, 0.035);
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item:selected,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:selected {
            background: rgba(81, 96, 116, 0.12);
            color: #111827;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 0;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::handle:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::handle:vertical {
            background: rgba(107, 114, 128, 0.28);
            border-radius: 5px;
            min-height: 24px;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::handle:vertical:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::handle:vertical:hover {
            background: rgba(107, 114, 128, 0.40);
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::add-line:vertical,
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::sub-line:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::add-line:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::sub-line:vertical {
            height: 0px;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::add-page:vertical,
        #summaryPivotRoot QFrame#summaryFieldsPanel QScrollBar::sub-page:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::add-page:vertical,
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar::sub-page:vertical {
            background: transparent;
        }
        #summaryPivotRoot QWidget#summaryAreaChip {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QWidget#summaryAreaChipRow {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryAreaChip {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.10);
            border-radius: 2px;
        }
        #summaryPivotRoot QLabel#summaryAreaChipText {
            color: #111827;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QToolButton#summaryAreaChipRemove {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 2px;
            padding: 0px;
        }
        #summaryPivotRoot QToolButton#summaryAreaChipRemove:hover {
            background: rgba(239, 68, 68, 0.08);
            border-color: rgba(239, 68, 68, 0.20);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 2px;
            margin-top: 8px;
            padding-top: 8px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup::title,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            background: #ffffff;
            color: #4b5563;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup::indicator,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup::indicator {
            width: 14px;
            height: 14px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QCheckBox,
        #summaryPivotRoot QFrame#summaryFiltersPanel QCheckBox {
            color: #6b7280;
            spacing: 8px;
            font-size: __FONT_SECONDARY_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QCheckBox#summaryAdvancedCheck {
            min-height: 18px;
            padding: 0px;
            margin: 0px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 0;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::handle:vertical {
            background: rgba(107, 114, 128, 0.28);
            border-radius: 5px;
            min-height: 24px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::handle:vertical:hover {
            background: rgba(107, 114, 128, 0.40);
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::add-line:vertical,
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::sub-line:vertical {
            height: 0px;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::add-page:vertical,
        #summaryPivotRoot QFrame#summarySidebarPanel QScrollBar::sub-page:vertical {
            background: transparent;
        }
        #summaryPivotRoot QFrame#summarySidebarFooter QPushButton#summaryPrimaryButton,
        #summaryPivotRoot QFrame#summaryFiltersFooter QPushButton#summaryPrimaryButton {
            background: #FFFFFF;
            color: #111827;
            border: 1px solid #D1D5DB;
            border-radius: 7px;
            padding: 0 12px;
            min-height: 34px;
            font-size: __FONT_BUTTON_PX__px;
            font-weight: __FONT_WEIGHT_REGULAR__;
        }
        #summaryPivotRoot QFrame#summarySidebarFooter QPushButton#summaryPrimaryButton:hover,
        #summaryPivotRoot QFrame#summaryFiltersFooter QPushButton#summaryPrimaryButton:hover {
            background: #F9FAFB;
            border-color: #9CA3AF;
        }
        #summaryPivotRoot QFrame#summaryFiltersFooter {
            background: #FFFFFF;
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 8px;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QScrollBar:vertical {
            width: 0px;
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryTableFooter {
            background: transparent;
            border-top: 1px solid rgba(17, 24, 39, 0.05);
            border-radius: 0px;
        }
        #summaryPivotRoot QFrame#summaryEmptyState {
            background: #ffffff;
            border: none;
            border-radius: 0px;
        }
        #summaryPivotRoot QTableView {
            background: #ffffff;
            border: 1px solid rgba(17, 24, 39, 0.07);
            border-radius: 5px;
            gridline-color: rgba(17, 24, 39, 0.045);
            alternate-background-color: #fcfcfd;
            selection-background-color: #E5E7EB;
            selection-color: #111827;
        }
        #summaryPivotRoot QTableView::item {
            padding: 6px 9px;
        }
        #summaryPivotRoot QTableView::item:alternate {
            background: #fcfcfd;
            padding: 6px 9px;
            border: none;
        }
        #summaryPivotRoot QTableView::item:selected {
            background: #E5E7EB;
            color: #111827;
            border: none;
            outline: none;
        }
        #summaryPivotRoot QHeaderView::section {
            background: #f9fafb;
            color: #4b5563;
            border: none;
            border-right: 1px solid rgba(17, 24, 39, 0.035);
            border-bottom: 1px solid rgba(17, 24, 39, 0.06);
            padding: 7px 8px;
            font-size: __FONT_CAPTION_PX__px;
            font-weight: __FONT_WEIGHT_MEDIUM__;
        }
        #summaryPivotRoot QTableCornerButton::section {
            background: #f9fafb;
            border: none;
            border-bottom: 1px solid rgba(17, 24, 39, 0.06);
        }
        #summaryPivotRoot QSplitter::handle {
            background: transparent;
            width: 6px;
            margin: 0;
        }
        #summaryPivotRoot QScrollArea {
            background: transparent;
            border: none;
        }
        """
    if dark_mode:
        qss += """
        QWidget#summaryPivotRoot,
        #summaryPivotRoot QFrame#summaryEmptyState {
            background: #0B1020;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryTableCard,
        #summaryPivotRoot QFrame#summaryFieldsPanel,
        #summaryPivotRoot QFrame#summaryFiltersPanel,
        #summaryPivotRoot QScrollArea#summaryFiltersScroll,
        #summaryPivotRoot QWidget#summaryFiltersViewport,
        #summaryPivotRoot QWidget#summaryFiltersBuilderContent,
        #summaryPivotRoot QFrame#summaryFiltersPanel QWidget[filterSectionCard="true"],
        #summaryPivotRoot QFrame#summarySidebarPanel QWidget[sidebarSection="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QWidget[sidebarSection="true"],
        #summaryPivotRoot QFrame#summaryAreaChip,
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup,
        #summaryPivotRoot QFrame#summaryFiltersFooter {
            background: #0B1020;
            border-color: #334155;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryTableCard,
        #summaryPivotRoot QFrame#summaryFieldsPanel,
        #summaryPivotRoot QFrame#summaryFiltersPanel {
            border: 1px solid #334155;
            border-radius: 5px;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel[collapsed="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel[collapsed="true"],
        #summaryPivotRoot QFrame#summaryPanelCollapsedRail,
        #summaryPivotRoot QHeaderView::section,
        #summaryPivotRoot QTableCornerButton::section {
            background: #0B1020;
            color: #CBD5E1;
            border-color: rgba(148, 163, 184, 0.16);
        }
        #summaryPivotRoot QLabel,
        #summaryPivotRoot QCheckBox,
        #summaryPivotRoot QToolButton,
        #summaryPivotRoot QLabel#summaryWelcomeTitle,
        #summaryPivotRoot QLabel#summaryAreaChipText,
        #summaryPivotRoot QToolButton#summarySourceCard {
            color: #F8FAFC;
        }
        #summaryPivotRoot QLabel#summaryWelcomeText,
        #summaryPivotRoot QLabel#summaryPanelCollapsedTitle,
        #summaryPivotRoot QFrame#summarySidebarPanel QCheckBox,
        #summaryPivotRoot QFrame#summaryFiltersPanel QCheckBox,
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup::title,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup::title {
            color: #CBD5E1;
            background: transparent;
        }
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup::title,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup::title {
            background: #0B1020;
        }
        #summaryPivotRoot QLabel#summaryEmptyTitle {
            color: #F8FAFC;
        }
        #summaryPivotRoot QLabel#summaryEmptyText,
        #summaryPivotRoot QLabel#summaryStatusLabel,
        #summaryPivotRoot QLabel#summarySelectionLabel {
            color: #94A3B8;
        }
        #summaryPivotRoot QTableView {
            background: #0B1020;
            color: #F8FAFC;
            border-color: rgba(148, 163, 184, 0.18);
            gridline-color: rgba(148, 163, 184, 0.14);
            alternate-background-color: #0F172A;
            selection-background-color: #1E293B;
            selection-color: #F8FAFC;
        }
        #summaryPivotRoot QTableView::item:alternate {
            background: #0F172A;
            padding: 6px 9px;
            border: none;
        }
        #summaryPivotRoot QTableView::item:selected,
        #summaryPivotRoot QTableView::item:alternate:selected,
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item:selected,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:selected {
            background: #1E293B;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summarySidebarFooter QPushButton#summaryPrimaryButton,
        #summaryPivotRoot QFrame#summaryFiltersFooter QPushButton#summaryPrimaryButton {
            background: #1F2937;
            color: #F8FAFC;
            border-color: #475569;
        }
        #summaryPivotRoot QFrame#summarySidebarFooter QPushButton#summaryPrimaryButton:hover,
        #summaryPivotRoot QFrame#summaryFiltersFooter QPushButton#summaryPrimaryButton:hover {
            background: #273449;
            border-color: #64748B;
        }
        #summaryPivotRoot QWidget#summaryToolbar,
        #summaryPivotRoot QFrame#summaryLayerHost,
        #summaryPivotRoot QWidget#summaryFieldsContextCard {
            background: #0B1020;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryToolbarStrip {
            background: transparent;
            border: 1px solid #334155;
            border-radius: 8px;
        }
        #summaryPivotRoot QWidget#summaryFieldsContextCard,
        #summaryPivotRoot QFrame#summaryLayerHost {
            border: none;
        }
        #summaryPivotRoot QWidget#summaryMainColumn,
        #summaryPivotRoot QWidget#summaryControlsZone,
        #summaryPivotRoot QWidget#summaryContentZone,
        #summaryPivotRoot QWidget#summaryTablePane,
        #summaryPivotRoot QWidget#summaryPanelBody,
        #summaryPivotRoot QStackedWidget#summaryTableStack,
        #summaryPivotRoot QSplitter#summaryMainSplitter,
        #summaryPivotRoot QSplitter#summaryAnalyticsSplitter {
            background: #0B1020;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryToolbarSeparator,
        #summaryPivotRoot QFrame#summarySidebarPanel[collapsed="true"] QFrame#summarySidebarHeader {
            background: rgba(148, 163, 184, 0.22);
        }
        #summaryPivotRoot QLineEdit#summarySearch,
        #summaryPivotRoot QWidget#summaryToolbar QLineEdit#summarySearch,
        #summaryPivotRoot QComboBox#summaryLayerCombo,
        #summaryPivotRoot QComboBox#summaryOperationCombo,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit#summaryFieldSearch,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLineEdit,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox {
            background: #172033;
            color: #F8FAFC;
            border: 1px solid #334155;
            selection-background-color: #1E293B;
            selection-color: #F8FAFC;
        }
        #summaryPivotRoot QComboBox QAbstractItemView,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox QAbstractItemView,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox QAbstractItemView {
            background: #172033;
            color: #F8FAFC;
            border: 1px solid #334155;
            selection-background-color: #312E81;
            selection-color: #F8FAFC;
        }
        #summaryPivotRoot QComboBox::drop-down {
            background: transparent;
            border: none;
        }
        #summaryPivotRoot QLineEdit#summarySearch:hover,
        #summaryPivotRoot QWidget#summaryToolbar QLineEdit#summarySearch:hover,
        #summaryPivotRoot QComboBox#summaryLayerCombo:hover,
        #summaryPivotRoot QComboBox#summaryOperationCombo:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit#summaryFieldSearch:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QLineEdit:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QComboBox:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QLineEdit:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QComboBox:hover {
            background: #1F2A3D;
            border: 1px solid #475569;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget#summaryFieldsList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryFilterList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList,
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget {
            background: #0B1020;
            color: #F8FAFC;
            border: 1px solid #334155;
            alternate-background-color: #0F172A;
            selection-background-color: #1E293B;
            selection-color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item,
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget::item {
            background: transparent;
            color: #F8FAFC;
            border: none;
        }
        #summaryPivotRoot QFrame#summaryFieldsPanel QListWidget::item:hover,
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget::item:hover,
        #summaryPivotRoot QFrame#summarySidebarPanel QListWidget::item:hover {
            background: #1F2A3D;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryRowList[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryColumnList[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryValueList[activeArea="true"],
        #summaryPivotRoot QFrame#summaryFiltersPanel QListWidget#summaryFilterList[activeArea="true"] {
            background: #172033;
            border: 1px solid #475569;
        }
        #summaryPivotRoot QFrame#summaryAreaChip,
        #summaryPivotRoot QFrame#summaryFiltersPanel QWidget[filterSectionCard="true"],
        #summaryPivotRoot QFrame#summarySidebarPanel QGroupBox#summaryAdvancedGroup,
        #summaryPivotRoot QFrame#summaryFiltersPanel QGroupBox#summaryAdvancedGroup {
            background: #0B1020;
            border: 1px solid #334155;
            color: #F8FAFC;
        }
        #summaryPivotRoot QFrame#summaryFiltersFooter {
            border: 1px solid #334155;
            border-radius: 8px;
        }
        #summaryPivotRoot QCheckBox::indicator {
            background: #172033;
            border-color: #475569;
        }
        #summaryPivotRoot QCheckBox::indicator:checked {
            background: #7C6CFF;
            border-color: #8B7CFF;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton,
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryPrimaryButton[toolbarPrimary="true"],
        #summaryPivotRoot QPushButton#summarySecondaryButton,
        #summaryPivotRoot QPushButton#summaryBackButton,
        #summaryPivotRoot QPushButton#summaryGhostButton,
        #summaryPivotRoot QToolButton#summarySidebarToggle {
            color: #E5E7EB;
            background: transparent;
            border-color: transparent;
        }
        #summaryPivotRoot QWidget#summaryToolbar QPushButton:hover,
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryToolbarButton:checked,
        #summaryPivotRoot QWidget#summaryToolbar QPushButton#summaryPrimaryButton[toolbarPrimary="true"]:hover,
        #summaryPivotRoot QPushButton#summarySecondaryButton:hover,
        #summaryPivotRoot QPushButton#summaryBackButton:hover,
        #summaryPivotRoot QPushButton#summaryGhostButton:hover,
        #summaryPivotRoot QToolButton#summarySidebarToggle:hover {
            background: #1F2A3D;
            border-color: #334155;
            color: #F8FAFC;
        }
        """
    for key, value in tokens.items():
        qss = qss.replace(key, value)
    if not dark_mode:
        qss = qss.replace("#111827", INK_COLOR)
    self.setStyleSheet(qss)
    self._refresh_toolbar_chrome()
    self._enforce_filters_surface_backgrounds()


def enforce_filters_surface_backgrounds(widget) -> None:
    self = widget
    dark_mode = is_dark_theme()
    surface = QColor("#0B1020" if dark_mode else "#ffffff")
    input_surface = QColor("#111827" if dark_mode else "#ffffff")
    text = QColor("#F8FAFC" if dark_mode else "#111827")

    for widget in (
        getattr(self, "toolbar_strip", None),
        getattr(self, "controls_zone", None),
        getattr(self, "toolbar_frame", None),
        getattr(self, "main_column", None),
        getattr(self, "content_zone", None),
        getattr(self, "table_container", None),
        getattr(self, "table_stack", None),
        getattr(self, "table_page", None),
        getattr(self, "table_card", None),
        getattr(self, "empty_state_frame", None),
        getattr(self, "fields_panel", None),
        getattr(self, "fields_panel_body", None),
        getattr(self, "filters_panel", None),
        getattr(self, "filters_panel_body", None),
        getattr(self, "filters_builder_scroll", None),
        getattr(self, "filters_builder_scroll", None).viewport() if getattr(self, "filters_builder_scroll", None) is not None else None,
        getattr(self, "filters_builder_content", None),
        getattr(self, "filter_area_card", None),
        getattr(self, "row_area_card", None),
        getattr(self, "column_area_card", None),
        getattr(self, "value_area_card", None),
        getattr(self, "advanced_group", None),
    ):
        if widget is None:
            continue
        try:
            palette = widget.palette()
            palette.setColor(QPalette.Window, surface)
            palette.setColor(QPalette.Base, surface)
            palette.setColor(QPalette.Text, text)
            palette.setColor(QPalette.WindowText, text)
            widget.setPalette(palette)
            widget.setAutoFillBackground(True)
        except Exception:
            log_exception("falha opcional ignorada")

    for list_widget in (
        getattr(self, "fields_list", None),
        getattr(self, "filter_fields_list", None),
        getattr(self, "row_fields_list", None),
        getattr(self, "column_fields_list", None),
        getattr(self, "value_fields_list", None),
    ):
        if list_widget is None:
            continue
        try:
            palette = list_widget.palette()
            palette.setColor(QPalette.Base, surface)
            palette.setColor(QPalette.Window, surface)
            palette.setColor(QPalette.Text, text)
            palette.setColor(QPalette.WindowText, text)
            list_widget.setPalette(palette)
            list_widget.setAutoFillBackground(True)
            viewport = list_widget.viewport()
            if viewport is not None:
                viewport.setPalette(palette)
                viewport.setAutoFillBackground(True)
                viewport.setBackgroundRole(QPalette.Base)
        except Exception:
            log_exception("falha opcional ignorada")

    combo_style = (
        """
        QComboBox {
            background: #111827;
            color: #F8FAFC;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 2px 8px;
            selection-background-color: #1E293B;
            selection-color: #F8FAFC;
        }
        QComboBox:hover,
        QComboBox:focus {
            background: #111827;
            border-color: #475569;
        }
        QComboBox::drop-down {
            background: transparent;
            border: none;
            width: 18px;
        }
        QComboBox QAbstractItemView {
            background: #111827;
            color: #F8FAFC;
            border: 1px solid #334155;
            selection-background-color: #1E293B;
            selection-color: #F8FAFC;
        }
        """
        if dark_mode
        else ""
    )
    for combo in (
        getattr(self, "agg_combo", None),
        getattr(self, "value_field_combo", None),
    ):
        if combo is None:
            continue
        try:
            palette = combo.palette()
            palette.setColor(QPalette.Window, input_surface)
            palette.setColor(QPalette.Base, input_surface)
            palette.setColor(QPalette.Button, input_surface)
            palette.setColor(QPalette.Text, text)
            palette.setColor(QPalette.ButtonText, text)
            palette.setColor(QPalette.WindowText, text)
            combo.setPalette(palette)
            combo.setAutoFillBackground(True)
            combo.setStyleSheet(combo_style)
        except Exception:
            log_exception("falha opcional ignorada")
