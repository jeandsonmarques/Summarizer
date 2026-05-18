from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from Summarizer.summary_view import summary_layer_io
from Summarizer.summary_view.summary_layer_io import (
    create_layer_from_dataframe,
    format_comparison_values,
    make_unique_field_name,
    map_series_to_variant,
    python_value,
    sanitize_field_name,
    unique_layer_name,
    variant_type_for_series,
)


def test_sanitize_field_name_preserves_existing_rules():
    assert sanitize_field_name("") == "resultado"
    assert sanitize_field_name(" / ") == "resultado"
    assert sanitize_field_name("123 valor total") == "f_123_valor_total"
    assert sanitize_field_name("Campo válido!") == "Campo_válido"
    assert sanitize_field_name("x" * 40) == "x" * 30


def test_make_unique_field_name_uses_existing_names():
    assert make_unique_field_name([], "Campo") == "Campo"
    assert make_unique_field_name(["Campo"], "Campo") == "Campo_2"
    assert make_unique_field_name(["Campo", "Campo_2"], "Campo") == "Campo_3"


def test_unique_layer_name_keeps_qgis_suffix_pattern():
    assert unique_layer_name("", set()) == "Camada_Resultado"
    assert unique_layer_name("Resultado", {"Resultado"}) == "Resultado (2)"
    assert unique_layer_name("Resultado", {"Resultado", "Resultado (2)"}) == "Resultado (3)"


def test_python_value_converts_numpy_and_pandas_values():
    assert python_value(np.int64(4)) == 4
    assert python_value(np.float64(2.5)) == 2.5
    assert python_value(np.bool_(True)) is True
    assert python_value(pd.NaT) is None
    assert python_value(pd.Timestamp("2026-05-18")).year == 2026
    assert python_value("texto") == "texto"


def test_variant_mapping_basic_dtypes_without_qgis():
    assert map_series_to_variant(pd.Series([1, 2])) == summary_layer_io.QVariant.LongLong
    assert map_series_to_variant(pd.Series([1.0, 2.0])) == summary_layer_io.QVariant.Double
    assert variant_type_for_series(pd.Series([True, False])) == summary_layer_io.QVariant.Bool
    assert (
        variant_type_for_series(pd.Series(pd.to_datetime(["2026-05-18"])))
        == summary_layer_io.QVariant.DateTime
    )
    assert variant_type_for_series(pd.Series(["a", "b"])) == summary_layer_io.QVariant.String


def test_format_comparison_values_uses_empty_label():
    assert (
        format_comparison_values(
            [None, "", "ok"],
            lambda value: value not in (None, ""),
        )
        == "(vazio), (vazio), ok"
    )


def test_create_layer_from_dataframe_validates_empty_and_protected_columns():
    layer, error = create_layer_from_dataframe(
        pd.DataFrame(),
        "Resultado",
        with_geometry=False,
    )
    assert layer is None
    assert error == "Nenhum dado disponível para materializar."

    layer, error = create_layer_from_dataframe(
        pd.DataFrame({"__feature_id": [1]}),
        "Resultado",
        with_geometry=False,
    )
    assert layer is None
    assert error == "Nenhuma coluna disponível após proteger os campos internos."


def test_create_layer_from_dataframe_fallback_without_geometry():
    layer, error = create_layer_from_dataframe(
        pd.DataFrame({"valor": [1, 2]}),
        "Resultado",
        with_geometry=True,
        geometry_layer=None,
    )
    assert layer is None
    assert error == "Os dados atuais não possuem geometria disponível."


@pytest.mark.skipif(
    summary_layer_io.QgsVectorLayer is None,
    reason="QGIS not available in this environment.",
)
def test_create_layer_from_dataframe_handles_duplicate_fields_with_qgis():
    df = pd.DataFrame([[1, 2]], columns=["Campo", "Campo"])

    layer, error = create_layer_from_dataframe(df, "Resultado", with_geometry=False)

    assert error is None
    assert layer is not None
    assert [field.name() for field in layer.fields()] == ["Campo", "Campo_2"]
