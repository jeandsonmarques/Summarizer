# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import os
import re
from typing import Optional

from ..utils.logging_utils import log_exception

try:
    from qgis.core import QgsProject, QgsVectorLayer
    from qgis.PyQt.QtCore import QSettings
    from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
except Exception:  # pragma: no cover - unit tests run outside QGIS
    QSettings = None
    QFileDialog = None
    QMessageBox = None
    QDialog = object  # type: ignore[assignment]
    QgsProject = None
    QgsVectorLayer = None

try:
    from ..slim_dialogs import slim_get_item
except Exception:  # pragma: no cover - unit tests run outside QGIS
    slim_get_item = None
try:
    from ..walker_dialogs import WalkerMessageBox
    if QMessageBox is not None:
        QMessageBox = WalkerMessageBox
except Exception:  # pragma: no cover - unit tests run outside QGIS
    log_exception("falha opcional ignorada")

MATERIALIZE_BASE_NAME_DEFAULT = "resultado"
MATERIALIZE_TABLE_LABEL = "Tabela (somente atributos)"
MATERIALIZE_MEM_LABEL = "Camada temporaria (memoria)"
MATERIALIZE_GPKG_LABEL = "Salvar como GPKG"
MATERIALIZE_GPKG_TABLE_LABEL = "Salvar como GPKG (tabela)"
MATERIALIZE_DEST_FILTER = "GeoPackage (*.gpkg)"


def normalize_base_name(base_name: Optional[str]) -> str:
    value = (base_name or MATERIALIZE_BASE_NAME_DEFAULT).strip()
    return value or MATERIALIZE_BASE_NAME_DEFAULT


def build_materialize_options(can_use_geometry: bool) -> tuple[list[str], str]:
    options = [MATERIALIZE_TABLE_LABEL]
    gpkg_label = MATERIALIZE_GPKG_LABEL
    if can_use_geometry:
        options.append(MATERIALIZE_MEM_LABEL)
        options.append(gpkg_label)
    else:
        gpkg_label = MATERIALIZE_GPKG_TABLE_LABEL
        options.append(gpkg_label)
    return options, gpkg_label


def build_gpkg_suggested_name(base_name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_\\-]+", "_", normalize_base_name(base_name)).strip("_")
    return sanitized or "resultado"


def build_default_gpkg_path(last_dir: str, base_name: str) -> str:
    suggested_name = build_gpkg_suggested_name(base_name)
    if last_dir:
        return os.path.join(last_dir, f"{suggested_name}.gpkg")
    return f"{suggested_name}.gpkg"


def ensure_gpkg_extension(path: str) -> str:
    if not path.lower().endswith(".gpkg"):
        return path + ".gpkg"
    return path


def materialize_dataframe_dialog(
    host,
    df,
    base_name: str,
    can_use_geometry: bool,
    geometry_layer: Optional[QgsVectorLayer],
    settings_key: str,
    dialog_title: str,
    table_prefix: str,
    memory_prefix: str,
    export_prefix: str,
):
    if QMessageBox is None or QFileDialog is None or slim_get_item is None:
        return

    if df is None or df.empty:
        QMessageBox.information(host, dialog_title, "Nenhum dado disponível para materializar.")
        return

    base_name = normalize_base_name(base_name)
    options, gpkg_label = build_materialize_options(can_use_geometry)

    choice, ok = slim_get_item(
        host,
        dialog_title,
        "Escolha como deseja materializar o resultado atual:",
        options,
        current=0,
    )
    if not ok or not choice:
        return

    if choice.startswith(MATERIALIZE_TABLE_LABEL):
        table_name = host._unique_layer_name(f"{table_prefix} {base_name}".strip())
        layer, error_message = host._create_layer_from_dataframe(
            df,
            table_name,
            with_geometry=False,
        )
        if layer is None:
            QMessageBox.warning(
                host,
                dialog_title,
                error_message or "Não foi possível gerar a tabela.",
            )
            return
        QgsProject.instance().addMapLayer(layer)
        QMessageBox.information(
            host,
            dialog_title,
            f"Tabela '{layer.name()}' criada com {layer.featureCount()} registros.",
        )
        return

    if choice.startswith(MATERIALIZE_MEM_LABEL):
        layer_name = host._unique_layer_name(f"{memory_prefix} {base_name}".strip())
        layer, error_message = host._create_layer_from_dataframe(
            df,
            layer_name,
            with_geometry=True,
            geometry_layer=geometry_layer,
        )
        fallback_note = ""
        fallback_available = all(
            (
                layer is None,
                can_use_geometry,
                error_message,
                "Nenhuma feição" in error_message if error_message else False,
            )
        )
        if fallback_available:
            layer, error_message = host._create_layer_from_dataframe(
                df,
                layer_name,
                with_geometry=False,
                geometry_layer=None,
            )
            if layer is not None:
                fallback_note = (
                    "\n\nAs transformacoes removeram as geometrias. "
                    "Foi criada uma tabela temporaria sem geometria."
                )
        if layer is None:
            QMessageBox.warning(
                host,
                dialog_title,
                error_message or "Não foi possível criar a camada temporária.",
            )
            return
        QgsProject.instance().addMapLayer(layer)
        QMessageBox.information(
            host,
            dialog_title,
            f"Camada '{layer.name()}' criada com {layer.featureCount()} feições.{fallback_note}",
        )
        return

    if choice.startswith(MATERIALIZE_GPKG_LABEL):
        last_dir = ""
        if settings_key and QSettings is not None:
            try:
                last_dir = QSettings().value(settings_key, "", type=str)
            except Exception:
                last_dir = ""
        default_path = build_default_gpkg_path(last_dir, base_name)
        path, _ = QFileDialog.getSaveFileName(
            host,
            "Salvar GeoPackage",
            default_path,
            MATERIALIZE_DEST_FILTER,
        )
        if not path:
            return
        directory = os.path.dirname(path)
        if settings_key and directory and QSettings is not None:
            QSettings().setValue(settings_key, directory)
        path = ensure_gpkg_extension(path)

        with_geometry = can_use_geometry and not choice.endswith("(tabela)")
        export_layer_name = f"{export_prefix} {base_name}".strip() or base_name
        layer, error_message = host._create_layer_from_dataframe(
            df,
            export_layer_name,
            with_geometry=with_geometry,
            geometry_layer=geometry_layer,
        )
        fallback_note = ""
        if layer is None and with_geometry and error_message and "Nenhuma feição" in error_message:
            layer, error_message = host._create_layer_from_dataframe(
                df,
                export_layer_name,
                with_geometry=False,
                geometry_layer=None,
            )
            if layer is not None:
                fallback_note = (
                    "\n\nAs transformacoes removeram as geometrias. "
                    "O arquivo foi salvo apenas com atributos."
                )
        if layer is None:
            QMessageBox.warning(
                host,
                dialog_title,
                error_message or "Não foi possível preparar os dados para exportação.",
            )
            return

        success, writer_message = host._export_layer_to_gpkg(layer, path, export_layer_name)
        if not success:
            QMessageBox.critical(
                host,
                dialog_title,
                writer_message or "Falha ao exportar o GeoPackage.",
            )
            return

        try:
            uri = f"{path}|layername={export_layer_name}"
            exported_layer = QgsVectorLayer(uri, export_layer_name, "ogr")
            if exported_layer and exported_layer.isValid():
                QgsProject.instance().addMapLayer(exported_layer)
        except Exception:
            log_exception("falha opcional ignorada")

        final_message = f"Arquivo GeoPackage salvo em:\n{path}{fallback_note}"
        QMessageBox.information(
            host,
            dialog_title,
            final_message,
        )
