# ruff: noqa: I001
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_table_renderer.py"

spec = importlib.util.spec_from_file_location("pivot_table_renderer", MODULE_PATH)
pivot_table_renderer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pivot_table_renderer)


def test_table_headers_preserve_dataframe_columns():
    df = pd.DataFrame([[1, 2]], columns=["Linha", "Total"])
    assert pivot_table_renderer.table_headers(df) == ["Linha", "Total"]


def test_format_table_value_matches_existing_display_rules():
    assert pivot_table_renderer.format_table_value(None) == ""
    assert pivot_table_renderer.format_table_value(np.nan) == ""
    assert pivot_table_renderer.format_table_value(1234.5) == "1,234.50"
    assert pivot_table_renderer.format_table_value(np.float64(4.25)) == "4.25"
    assert pivot_table_renderer.format_table_value(7) == "7"
    assert pivot_table_renderer.format_table_value("SS-14") == "SS-14"


def test_calculate_row_header_depth_uses_metadata_and_display_keys():
    result = SimpleNamespace(metadata={"row_fields": ["subbacia"]})
    assert pivot_table_renderer.calculate_row_header_depth(result, [("SS-14", "Ativo")]) == 2
    result = SimpleNamespace(metadata={"row_fields": ["subbacia", "Estado", "Trecho"]})
    assert pivot_table_renderer.calculate_row_header_depth(result, [("SS-14",)]) == 3
    assert pivot_table_renderer.calculate_row_header_depth(SimpleNamespace(metadata={}), []) == 1


def test_feature_ids_for_cell_preserves_cell_feature_id_payload():
    cell = SimpleNamespace(feature_ids=[10, "11"])
    result = SimpleNamespace(matrix=[[cell]], metadata={})
    assert (
        pivot_table_renderer.feature_ids_for_cell(
            result,
            row_index=0,
            pivot_column_index=0,
            display_column_keys=[("Total",)],
        )
        == "10,11"
    )
    assert (
        pivot_table_renderer.feature_ids_for_cell(
            result,
            row_index=0,
            pivot_column_index=1,
            display_column_keys=[("Total",)],
        )
        is None
    )
