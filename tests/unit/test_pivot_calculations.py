from __future__ import annotations

import pandas as pd

from Summarizer.pivot.pivot_calculations import (
    aggregate_series,
    coerce_python_value,
    flatten_pandas_columns,
    normalize_field_token,
    pandas_aggfunc_name,
    resolve_available_field_name,
)


def test_pivot_calculations_normalize_and_resolve_field_names():
    fields = ["Código", "Nome do Município", "valor_total"]

    assert normalize_field_token("  NOME   DO municipio ") == "nome do municipio"
    assert resolve_available_field_name("nome do municipio", fields) == "Nome do Município"
    assert resolve_available_field_name(
        "",
        fields,
        fallback_candidates=["valor_total"],
    ) == "valor_total"


def test_pivot_calculations_coerce_and_aggregate_series():
    assert coerce_python_value("  texto  ") == "texto"
    assert coerce_python_value(None) is None

    series = pd.Series([1, 2, 3, None])
    assert aggregate_series(series, "average") == 2.0
    assert aggregate_series(series, "median") == 2.0
    assert aggregate_series(series, "variance") == 0.6666666666666666
    assert aggregate_series(series, "stddev") == 0.816496580927726
    assert aggregate_series(series.astype(str), "unique") == 3
    assert pandas_aggfunc_name("average") == "mean"


def test_pivot_calculations_flatten_pandas_columns():
    df = pd.DataFrame([["A", 1]], columns=[("Grupo", "Nome"), ("__row_total__", "")])

    flattened = flatten_pandas_columns(df, synthetic_row=True)

    assert list(flattened.columns) == ["Grupo / Nome", "Total"]
