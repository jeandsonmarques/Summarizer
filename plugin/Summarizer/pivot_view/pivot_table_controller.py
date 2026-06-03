# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _log_optional_exception(widget: Any) -> None:
    callback = getattr(widget, "_log_optional_exception", None)
    if callable(callback):
        callback()


def compute_dataframe_pivot(widget: Any) -> None:
    self = widget
    df = self.filtered_df
    self._current_pivot_request = None
    self._current_pivot_result = None
    if df is None or df.empty:
        self.pivot_df = pd.DataFrame()
        return

    metric_key = self.value_field_combo.currentData()
    row_specs = self._selected_area_specs("row")
    col_specs = self._selected_area_specs("column")
    agg_func = self.agg_combo.currentData()
    metric = self._field_name_from_key(metric_key)
    row_fields = [spec.field_name for spec in row_specs if spec.source_type == "attribute"]
    col_fields = [spec.field_name for spec in col_specs if spec.source_type == "attribute"]

    if metric is None and agg_func != "count":
        self.pivot_df = pd.DataFrame()
        return

    metric_needs_numeric = all(
        (
            metric is not None,
            agg_func not in {"count", "min", "max", "unique"},
            metric not in self.numeric_candidates,
        )
    )
    if metric_needs_numeric:
        try:
            df[metric] = pd.to_numeric(df[metric], errors="coerce")
        except Exception:
            _log_optional_exception(self)

    if not row_fields and not col_fields:
        if metric is None:
            self.pivot_df = pd.DataFrame({"Indicador": ["Contagem"], "Valor": [len(df.index)]})
            return
        series = df[metric]
        if agg_func == "count":
            value = series.count()
        else:
            value = self._aggregate_series(series, agg_func)
        self.pivot_df = pd.DataFrame({"Indicador": [metric], "Valor": [value]})
        return

    working = df.copy()
    synthetic_row = False
    if not row_fields:
        working["__row_total__"] = "Total"
        row_fields = ["__row_total__"]
        synthetic_row = True

    if col_fields:
        if metric is None and agg_func == "count":
            pivot = pd.crosstab(
                index=[working[field] for field in row_fields]
                if len(row_fields) > 1
                else working[row_fields[0]],
                columns=[working[field] for field in col_fields]
                if len(col_fields) > 1
                else working[col_fields[0]],
                dropna=False,
            )
        else:
            values = None if metric is None else metric
            values_need_numeric = all(
                (
                    values is not None,
                    agg_func not in {"count", "min", "max", "unique"},
                    values not in self.numeric_candidates,
                )
            )
            if values_need_numeric:
                try:
                    working[values] = pd.to_numeric(working[values], errors="coerce")
                except Exception:
                    _log_optional_exception(self)
            pivot = pd.pivot_table(
                working,
                index=row_fields,
                columns=col_fields,
                values=values,
                aggfunc="size"
                if metric is None and agg_func == "count"
                else self._pandas_aggfunc_name(agg_func),
                dropna=False,
            )
        pivot = pivot.reset_index()
        pivot = self._flatten_pandas_columns(pivot, synthetic_row=synthetic_row)
        if agg_func != "count":
            def round_float(value):
                return round(value, 2) if isinstance(value, (float, np.floating)) else value

            pivot = (
                pivot.map(round_float)
                if hasattr(pivot, "map")
                else pivot.applymap(round_float)
            )
        self.pivot_df = pivot
        return

    if metric is None:
        grouped = working.groupby(row_fields, dropna=False).size()
    else:
        grouped = working.groupby(row_fields, dropna=False)[metric].agg(
            self._pandas_aggfunc_name(agg_func)
        )
    pivot = grouped.reset_index()
    header = f"{agg_func.upper()}({metric})" if agg_func != "count" else f"COUNT({metric})"
    pivot.columns = row_fields + [header]
    if synthetic_row and row_fields:
        pivot = pivot.rename(columns={"__row_total__": "Total"})
        row_fields = ["Total"]
        header = pivot.columns[-1]
    if agg_func != "count":
        pivot[header] = pivot[header].round(2)
    if agg_func in ("sum", "count"):
        total = pivot[header].sum()
        if total:
            pivot["% do total"] = (pivot[header] / total * 100).round(2)
    pivot = pivot.sort_values(by=header, ascending=False).reset_index(drop=True)
    self.pivot_df = pivot


def compute_layer_backed_pivot(
    widget: Any,
    layer: Any,
    *,
    pivot_validation_error: type,
    translate,
) -> None:
    self = widget
    try:
        request = self._build_pivot_request(layer)
        self._current_pivot_request = request
        self._current_pivot_result = self.pivot_engine.execute(request)
        self.pivot_df = self._pivot_result_to_dataframe(self._current_pivot_result)
        self.status_label.setText("")
    except pivot_validation_error as exc:
        self._current_pivot_result = None
        self.pivot_df = pd.DataFrame()
        self.status_label.setText(str(exc))
    except Exception as exc:
        self._current_pivot_result = None
        self.pivot_df = pd.DataFrame()
        self.status_label.setText(translate("Falha ao calcular a pivot: {exc}", exc=exc))
