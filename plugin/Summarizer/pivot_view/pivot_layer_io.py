# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

try:
    from qgis.PyQt.QtCore import QVariant
except Exception:  # pragma: no cover - allows pure-python smoke tests

    class _FallbackQVariant:
        Int = "Int"
        UInt = "UInt"
        LongLong = "LongLong"
        ULongLong = "ULongLong"
        Double = "Double"
        Date = "Date"
        DateTime = "DateTime"
        Time = "Time"
        Bool = "Bool"
        String = "String"
        Type = str

    QVariant = _FallbackQVariant()

try:
    from qgis.core import (
        QgsFeature,
        QgsFeatureRequest,
        QgsField,
        QgsFields,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
except Exception:  # pragma: no cover - unit tests patch these symbols directly
    QgsFeature = None
    QgsFeatureRequest = None
    QgsField = None
    QgsFields = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsVectorLayer = None

from ..pivot import coerce_python_value as _pivot_coerce_python_value
from ..pivot import normalize_field_token as _pivot_normalize_field_token
from ..pivot import resolve_available_field_name as _pivot_resolve_available_field_name
from ..utils.logging_utils import log_exception


def sanitize_field_name(value: Any) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value or ""))


def make_unique_field_name(base_name: str, existing_names: Sequence[str]) -> str:
    candidate = str(base_name or "").strip() or "campo"
    existing = {str(name) for name in existing_names}
    if candidate not in existing:
        return candidate
    counter = 2
    while True:
        unique = f"{candidate}_{counter}"
        if unique not in existing:
            return unique
        counter += 1


def unique_layer_name(layer_name: Any) -> str:
    safe_name = sanitize_field_name(layer_name).strip("_")
    return safe_name or "tabela_dinamica"


def python_value(value: Any) -> Any:
    return _pivot_coerce_python_value(value)


def format_comparison_values(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return float(value) if not pd.isna(value) else None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if pd.isna(value):
        return None
    return value


def is_numeric_column(series: pd.Series) -> bool:
    if ptypes.is_numeric_dtype(series):
        return True
    converted = pd.to_numeric(series, errors="coerce")
    return converted.notna().any()


def variant_type_for_series(series: pd.Series) -> QVariant.Type:
    if ptypes.is_bool_dtype(series):
        return QVariant.Bool
    if is_numeric_column(series):
        if ptypes.is_integer_dtype(series):
            return QVariant.LongLong
        return QVariant.Double
    if ptypes.is_datetime64_any_dtype(series):
        return QVariant.DateTime
    return QVariant.String


def map_series_to_variant(series: pd.Series) -> QVariant.Type:
    return variant_type_for_series(series)


def build_geometry_lookup(
    value_field_requested: Any,
    value_field_label: Any,
) -> Tuple[str, str]:
    geometry_token = _pivot_normalize_field_token(value_field_requested or value_field_label)
    if not geometry_token:
        return "", ""
    if "geometry_length" in geometry_token or "comprimento geometrico" in geometry_token:
        return "__geometry_length__", "length"
    if "geometry_area" in geometry_token or "area geometrica" in geometry_token:
        return "__geometry_area__", "area"
    return "", ""


def geometry_from_lookup(feature: Any, geometry_value_name: str, geometry_op: str) -> Any:
    if not geometry_value_name:
        return None
    try:
        geometry = feature.geometry()
        if geometry is not None and not geometry.isEmpty():
            if geometry_op == "area":
                return float(geometry.area())
            return float(geometry.length())
    except Exception:
        return None
    return None


def resolve_layer_field_name(
    layer: Any,
    field_name: Any,
    fallback_candidates: Optional[Sequence[Any]] = None,
) -> str:
    if layer is None:
        return ""
    fields = list(layer.fields())
    layer_field_names = [str(field.name()) for field in fields]
    resolved = _pivot_resolve_available_field_name(
        field_name,
        layer_field_names,
        fallback_candidates=fallback_candidates,
    )
    if resolved:
        return resolved

    alias_map: Dict[str, str] = {}
    for field in fields:
        canonical_name = str(field.name())
        alias = str(field.alias() or "").strip()
        for candidate in (alias, canonical_name):
            token = _pivot_normalize_field_token(candidate)
            if token and token not in alias_map:
                alias_map[token] = canonical_name

    lookup_values: List[Any] = [field_name]
    lookup_values.extend(list(fallback_candidates or []))
    for lookup in lookup_values:
        token = _pivot_normalize_field_token(lookup)
        if token and token in alias_map:
            return alias_map[token]
    return ""


def resolve_current_layer(host: Any):
    metadata = dict(getattr(host, "_current_metadata", {}) or {})
    layer_id = metadata.get("layer_id") or ""
    if layer_id and QgsProject is not None:
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is not None:
            return layer
    layer_name = metadata.get("layer_name") or ""
    if layer_name and QgsProject is not None:
        matches = QgsProject.instance().mapLayersByName(layer_name)
        if matches:
            return matches[0]
    return None


def build_layer_dataframe_from_request(
    host: Any,
    layer: Any,
    request: Any,
    extra_attribute_fields: Optional[List[str]] = None,
) -> pd.DataFrame:
    if layer is None or request is None:
        return pd.DataFrame()

    attribute_fields: List[str] = []

    def _add_attribute_field(name: Any):
        field_name = str(name or "").strip()
        if field_name and field_name not in attribute_fields:
            attribute_fields.append(field_name)

    for spec in list(request.row_fields or []) + list(request.column_fields or []):
        if spec is not None and spec.source_type == "attribute":
            _add_attribute_field(spec.field_name)
    if request.value_field is not None and request.value_field.source_type == "attribute":
        _add_attribute_field(request.value_field.field_name)
    for extra in extra_attribute_fields or []:
        _add_attribute_field(extra)

    layer_field_names = [field.name() for field in list(layer.fields())]
    valid_layer_fields = set(layer_field_names)
    attribute_fields = [name for name in attribute_fields if name in valid_layer_fields]

    geometry_value_name = ""
    geometry_op = ""
    if request.value_field is not None and request.value_field.source_type == "geometry":
        geometry_value_name = str(request.value_field.field_name or "").strip()
        geometry_op = str(request.value_field.geometry_op or "").strip().lower()

    feature_request = QgsFeatureRequest()
    if request.filter_expression:
        feature_request.setFilterExpression(request.filter_expression)
    if attribute_fields:
        try:
            feature_request.setSubsetOfAttributes(attribute_fields, layer.fields())
        except Exception:
            log_exception("falha opcional ignorada")
    if not geometry_value_name:
        try:
            feature_request.setFlags(QgsFeatureRequest.Flag.NoGeometry)
        except Exception:
            log_exception("falha opcional ignorada")

    selected_ids = set()
    if request.only_selected:
        try:
            selected_ids = set(layer.selectedFeatureIds())
        except Exception:
            selected_ids = set()

    row_col_attribute_fields: List[str] = []
    for spec in list(request.row_fields or []) + list(request.column_fields or []):
        if spec is None or spec.source_type != "attribute":
            continue
        name = str(spec.field_name or "").strip()
        if name and name not in row_col_attribute_fields:
            row_col_attribute_fields.append(name)

    records: List[Dict[str, Any]] = []
    for feature in layer.getFeatures(feature_request):
        if selected_ids and int(feature.id()) not in selected_ids:
            continue

        if not request.include_nulls and row_col_attribute_fields:
            has_null_axis_value = False
            for field_name in row_col_attribute_fields:
                try:
                    raw_value = feature[field_name]
                except Exception:
                    raw_value = None
                if python_value(raw_value) is None:
                    has_null_axis_value = True
                    break
            if has_null_axis_value:
                continue

        record: Dict[str, Any] = {}
        for field_name in attribute_fields:
            try:
                raw_value = feature[field_name]
            except Exception:
                raw_value = None
            record[field_name] = python_value(raw_value)

        if geometry_value_name:
            record[geometry_value_name] = geometry_from_lookup(
                feature, geometry_value_name, geometry_op
            )

        records.append(record)

    ordered_columns = list(attribute_fields)
    if geometry_value_name and geometry_value_name not in ordered_columns:
        ordered_columns.append(geometry_value_name)
    if not ordered_columns:
        return pd.DataFrame(records)
    return pd.DataFrame(records, columns=ordered_columns)


def build_layer_dataframe_from_pivot_config(
    host: Any,
    layer: Any,
    pivot_config: Dict[str, Any],
) -> pd.DataFrame:
    if layer is None or not isinstance(pivot_config, dict):
        return pd.DataFrame()

    row_requested = [
        str(value or "").strip()
        for value in (pivot_config.get("row_fields") or [])
        if str(value or "").strip()
    ]
    row_labels = [str(value or "").strip() for value in (pivot_config.get("row_labels") or [])]
    row_fields: List[str] = []
    for index, value in enumerate(row_requested):
        fallback = row_labels[index] if index < len(row_labels) else ""
        resolved = resolve_layer_field_name(layer, value, fallback_candidates=[fallback])
        if resolved and resolved not in row_fields:
            row_fields.append(resolved)

    col_requested = [
        str(value or "").strip()
        for value in (pivot_config.get("column_fields") or [])
        if str(value or "").strip()
    ]
    col_labels = [str(value or "").strip() for value in (pivot_config.get("column_labels") or [])]
    column_fields: List[str] = []
    for index, value in enumerate(col_requested):
        fallback = col_labels[index] if index < len(col_labels) else ""
        resolved = resolve_layer_field_name(layer, value, fallback_candidates=[fallback])
        if resolved and resolved not in column_fields:
            column_fields.append(resolved)

    filter_requested = [
        str(value or "").strip()
        for value in (pivot_config.get("filter_fields") or [])
        if str(value or "").strip()
    ]
    filter_labels = [
        str(value or "").strip() for value in (pivot_config.get("filter_labels") or [])
    ]
    filter_fields: List[str] = []
    for index, value in enumerate(filter_requested):
        fallback = filter_labels[index] if index < len(filter_labels) else ""
        resolved = resolve_layer_field_name(layer, value, fallback_candidates=[fallback])
        if resolved and resolved not in filter_fields:
            filter_fields.append(resolved)

    value_field_requested = str(pivot_config.get("value_field") or "").strip()
    value_field_label = str(pivot_config.get("value_label") or "").strip()
    resolved_value_field = resolve_layer_field_name(
        layer,
        value_field_requested,
        fallback_candidates=[value_field_label],
    )
    geometry_value_name, geometry_op = build_geometry_lookup(
        value_field_requested, value_field_label
    )
    if resolved_value_field:
        geometry_value_name = ""
        geometry_op = ""

    attribute_fields: List[str] = []
    for name in row_fields + column_fields + filter_fields:
        if name and name not in attribute_fields:
            attribute_fields.append(name)
    if resolved_value_field and resolved_value_field not in attribute_fields:
        attribute_fields.append(resolved_value_field)

    feature_request = QgsFeatureRequest()
    filter_expression = str(
        (getattr(host, "_current_metadata", {}) or {}).get("filter_expression") or ""
    ).strip()
    if filter_expression:
        feature_request.setFilterExpression(filter_expression)
    if attribute_fields:
        try:
            feature_request.setSubsetOfAttributes(attribute_fields, layer.fields())
        except Exception:
            log_exception("falha opcional ignorada")
    if not geometry_value_name:
        try:
            feature_request.setFlags(QgsFeatureRequest.Flag.NoGeometry)
        except Exception:
            log_exception("falha opcional ignorada")

    selected_ids = set()
    if bool(pivot_config.get("only_selected")):
        try:
            selected_ids = set(layer.selectedFeatureIds())
        except Exception:
            selected_ids = set()

    include_nulls = bool(pivot_config.get("include_nulls"))
    null_gate_fields = row_fields + column_fields

    records: List[Dict[str, Any]] = []
    for feature in layer.getFeatures(feature_request):
        if selected_ids and int(feature.id()) not in selected_ids:
            continue

        if not include_nulls and null_gate_fields:
            has_null_axis_value = False
            for field_name in null_gate_fields:
                try:
                    raw_value = feature[field_name]
                except Exception:
                    raw_value = None
                if python_value(raw_value) is None:
                    has_null_axis_value = True
                    break
            if has_null_axis_value:
                continue

        record: Dict[str, Any] = {}
        for field_name in attribute_fields:
            try:
                raw_value = feature[field_name]
            except Exception:
                raw_value = None
            record[field_name] = python_value(raw_value)

        if geometry_value_name:
            record[geometry_value_name] = geometry_from_lookup(
                feature, geometry_value_name, geometry_op
            )

        records.append(record)

    if not records:
        return pd.DataFrame(
            columns=attribute_fields + ([geometry_value_name] if geometry_value_name else [])
        )

    ordered_columns = list(attribute_fields)
    if geometry_value_name and geometry_value_name not in ordered_columns:
        ordered_columns.append(geometry_value_name)
    if not ordered_columns:
        return pd.DataFrame(records)
    return pd.DataFrame(records, columns=ordered_columns)


def build_export_layer_dataframe(
    host: Any, pivot_config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    extra_fields: List[str] = []
    if isinstance(pivot_config, dict):
        for key in ("row_fields", "column_fields", "filter_fields"):
            for value in pivot_config.get(key) or []:
                field_name = str(value or "").strip()
                if field_name and field_name not in extra_fields:
                    extra_fields.append(field_name)
        value_field = str(pivot_config.get("value_field") or "").strip()
        if value_field and value_field not in extra_fields:
            extra_fields.append(value_field)
        layer = resolve_current_layer(host)
        if layer is not None:
            layer_df_from_config = build_layer_dataframe_from_pivot_config(
                host, layer, pivot_config
            )
            if not layer_df_from_config.empty:
                return layer_df_from_config

    layer = resolve_current_layer(host)
    request = getattr(host, "_current_pivot_request", None)
    if layer is not None and request is not None:
        layer_df = build_layer_dataframe_from_request(
            host, layer, request, extra_attribute_fields=extra_fields
        )
        if not layer_df.empty:
            return layer_df

    if layer is not None:
        try:
            request = host._build_pivot_request(layer)
            layer_df = build_layer_dataframe_from_request(
                host, layer, request, extra_attribute_fields=extra_fields
            )
            if not layer_df.empty:
                return layer_df
        except Exception:
            log_exception("falha opcional ignorada")

    for candidate in (getattr(host, "filtered_df", None), getattr(host, "raw_df", None)):
        if isinstance(candidate, pd.DataFrame) and not candidate.empty:
            return candidate.copy()
    if isinstance(getattr(host, "filtered_df", None), pd.DataFrame):
        return host.filtered_df.copy()
    if isinstance(getattr(host, "raw_df", None), pd.DataFrame):
        return host.raw_df.copy()
    return pd.DataFrame()


def create_layer_from_dataframe(df: pd.DataFrame, layer_name: Any):
    safe_name = unique_layer_name(layer_name)
    memory_layer = QgsVectorLayer("None", safe_name, "memory")
    provider = memory_layer.dataProvider()

    fields = QgsFields()
    for column in df.columns:
        variant_type = variant_type_for_series(df[column])
        fields.append(QgsField(column, variant_type))
    provider.addAttributes(fields)
    memory_layer.updateFields()

    features = []
    for row in df.itertuples(index=False, name=None):
        feature = QgsFeature()
        feature.setFields(fields)
        attrs = [format_comparison_values(value) for value in row]
        feature.setAttributes(attrs)
        features.append(feature)
    provider.addFeatures(features)
    memory_layer.updateExtents()
    return memory_layer, safe_name


def export_to_gpkg(host: Any, path: str):
    df = getattr(host, "pivot_df", pd.DataFrame())
    layer_name = getattr(host, "_current_metadata", {}).get("layer_name") or "tabela_dinamica"
    memory_layer, safe_name = create_layer_from_dataframe(df, layer_name)

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = safe_name

    transform_context = QgsProject.instance().transformContext()
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        memory_layer,
        path,
        transform_context,
        options,
    )

    if isinstance(result, tuple):
        status = result[0]
        message = result[1] if len(result) > 1 else ""
    else:
        status = result
        message = ""

    if status != QgsVectorFileWriter.WriterError.NoError:
        raise RuntimeError(message or "Falha ao escrever GeoPackage.")


@dataclass
class PivotLayerIoController:
    host: Any

    def build_layer_dataframe_from_request(self, layer, request, extra_attribute_fields=None):
        return build_layer_dataframe_from_request(
            self.host,
            layer,
            request,
            extra_attribute_fields=extra_attribute_fields,
        )

    def build_layer_dataframe_from_pivot_config(self, layer, pivot_config):
        return build_layer_dataframe_from_pivot_config(self.host, layer, pivot_config)

    def build_export_layer_dataframe(self, pivot_config=None):
        return build_export_layer_dataframe(self.host, pivot_config)

    def export_to_gpkg(self, path: str):
        return export_to_gpkg(self.host, path)


__all__ = [
    "PivotLayerIoController",
    "build_export_layer_dataframe",
    "build_geometry_lookup",
    "build_layer_dataframe_from_pivot_config",
    "build_layer_dataframe_from_request",
    "create_layer_from_dataframe",
    "export_to_gpkg",
    "format_comparison_values",
    "geometry_from_lookup",
    "is_numeric_column",
    "make_unique_field_name",
    "map_series_to_variant",
    "python_value",
    "resolve_current_layer",
    "resolve_layer_field_name",
    "sanitize_field_name",
    "unique_layer_name",
    "variant_type_for_series",
]
