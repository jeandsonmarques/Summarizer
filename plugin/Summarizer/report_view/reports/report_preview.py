from __future__ import annotations

from typing import List

from ..result_models import QueryResult
from .report_data import MAX_TABLE_ROWS, PREVIEW_ROWS
from .report_models import ReportPreviewModel, ReportPreviewRow


def format_result_value(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_filter_chip(filter_spec) -> str:
    field_label = str(getattr(filter_spec, "field", "") or "").replace("_", " ").strip()
    value_label = str(getattr(filter_spec, "value", "") or "").strip()
    if field_label and value_label:
        return f"{field_label}: {value_label}"
    return value_label or field_label or "Filtro"


def build_result_helper_text(result: QueryResult) -> str:
    parts = []
    plan = result.plan
    if plan is not None and plan.understanding_text:
        parts.append(f"Entendi como: {plan.understanding_text}")
    if plan is not None and plan.detected_filters_text:
        parts.append(f"Filtros detectados: {plan.detected_filters_text}")
    if plan is not None:
        trace = dict(plan.planning_trace or {})
        for item in list(trace.get("conversation_debug") or [])[:2]:
            text = str(item or "").strip()
            if text:
                parts.append(text)
    if result.total_records:
        parts.append(f"{result.total_records} registros analisados")
    if result.rows:
        parts.append(f"{len(result.rows)} categorias")
    return "  |  ".join(parts)


def build_preview_rows(
    result: QueryResult,
    preview_limit: int = PREVIEW_ROWS,
) -> List[ReportPreviewRow]:
    visible_rows = result.rows[: min(preview_limit, MAX_TABLE_ROWS)]
    rows: List[ReportPreviewRow] = []
    for row in visible_rows:
        percent_text = ""
        if result.show_percent:
            percent_text = "-" if row.percent is None else f"{row.percent:.1f}%".replace(".", ",")
        rows.append(
            ReportPreviewRow(
                category=row.category,
                value_text=format_result_value(row.value),
                percent_text=percent_text,
            )
        )
    return rows


def build_result_preview_model(
    result: QueryResult,
    preview_limit: int = PREVIEW_ROWS,
) -> ReportPreviewModel:
    return ReportPreviewModel(
        helper_text=build_result_helper_text(result),
        rows=build_preview_rows(result, preview_limit=preview_limit),
        value_label=result.value_label,
        show_percent=bool(result.show_percent),
    )
