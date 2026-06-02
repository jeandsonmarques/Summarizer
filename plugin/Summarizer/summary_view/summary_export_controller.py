# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Mapping

try:
    from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
except Exception:  # pragma: no cover - unit tests run outside QGIS
    QFileDialog = None
    QMessageBox = None
try:
    from ..walker_dialogs import WalkerMessageBox
    if QMessageBox is not None:
        QMessageBox = WalkerMessageBox
except Exception:  # pragma: no cover - unit tests run outside QGIS
    pass
try:
    from ..utils.i18n_runtime import tr_text as _rt
except Exception:  # pragma: no cover

    def _rt(text: str, **kwargs) -> str:
        return str(text).format(**kwargs) if kwargs else str(text)

TIMESTAMP_PATTERN = re.compile(r"_\d{8}_\d{6}$")


def strip_existing_timestamp(base_path: str) -> str:
    if TIMESTAMP_PATTERN.search(base_path):
        return TIMESTAMP_PATTERN.sub("", base_path)
    return base_path


def normalize_filename_component(value: str) -> str:
    if not value:
        return ""
    normalized = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return normalized.strip("_")


def build_default_export_basename(summary_data: Mapping[str, Any]) -> str:
    metadata = summary_data.get("metadata", {}) if summary_data else {}
    layer_part = normalize_filename_component(metadata.get("layer_name", ""))
    field_part = normalize_filename_component(metadata.get("field_name", ""))
    parts = [part for part in (layer_part, field_part) if part]
    return "_".join(parts) if parts else "resumo_summarizer"


def current_export_format(
    export_formats: Mapping[str, Mapping[str, str]],
    current_text: str,
) -> Mapping[str, str]:
    if current_text in export_formats:
        return export_formats[current_text]
    return next(iter(export_formats.values()))


class SummaryExportController:
    def __init__(self, host):
        self.host = host

    def current_export_format(self):
        text = self.host.ui.export_format_combo.currentText()
        return current_export_format(self.host.export_formats, text)

    def strip_existing_timestamp(self, base_path: str) -> str:
        return strip_existing_timestamp(base_path)

    def normalize_filename_component(self, value: str) -> str:
        return normalize_filename_component(value)

    def build_default_export_basename(self, summary_data):
        return build_default_export_basename(summary_data)

    def set_export_path(self, path: str):
        base, ext = os.path.splitext(path)
        base = strip_existing_timestamp(base)
        sanitized = base + ext
        self.host._export_base_path = base
        self.host._updating_export_path = True
        self.host.ui.export_path_edit.setText(sanitized)
        self.host._updating_export_path = False

    def prepare_export_tab_defaults(self, summary_data):
        if not summary_data:
            return
        format_info = self.current_export_format()
        base_name = build_default_export_basename(summary_data)
        suggested_dir = self.host.export_manager.export_dir
        suggested_path = os.path.join(suggested_dir, base_name + format_info["extension"])
        self.set_export_path(suggested_path)

    def on_export_format_changed(self):
        format_info = self.current_export_format()
        if self.host._export_base_path:
            self.set_export_path(self.host._export_base_path + format_info["extension"])
        elif self.host.current_summary_data:
            self.prepare_export_tab_defaults(self.host.current_summary_data)

    def on_export_path_edited(self):
        if self.host._updating_export_path:
            return
        path = self.host.ui.export_path_edit.text().strip()
        if not path:
            self.host._export_base_path = ""
            return

        base, _ = os.path.splitext(path)
        base = strip_existing_timestamp(base)
        format_info = self.current_export_format()
        self.set_export_path(base + format_info["extension"])

    def choose_export_path(self):
        if QFileDialog is None:
            return False

        format_info = self.current_export_format()
        initial_path = self.host.ui.export_path_edit.text().strip()
        if not initial_path:
            initial_path = os.path.join(self.host.export_manager.export_dir, "")

        file_path, _ = QFileDialog.getSaveFileName(
            self.host,
            _rt("Selecionar arquivo"),
            initial_path,
            format_info["filter"],
        )

        if file_path:
            base, _ = os.path.splitext(file_path)
            base = strip_existing_timestamp(base)
            self.set_export_path(base + format_info["extension"])
            return True
        return False

    def export_results(self):
        if QMessageBox is None:
            return

        if not self.host.current_summary_data:
            QMessageBox.warning(self.host, _rt("Aviso"), _rt("Gere um resumo primeiro!"))
            self.host.open_export_tab()
            return

        format_info = self.current_export_format()
        target_path = self.host.ui.export_path_edit.text().strip()

        if not target_path:
            if not self.host.choose_export_path():
                QMessageBox.warning(
                    self.host, _rt("Aviso"), _rt("Selecione o arquivo de destino para exportar.")
                )
                return
            target_path = self.host.ui.export_path_edit.text().strip()

        base, _ = os.path.splitext(target_path)
        base = strip_existing_timestamp(base)

        if self.host.ui.export_include_timestamp_check.isChecked():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = f"{base}_{stamp}{format_info['extension']}"
        else:
            export_path = base + format_info["extension"]

        try:
            self.host.export_manager.export_data(
                self.host.current_summary_data, export_path, format_info["filter"]
            )
            QMessageBox.information(self.host, _rt("Sucesso"), _rt("Dados exportados para:") + f"\n{export_path}")
            self.set_export_path(base + format_info["extension"])
        except Exception as exc:
            QMessageBox.critical(self.host, _rt("Erro"), _rt("Erro na exportação: {exc}", exc=exc))

