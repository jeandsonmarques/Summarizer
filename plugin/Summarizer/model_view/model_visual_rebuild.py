from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..dashboard_models import (
    DashboardChartBinding,
    DashboardChartItem,
    FieldBindingItem,
    ROLE_FILTERS,
    ROLE_LEGEND,
    ROLE_SIZE,
    ROLE_TOOLTIP,
    ROLE_VALUES,
    ROLE_X_AXIS,
    ROLE_Y_AXIS,
    empty_binding_message,
    normalize_aggregation,
    normalize_binding_role,
)
from ..report_view.charts import ChartVisualState
from ..report_view.result_models import ChartPayload
from .model_data_panel import field_kind_for_layer_field, resolve_layer_field_name

try:
    from ..utils.i18n_runtime import tr_text as _rt
except Exception:

    def _rt(text: str, **kwargs) -> str:
        return str(text).format(**kwargs) if kwargs else str(text)

try:
    from ..utils.logging_utils import log_exception
except Exception:

    def log_exception(_message: str):
        return None


@dataclass
class BuilderChartResult:
    item: Optional[DashboardChartItem] = None
    error: str = ""


def safe_float(value) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def empty_chart_payload(chart_type: str, title: str = "") -> ChartPayload:
    return ChartPayload.build(
        chart_type=str(chart_type or "bar"),
        title=str(title or ""),
        categories=[],
        values=[],
        value_label=_rt("Valor"),
    )


def resolve_binding_items_for_layer(binding: DashboardChartBinding, role: str, layer) -> List[FieldBindingItem]:
    normalized = binding.normalized()
    result: List[FieldBindingItem] = []
    for index, item in enumerate(list(normalized.bindings.get(normalize_binding_role(role)) or [])):
        resolved_name = resolve_layer_field_name(layer, item.field)
        if not resolved_name:
            continue
        field_type = field_kind_for_layer_field(layer, resolved_name)
        result.append(
            FieldBindingItem(
                field=resolved_name,
                display_name=item.display_name or resolved_name,
                type=field_type,
                aggregation=normalize_aggregation(item.aggregation, field_type, item.role),
                role=item.role,
                order=index,
            ).normalized(item.role, index)
        )
    return result


def feature_category_from_items(feature, items: List[FieldBindingItem]) -> tuple[str, object]:
    if not items:
        return _rt("Total"), _rt("Total")
    raw_parts = []
    display_parts = []
    for item in items:
        raw_value = feature.attribute(item.field)
        raw_parts.append(raw_value)
        text = str(raw_value).strip() if raw_value not in (None, "") else _rt("(vazio)")
        display_parts.append(text)
    return " / ".join(display_parts), tuple(raw_parts)


def aggregate_feature_rows(
    layer,
    *,
    dimension_field: str,
    value_field: str = "__count__",
    aggregation: str = "count",
    top_n: int = 12,
) -> tuple[List[Dict[str, object]], bool, bool]:
    grouped: Dict[str, Dict[str, object]] = {}
    has_numeric_values = False
    for feature in layer.getFeatures():
        raw_category = feature.attribute(dimension_field)
        category = str(raw_category).strip() if raw_category is not None else ""
        if not category:
            category = "(vazio)"
        bucket = grouped.setdefault(
            category,
            {
                "raw_category": raw_category if raw_category is not None else category,
                "feature_ids": [],
                "sum": 0.0,
                "count": 0,
                "min": None,
                "max": None,
            },
        )
        try:
            bucket["feature_ids"].append(int(feature.id()))
        except Exception:
            log_exception("falha opcional ignorada")

        if value_field == "__count__":
            value = 1.0
        else:
            value = safe_float(feature.attribute(value_field))
            if value is None:
                continue
            has_numeric_values = True

        bucket["sum"] = float(bucket.get("sum") or 0.0) + float(value)
        bucket["count"] = int(bucket.get("count") or 0) + 1
        current_min = bucket.get("min")
        current_max = bucket.get("max")
        bucket["min"] = float(value) if current_min is None else min(float(current_min), float(value))
        bucket["max"] = float(value) if current_max is None else max(float(current_max), float(value))

    rows: List[Dict[str, object]] = []
    for category, bucket in grouped.items():
        count = int(bucket.get("count") or 0)
        if count <= 0:
            continue
        if aggregation == "avg":
            metric_value = float(bucket.get("sum") or 0.0) / float(count)
        elif aggregation == "min":
            metric_value = float(bucket.get("min") or 0.0)
        elif aggregation == "max":
            metric_value = float(bucket.get("max") or 0.0)
        elif aggregation == "sum":
            metric_value = float(bucket.get("sum") or 0.0)
        else:
            metric_value = float(count)
        rows.append(
            {
                "category": str(category),
                "value": metric_value,
                "raw_category": bucket.get("raw_category"),
                "feature_ids": list(bucket.get("feature_ids") or []),
            }
        )
    rows.sort(key=lambda item: float(item.get("value") or 0.0), reverse=True)
    truncated = len(rows) > max(1, int(top_n or 12))
    return rows[: max(1, int(top_n or 12))], truncated, has_numeric_values


def _agg_label(aggregation: str) -> str:
    return {
        "count": _rt("Contagem"),
        "sum": _rt("Soma"),
        "avg": _rt("Media"),
        "min": _rt("Minimo"),
        "max": _rt("Maximo"),
        "count_distinct": _rt("Contagem distinta"),
        "unique_count": _rt("Contagem distinta"),
    }.get(str(aggregation or "count"), _rt("Contagem"))


def rebuild_scatter_item_from_binding(item: DashboardChartItem, binding: DashboardChartBinding, layer) -> DashboardChartItem:
    updated_item = item.clone()
    updated_binding = binding.normalized()
    x_items = resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
    y_items = resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
    size_items = resolve_binding_items_for_layer(updated_binding, ROLE_SIZE, layer)
    legend_items = resolve_binding_items_for_layer(updated_binding, ROLE_LEGEND, layer)
    if x_items:
        updated_binding.x_field = x_items[0].field
    if y_items:
        updated_binding.y_field = y_items[0].field
    if size_items:
        updated_binding.size_field = size_items[0].field
    if legend_items:
        updated_binding.legend_field = legend_items[0].field
    points = []
    for feature in layer.getFeatures():
        x_value = safe_float(feature.attribute(updated_binding.x_field))
        y_value = safe_float(feature.attribute(updated_binding.y_field))
        if x_value is None or y_value is None:
            continue
        size_value = safe_float(feature.attribute(updated_binding.size_field)) if updated_binding.size_field else None
        legend_value = feature.attribute(updated_binding.legend_field) if updated_binding.legend_field else None
        try:
            feature_ids = [int(feature.id())]
        except Exception:
            feature_ids = []
        category = str(legend_value).strip() if legend_value not in (None, "") else str(x_value)
        points.append({"category": category, "x": float(x_value), "y": float(y_value), "size": float(size_value) if size_value is not None else 1.0, "feature_ids": feature_ids})
    if not points:
        updated_item.binding = updated_binding
        updated_item.payload = empty_chart_payload("scatter", updated_binding.title_override)
        updated_item.subtitle = _rt("Sem pares numericos validos para X e Y")
        updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
        return updated_item
    top_n = max(1, int(updated_binding.top_n or 50))
    truncated = len(points) > top_n
    points = points[:top_n]
    title_text = str(updated_binding.title_override or "").strip() or _rt("{y_field} por {x_field}", y_field=updated_binding.y_field, x_field=updated_binding.x_field)
    updated_item.binding = updated_binding
    updated_item.title = title_text if updated_binding.title_override else ""
    updated_item.subtitle = f"{layer.name()} - X: {updated_binding.x_field} - Y: {updated_binding.y_field}"
    updated_item.payload = ChartPayload.build(
        chart_type="scatter",
        title=title_text,
        categories=[point["category"] for point in points],
        values=[point["y"] for point in points],
        value_label=updated_binding.y_field,
        truncated=truncated,
        selection_layer_id=layer.id(),
        selection_layer_name=layer.name(),
        category_field=updated_binding.legend_field or updated_binding.x_field,
        raw_categories=[point["category"] for point in points],
        category_feature_ids=[point["feature_ids"] for point in points],
        x_values=[point["x"] for point in points],
        size_values=[point["size"] for point in points],
        series_labels=[point["category"] for point in points],
    )
    updated_item.source_meta = {
        "builder_version": "v2",
        "empty_visual": False,
        "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
    }
    return updated_item


def rebuild_matrix_item_from_binding(item: DashboardChartItem, binding: DashboardChartBinding, layer) -> DashboardChartItem:
    updated_item = item.clone()
    updated_binding = binding.normalized()
    row_items = resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
    column_items = resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
    value_items = resolve_binding_items_for_layer(updated_binding, ROLE_VALUES, layer)
    rows = [item.field for item in row_items]
    columns = [item.field for item in column_items]
    values = [item.field for item in value_items]
    value_item = value_items[0] if value_items else None
    value_field = value_item.field if value_item is not None else ""
    aggregation = normalize_aggregation(value_item.aggregation if value_item is not None else updated_binding.aggregation, value_item.type if value_item is not None else "", ROLE_VALUES)
    grouped: Dict[str, Dict[str, object]] = {}
    has_numeric_values = False
    for feature in layer.getFeatures():
        row_parts = [str(feature.attribute(field) or _rt("(vazio)")).strip() for field in rows]
        column_parts = [str(feature.attribute(field) or _rt("(vazio)")).strip() for field in columns[:1]]
        category = " / ".join([part for part in [*row_parts, *column_parts] if part]) or _rt("(vazio)")
        bucket = grouped.setdefault(category, {"sum": 0.0, "count": 0, "feature_ids": []})
        try:
            bucket["feature_ids"].append(int(feature.id()))
        except Exception:
            log_exception("falha opcional ignorada")
        if aggregation == "count":
            numeric = 1.0
        else:
            numeric = safe_float(feature.attribute(value_field)) if value_field else None
            if numeric is None:
                continue
            has_numeric_values = True
        bucket["sum"] = float(bucket.get("sum") or 0.0) + float(numeric)
        bucket["count"] = int(bucket.get("count") or 0) + 1
    if not grouped or (aggregation != "count" and not has_numeric_values):
        updated_item.binding = updated_binding
        updated_item.payload = empty_chart_payload("matrix", updated_binding.title_override)
        updated_item.subtitle = _rt("Sem valores numericos para a matriz")
        updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
        return updated_item
    matrix_rows = []
    for category, bucket in grouped.items():
        count = int(bucket.get("count") or 0)
        value = float(bucket.get("sum") or 0.0)
        if aggregation == "avg":
            value = value / float(max(1, count))
        elif aggregation == "count":
            value = float(count)
        matrix_rows.append({"category": category, "value": value, "feature_ids": list(bucket.get("feature_ids") or [])})
    matrix_rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
    top_n = max(1, int(updated_binding.top_n or 50))
    truncated = len(matrix_rows) > top_n
    matrix_rows = matrix_rows[:top_n]
    title_text = str(updated_binding.title_override or "").strip() or _rt("Matriz - {layer_name}", layer_name=layer.name())
    updated_item.binding = updated_binding
    updated_item.title = title_text if updated_binding.title_override else ""
    updated_item.subtitle = f"{layer.name()} - {', '.join(rows)} - {value_field}"
    updated_item.payload = ChartPayload.build(
        chart_type="matrix",
        title=title_text,
        categories=[str(row.get("category") or "") for row in matrix_rows],
        values=[float(row.get("value") or 0.0) for row in matrix_rows],
        value_label=value_field,
        truncated=truncated,
        selection_layer_id=layer.id(),
        selection_layer_name=layer.name(),
        category_field=rows[0] if rows else "",
        raw_categories=[str(row.get("category") or "") for row in matrix_rows],
        category_feature_ids=[list(row.get("feature_ids") or []) for row in matrix_rows],
    )
    updated_item.source_meta = {
        "builder_version": "v2",
        "empty_visual": False,
        "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
    }
    return updated_item


def rebuild_chart_item_from_binding(item: DashboardChartItem, binding: DashboardChartBinding, layer) -> Optional[DashboardChartItem]:
    if item is None:
        return None
    updated_item = item.clone()
    updated_binding = binding.normalized()
    chart_type = str(updated_binding.chart_type or getattr(updated_item.visual_state, "chart_type", "bar") or "bar").strip().lower() or "bar"
    updated_binding.chart_type = chart_type
    updated_item.visual_state.chart_type = chart_type

    if layer is None or not layer.isValid():
        updated_item.binding = updated_binding
        updated_item.payload = empty_chart_payload(chart_type, updated_binding.title_override)
        updated_item.subtitle = _rt("Selecione uma camada para continuar")
        updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
        return updated_item

    updated_binding.source_id = layer.id()
    updated_binding.source_name = layer.name()
    x_axis_items = resolve_binding_items_for_layer(updated_binding, ROLE_X_AXIS, layer)
    y_axis_items = resolve_binding_items_for_layer(updated_binding, ROLE_Y_AXIS, layer)
    value_items = resolve_binding_items_for_layer(updated_binding, ROLE_VALUES, layer)
    legend_items = resolve_binding_items_for_layer(updated_binding, ROLE_LEGEND, layer)
    filter_items = resolve_binding_items_for_layer(updated_binding, ROLE_FILTERS, layer)
    tooltip_items = resolve_binding_items_for_layer(updated_binding, ROLE_TOOLTIP, layer)
    measure_items = list(value_items or []) or list(y_axis_items or [])
    dimension_field = x_axis_items[0].field if x_axis_items else ""
    measure_field = measure_items[0].field if measure_items else ""
    legend_field = legend_items[0].field if legend_items else ""
    aggregation = normalize_aggregation(measure_items[0].aggregation if measure_items else updated_binding.aggregation, measure_items[0].type if measure_items else "", ROLE_VALUES)
    top_n = max(1, int(updated_binding.top_n or 12))

    updated_binding.dimension_field = dimension_field
    updated_binding.measure_field = measure_field
    updated_binding.legend_field = legend_field
    updated_binding.x_field = x_axis_items[0].field if x_axis_items else ""
    updated_binding.y_field = y_axis_items[0].field if y_axis_items else ""
    updated_binding.row_fields = [item.field for item in x_axis_items]
    updated_binding.column_fields = [item.field for item in y_axis_items]
    updated_binding.value_fields = [item.field for item in value_items]
    updated_binding.filter_fields = [item.field for item in filter_items]
    updated_binding.tooltip_fields = [item.field for item in tooltip_items]
    updated_binding.bindings = {
        role: items
        for role, items in {
            ROLE_X_AXIS: x_axis_items,
            ROLE_Y_AXIS: y_axis_items,
            ROLE_VALUES: value_items,
            ROLE_LEGEND: legend_items,
            ROLE_FILTERS: filter_items,
            ROLE_TOOLTIP: tooltip_items,
        }.items()
        if items
    }
    if dimension_field:
        updated_binding.semantic_field_key = dimension_field
        updated_binding.semantic_field_aliases = [item.field for item in x_axis_items]

    if not updated_binding.has_minimum_fields():
        updated_item.binding = updated_binding
        updated_item.payload = empty_chart_payload(chart_type, updated_binding.title_override)
        updated_item.subtitle = _rt(empty_binding_message(chart_type, updated_binding))
        updated_item.source_meta = {
            "builder_version": "v2",
            "empty_visual": True,
            "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
        }
        return updated_item

    if chart_type == "scatter":
        return rebuild_scatter_item_from_binding(updated_item, updated_binding, layer)

    if chart_type == "matrix":
        return rebuild_matrix_item_from_binding(updated_item, updated_binding, layer)

    active_measure_items = measure_items or [
        FieldBindingItem(
            field=dimension_field,
            display_name=_rt("Contagem"),
            type="unknown",
            aggregation="count",
            role=ROLE_VALUES,
            order=0,
        ).normalized(ROLE_VALUES, 0)
    ]
    if chart_type in {"pie", "donut", "card", "kpi", "gauge"} and active_measure_items:
        active_measure_items = active_measure_items[:1]

    grouped: Dict[tuple[str, str], Dict[str, object]] = {}
    has_numeric_values = False
    for feature in layer.getFeatures():
        category, raw_category = feature_category_from_items(feature, x_axis_items)
        for measure_item in active_measure_items:
            measure_label = measure_item.display_name or measure_item.field or _rt("Valor")
            bucket_key = (category, measure_label if len(active_measure_items) > 1 else "")
            bucket = grouped.setdefault(
                bucket_key,
                {
                    "category": category,
                    "series": measure_label if len(active_measure_items) > 1 else "",
                    "raw_category": (raw_category, measure_label) if len(active_measure_items) > 1 else raw_category,
                    "feature_ids": [],
                    "sum": 0.0,
                    "count": 0,
                    "distinct": set(),
                    "min": None,
                    "max": None,
                },
            )
            try:
                bucket["feature_ids"].append(int(feature.id()))
            except Exception:
                log_exception("falha opcional ignorada")

            item_aggregation = normalize_aggregation(measure_item.aggregation, measure_item.type, measure_item.role)
            target_field = measure_item.field or dimension_field
            raw_value = feature.attribute(target_field) if target_field else None
            if item_aggregation == "count":
                value = 1.0
            elif item_aggregation == "unique_count":
                if raw_value is not None and str(raw_value).strip():
                    bucket["distinct"].add(str(raw_value).strip())
                bucket["count"] = int(bucket.get("count") or 0) + 1
                continue
            else:
                value = safe_float(raw_value)
                if value is None:
                    continue
                has_numeric_values = True

            bucket["sum"] = float(bucket.get("sum") or 0.0) + float(value)
            bucket["count"] = int(bucket.get("count") or 0) + 1
            current_min = bucket.get("min")
            current_max = bucket.get("max")
            bucket["min"] = float(value) if current_min is None else min(float(current_min), float(value))
            bucket["max"] = float(value) if current_max is None else max(float(current_max), float(value))

    if any(normalize_aggregation(item.aggregation, item.type, item.role) not in {"count", "unique_count"} for item in active_measure_items) and not has_numeric_values:
        updated_item.binding = updated_binding
        updated_item.payload = empty_chart_payload(chart_type, updated_binding.title_override)
        updated_item.subtitle = _rt("Sem valores numericos para o campo selecionado")
        updated_item.source_meta = {"builder_version": "v2", "empty_visual": True}
        return updated_item

    rows: List[Dict[str, object]] = []
    for (_category, _series), bucket in grouped.items():
        count = int(bucket.get("count") or 0)
        measure_label = str(bucket.get("series") or "")
        measure_item = next((item for item in active_measure_items if (item.display_name or item.field) == measure_label), active_measure_items[0])
        item_aggregation = normalize_aggregation(measure_item.aggregation, measure_item.type, measure_item.role)
        if item_aggregation == "avg":
            metric_value = float(bucket.get("sum") or 0.0) / float(max(1, count))
        elif item_aggregation == "min":
            metric_value = float(bucket.get("min") or 0.0)
        elif item_aggregation == "max":
            metric_value = float(bucket.get("max") or 0.0)
        elif item_aggregation == "sum":
            metric_value = float(bucket.get("sum") or 0.0)
        elif item_aggregation == "unique_count":
            metric_value = float(len(bucket.get("distinct") or set()))
        else:
            metric_value = float(count)
        display_category = str(bucket.get("category") or "")
        if measure_label:
            display_category = f"{display_category} / {measure_label}"
        rows.append(
            {
                "category": display_category,
                "value": metric_value,
                "raw_category": bucket.get("raw_category"),
                "feature_ids": list(bucket.get("feature_ids") or []),
            }
        )

    rows.sort(key=lambda row: float(row.get("value") or 0.0), reverse=True)
    truncated = len(rows) > top_n
    rows = rows[:top_n]
    categories = [str(row.get("category") or "") for row in rows]
    values = [float(row.get("value") or 0.0) for row in rows]
    raw_categories = [row.get("raw_category") for row in rows]
    feature_groups = [list(row.get("feature_ids") or []) for row in rows]

    agg_label = _agg_label(aggregation)
    value_target = measure_field or dimension_field
    value_label = _rt("Contagem") if aggregation == "count" else _rt("{agg_label} de {field_name}", agg_label=agg_label, field_name=value_target)

    title_text = str(updated_binding.title_override or "").strip()
    if not title_text:
        if chart_type in {"card", "kpi", "gauge"}:
            title_text = _rt("{agg_label} - {layer_name}", agg_label=agg_label, layer_name=layer.name())
        else:
            title_text = _rt("{agg_label} por {dimension_field}", agg_label=agg_label, dimension_field=" / ".join(item.display_name or item.field for item in x_axis_items) or dimension_field)

    updated_item.binding = updated_binding
    updated_item.title = title_text if updated_binding.title_override else ""
    updated_item.subtitle = f"{layer.name()} - {dimension_field} - {value_label}"
    updated_item.payload = ChartPayload.build(
        chart_type=chart_type,
        title=title_text,
        categories=categories,
        values=values,
        value_label=value_label,
        truncated=truncated,
        selection_layer_id=layer.id(),
        selection_layer_name=layer.name(),
        category_field=dimension_field,
        raw_categories=raw_categories,
        category_feature_ids=feature_groups,
    )
    updated_item.source_meta = {
        "builder_version": "v2",
        "empty_visual": False,
        "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
    }
    return updated_item


def build_model_chart_item_from_layer(
    layer,
    *,
    dimension_field: str,
    value_field: str,
    aggregation: str,
    chart_type: str,
    top_n: int,
    title_text: str = "",
) -> BuilderChartResult:
    if layer is None or not layer.isValid():
        return BuilderChartResult(error=_rt("Selecione uma camada valida para criar o grafico."))
    dimension_field = resolve_layer_field_name(layer, dimension_field)
    if not dimension_field:
        return BuilderChartResult(error=_rt("O campo de categoria nao existe na camada selecionada."))
    value_field = str(value_field or "__count__").strip() or "__count__"
    if value_field != "__count__":
        value_field = resolve_layer_field_name(layer, value_field)
        if not value_field:
            return BuilderChartResult(error=_rt("O campo de metrica nao existe na camada selecionada."))

    rows, truncated, has_numeric_values = aggregate_feature_rows(
        layer,
        dimension_field=dimension_field,
        value_field=value_field,
        aggregation=aggregation,
        top_n=top_n,
    )
    if value_field != "__count__" and not has_numeric_values:
        return BuilderChartResult(error=_rt("Nao foi possivel calcular valores numericos para esse campo."))
    if not rows:
        return BuilderChartResult(error=_rt("A camada nao possui dados suficientes para montar o grafico."))

    categories = [str(item.get("category") or "") for item in rows]
    values = [float(item.get("value") or 0.0) for item in rows]
    raw_categories = [item.get("raw_category") for item in rows]
    feature_groups = [list(item.get("feature_ids") or []) for item in rows]

    agg_label = _agg_label(aggregation)
    value_label = _rt("Contagem") if value_field == "__count__" else _rt("{agg_label} de {value_field}", agg_label=agg_label, value_field=value_field)
    title_text = str(title_text or "").strip()
    if not title_text:
        if value_field == "__count__":
            title_text = _rt("Contagem por {dimension_field}", dimension_field=dimension_field)
        else:
            title_text = _rt("{agg_label} de {value_field} por {dimension_field}", agg_label=agg_label, value_field=value_field, dimension_field=dimension_field)

    payload = ChartPayload.build(
        chart_type=chart_type,
        title=title_text,
        categories=categories,
        values=values,
        value_label=value_label,
        truncated=truncated,
        selection_layer_id=layer.id(),
        selection_layer_name=layer.name(),
        category_field=dimension_field,
        raw_categories=raw_categories,
        category_feature_ids=feature_groups,
    )

    item_id = uuid.uuid4().hex
    visual_state = ChartVisualState(chart_type=chart_type, show_legend=chart_type in {"pie", "donut", "funnel"})
    value_binding_field = dimension_field if value_field == "__count__" else value_field
    value_binding_label = _rt("Contagem") if value_field == "__count__" else value_field
    binding = DashboardChartBinding(
        chart_id=item_id,
        chart_type=chart_type,
        source_id=layer.id(),
        dimension_field=dimension_field,
        semantic_field_key=dimension_field,
        semantic_field_aliases=[dimension_field],
        measure_field="" if value_field == "__count__" else value_field,
        aggregation=aggregation,
        top_n=top_n,
        title_override=title_text,
        source_name=layer.name(),
        bindings={
            ROLE_X_AXIS: [
                FieldBindingItem(
                    field=dimension_field,
                    display_name=dimension_field,
                    type=field_kind_for_layer_field(layer, dimension_field),
                    aggregation="none",
                    role=ROLE_X_AXIS,
                    order=0,
                )
            ],
            ROLE_VALUES: [
                FieldBindingItem(
                    field=value_binding_field,
                    display_name=value_binding_label,
                    type=field_kind_for_layer_field(layer, value_binding_field),
                    aggregation=aggregation,
                    role=ROLE_VALUES,
                    order=0,
                )
            ],
        },
    ).normalized()
    subtitle = f"{layer.name()} - {dimension_field} - {value_label}"
    return BuilderChartResult(
        item=DashboardChartItem(
            item_id=item_id,
            origin="model_builder",
            payload=payload,
            visual_state=visual_state,
            binding=binding,
            title=title_text,
            subtitle=subtitle,
            source_meta={
                "metadata": {"layer_id": layer.id(), "layer_name": layer.name()},
    },
)
    )


__all__ = [
    "BuilderChartResult",
    "aggregate_feature_rows",
    "build_model_chart_item_from_layer",
    "empty_chart_payload",
    "feature_category_from_items",
    "rebuild_chart_item_from_binding",
    "rebuild_matrix_item_from_binding",
    "rebuild_scatter_item_from_binding",
    "resolve_binding_items_for_layer",
    "safe_float",
]
