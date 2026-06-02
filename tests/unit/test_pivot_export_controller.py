from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_export_controller.py"

spec = importlib.util.spec_from_file_location(
    "Summarizer.pivot_view.pivot_export_controller",
    MODULE_PATH,
)
pivot_export_controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pivot_export_controller)


class _FakeHost:
    EXPORT_FILTERS = "CSV (*.csv);;Excel (*.xlsx);;GeoPackage (*.gpkg)"

    def __init__(self):
        self.pivot_df = pd.DataFrame({"campo": [1]})
        self.pivot_export_df = pd.DataFrame({"pivot": [10]})
        self.layer_export_df = pd.DataFrame({"layer": [20]})
        self.messages = []
        self.exported_csv = []
        self.exported_gpkg = []
        self.exported_excel = []
        self.pivot_config = {
            "row_fields": ["linha"],
            "column_fields": ["coluna"],
            "filter_fields": ["filtro"],
            "value_field": "valor",
            "aggregation": "sum",
        }

    def _build_export_pivot_dataframe(self):
        return self.pivot_export_df

    def _build_export_layer_dataframe(self, pivot_config=None):
        self.exported_excel.append(("layer", pivot_config))
        return self.layer_export_df

    def _export_to_excel_with_layer_data(self, path, pivot_df, layer_df, pivot_config=None):
        self.exported_excel.append((path, pivot_df.copy(), layer_df.copy(), pivot_config))
        return "Tabela nativa criada."

    def _export_to_gpkg(self, path):
        self.exported_gpkg.append(path)

    def get_current_configuration(self):
        return self.pivot_config


def _install_dialog(monkeypatch, result):
    monkeypatch.setattr(
        pivot_export_controller,
        "QFileDialog",
        SimpleNamespace(getSaveFileName=lambda *args, **kwargs: result),
    )


def _capture_messages(monkeypatch, host):
    def _message(widget, title, text):
        host.messages.append((title, text))

    monkeypatch.setattr(pivot_export_controller, "slim_message", _message)


def test_export_format_from_selected_filter_and_extension_helper():
    assert pivot_export_controller.export_format_from_selected_filter("CSV (*.csv)") == (
        "csv",
        ".csv",
    )
    assert pivot_export_controller.export_format_from_selected_filter("Excel (*.xlsx)") == (
        "xlsx",
        ".xlsx",
    )
    assert pivot_export_controller.export_format_from_selected_filter("GeoPackage (*.gpkg)") == (
        "gpkg",
        ".gpkg",
    )
    assert pivot_export_controller.export_format_from_selected_filter("desconhecido") == (
        "gpkg",
        ".gpkg",
    )
    assert pivot_export_controller.ensure_export_extension("saida", ".csv") == "saida.csv"
    assert pivot_export_controller.ensure_export_extension("saida.csv", ".csv") == "saida.csv"
    assert pivot_export_controller.ensure_export_extension("saida.txt", ".csv") == "saida.txt.csv"


def test_export_pivot_table_csv_uses_csv_branch(monkeypatch, tmp_path):
    host = _FakeHost()
    _install_dialog(monkeypatch, (str(tmp_path / "pivot_result"), "CSV (*.csv)"))
    _capture_messages(monkeypatch, host)

    csv_calls = []

    def fake_csv(df, path, *, sep=";"):
        csv_calls.append((df.copy(), path, sep))

    monkeypatch.setattr(pivot_export_controller, "export_dataframe_to_csv", fake_csv)

    controller = pivot_export_controller.PivotExportController(host)
    controller.export_pivot_table()

    assert csv_calls[0][1].endswith(".csv")
    assert csv_calls[0][2] == ";"
    assert host.exported_excel == []
    assert host.exported_gpkg == []
    assert host.messages[-1][1].startswith("Tabela dinâmica exportada para:")


def test_export_pivot_table_xlsx_uses_layer_branch(monkeypatch, tmp_path):
    host = _FakeHost()
    _install_dialog(monkeypatch, (str(tmp_path / "pivot_result"), "Excel (*.xlsx)"))
    _capture_messages(monkeypatch, host)

    controller = pivot_export_controller.PivotExportController(host)
    controller.export_pivot_table()

    assert host.exported_excel
    export_path, pivot_df, layer_df, pivot_config = host.exported_excel[-1]
    assert export_path.endswith(".xlsx")
    assert pivot_df.equals(host.pivot_export_df)
    assert layer_df.equals(host.layer_export_df)
    assert pivot_config == host.pivot_config
    assert host.exported_gpkg == []
    assert host.messages[-1][1].endswith("Tabela nativa criada.")


def test_export_pivot_table_unknown_filter_uses_gpkg(monkeypatch, tmp_path):
    host = _FakeHost()
    _install_dialog(monkeypatch, (str(tmp_path / "pivot_result"), "Formato desconhecido"))
    _capture_messages(monkeypatch, host)

    controller = pivot_export_controller.PivotExportController(host)
    controller.export_pivot_table()

    assert host.exported_gpkg == [str(tmp_path / "pivot_result.gpkg")]
    assert host.messages[-1][1].endswith(str(tmp_path / "pivot_result.gpkg"))
