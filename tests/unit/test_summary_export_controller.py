from __future__ import annotations

from Summarizer.summary_view.summary_export_controller import (
    build_default_export_basename,
    current_export_format,
    normalize_filename_component,
    strip_existing_timestamp,
)

EXPORT_FORMATS = {
    "Excel (.xlsx)": {"filter": "Excel (*.xlsx)", "extension": ".xlsx"},
    "CSV (.csv)": {"filter": "CSV (*.csv)", "extension": ".csv"},
    "PDF (.pdf)": {"filter": "PDF (*.pdf)", "extension": ".pdf"},
    "JSON (.json)": {"filter": "JSON (*.json)", "extension": ".json"},
}


def test_strip_existing_timestamp_removes_only_final_timestamp():
    assert strip_existing_timestamp("saida_20260518_143000") == "saida"
    assert strip_existing_timestamp("saida_20260518_143000_extra") == "saida_20260518_143000_extra"
    assert strip_existing_timestamp("saida") == "saida"


def test_normalize_filename_component_preserves_allowed_characters():
    assert normalize_filename_component(" Camada A/Valor Total ") == "Camada_A_Valor_Total"
    assert normalize_filename_component("SES-SS_14") == "SES-SS_14"
    assert normalize_filename_component("") == ""
    assert normalize_filename_component(" / ") == ""


def test_build_default_export_basename_uses_layer_and_field():
    assert (
        build_default_export_basename(
            {"metadata": {"layer_name": "Camada A", "field_name": "Valor Total"}}
        )
        == "Camada_A_Valor_Total"
    )
    assert (
        build_default_export_basename({"metadata": {"layer_name": "", "field_name": "Valor"}})
        == "Valor"
    )
    assert (
        build_default_export_basename({"metadata": {"layer_name": "", "field_name": ""}})
        == "resumo_summarizer"
    )
    assert build_default_export_basename({}) == "resumo_summarizer"


def test_current_export_format_keeps_extensions_and_unknown_fallback():
    assert current_export_format(EXPORT_FORMATS, "Excel (.xlsx)")["extension"] == ".xlsx"
    assert current_export_format(EXPORT_FORMATS, "CSV (.csv)")["extension"] == ".csv"
    assert current_export_format(EXPORT_FORMATS, "PDF (.pdf)")["extension"] == ".pdf"
    assert current_export_format(EXPORT_FORMATS, "JSON (.json)")["extension"] == ".json"

    fallback = current_export_format(EXPORT_FORMATS, "Formato desconhecido")
    assert fallback == {"filter": "Excel (*.xlsx)", "extension": ".xlsx"}
