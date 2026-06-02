# ruff: noqa: I001,E402
from __future__ import annotations

import pytest

qgis = pytest.importorskip("qgis", reason="QGIS not available in this environment.")

import pandas as pd  # noqa: E402
from qgis.PyQt.QtCore import Qt  # noqa: E402

from Summarizer.pivot_view.pivot_field_panel import (  # noqa: E402
    build_field_drag_payload,
    build_attribute_field_spec,
    detect_numeric_candidates,
    field_matches_filter,
    geometry_field_specs_for_layer,
)


class DummyItem:
    def __init__(self, text, spec_key=None):
        self._text = text
        self._spec_key = spec_key

    def text(self):
        return self._text

    def data(self, role):
        if role == Qt.UserRole:
            return self._spec_key
        return None


def test_field_drag_payload_skips_empty_items():
    payload = build_field_drag_payload(
        [
            DummyItem("Campo A", "attribute:campo_a:"),
            DummyItem("Placeholder"),
        ]
    )
    assert payload == [{"spec_key": "attribute:campo_a:", "text": "Campo A"}]


def test_field_filter_matches_current_label_rules():
    assert field_matches_filter("Valor Total", "valor")
    assert field_matches_filter("Valor Total", "")
    assert not field_matches_filter("Valor Total", "abc")


def test_numeric_candidate_detection_uses_predicate():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"], "c": [3.2, None]})
    result = detect_numeric_candidates(
        df,
        lambda series: pd.api.types.is_numeric_dtype(series) or series.notna().any(),
    )
    assert result == ["a", "b", "c"]


def test_attribute_field_spec_falls_back_to_dataframe_dtype():
    df = pd.DataFrame({"valor": [1.0, 2.5], "texto": ["a", "b"]})
    widget = type(
        "W",
        (),
        {
            "_map_variant_to_data_type": lambda self, value: "text",
            "_is_numeric_column": lambda self, series: pd.api.types.is_numeric_dtype(series),
        },
    )()
    spec = build_attribute_field_spec(
        widget=widget,
        field_name="valor",
        layer=None,
        df=df,
    )
    assert spec.field_name == "valor"
    assert spec.data_type == "numeric"


def test_geometry_field_specs_returns_empty_for_unknown_layer():
    class DummyLayer:
        def geometryType(self):
            return None

    assert geometry_field_specs_for_layer(DummyLayer()) == []
