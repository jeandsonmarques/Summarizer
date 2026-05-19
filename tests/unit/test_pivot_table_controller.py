# ruff: noqa: I001
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_table_controller.py"

spec = importlib.util.spec_from_file_location("pivot_table_controller", MODULE_PATH)
pivot_table_controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pivot_table_controller)


class _Combo:
    def __init__(self, value):
        self._value = value

    def currentData(self):
        return self._value


class _FakePivotWidget:
    def __init__(self, df, *, rows=None, columns=None, metric=None, aggregation="count"):
        self.filtered_df = df.copy()
        self.pivot_df = pd.DataFrame()
        self._current_pivot_request = object()
        self._current_pivot_result = object()
        self.value_field_combo = _Combo(metric)
        self.agg_combo = _Combo(aggregation)
        self.numeric_candidates = ["valor"]
        self._rows = rows or []
        self._columns = columns or []

    def _selected_area_specs(self, area):
        specs = {"row": self._rows, "column": self._columns}
        return specs.get(area, [])

    def _field_name_from_key(self, key):
        return key

    def _aggregate_series(self, series, agg_func):
        if agg_func == "sum":
            return series.sum()
        if agg_func == "min":
            return series.min()
        if agg_func == "max":
            return series.max()
        if agg_func == "unique":
            return series.nunique(dropna=True)
        return series.count()

    def _pandas_aggfunc_name(self, agg_func):
        return {
            "count": "count",
            "sum": "sum",
            "min": "min",
            "max": "max",
            "unique": "nunique",
        }.get(agg_func, "count")

    def _flatten_pandas_columns(self, df, synthetic_row=False):
        df = df.copy()
        flattened = []
        for column in df.columns:
            if isinstance(column, tuple):
                parts = [str(part) for part in column if str(part) and str(part) != "nan"]
                flattened.append(" / ".join(parts) if parts else "Total")
            else:
                flattened.append(str(column))
        df.columns = flattened
        if synthetic_row and "__row_total__" in df.columns:
            df = df.rename(columns={"__row_total__": "Total"})
        return df


def _spec(field_name):
    return SimpleNamespace(field_name=field_name, source_type="attribute")


def test_compute_dataframe_pivot_simple_count():
    widget = _FakePivotWidget(pd.DataFrame({"categoria": ["A", "A", "B"]}))
    pivot_table_controller.compute_dataframe_pivot(widget)
    assert widget.pivot_df.to_dict("records") == [{"Indicador": "Contagem", "Valor": 3}]
    assert widget._current_pivot_request is None
    assert widget._current_pivot_result is None


def test_compute_dataframe_pivot_rows_and_columns_preserves_expected_output():
    df = pd.DataFrame(
        {
            "linha": ["A", "A", "B"],
            "coluna": ["X", "Y", "X"],
            "valor": [10.0, 5.0, 2.0],
        }
    )
    widget = _FakePivotWidget(
        df,
        rows=[_spec("linha")],
        columns=[_spec("coluna")],
        metric="valor",
        aggregation="sum",
    )
    pivot_table_controller.compute_dataframe_pivot(widget)
    assert widget.pivot_df.loc[0].to_dict() == {"linha": "A", "X": 10.0, "Y": 5.0}
    assert widget.pivot_df.loc[1, "linha"] == "B"
    assert widget.pivot_df.loc[1, "X"] == 2.0
    assert pd.isna(widget.pivot_df.loc[1, "Y"])


def test_compute_dataframe_pivot_with_null_values_keeps_count_semantics():
    df = pd.DataFrame({"linha": ["A", "A", "B"], "valor": [1.0, None, None]})
    widget = _FakePivotWidget(df, rows=[_spec("linha")], metric="valor", aggregation="count")
    pivot_table_controller.compute_dataframe_pivot(widget)
    assert widget.pivot_df.to_dict("records") == [
        {"linha": "A", "COUNT(valor)": 1, "% do total": 100.0},
        {"linha": "B", "COUNT(valor)": 0, "% do total": 0.0},
    ]


def test_compute_dataframe_pivot_uses_filtered_dataframe():
    df = pd.DataFrame({"linha": ["A", "B"], "valor": [1, 2]})
    widget = _FakePivotWidget(df[df["linha"] == "B"], rows=[_spec("linha")], aggregation="count")
    pivot_table_controller.compute_dataframe_pivot(widget)
    assert widget.pivot_df.to_dict("records") == [
        {"linha": "B", "COUNT(None)": 1, "% do total": 100.0}
    ]


def test_compute_dataframe_pivot_missing_metric_for_sum_returns_empty_dataframe():
    widget = _FakePivotWidget(pd.DataFrame({"linha": ["A"]}), metric=None, aggregation="sum")
    pivot_table_controller.compute_dataframe_pivot(widget)
    assert widget.pivot_df.empty
