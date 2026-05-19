from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_excel_export.py"

spec = importlib.util.spec_from_file_location(
    "Summarizer.pivot_view.pivot_excel_export",
    MODULE_PATH,
)
pivot_excel_export = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pivot_excel_export)


def _translate(text, **kwargs):
    return text.format(**kwargs) if kwargs else text


def _resolve_field(value, available_fields, fallback_candidates=None):
    candidates = [str(value or "").strip()]
    candidates.extend(str(candidate or "").strip() for candidate in (fallback_candidates or []))
    normalized = {field.lower(): field for field in available_fields}
    for candidate in candidates:
        if not candidate:
            continue
        resolved = normalized.get(candidate.lower())
        if resolved:
            return resolved
    return None


def test_native_excel_helpers_cover_aggregation_caption_and_field_resolution():
    assert pivot_excel_export.native_excel_aggregation_code("sum") == -4157
    assert pivot_excel_export.native_excel_aggregation_code("unknown") == -4112
    assert (
        pivot_excel_export.build_native_excel_data_caption("sum", "Valor", "Soma")
        == "Soma de Valor"
    )
    assert (
        pivot_excel_export.build_native_excel_data_caption("count", "Valor", "COUNT")
        == "Contagem de Valor"
    )
    assert pivot_excel_export.resolve_native_excel_fields(
        ["Linha", "Linha", "Outra"],
        ["Fallback 1", "Fallback 2", "Fallback 3"],
        ["Linha", "Outra"],
        _resolve_field,
    ) == ["Linha", "Outra"]


def test_try_create_native_excel_pivot_without_win32_returns_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "win32com", None)
    monkeypatch.setitem(sys.modules, "win32com.client", None)

    success, message = pivot_excel_export.try_create_native_excel_pivot(
        "saida.xlsx",
        pd.DataFrame({"Linha": [1]}),
        {"aggregation": "sum"},
        translate=_translate,
        resolve_available_field_name=_resolve_field,
    )

    assert success is False
    assert "pywin32/Excel não disponível" in message


def test_try_create_native_excel_pivot_success_uses_expected_excel_structure(monkeypatch):
    calls = []

    class _FakeField:
        def __init__(self, name):
            self.name = name
            self.Orientation = None
            self.Position = None

    class _FakePivotTable:
        def __init__(self):
            self.fields = {}
            self.added = None
            self.RowGrand = False
            self.ColumnGrand = False

        def PivotFields(self, name):
            field = self.fields.setdefault(name, _FakeField(name))
            return field

        def AddDataField(self, field, caption, agg_function):
            self.added = (field.name, caption, agg_function)

    class _FakeWorksheet:
        def __init__(self, name, workbook):
            self.Name = name
            self.workbook = workbook
            self.deleted = False
            self.autofit = False
            self.Columns = SimpleNamespace(AutoFit=self._autofit)
            self.UsedRange = SimpleNamespace(
                Rows=SimpleNamespace(Count=3),
                Columns=SimpleNamespace(Count=3),
            )

        def _autofit(self):
            self.autofit = True

        def Delete(self):
            self.deleted = True

        def Range(self, start, end):
            return SimpleNamespace(start=start, end=end)

        def Cells(self, row, column):
            return SimpleNamespace(row=row, column=column)

        def PivotTables(self, name):
            calls.append(("PivotTables", name))
            return self.workbook.pivot_table

    class _FakeWorksheets:
        def __init__(self, workbook):
            self.workbook = workbook
            self.sheets = {
                "Dados_Camada": _FakeWorksheet("Dados_Camada", workbook),
                "Tabela_Dinamica": _FakeWorksheet("Tabela_Dinamica", workbook),
                "Resumo_Pivot": _FakeWorksheet("Resumo_Pivot", workbook),
            }

        def __call__(self, name):
            return self.sheets[name]

        def Add(self):
            sheet = _FakeWorksheet("Nova", self.workbook)
            self.sheets["Tabela_Dinamica"] = sheet
            return sheet

    class _FakePivotCache:
        def __init__(self, workbook):
            self.workbook = workbook

        def CreatePivotTable(self, TableDestination, TableName):
            calls.append(("CreatePivotTable", TableDestination, TableName))
            self.workbook.pivot_table = _FakePivotTable()

    class _FakePivotCaches:
        def __init__(self, workbook):
            self.workbook = workbook

        def Create(self, SourceType, SourceData):
            calls.append(("CreateCache", SourceType, SourceData))
            return _FakePivotCache(self.workbook)

    class _FakeWorkbook:
        def __init__(self):
            self.pivot_table = _FakePivotTable()
            self.Worksheets = _FakeWorksheets(self)
            self.PivotCaches = lambda: _FakePivotCaches(self)
            self.saved = False
            self.closed = False

        def Save(self):
            self.saved = True

        def Close(self, SaveChanges=True):
            self.closed = SaveChanges

    class _FakeExcel:
        def __init__(self):
            self.Visible = None
            self.DisplayAlerts = None
            self.Workbooks = SimpleNamespace(Open=self._open)
            self.quit = False
            self.workbook = _FakeWorkbook()

        def _open(self, file_path):
            calls.append(("Open", file_path))
            return self.workbook

        def Quit(self):
            self.quit = True

    fake_client = SimpleNamespace(DispatchEx=lambda app: _FakeExcel())
    fake_win32 = SimpleNamespace(client=fake_client)
    monkeypatch.setitem(sys.modules, "win32com", fake_win32)
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)

    success, message = pivot_excel_export.try_create_native_excel_pivot(
        "saida.xlsx",
        pd.DataFrame({"Linha": [1], "Valor": [2]}),
        {
            "row_fields": ["Linha"],
            "column_fields": [],
            "filter_fields": [],
            "value_field": "Valor",
            "aggregation": "sum",
            "aggregation_label": "Soma",
        },
        translate=_translate,
        resolve_available_field_name=_resolve_field,
    )

    assert success is True
    assert message == "Tabela dinâmica nativa do Excel criada com campos interativos."
    assert ("Open", "saida.xlsx") in calls

