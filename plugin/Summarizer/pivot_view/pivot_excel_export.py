# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from ..utils.logging_utils import log_exception


def native_excel_aggregation_code(aggregation: str) -> int:
    agg_map = {
        "count": -4112,    # xlCount
        "sum": -4157,      # xlSum
        "average": -4106,  # xlAverage
        "min": -4139,      # xlMin
        "max": -4136,      # xlMax
        "stddev": -4155,   # xlStDev
        "variance": -4164,  # xlVar
        "median": -4106,   # fallback: media
        "unique": -4112,   # fallback: contagem
    }
    return agg_map.get(str(aggregation or "count").lower(), -4112)


def resolve_native_excel_fields(
    values: Optional[Sequence[str]],
    labels: Optional[Sequence[str]],
    available_fields: Sequence[str],
    resolve_available_field_name: Callable[..., Optional[str]],
) -> List[str]:
    valid: List[str] = []
    label_values = list(labels or [])
    for index, value in enumerate(values or []):
        fallback = label_values[index] if index < len(label_values) else ""
        resolved = resolve_available_field_name(
            value,
            available_fields,
            fallback_candidates=[fallback],
        )
        if resolved and resolved not in valid:
            valid.append(resolved)
    return valid


def build_native_excel_data_caption(
    aggregation: str,
    value_field: str,
    aggregation_label: str,
) -> str:
    aggregation = str(aggregation or "count").lower()
    label = str(aggregation_label or aggregation.upper()).strip()
    if aggregation != "count":
        return f"{label} de {value_field}"
    return f"Contagem de {value_field}"


class PivotExcelExportController:
    def __init__(self, host):
        self.host = host

    def try_create_native_excel_pivot(
        self,
        file_path: str,
        layer_df: pd.DataFrame,
        pivot_config: Dict[str, Any],
        *,
        translate,
    ) -> Tuple[bool, str]:
        return try_create_native_excel_pivot(
            file_path,
            layer_df,
            pivot_config,
            translate=translate,
            resolve_available_field_name=self.host._resolve_available_field_name,
        )


def try_create_native_excel_pivot(
    file_path: str,
    layer_df: pd.DataFrame,
    pivot_config: Dict[str, Any],
    *,
    translate,
    resolve_available_field_name: Callable[..., Optional[str]],
) -> Tuple[bool, str]:
    if layer_df is None or layer_df.empty:
        return False, translate("Sem dados da camada para gerar tabela dinâmica nativa.")

    try:
        import win32com.client as win32  # type: ignore
    except Exception:
        return (
            False,
            translate("Tabela dinâmica nativa do Excel não criada (pywin32/Excel não disponível)."),
        )

    available_fields = [str(column) for column in list(layer_df.columns)]
    if not available_fields:
        return False, translate("Sem colunas válidas para montar tabela dinâmica nativa.")

    requested_row_fields = [
        str(value or "").strip()
        for value in (pivot_config.get("row_fields") or [])
        if str(value or "").strip()
    ]
    requested_column_fields = [
        str(value or "").strip()
        for value in (pivot_config.get("column_fields") or [])
        if str(value or "").strip()
    ]
    requested_filter_fields = [
        str(value or "").strip()
        for value in (pivot_config.get("filter_fields") or [])
        if str(value or "").strip()
    ]

    row_fields = resolve_native_excel_fields(
        requested_row_fields,
        pivot_config.get("row_labels"),
        available_fields,
        resolve_available_field_name,
    )
    column_fields = resolve_native_excel_fields(
        requested_column_fields,
        pivot_config.get("column_labels"),
        available_fields,
        resolve_available_field_name,
    )
    filter_fields = resolve_native_excel_fields(
        requested_filter_fields,
        pivot_config.get("filter_labels"),
        available_fields,
        resolve_available_field_name,
    )

    if requested_row_fields and not row_fields:
        return False, translate(
            "Tabela dinâmica nativa não criada: campos de Linhas "
            "não foram mapeados na base exportada."
        )
    if requested_column_fields and not column_fields:
        return False, translate(
            "Tabela dinâmica nativa não criada: campos de Colunas "
            "não foram mapeados na base exportada."
        )
    if requested_filter_fields and not filter_fields:
        return False, translate(
            "Tabela dinâmica nativa não criada: campos de Filtros "
            "não foram mapeados na base exportada."
        )

    value_field = resolve_available_field_name(
        pivot_config.get("value_field"),
        available_fields,
        fallback_candidates=[pivot_config.get("value_label")],
    )
    if not value_field:
        excluded = set(row_fields + column_fields + filter_fields)
        candidates = [field for field in available_fields if field not in excluded]
        if candidates:
            value_field = candidates[0]
        elif row_fields:
            value_field = row_fields[0]
        elif column_fields:
            value_field = column_fields[0]
        else:
            value_field = available_fields[0]

    requested_row_fields_lower = {value.lower() for value in requested_row_fields}
    requested_column_fields_lower = {value.lower() for value in requested_column_fields}

    if requested_row_fields and len(row_fields) < len(requested_row_fields_lower):
        return False, translate(
            "Tabela dinâmica nativa não criada: parte dos campos de Linhas "
            "não foi reconhecida."
        )
    if requested_column_fields and len(column_fields) < len(requested_column_fields_lower):
        return False, translate(
            "Tabela dinâmica nativa não criada: parte dos campos de Colunas "
            "não foi reconhecida."
        )

    if not value_field:
        return False, translate(
            "Não foi possível determinar um campo de valor para a tabela dinâmica."
        )

    aggregation = str(pivot_config.get("aggregation") or "count").lower()
    agg_function = native_excel_aggregation_code(aggregation)
    aggregation_label = str(pivot_config.get("aggregation_label") or aggregation.upper()).strip()
    data_caption = build_native_excel_data_caption(aggregation, value_field, aggregation_label)

    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(file_path)

        ws_data = workbook.Worksheets("Dados_Camada")
        used = ws_data.UsedRange
        last_row = int(used.Rows.Count)
        last_col = int(used.Columns.Count)
        if last_row < 2 or last_col < 1:
            return False, translate("Dados insuficientes para montar a tabela dinâmica nativa.")

        try:
            ws_snapshot = workbook.Worksheets("Tabela_Dinamica")
            try:
                workbook.Worksheets("Resumo_Pivot").Delete()
            except Exception:
                log_exception("falha opcional ignorada")
            ws_snapshot.Name = "Resumo_Pivot"
        except Exception:
            log_exception("falha opcional ignorada")

        try:
            workbook.Worksheets("Tabela_Dinamica").Delete()
        except Exception:
            log_exception("falha opcional ignorada")

        ws_pivot = workbook.Worksheets.Add()
        ws_pivot.Name = "Tabela_Dinamica"

        source_range = ws_data.Range(ws_data.Cells(1, 1), ws_data.Cells(last_row, last_col))
        pivot_cache = workbook.PivotCaches().Create(SourceType=1, SourceData=source_range)
        pivot_name = "PivotSummarizer"
        pivot_cache.CreatePivotTable(
            TableDestination="'Tabela_Dinamica'!R3C1",
            TableName=pivot_name,
        )
        pivot_table = ws_pivot.PivotTables(pivot_name)

        for position, field_name in enumerate(filter_fields, start=1):
            field = pivot_table.PivotFields(field_name)
            field.Orientation = 3  # xlPageField
            field.Position = position

        for position, field_name in enumerate(row_fields, start=1):
            field = pivot_table.PivotFields(field_name)
            field.Orientation = 1  # xlRowField
            field.Position = position

        for position, field_name in enumerate(column_fields, start=1):
            field = pivot_table.PivotFields(field_name)
            field.Orientation = 2  # xlColumnField
            field.Position = position

        value_pivot_field = pivot_table.PivotFields(value_field)
        pivot_table.AddDataField(value_pivot_field, data_caption, agg_function)
        pivot_table.RowGrand = True
        pivot_table.ColumnGrand = True
        ws_pivot.Columns.AutoFit()

        workbook.Save()
        return True, translate("Tabela dinâmica nativa do Excel criada com campos interativos.")
    except Exception as exc:
        return False, translate("Tabela dinâmica nativa do Excel não criada: {exc}", exc=exc)
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=True)
            except Exception:
                log_exception("falha opcional ignorada")
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                log_exception("falha opcional ignorada")


def try_create_native_excel_pivot_with_controller(
    controller: PivotExcelExportController,
    file_path: str,
    layer_df: pd.DataFrame,
    pivot_config: Dict[str, Any],
    *,
    translate,
) -> Tuple[bool, str]:
    return controller.try_create_native_excel_pivot(
        file_path,
        layer_df,
        pivot_config,
        translate=translate,
    )
