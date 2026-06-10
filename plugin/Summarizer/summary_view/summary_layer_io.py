# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import re
from typing import Any, Optional

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

try:
    from qgis.core import (
        Qgis,
        QgsFeature,
        QgsFeatureRequest,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsMessageLog,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
        QgsWkbTypes,
    )
    from qgis.PyQt.QtCore import QVariant
except Exception:  # pragma: no cover - pure helper tests run outside QGIS

    class QVariant:  # type: ignore[no-redef]
        Bool = "Bool"
        LongLong = "LongLong"
        Double = "Double"
        DateTime = "DateTime"
        String = "String"

    QgsFeature = None
    QgsFeatureRequest = None
    QgsField = None
    QgsFields = None
    QgsGeometry = None
    QgsMessageLog = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsVectorLayer = None
    QgsWkbTypes = None
    Qgis = None

PROTECTED_COLUMNS_DEFAULT = {"__feature_id", "__geometry_wkb", "__target_feature_id"}


def map_series_to_variant(series: pd.Series):
    if ptypes.is_integer_dtype(series):
        return QVariant.LongLong
    if ptypes.is_float_dtype(series):
        return QVariant.Double
    if ptypes.is_bool_dtype(series):
        return QVariant.Bool
    if ptypes.is_datetime64_any_dtype(series):
        return QVariant.DateTime
    return QVariant.String


def variant_type_for_series(series: pd.Series):
    try:
        if ptypes.is_bool_dtype(series):
            return QVariant.Bool
        if ptypes.is_integer_dtype(series):
            return QVariant.LongLong
        if ptypes.is_float_dtype(series):
            return QVariant.Double
        if ptypes.is_datetime64_any_dtype(series):
            return QVariant.DateTime
    except Exception:
        pass
    return QVariant.String


def python_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def format_comparison_values(values, is_meaningful_value) -> str:
    formatted = []
    for value in values:
        if not is_meaningful_value(value):
            formatted.append("(vazio)")
        else:
            formatted.append(str(value))
    return ", ".join(formatted)


def sanitize_field_name(raw_name: str) -> str:
    if not raw_name:
        raw_name = "resultado"
    sanitized = re.sub(r"\W+", "_", raw_name).strip("_")
    if not sanitized:
        sanitized = "resultado"
    if sanitized[0].isdigit():
        sanitized = f"f_{sanitized}"
    return sanitized[:30]


def make_unique_field_name(existing_names, base_name: str) -> str:
    sanitized = sanitize_field_name(base_name)
    candidate = sanitized
    counter = 1
    existing = set(existing_names)
    while candidate in existing:
        counter += 1
        candidate = f"{sanitized}_{counter}"
    return candidate


def unique_layer_name(base_name: str, existing_names) -> str:
    base = base_name.strip() if base_name else "Camada_Resultado"
    if not base:
        base = "Camada_Resultado"
    candidate = base
    counter = 1
    while candidate in existing_names:
        counter += 1
        candidate = f"{base} ({counter})"
    return candidate


def build_geometry_lookup(layer, id_series: pd.Series, log_exception=None):
    if QgsFeatureRequest is None:
        return {}
    if layer is None or not layer.isValid():
        return {}
    if id_series is None or id_series.empty:
        return {}
    try:
        unique_ids = id_series.dropna().unique().tolist()
    except Exception:
        return {}
    candidate_ids = []
    for raw in unique_ids:
        if pd.isna(raw):
            continue
        try:
            candidate_ids.append(int(float(raw)))
        except Exception:
            try:
                candidate_ids.append(int(str(raw)))
            except Exception:
                continue
    if not candidate_ids:
        return {}
    lookup = {}
    request = QgsFeatureRequest()
    request.setFilterFids(candidate_ids)
    try:
        for feature in layer.getFeatures(request):
            try:
                lookup[int(feature.id())] = feature.geometry().clone()
            except Exception:
                if log_exception is not None:
                    log_exception("falha opcional ignorada")
    except Exception:
        return {}
    return lookup


def geometry_from_lookup(fid_value, geometry_lookup):
    if QgsGeometry is None:
        return None
    if fid_value is None or pd.isna(fid_value):
        return None
    try:
        fid = int(float(fid_value))
    except Exception:
        try:
            fid = int(str(fid_value))
        except Exception:
            return None
    geometry = geometry_lookup.get(fid)
    if geometry is None:
        return None
    try:
        return geometry.clone()
    except Exception:
        return QgsGeometry(geometry)


def create_layer_from_dataframe(
    df: pd.DataFrame,
    layer_name: str,
    with_geometry: bool,
    geometry_layer: Optional[Any] = None,
    *,
    protected_columns=PROTECTED_COLUMNS_DEFAULT,
    log_exception=None,
):
    if df is None or df.empty:
        return None, "Nenhum dado disponível para materializar."

    display_columns = [c for c in df.columns if c not in protected_columns]
    if not display_columns:
        return None, "Nenhuma coluna disponível após proteger os campos internos."

    geometry_lookup = {}
    geometry_column_available = False
    geom_type = None
    crs_authid = ""

    if with_geometry:
        if "__geometry_wkb" in df.columns:
            try:
                geometry_column_available = df["__geometry_wkb"].notna().any()
            except Exception:
                geometry_column_available = False

        if geometry_layer is not None and geometry_layer.isValid():
            geom_type = QgsWkbTypes.displayString(geometry_layer.wkbType())
            try:
                crs_authid = geometry_layer.crs().authid()
            except Exception:
                crs_authid = ""

        geometry_lookup_available = all(
            (
                "__target_feature_id" in df.columns,
                geometry_layer is not None,
                geometry_layer.isValid() if geometry_layer is not None else False,
            )
        )
        if geometry_lookup_available:
            geometry_lookup = build_geometry_lookup(
                geometry_layer,
                df["__target_feature_id"],
                log_exception,
            )
            if geometry_lookup:
                geometry_column_available = True
                if geom_type is None:
                    geom_type = QgsWkbTypes.displayString(geometry_layer.wkbType())
                    try:
                        crs_authid = geometry_layer.crs().authid()
                    except Exception:
                        crs_authid = ""

        if geom_type is None and geometry_column_available:
            sample_hex = None
            try:
                for raw in df["__geometry_wkb"]:
                    if isinstance(raw, str) and raw:
                        sample_hex = raw
                        break
            except Exception:
                sample_hex = None
            if sample_hex:
                try:
                    sample_geom = QgsGeometry.fromWkb(bytes.fromhex(sample_hex))
                    geom_type = QgsWkbTypes.displayString(sample_geom.wkbType())
                except Exception:
                    geom_type = None

        if not geometry_column_available:
            return None, "Os dados atuais não possuem geometria disponível."
        if geom_type is None:
            return None, "Não foi possível determinar o tipo de geometria."

    if QgsFields is None or QgsField is None or QgsFeature is None or QgsVectorLayer is None:
        return None, "Não foi possível criar a camada em memória."

    qfields = QgsFields()
    existing_names = []
    for column in display_columns:
        try:
            variant = variant_type_for_series(df[column])
        except Exception:
            variant = QVariant.String
        safe_name = make_unique_field_name(existing_names, column)
        qfields.append(QgsField(safe_name, variant))
        existing_names.append(safe_name)

    uri = "None"
    if with_geometry:
        uri = geom_type if not crs_authid else f"{geom_type}?crs={crs_authid}"

    temp_layer = QgsVectorLayer(uri, layer_name, "memory")
    if not temp_layer or not temp_layer.isValid():
        return None, "Não foi possível criar a camada em memória."

    provider = temp_layer.dataProvider()
    if not provider.addAttributes(qfields):
        return None, "Falha ao definir os campos da camada."
    temp_layer.updateFields()

    features = []
    for _, row in df.iterrows():
        feature = QgsFeature(temp_layer.fields())
        if with_geometry:
            geometry = None
            geom_hex = row.get("__geometry_wkb") if "__geometry_wkb" in df.columns else None
            if isinstance(geom_hex, str) and geom_hex:
                try:
                    geometry = QgsGeometry.fromWkb(bytes.fromhex(geom_hex))
                except Exception:
                    geometry = None
            if geometry is None and geometry_lookup:
                geometry = geometry_from_lookup(row.get("__target_feature_id"), geometry_lookup)
            if geometry is None:
                continue
            try:
                feature.setGeometry(geometry)
            except Exception:
                continue
        attrs = []
        for column in display_columns:
            attrs.append(python_value(row[column]))
        feature.setAttributes(attrs)
        features.append(feature)

    if not features:
        return None, "Nenhuma feição gerada a partir dos dados filtrados."

    if not provider.addFeatures(features):
        return None, "Falha ao adicionar as feições na camada."

    temp_layer.updateExtents()
    return temp_layer, None


def export_layer_to_gpkg(layer, path: str, layer_name: str):
    if QgsVectorFileWriter is None or QgsProject is None:
        return False, "Exportação GPKG indisponível fora do QGIS."
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name
    options.fileEncoding = "UTF-8"
    options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
    context = QgsProject.instance().transformContext()
    result = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path, context, options)
    error = result[0] if isinstance(result, (list, tuple)) else result
    message = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else ""
    if error != QgsVectorFileWriter.WriterError.NoError:
        return False, message
    return True, ""


def create_memory_table_from_dataframe(
    df: pd.DataFrame,
    descriptor: dict,
    *,
    unique_layer_name_fn,
    create_layer_from_dataframe_fn,
    add_layer_to_project_fn,
):
    try:
        base_name = (descriptor.get("display_name") or "Tabela externa").strip()
        if not base_name:
            base_name = "Tabela externa"
        layer_name = unique_layer_name_fn(base_name)
        layer, error_message = create_layer_from_dataframe_fn(
            df,
            layer_name,
            with_geometry=False,
            geometry_layer=None,
        )
        if layer is None:
            if error_message and QgsMessageLog is not None and Qgis is not None:
                QgsMessageLog.logMessage(
                    f"Falha ao criar tabela de integração: {error_message}",
                    "Summarizer",
                    Qgis.MessageLevel.Warning,
                )
            return None
        return add_layer_to_project_fn(layer)
    except Exception:
        return None
