from __future__ import annotations

from typing import Any, Dict, List

from ..result_models import QueryResult
from .report_models import ReportExportBundle
from .report_preview import build_result_helper_text, format_result_value


def build_result_export_bundle(result: QueryResult) -> ReportExportBundle:
    rows: List[Dict[str, Any]] = []
    for row in result.rows:
        payload: Dict[str, Any] = {
            "Categoria": row.category,
            result.value_label or "Valor": format_result_value(row.value),
        }
        if result.show_percent:
            payload["Percentual"] = (
                "-" if row.percent is None else f"{row.percent:.1f}%".replace(".", ",")
            )
        rows.append(payload)

    headers = ["Categoria", result.value_label or "Valor"]
    if result.show_percent:
        headers.append("Percentual")

    return ReportExportBundle(
        headers=headers,
        rows=rows,
        helper_text=build_result_helper_text(result),
        value_label=result.value_label,
    )
