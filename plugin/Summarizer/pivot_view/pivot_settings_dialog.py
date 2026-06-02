# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

TABLE_SETTINGS_DIALOG_OBJECT_NAME = "SummaryTableSettingsDialog"
TABLE_SETTINGS_TITLE = "Personalizar tabela"
TABLE_SETTINGS_TITLE_LABEL = "SummarySettingsTitle"
TABLE_SETTINGS_LABEL = "SummarySettingsLabel"
TABLE_SETTINGS_CHECK = "SummarySettingsCheck"
TABLE_SETTINGS_INPUT = "SummarySettingsInput"
TABLE_SETTINGS_PRIMARY = "SummarySettingsPrimary"
TABLE_SETTINGS_SECONDARY = "SummarySettingsSecondary"
TABLE_ROW_HEIGHT_DEFAULT = 30
TABLE_ROW_HEIGHT_MIN = 24
TABLE_ROW_HEIGHT_MAX = 52
TABLE_HEADER_HEIGHT_COMPACT = 30
TABLE_HEADER_HEIGHT_EXPANDED = 38


def normalize_table_row_height(
    value: Any,
    *,
    default: int = TABLE_ROW_HEIGHT_DEFAULT,
    minimum: int = TABLE_ROW_HEIGHT_MIN,
    maximum: int = TABLE_ROW_HEIGHT_MAX,
) -> int:
    try:
        row_height = int(value)
    except Exception:
        row_height = int(default)
    return max(int(minimum), min(int(maximum), row_height))


def normalize_table_settings(
    row_height: Any,
    alternating_rows: Any,
    header_compact: Any,
    *,
    default_row_height: int = TABLE_ROW_HEIGHT_DEFAULT,
    minimum_row_height: int = TABLE_ROW_HEIGHT_MIN,
    maximum_row_height: int = TABLE_ROW_HEIGHT_MAX,
) -> Dict[str, Any]:
    return {
        "row_height": normalize_table_row_height(
            row_height,
            default=default_row_height,
            minimum=minimum_row_height,
            maximum=maximum_row_height,
        ),
        "alternating_rows": bool(alternating_rows),
        "header_compact": bool(header_compact),
    }


def build_table_settings_defaults(widget) -> Dict[str, Any]:
    return normalize_table_settings(
        getattr(widget, "_table_row_height", TABLE_ROW_HEIGHT_DEFAULT),
        getattr(widget, "_table_alternating_rows", True),
        getattr(widget, "_table_header_compact", True),
    )


def apply_table_settings(
    widget,
    row_height: Any,
    alternating_rows: Any,
    header_compact: Any,
    *,
    apply_callback: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    settings = normalize_table_settings(row_height, alternating_rows, header_compact)
    widget._table_row_height = settings["row_height"]
    widget._table_alternating_rows = settings["alternating_rows"]
    widget._table_header_compact = settings["header_compact"]
    if apply_callback is not None:
        apply_callback()
    return settings


def _is_dark_theme() -> bool:
    try:
        from qgis.PyQt.QtCore import QSettings

        theme = str(QSettings().value("Summarizer/uiTheme", "light") or "light")
        return theme.strip().lower() == "dark"
    except Exception:
        return False


def open_table_settings_dialog(
    widget,
    *,
    translate,
    apply_preferences_callback: Optional[Callable[[], None]] = None,
) -> None:
    try:
        from qgis.PyQt.QtWidgets import (
            QCheckBox,
            QDialog,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QSpinBox,
            QVBoxLayout,
        )
    except Exception:
        return

    from ..utils.fonts import attach_ui_font_enforcer, harmonize_widget_fonts, ui_font
    from ..utils.window_theme import apply_windows_title_bar_theme
    from ..walker_dialogs import WALKER_DIALOG_STYLE, add_walker_close_button, apply_walker_buttons, install_walker_modal_chrome

    dialog = QDialog(widget)
    dialog.setObjectName(TABLE_SETTINGS_DIALOG_OBJECT_NAME)
    dialog.setProperty("walkerDialog", True)
    dialog.setWindowTitle(translate(TABLE_SETTINGS_TITLE))
    dialog.setModal(True)
    dialog.resize(360, 250)
    dialog.setFont(ui_font())
    dialog._font_enforcer = attach_ui_font_enforcer(dialog)
    install_walker_modal_chrome(dialog)
    dialog.setStyleSheet(
        WALKER_DIALOG_STYLE + """
        QDialog#SummaryTableSettingsDialog {
            background: #FFFFFF;
            border: 1px solid #D6D9E0;
            border-radius: 8px;
        }
        QLabel#SummarySettingsTitle {
            color: #111827;
            font-size: 17px;
            font-weight: 600;
        }
        QLabel#SummarySettingsLabel,
        QCheckBox#SummarySettingsCheck {
            color: #111827;
            font-size: 12px;
            font-weight: 400;
        }
        QSpinBox#SummarySettingsInput {
            min-height: 30px;
            padding: 0 8px;
            background: #FFFFFF;
            border: 1px solid #D1D5DB;
            border-radius: 6px;
        }
        QPushButton#SummarySettingsPrimary,
        QPushButton#SummarySettingsSecondary {
            min-height: 32px;
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            font-weight: 400;
        }
        QPushButton#SummarySettingsPrimary {
            color: #FFFFFF;
            background: #111827;
            border: 1px solid #111827;
        }
        QPushButton#SummarySettingsPrimary:hover {
            background: #1F2937;
        }
        QPushButton#SummarySettingsSecondary {
            color: #111827;
            background: #FFFFFF;
            border: 1px solid #D1D5DB;
        }
        QPushButton#SummarySettingsSecondary:hover {
            background: #F9FAFB;
            border-color: #9CA3AF;
        }
        """
    )
    if _is_dark_theme():
        dialog.setStyleSheet(
            """
            QDialog#SummaryTableSettingsDialog {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #F8FAFC;
            }
            QLabel#SummarySettingsTitle {
                color: #F8FAFC;
                font-size: 17px;
                font-weight: 600;
                background: transparent;
            }
            QLabel#SummarySettingsLabel,
            QCheckBox#SummarySettingsCheck {
                color: #F8FAFC;
                font-size: 12px;
                font-weight: 400;
                background: transparent;
            }
            QSpinBox#SummarySettingsInput {
                min-height: 30px;
                padding: 0 8px;
                background: #172033;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                selection-background-color: #1E293B;
                selection-color: #F8FAFC;
            }
            QSpinBox#SummarySettingsInput:focus {
                border-color: #7C6CFF;
            }
            QSpinBox#SummarySettingsInput::up-button,
            QSpinBox#SummarySettingsInput::down-button,
            QSpinBox#SummarySettingsInput::up-arrow,
            QSpinBox#SummarySettingsInput::down-arrow {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
                image: none;
            }
            QPushButton#SummarySettingsPrimary,
            QPushButton#SummarySettingsSecondary {
                min-height: 32px;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 400;
            }
            QPushButton#SummarySettingsPrimary {
                color: #0B1020;
                background: #F8FAFC;
                border: 1px solid #F8FAFC;
                font-weight: 500;
            }
            QPushButton#SummarySettingsPrimary:hover {
                background: #E2E8F0;
                border-color: #E2E8F0;
            }
            QPushButton#SummarySettingsSecondary {
                color: #F8FAFC;
                background: #111827;
                border: 1px solid #334155;
            }
            QPushButton#SummarySettingsSecondary:hover {
                background: #1F2A3D;
                border-color: #475569;
            }
            """
        )
        apply_windows_title_bar_theme(dialog, True)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 16, 16, 14)
    layout.setSpacing(12)

    body_text_font = ui_font()
    body_text_font.setPixelSize(12)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)
    title = QLabel(translate(TABLE_SETTINGS_TITLE), dialog)
    title.setObjectName(TABLE_SETTINGS_TITLE_LABEL)
    title_font = ui_font()
    title_font.setPixelSize(17)
    title_font.setWeight(600)
    title.setFont(title_font)
    header.addWidget(title, 1)
    add_walker_close_button(header, dialog)
    layout.addLayout(header)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)

    row_label = QLabel(translate("Altura da linha"), dialog)
    row_label.setObjectName(TABLE_SETTINGS_LABEL)
    row_label.setFont(body_text_font)
    row_spin = QSpinBox(dialog)
    row_spin.setObjectName(TABLE_SETTINGS_INPUT)
    row_spin.setFont(body_text_font)
    row_spin.setRange(TABLE_ROW_HEIGHT_MIN, TABLE_ROW_HEIGHT_MAX)
    defaults = build_table_settings_defaults(widget)
    row_spin.setValue(int(defaults["row_height"]))
    row_spin.setButtonSymbols(QSpinBox.NoButtons)
    grid.addWidget(row_label, 0, 0)
    grid.addWidget(row_spin, 0, 1)

    alternating_check = QCheckBox(translate("Linhas alternadas"), dialog)
    alternating_check.setObjectName(TABLE_SETTINGS_CHECK)
    alternating_check.setFont(body_text_font)
    alternating_check.setChecked(bool(defaults["alternating_rows"]))
    grid.addWidget(alternating_check, 1, 0, 1, 2)

    compact_check = QCheckBox(translate("Cabeçalho compacto"), dialog)
    compact_check.setObjectName(TABLE_SETTINGS_CHECK)
    compact_check.setFont(body_text_font)
    compact_check.setChecked(bool(defaults["header_compact"]))
    grid.addWidget(compact_check, 2, 0, 1, 2)
    layout.addLayout(grid)
    layout.addStretch(1)

    actions = QHBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(8)
    actions.addStretch(1)
    cancel_btn = QPushButton(translate("Cancelar"), dialog)
    cancel_btn.setObjectName(TABLE_SETTINGS_SECONDARY)
    cancel_btn.setFont(body_text_font)
    apply_btn = QPushButton(translate("Aplicar"), dialog)
    apply_btn.setObjectName(TABLE_SETTINGS_PRIMARY)
    apply_btn.setFont(body_text_font)
    apply_walker_buttons(primary=[apply_btn], secondary=[cancel_btn])
    actions.addWidget(cancel_btn, 0)
    actions.addWidget(apply_btn, 0)
    layout.addLayout(actions)
    harmonize_widget_fonts(dialog)

    cancel_btn.clicked.connect(dialog.reject)

    def _apply():
        apply_table_settings(
            widget,
            row_height=row_spin.value(),
            alternating_rows=alternating_check.isChecked(),
            header_compact=compact_check.isChecked(),
            apply_callback=apply_preferences_callback,
        )
        dialog.accept()

    apply_btn.clicked.connect(_apply)
    dialog.exec_()

