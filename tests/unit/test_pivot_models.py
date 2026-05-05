from __future__ import annotations

from Summarizer.pivot.pivot_models import PivotExportSpec, PivotFieldResolution


def test_pivot_models_defaults_are_safe():
    field = PivotFieldResolution(requested="Nome", resolved="Nome do Município")
    spec = PivotExportSpec(file_path="saida.xlsx")

    assert field.requested == "Nome"
    assert field.resolved == "Nome do Município"
    assert spec.sheet_name == "Pivot"
    assert spec.row_fields == []
    assert spec.metadata == {}
