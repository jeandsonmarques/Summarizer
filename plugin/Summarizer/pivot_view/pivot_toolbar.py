# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

# ruff: noqa: E501
from __future__ import annotations

from typing import Optional

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from ..utils.logging_utils import log_exception
from ..utils.resources import svg_icon

INK_COLOR = "#252B33"


def configure_toolbar_button(button: Optional[QPushButton]) -> None:
    if button is None:
        return
    button.setFlat(True)
    button.setAutoDefault(False)
    button.setDefault(False)
    button.setCursor(Qt.PointingHandCursor)


def configure_toolbar_icon_button(
    button: Optional[QPushButton],
    icon_name: str,
    tooltip: str,
    icon_size: int = 18,
) -> None:
    if button is None:
        return
    configure_toolbar_button(button)
    button.setProperty("toolbarMode", "icon")
    button.setProperty("iconOnly", True)
    button.setFocusPolicy(Qt.NoFocus)
    button.setToolTip(tooltip)
    button.setStatusTip(tooltip)
    try:
        button.setAccessibleName(tooltip)
    except Exception:
        log_exception("falha opcional ignorada")
    icon = svg_icon(icon_name)
    if not icon.isNull():
        button.setIcon(icon)
    button.setIconSize(QSize(icon_size, icon_size))


def create_toolbar_separator(parent: QWidget) -> QFrame:
    separator = QFrame(parent)
    separator.setObjectName("summaryToolbarSeparator")
    separator.setFrameShape(QFrame.NoFrame)
    separator.setFrameShadow(QFrame.Plain)
    separator.setFixedWidth(1)
    return separator


def polish_toolbar_button(button: Optional[QPushButton]) -> None:
    if button is None:
        return
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)
    button.update()


def build_state_labels(
    widget,
    *,
    context_layout: QHBoxLayout,
    selection_layout: QHBoxLayout | None,
    helper_text_font,
) -> None:
    self = widget

    if not hasattr(self, "meta_label"):
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("summaryMetaLabel")
        self.meta_label.setWordWrap(True)
        self.meta_label.setFont(helper_text_font)
        context_layout.addWidget(self.meta_label)

    if selection_layout is not None and not hasattr(self, "status_label"):
        self.status_label = QLabel("")
        self.status_label.setObjectName("summaryStatusLabel")
        self.status_label.setFont(helper_text_font)
        selection_layout.addWidget(self.status_label, 1)


def build_toolbar(
    widget,
    *,
    body_text_font,
    translate,
    icon_factory,
    toolbar_icons,
    ink_color: str = INK_COLOR,
) -> None:
    self = widget
    _rt = translate
    _svg_icon_from_template = icon_factory
    _TOOLBAR_SVG_ICONS = toolbar_icons

    self.toolbar_frame = QWidget()
    self.toolbar_frame.setObjectName("summaryToolbar")
    toolbar = QHBoxLayout(self.toolbar_frame)
    toolbar.setContentsMargins(0, 0, 0, 0)
    toolbar.setSpacing(8)
    self.toolbar_layout = toolbar

    self.undo_btn = QPushButton(_rt("Desfazer"))
    self.redo_btn = QPushButton(_rt("Refazer"))
    self.import_sheet_btn = QPushButton(_rt("Importar planilha"))
    self.clear_filters_btn = QPushButton(_rt("Limpar busca"))
    self.export_btn = QPushButton(_rt("Exportar"))
    self.edit_mode_btn = QPushButton(_rt("Edicao"))
    self.settings_btn = QPushButton(_rt("Configuracoes"))
    self.edit_mode_btn.setCheckable(True)
    self.edit_mode_btn.setChecked(True)
    self.sidebar_toggle_btn = self.edit_mode_btn
    self.clear_filters_btn.setProperty("variant", "secondary")

    for button in (
        self.undo_btn,
        self.redo_btn,
        self.import_sheet_btn,
        self.clear_filters_btn,
        self.export_btn,
        self.edit_mode_btn,
        self.settings_btn,
    ):
        button.setObjectName("summaryToolbarButton")
        button.setProperty("toolbarMode", "icon")
        button.setProperty("iconOnly", True)
        button.setFixedSize(30, 30)
        button.setCursor(Qt.PointingHandCursor)
        button.setText("")
        button.setFlat(True)
        button.setAutoDefault(False)
        button.setDefault(False)

    configure_toolbar_icon_button(self.undo_btn, "Walker-Undo.svg", _rt("Desfazer (Ctrl+Z)"))
    configure_toolbar_icon_button(self.redo_btn, "Walker-Redo.svg", _rt("Refazer (Ctrl+Shift+Z)"))
    configure_toolbar_icon_button(self.import_sheet_btn, "Excel-Workbook.svg", _rt("Importar planilha"))
    configure_toolbar_icon_button(self.export_btn, "Walker-Image.svg", _rt("Exportar"))
    configure_toolbar_icon_button(
        self.edit_mode_btn,
        "Walker-Edit.svg",
        _rt("Mostrar ou ocultar camada e filtros"),
    )
    configure_toolbar_icon_button(self.settings_btn, "Walker-Settings.svg", _rt("Personalizar tabela"))
    mono_icon_colors = {
        QIcon.Normal: ink_color,
        QIcon.Active: ink_color,
        QIcon.Selected: ink_color,
        QIcon.Disabled: "#C7CDD6",
    }
    self.import_sheet_btn.setIcon(
        _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_sheet"], size=18, color_map=mono_icon_colors)
    )
    self.export_btn.setIcon(
        _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_image"], size=18, color_map=mono_icon_colors)
    )
    self.edit_mode_btn.setIcon(
        _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_edit"], size=18, color_map=mono_icon_colors)
    )
    self.settings_btn.setIcon(
        _svg_icon_from_template(_TOOLBAR_SVG_ICONS["summary_settings"], size=18, color_map=mono_icon_colors)
    )

    self.toolbar_strip = QFrame(self.toolbar_frame)
    self.toolbar_strip.setObjectName("summaryToolbarStrip")
    self.toolbar_strip.setAttribute(Qt.WA_StyledBackground, True)
    self.toolbar_strip.setFrameShape(QFrame.StyledPanel)
    self.toolbar_strip.setStyleSheet(
        """
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
            min-width: 30px;
            max-width: 30px;
            min-height: 30px;
            max-height: 30px;
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
            min-height: 30px;
        }
        QPushButton[variant="secondary"]:hover {
            background: #F9FAFB;
            border-color: #9CA3AF;
        }
        QLineEdit#summarySearch {
            min-height: 30px;
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
    )
    self.toolbar_strip_layout = QHBoxLayout(self.toolbar_strip)
    self.toolbar_strip_layout.setContentsMargins(8, 5, 8, 5)
    self.toolbar_strip_layout.setSpacing(2)
    for button in (self.undo_btn, self.redo_btn):
        self.toolbar_strip_layout.addWidget(button, 0)
    self.toolbar_strip_layout.addWidget(create_toolbar_separator(self.toolbar_strip), 0)
    for button in (self.import_sheet_btn, self.export_btn):
        self.toolbar_strip_layout.addWidget(button, 0)
    self.toolbar_strip_layout.addWidget(create_toolbar_separator(self.toolbar_strip), 0)
    for button in (self.edit_mode_btn, self.settings_btn):
        self.toolbar_strip_layout.addWidget(button, 0)

    self.search_input = QLineEdit()
    self.search_input.setObjectName("summarySearch")
    self.search_input.setPlaceholderText(_rt("Buscar"))
    self.search_input.setFixedHeight(30)
    self.search_input.setMinimumWidth(166)
    self.search_input.setMaximumWidth(220)
    self.search_input.setFont(body_text_font)
    self.toolbar_strip_layout.addStretch(1)
    self.toolbar_strip_layout.addWidget(self.search_input, 0)
    self.toolbar_strip_layout.addWidget(self.clear_filters_btn, 0)
    toolbar.addWidget(self.toolbar_strip, 1)


def update_undo_redo_buttons(widget) -> None:
    self = widget
    has_data = self.raw_df is not None and not self.raw_df.empty
    if hasattr(self, "undo_btn") and self.undo_btn is not None:
        self.undo_btn.setEnabled(bool(has_data and self._history_undo))
    if hasattr(self, "redo_btn") and self.redo_btn is not None:
        self.redo_btn.setEnabled(bool(has_data and self._history_redo))

