from __future__ import annotations

import pandas as pd

from .pivot_models import PivotExportSpec


def export_dataframe_to_csv(df: pd.DataFrame, file_path: str, *, sep: str = ";") -> None:
    df.to_csv(file_path, index=False, sep=sep, encoding="utf-8-sig", decimal=",")


def export_dataframes_to_excel(
    pivot_df: pd.DataFrame,
    layer_df: pd.DataFrame,
    spec: PivotExportSpec,
) -> None:
    with pd.ExcelWriter(spec.file_path, engine="openpyxl") as writer:
        pivot_df.to_excel(writer, sheet_name=spec.pivot_sheet_name, index=False)
        layer_df.to_excel(writer, sheet_name=spec.data_sheet_name, index=False)


__all__ = ["export_dataframe_to_csv", "export_dataframes_to_excel"]
