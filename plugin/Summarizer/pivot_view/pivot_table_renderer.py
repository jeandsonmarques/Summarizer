# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence

import numpy as np
import pandas as pd


def table_headers(df: pd.DataFrame) -> List[Any]:
    if df is None:
        return []
    return list(df.columns)


def format_table_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{value:,.2f}"
    return str(value)


def calculate_row_header_depth(pivot_result: Any, display_row_keys: Sequence[Sequence[Any]]) -> int:
    metadata = getattr(pivot_result, "metadata", None) or {}
    row_fields = metadata.get("row_fields") or []
    return max(
        len(row_fields),
        max((len(key) for key in display_row_keys), default=0),
        1,
    )


def feature_ids_for_cell(
    pivot_result: Any,
    *,
    row_index: int,
    pivot_column_index: int,
    display_column_keys: Sequence[Any],
) -> Optional[str]:
    if pivot_result is None:
        return None
    if pivot_column_index < 0 or pivot_column_index >= len(display_column_keys):
        return None
    matrix = getattr(pivot_result, "matrix", None) or []
    if row_index < 0 or row_index >= len(matrix):
        return None
    row = matrix[row_index]
    if pivot_column_index >= len(row):
        return None
    matrix_cell = row[pivot_column_index]
    feature_ids = list(getattr(matrix_cell, "feature_ids", []) or [])
    return ",".join(str(fid) for fid in feature_ids)


def populate_table(
    widget: Any,
    *,
    translate: Callable[..., str],
    message_log: Any,
    qgis_info: Any,
    ui_font_factory: Callable[[], Any],
    typography: dict,
) -> None:
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QFont, QStandardItem, QStandardItemModel

    from ..utils.fonts import _qfont_weight

    self = widget
    message_log.logMessage("PivotTableWidget: rebuilding table model", "Summarizer", qgis_info)
    self.proxy_model.setSourceModel(None)
    new_model = QStandardItemModel(self)
    self._display_row_keys = []
    self._display_column_keys = []
    self._pivot_data_column_offset = 0
    self._row_header_depth = 1

    if self.pivot_df is None or self.pivot_df.empty:
        new_model.setHorizontalHeaderLabels([translate("Nenhum resultado")])
        self.table_model = new_model
        self.proxy_model.setSourceModel(self.table_model)
        self.table_view.setModel(self.proxy_model)
        has_structure = bool(
            self._selected_area_specs("row") or self._selected_area_specs("column")
        )
        if has_structure:
            self.empty_state_title.setText(
                translate("Nenhum resultado para a configuração atual")
            )
            self.empty_state_text.setText(
                translate("Ajuste os agrupamentos ou a operação para continuar a análise.")
            )
        else:
            self.empty_state_title.setText(
                translate("Adicione campos em Linhas ou Colunas para começar")
            )
            self.empty_state_text.setText(
                translate(
                    "Escolha os agrupamentos no painel Campos da Tabela Dinamica "
                    "para montar a tabela dinamica."
                )
            )
        self.table_stack.setCurrentWidget(self.empty_state_frame)
        self._connect_selection_summary()
        self.proxy_model.invalidate()
        self._apply_table_preferences()
        self._update_status_label()
        self._update_selection_summary()
        message_log.logMessage("PivotTableWidget: model rebuilt (empty)", "Summarizer", qgis_info)
        return

    headers = table_headers(self.pivot_df)
    new_model.setHorizontalHeaderLabels(headers)
    self._display_row_keys = list(getattr(self._current_pivot_result, "row_headers", []) or [])
    self._display_column_keys = list(
        getattr(self._current_pivot_result, "column_headers", []) or []
    )
    self._row_header_depth = calculate_row_header_depth(
        self._current_pivot_result,
        self._display_row_keys,
    )
    self._pivot_data_column_offset = self._row_header_depth

    base_font = ui_font_factory()
    base_font.setPixelSize(int(typography.get("font_body_px", 13)))
    base_font.setWeight(_qfont_weight("Medium", 57))
    total_column_index = headers.index("Total") if "Total" in headers else -1
    for row_index, row in enumerate(self.pivot_df.itertuples(index=False, name=None)):
        items = []
        for column_index, value in enumerate(row):
            item = QStandardItem(format_table_value(value))
            item.setEditable(False)
            item.setData(None if pd.isna(value) else value, Qt.ItemDataRole.UserRole + 3)
            font = QFont(base_font)
            if column_index == total_column_index:
                font.setBold(True)
            item.setFont(font)
            if column_index < self._pivot_data_column_offset:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            if isinstance(value, (float, np.floating, int, np.integer)):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            has_feature_lookup = all(
                (
                    self._current_pivot_result is not None,
                    row_index < len(self._display_row_keys),
                    column_index >= self._pivot_data_column_offset,
                )
            )
            if has_feature_lookup:
                pivot_column_index = column_index - self._pivot_data_column_offset
                feature_ids = feature_ids_for_cell(
                    self._current_pivot_result,
                    row_index=row_index,
                    pivot_column_index=pivot_column_index,
                    display_column_keys=self._display_column_keys,
                )
                if feature_ids is not None:
                    item.setData(feature_ids, Qt.ItemDataRole.UserRole)
            items.append(item)
        new_model.appendRow(items)

    self.table_model = new_model
    self.proxy_model.setSourceModel(self.table_model)
    self.table_view.setModel(self.proxy_model)
    self.table_stack.setCurrentWidget(self.table_page)
    self._connect_selection_summary()
    self.proxy_model.invalidate()
    self.table_view.resizeColumnsToContents()
    self._apply_table_preferences()
    self._update_status_label()
    self._update_selection_summary()
    message_log.logMessage(
        f"PivotTableWidget: model rebuilt with {self.table_model.rowCount()} rows",
        "Summarizer",
        qgis_info,
    )
