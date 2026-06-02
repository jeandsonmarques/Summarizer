from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_layer_io.py"

spec = importlib.util.spec_from_file_location(
    "Summarizer.pivot_view.pivot_layer_io",
    MODULE_PATH,
)
pivot_layer_io = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = pivot_layer_io
spec.loader.exec_module(pivot_layer_io)


class _FakeGeometry:
    def __init__(self, *, area=0.0, length=0.0, empty=False):
        self._area = area
        self._length = length
        self._empty = empty

    def isEmpty(self):
        return self._empty

    def area(self):
        return self._area

    def length(self):
        return self._length


class _FakeField:
    def __init__(self, name, alias=""):
        self._name = name
        self._alias = alias

    def name(self):
        return self._name

    def alias(self):
        return self._alias


class _FakeFeature:
    def __init__(self, fid=0, values=None, geometry=None):
        self._fid = fid
        self._values = values or {}
        self._geometry = geometry or _FakeGeometry()
        self.fields = None
        self.attrs = None

    def id(self):
        return self._fid

    def __getitem__(self, key):
        return self._values.get(key)

    def geometry(self):
        return self._geometry

    def setFields(self, fields):
        self.fields = list(fields)

    def setAttributes(self, attrs):
        self.attrs = list(attrs)


class _FakeFeatureRequest:
    NoGeometry = 1

    def __init__(self):
        self.filter_expression = ""
        self.subset_attributes = None
        self.flags = None

    def setFilterExpression(self, expression):
        self.filter_expression = expression

    def setSubsetOfAttributes(self, attributes, fields):
        self.subset_attributes = list(attributes)

    def setFlags(self, flags):
        self.flags = flags


class _FakeLayer:
    def __init__(self, fields, features, selected_ids=None):
        self._fields = [_FakeField(name, alias) for name, alias in fields]
        self._features = features
        self._selected_ids = list(selected_ids or [])
        self.last_request = None

    def fields(self):
        return list(self._fields)

    def selectedFeatureIds(self):
        return list(self._selected_ids)

    def getFeatures(self, request):
        self.last_request = request
        return iter(self._features)


class _FakeFieldDef:
    def __init__(self, name, variant_type):
        self.name = name
        self.variant_type = variant_type


class _FakeFields(list):
    pass


class _FakeProvider:
    def __init__(self):
        self.added_fields = None
        self.added_features = None

    def addAttributes(self, fields):
        self.added_fields = list(fields)

    def addFeatures(self, features):
        self.added_features = list(features)


class _FakeVectorLayer:
    def __init__(self, geometry_type, name, provider_name):
        self.geometry_type = geometry_type
        self.name = name
        self.provider_name = provider_name
        self.provider = _FakeProvider()
        self.extents_updated = False

    def dataProvider(self):
        return self.provider

    def updateFields(self):
        return None

    def updateExtents(self):
        self.extents_updated = True


class _FakeProject:
    @staticmethod
    def instance():
        return SimpleNamespace(transformContext=lambda: "ctx")


class _FakeWriter:
    NoError = 0
    captured = None

    class SaveVectorOptions:
        def __init__(self):
            self.driverName = ""
            self.layerName = ""

    @staticmethod
    def writeAsVectorFormatV3(memory_layer, path, transform_context, options):
        _FakeWriter.captured = {
            "memory_layer": memory_layer,
            "path": path,
            "transform_context": transform_context,
            "options": options,
        }
        return _FakeWriter.NoError


def _spec(name, source_type="attribute", geometry_op=""):
    return SimpleNamespace(field_name=name, source_type=source_type, geometry_op=geometry_op)


def _install_fake_qgis(monkeypatch):
    monkeypatch.setattr(pivot_layer_io, "QgsFeatureRequest", _FakeFeatureRequest)
    monkeypatch.setattr(pivot_layer_io, "QgsFields", _FakeFields)
    monkeypatch.setattr(pivot_layer_io, "QgsField", _FakeFieldDef)
    monkeypatch.setattr(pivot_layer_io, "QgsFeature", _FakeFeature)
    monkeypatch.setattr(pivot_layer_io, "QgsVectorLayer", _FakeVectorLayer)
    monkeypatch.setattr(pivot_layer_io, "QgsProject", _FakeProject)
    monkeypatch.setattr(pivot_layer_io, "QgsVectorFileWriter", _FakeWriter)


def test_layer_io_helpers_cover_names_and_variants():
    assert pivot_layer_io.sanitize_field_name("Camada A/Valor") == "Camada_A_Valor"
    assert pivot_layer_io.make_unique_field_name("campo", ["campo"]) == "campo_2"
    assert pivot_layer_io.unique_layer_name("Camada A/Valor") == "Camada_A_Valor"
    assert pivot_layer_io.format_comparison_values(np.nan) is None
    assert pivot_layer_io.format_comparison_values(np.float64(2.5)) == 2.5
    assert pivot_layer_io.format_comparison_values(np.int64(4)) == 4
    assert pivot_layer_io.build_geometry_lookup("Comprimento Geométrico", "") == (
        "__geometry_length__",
        "length",
    )
    assert pivot_layer_io.build_geometry_lookup("Área Geométrica", "") == (
        "__geometry_area__",
        "area",
    )
    assert (
        pivot_layer_io.variant_type_for_series(pd.Series([1, 2]))
        == pivot_layer_io.QVariant.LongLong
    )
    assert (
        pivot_layer_io.variant_type_for_series(pd.Series([1.5, 2.5]))
        == pivot_layer_io.QVariant.Double
    )
    assert (
        pivot_layer_io.variant_type_for_series(pd.Series([True, False]))
        == pivot_layer_io.QVariant.Bool
    )


def test_build_layer_dataframe_from_request_deduplicates_and_skips_missing(monkeypatch):
    _install_fake_qgis(monkeypatch)
    features = [
        _FakeFeature(1, {"linha": "A", "coluna": "X", "valor": 10}),
        _FakeFeature(2, {"linha": "B", "coluna": "Y", "valor": 20}),
    ]
    layer = _FakeLayer(
        [("linha", ""), ("coluna", ""), ("valor", "")],
        features,
    )
    request = SimpleNamespace(
        row_fields=[_spec("linha"), _spec("linha")],
        column_fields=[_spec("coluna")],
        value_field=_spec("valor"),
        filter_expression="1=1",
        only_selected=False,
        include_nulls=True,
    )

    df = pivot_layer_io.build_layer_dataframe_from_request(
        SimpleNamespace(),
        layer,
        request,
        extra_attribute_fields=["valor", "nao_existe"],
    )

    assert list(df.columns) == ["linha", "coluna", "valor"]
    assert df.to_dict("records") == [
        {"linha": "A", "coluna": "X", "valor": 10},
        {"linha": "B", "coluna": "Y", "valor": 20},
    ]
    assert layer.last_request.filter_expression == "1=1"
    assert layer.last_request.subset_attributes == ["linha", "coluna", "valor"]


def test_build_layer_dataframe_from_pivot_config_ignores_missing_fields_and_geometry_fallback(
    monkeypatch,
):
    _install_fake_qgis(monkeypatch)
    features = [_FakeFeature(1, {"valor": 99}, _FakeGeometry(length=7.5))]
    layer = _FakeLayer([("valor", "")], features)
    config = {
        "row_fields": ["inexistente"],
        "row_labels": ["Inexistente"],
        "column_fields": [],
        "filter_fields": [],
        "value_field": "Comprimento Geométrico",
        "value_label": "Comprimento Geométrico",
        "include_nulls": True,
    }

    df = pivot_layer_io.build_layer_dataframe_from_pivot_config(
        SimpleNamespace(_current_metadata={}), layer, config
    )

    assert list(df.columns) == ["__geometry_length__"]
    assert df.iloc[0]["__geometry_length__"] == 7.5


def test_export_to_gpkg_uses_sanitized_layer_name_and_formatting(monkeypatch):
    _install_fake_qgis(monkeypatch)
    host = SimpleNamespace(
        pivot_df=pd.DataFrame(
            {
                "Valor": [1.5, np.nan],
                "Texto": [" A ", "B"],
                "Inteiro": [1, 2],
            }
        ),
        _current_metadata={"layer_name": "Camada A/1"},
    )

    pivot_layer_io.export_to_gpkg(host, "saida.gpkg")

    writer = _FakeWriter.captured
    assert writer["path"] == "saida.gpkg"
    assert writer["options"].driverName == "GPKG"
    assert writer["options"].layerName == "Camada_A_1"
    assert writer["memory_layer"].name == "Camada_A_1"
    assert [field.name for field in writer["memory_layer"].provider.added_fields] == [
        "Valor",
        "Texto",
        "Inteiro",
    ]
    assert writer["memory_layer"].provider.added_features[0].attrs == [1.5, " A ", 1]
    assert writer["memory_layer"].provider.added_features[1].attrs == [None, "B", 2]
