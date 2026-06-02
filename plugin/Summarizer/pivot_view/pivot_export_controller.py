# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

from typing import Any, Tuple

try:
    from qgis.PyQt.QtWidgets import QFileDialog
except Exception:  # pragma: no cover - unit tests run outside QGIS
    QFileDialog = None

try:
    from ..slim_dialogs import slim_message
except Exception:  # pragma: no cover - unit tests run outside QGIS
    slim_message = None

from ..pivot.pivot_export import export_dataframe_to_csv


def export_format_from_selected_filter(selected_filter: str) -> Tuple[str, str]:
    lowered = (selected_filter or "").lower()
    if "csv" in lowered:
        return "csv", ".csv"
    if "xlsx" in lowered:
        return "xlsx", ".xlsx"
    return "gpkg", ".gpkg"


def ensure_export_extension(path: str, extension: str) -> str:
    if not path.lower().endswith(extension.lower()):
        return path + extension
    return path


def _show_message(widget: Any, title: str, text: str) -> None:
    if callable(slim_message):
        slim_message(widget, title, text)


class PivotExportController:
    def __init__(self, host):
        self.host = host

    def export_pivot_table(self):
        if self.host.pivot_df is None or self.host.pivot_df.empty:
            _show_message(
                self.host,
                "Exportar tabela dinâmica",
                "Não há dados para exportar.",
            )
            return

        if QFileDialog is None:
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self.host,
            "Exportar tabela dinâmica",
            "",
            self.host.EXPORT_FILTERS,
        )
        if not path:
            return

        pivot_export_df = self.host._build_export_pivot_dataframe()
        success_note = ""

        try:
            export_kind, extension = export_format_from_selected_filter(selected_filter)
            path = ensure_export_extension(path, extension)
            if export_kind == "csv":
                export_dataframe_to_csv(pivot_export_df, path, sep=";")
            elif export_kind == "xlsx":
                pivot_config = self.host.get_current_configuration()
                layer_export_df = self.host._build_export_layer_dataframe(
                    pivot_config=pivot_config
                )
                native_note = self.host._export_to_excel_with_layer_data(
                    path,
                    pivot_export_df,
                    layer_export_df,
                    pivot_config=pivot_config,
                )
                success_note = "\nAbas geradas: Tabela_Dinamica e Dados_Camada."
                if native_note:
                    success_note += f"\n{native_note}"
            else:
                self.host._export_to_gpkg(path)
        except Exception as exc:
            _show_message(
                self.host,
                "Exportar tabela dinâmica",
                f"Falha ao exportar a tabela dinâmica: {exc}",
            )
            return

        _show_message(
            self.host,
            "Exportar tabela dinâmica",
            f"Tabela dinâmica exportada para:\n{path}{success_note}",
        )


def export_pivot_table(widget):
    PivotExportController(widget).export_pivot_table()
