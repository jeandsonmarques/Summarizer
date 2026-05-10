from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .report_view.charts import ChartVisualState
from .report_view.report_logging import log_warning
from .report_view.result_models import ChartPayload


def _timestamp_now() -> str:
    return datetime.now().isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _flatten_text_list(value: Any) -> List[str]:
    flattened: List[str] = []

    def _walk(item: Any):
        if item is None:
            return
        if isinstance(item, (list, tuple, set)):
            for nested in item:
                _walk(nested)
            return
        text = str(item).strip()
        if text:
            flattened.append(text)

    _walk(value)
    return flattened


def _unique_normalized_texts(values: Any) -> List[str]:
    seen = set()
    results: List[str] = []
    for text in _flatten_text_list(values):
        key = text.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(text)
    return results


def _first_text(values: Any) -> str:
    texts = _flatten_text_list(values)
    return texts[0] if texts else ""


SLOT_CATEGORY = "category"
SLOT_VALUES = "values"
SLOT_LEGEND = "legend"
SLOT_FILTERS = "filters"
SLOT_TOOLTIP = "tooltip"
SLOT_X = "x"
SLOT_Y = "y"
SLOT_SIZE = "size"
SLOT_ROWS = "rows"
SLOT_COLUMNS = "columns"
ROLE_X_AXIS = "x_axis"
ROLE_Y_AXIS = "y_axis"
ROLE_VALUES = "values"
ROLE_LEGEND = "legend"
ROLE_FILTERS = "filters"
ROLE_TOOLTIP = "tooltip"
ROLE_SIZE = "size"

VISUAL_BINDING_ROLES = (ROLE_X_AXIS, ROLE_Y_AXIS, ROLE_VALUES, ROLE_LEGEND, ROLE_FILTERS, ROLE_TOOLTIP)
_ROLE_ALIASES = {
    SLOT_CATEGORY: ROLE_X_AXIS,
    SLOT_X: ROLE_X_AXIS,
    SLOT_ROWS: ROLE_X_AXIS,
    SLOT_Y: ROLE_Y_AXIS,
    SLOT_COLUMNS: ROLE_Y_AXIS,
    SLOT_VALUES: ROLE_VALUES,
    SLOT_LEGEND: ROLE_LEGEND,
    SLOT_FILTERS: ROLE_FILTERS,
    SLOT_TOOLTIP: ROLE_TOOLTIP,
    SLOT_SIZE: ROLE_SIZE,
}


def normalize_binding_role(role: str) -> str:
    normalized = str(role or "").strip().lower()
    return _ROLE_ALIASES.get(normalized, normalized if normalized in {*VISUAL_BINDING_ROLES, ROLE_SIZE} else "")


def normalize_field_type(field_type: str) -> str:
    normalized = str(field_type or "").strip().lower()
    if normalized in {"numeric", "number", "integer", "float", "double", "decimal", "real", "measure"}:
        return "numeric"
    if normalized in {"text", "string", "str", "dimension"}:
        return "text"
    if normalized in {"date", "datetime", "time"}:
        return "date"
    if normalized in {"bool", "boolean"}:
        return "boolean"
    return "unknown"


def default_aggregation_for_binding(field_type: str, role: str) -> str:
    normalized_role = normalize_binding_role(role)
    normalized_type = normalize_field_type(field_type)
    if normalized_role in {ROLE_VALUES, ROLE_Y_AXIS, ROLE_SIZE}:
        if normalized_type == "numeric":
            return "sum"
        return "count"
    return "none"


def normalize_aggregation(aggregation: str, field_type: str = "", role: str = "") -> str:
    normalized = str(aggregation or "").strip().lower()
    if normalized in {"", "default"}:
        return default_aggregation_for_binding(field_type, role)
    if normalized in {"count_distinct", "distinct_count"}:
        return "unique_count"
    if normalized in {"sum", "count", "avg", "min", "max", "unique_count", "none"}:
        return normalized
    return default_aggregation_for_binding(field_type, role)


@dataclass
class FieldBindingItem:
    field: str
    display_name: str = ""
    type: str = "unknown"
    aggregation: str = "none"
    role: str = ""
    order: int = 0

    def normalized(self, fallback_role: str = "", fallback_order: int = 0) -> "FieldBindingItem":
        role = normalize_binding_role(self.role or fallback_role)
        field = str(self.field or "").strip()
        display_name = str(self.display_name or field).strip() or field
        field_type = normalize_field_type(self.type)
        return FieldBindingItem(
            field=field,
            display_name=display_name,
            type=field_type,
            aggregation=normalize_aggregation(self.aggregation, field_type, role),
            role=role,
            order=max(0, int(self.order if self.order is not None else fallback_order)),
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "field": normalized.field,
            "display_name": normalized.display_name,
            "type": normalized.type,
            "aggregation": normalized.aggregation,
            "role": normalized.role,
            "order": normalized.order,
        }

    @classmethod
    def from_payload(cls, payload: Any, role: str = "", order: int = 0) -> Optional["FieldBindingItem"]:
        if isinstance(payload, FieldBindingItem):
            item = payload
        elif isinstance(payload, dict):
            item = cls(
                field=str(payload.get("field") or payload.get("field_name") or "").strip(),
                display_name=str(payload.get("display_name") or payload.get("name") or payload.get("field") or "").strip(),
                type=str(payload.get("type") or payload.get("field_type") or payload.get("field_kind") or "unknown"),
                aggregation=str(payload.get("aggregation") or ""),
                role=str(payload.get("role") or role),
                order=int(payload.get("order", order) or 0),
            )
        else:
            item = cls(field=str(payload or "").strip(), display_name=str(payload or "").strip(), role=role, order=order)
        normalized = item.normalized(fallback_role=role, fallback_order=order)
        if not normalized.field or not normalized.role:
            return None
        return normalized


SLOT_DEFINITIONS: Dict[str, List[Dict[str, Any]]] = {
    "card": [
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "bar": [
        {"name": ROLE_X_AXIS, "label": "Eixo X", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_Y_AXIS, "label": "Eixo Y", "multiple": True, "groups": {"measure"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "barh": [
        {"name": ROLE_X_AXIS, "label": "Eixo Y", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_Y_AXIS, "label": "Eixo X", "multiple": True, "groups": {"measure"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "line": [
        {"name": ROLE_X_AXIS, "label": "Eixo X", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_Y_AXIS, "label": "Eixo Y", "multiple": True, "groups": {"measure"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "pie": [
        {"name": ROLE_X_AXIS, "label": "Categoria", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "donut": [
        {"name": ROLE_X_AXIS, "label": "Categoria", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "scatter": [
        {"name": ROLE_X_AXIS, "label": "Eixo X", "multiple": False, "groups": {"measure"}},
        {"name": ROLE_Y_AXIS, "label": "Eixo Y", "multiple": False, "groups": {"measure"}},
        {"name": ROLE_SIZE, "label": "Tamanho", "multiple": False, "groups": {"measure"}},
        {"name": ROLE_LEGEND, "label": "Legenda", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
    "matrix": [
        {"name": ROLE_X_AXIS, "label": "Linhas", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_Y_AXIS, "label": "Colunas", "multiple": True, "groups": {"dimension", "date", "other"}},
        {"name": ROLE_VALUES, "label": "Valores", "multiple": True, "groups": {"measure", "dimension", "date", "other"}},
        {"name": ROLE_TOOLTIP, "label": "Tooltip", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
        {"name": ROLE_FILTERS, "label": "Filtros", "multiple": True, "groups": {"dimension", "date", "measure", "other"}},
    ],
}
SLOT_DEFINITIONS["table"] = SLOT_DEFINITIONS["matrix"]
for _chart_type in ("kpi", "gauge"):
    SLOT_DEFINITIONS[_chart_type] = SLOT_DEFINITIONS["card"]
for _chart_type in (
    "area",
    "column_clustered",
    "column_stacked",
    "bar100_stacked",
    "combo",
    "treemap",
    "waterfall",
    "funnel",
    "slicer",
):
    SLOT_DEFINITIONS[_chart_type] = SLOT_DEFINITIONS["bar"]


def normalize_chart_type(chart_type: str) -> str:
    normalized = str(chart_type or "bar").strip().lower()
    if normalized in {"column", "columns"}:
        return "bar"
    if normalized == "table":
        return "matrix"
    return normalized or "bar"


def binding_slot_definitions(chart_type: str) -> List[Dict[str, Any]]:
    return [dict(item) for item in SLOT_DEFINITIONS.get(normalize_chart_type(chart_type), SLOT_DEFINITIONS["bar"])]


def binding_slot_names(chart_type: str) -> List[str]:
    return [str(item.get("name") or "") for item in binding_slot_definitions(chart_type)]


def is_binding_slot_compatible(chart_type: str, slot_name: str, field_group: str) -> bool:
    slot_name = normalize_binding_role(slot_name)
    field_group = str(field_group or "other").strip().lower() or "other"
    for slot in binding_slot_definitions(chart_type):
        if str(slot.get("name") or "") == slot_name:
            return field_group in set(slot.get("groups") or [])
    return False


def suggest_binding_slot(chart_type: str, field_group: str, binding: Optional["DashboardChartBinding"] = None) -> str:
    chart_type = normalize_chart_type(chart_type)
    field_group = str(field_group or "other").strip().lower() or "other"
    binding = (binding or DashboardChartBinding(chart_type=chart_type)).normalized()
    if chart_type in {"card", "kpi", "gauge"}:
        return ROLE_VALUES if field_group == "measure" else ""
    if chart_type == "scatter":
        if field_group == "measure":
            if not binding.field_names(ROLE_X_AXIS):
                return ROLE_X_AXIS
            if not binding.field_names(ROLE_Y_AXIS):
                return ROLE_Y_AXIS
            if not binding.field_names(ROLE_SIZE):
                return ROLE_SIZE
            return ROLE_TOOLTIP
        if not binding.legend_field:
            return ROLE_LEGEND
        return ROLE_TOOLTIP
    if chart_type == "matrix":
        if field_group == "measure":
            return ROLE_VALUES
        if not binding.field_names(ROLE_X_AXIS):
            return ROLE_X_AXIS
        return ROLE_Y_AXIS
    if field_group == "measure":
        return ROLE_VALUES
    if not binding.field_names(ROLE_X_AXIS):
        return ROLE_X_AXIS
    if not binding.legend_field:
        return ROLE_LEGEND
    return ROLE_TOOLTIP


def empty_binding_message(chart_type: str, binding: Optional["DashboardChartBinding"] = None) -> str:
    chart_type = normalize_chart_type(chart_type)
    binding = (binding or DashboardChartBinding(chart_type=chart_type)).normalized()
    if chart_type in {"card", "kpi", "gauge"}:
        return "Arraste uma medida para Valor."
    if chart_type == "scatter":
        return "Arraste campos numericos para X e Y."
    if chart_type == "matrix":
        return "Arraste campos para Linhas e Valores."
    if chart_type in {"bar", "barh", "line", "area", "pie", "donut"}:
        return "Arraste campos para Eixo X/Categoria e Valores."
    return "Arraste campos para configurar este visual."


def serialize_chart_payload(payload: Optional[ChartPayload]) -> Dict[str, Any]:
    if payload is None:
        return {}
    return {
        "chart_type": str(payload.chart_type or "bar"),
        "title": str(payload.title or ""),
        "categories": [str(item) for item in list(payload.categories or [])],
        "values": [float(item) for item in list(payload.values or [])],
        "value_label": str(payload.value_label or "Valor"),
        "truncated": bool(payload.truncated),
        "selection_layer_id": payload.selection_layer_id,
        "selection_layer_name": str(payload.selection_layer_name or ""),
        "category_field": str(payload.category_field or ""),
        "raw_categories": _json_safe(list(payload.raw_categories or [])),
        "category_feature_ids": _json_safe(list(payload.category_feature_ids or [])),
        "x_values": _json_safe(list(getattr(payload, "x_values", []) or [])),
        "size_values": _json_safe(list(getattr(payload, "size_values", []) or [])),
        "series_labels": _json_safe(list(getattr(payload, "series_labels", []) or [])),
    }


def deserialize_chart_payload(data: Optional[Dict[str, Any]]) -> ChartPayload:
    payload = dict(data or {})
    return ChartPayload.build(
        chart_type=payload.get("chart_type") or "bar",
        title=payload.get("title") or "",
        categories=list(payload.get("categories") or []),
        values=list(payload.get("values") or []),
        value_label=payload.get("value_label") or "Valor",
        truncated=bool(payload.get("truncated")),
        selection_layer_id=payload.get("selection_layer_id"),
        selection_layer_name=payload.get("selection_layer_name") or "",
        category_field=payload.get("category_field") or "",
        raw_categories=list(payload.get("raw_categories") or []),
        category_feature_ids=list(payload.get("category_feature_ids") or []),
        x_values=list(payload.get("x_values") or []),
        size_values=list(payload.get("size_values") or []),
        series_labels=list(payload.get("series_labels") or []),
    )


def serialize_chart_visual_state(state: Optional[ChartVisualState]) -> Dict[str, Any]:
    if state is None:
        state = ChartVisualState()
    payload = asdict(state)
    return _json_safe(payload)


def deserialize_chart_visual_state(data: Optional[Dict[str, Any]]) -> ChartVisualState:
    payload = dict(data or {})
    try:
        font_scale = float(payload.get("font_scale") or 1.0)
    except Exception:
        log_warning("[Dashboard] valor invalido de font_scale ao restaurar estado; usando 1.0")
        font_scale = 1.0
    try:
        border_radius = int(payload.get("border_radius", 8) or 8)
    except Exception:
        border_radius = 8
    try:
        border_width = int(payload.get("border_width", 1) or 1)
    except Exception:
        border_width = 1
    try:
        padding = int(payload.get("padding", 8) or 8)
    except Exception:
        padding = 8
    try:
        background_opacity = int(payload.get("background_opacity", 100) if payload.get("background_opacity", 100) != "" else 100)
    except Exception:
        background_opacity = 100
    try:
        shadow_opacity = int(payload.get("shadow_opacity", 18) if payload.get("shadow_opacity", 18) != "" else 18)
    except Exception:
        shadow_opacity = 18
    try:
        grid_width = int(payload.get("grid_width", 1) or 1)
    except Exception:
        grid_width = 1
    try:
        grid_opacity = int(payload.get("grid_opacity", 100) if payload.get("grid_opacity", 100) != "" else 100)
    except Exception:
        grid_opacity = 100
    try:
        title_size = int(payload.get("title_size", 0) or 0)
    except Exception:
        title_size = 0
    try:
        label_size = int(payload.get("label_size", 0) or 0)
    except Exception:
        label_size = 0
    try:
        axis_label_size = int(payload.get("axis_label_size", 0) or 0)
    except Exception:
        axis_label_size = 0
    try:
        decimal_places = int(payload.get("decimal_places", 2))
    except Exception:
        decimal_places = 2
    try:
        bar_width_percent = int(payload.get("bar_width_percent", 62) or 62)
    except Exception:
        bar_width_percent = 62
    try:
        line_width = int(payload.get("line_width", 2) or 2)
    except Exception:
        line_width = 2
    try:
        marker_size = int(payload.get("marker_size", 4) or 4)
    except Exception:
        marker_size = 4
    try:
        value_size = int(payload.get("value_size", 0) or 0)
    except Exception:
        value_size = 0
    card_density = str(payload.get("card_density") or "normal").strip().lower()
    if card_density not in {"compact", "normal", "expanded"}:
        card_density = "normal"
    data_label_position = str(payload.get("data_label_position") or "outside").strip().lower()
    if data_label_position not in {"auto", "inside", "outside"}:
        data_label_position = "outside"
    display_units = str(payload.get("display_units") or "none").strip().lower()
    if display_units not in {"none", "auto", "thousand", "million"}:
        display_units = "none"
    return ChartVisualState(
        chart_type=str(payload.get("chart_type") or "bar"),
        palette=str(payload.get("palette") or "purple"),
        font_scale=font_scale,
        show_legend=bool(payload.get("show_legend")),
        show_values=bool(payload.get("show_values", True)),
        show_percent=bool(payload.get("show_percent")),
        show_grid=bool(payload.get("show_grid")),
        show_title=bool(payload.get("show_title", True)),
        show_border=bool(payload.get("show_border")),
        sort_mode=str(payload.get("sort_mode") or "default"),
        bar_corner_style=str(payload.get("bar_corner_style") or "square"),
        title_override=str(payload.get("title_override") or ""),
        legend_label_override=str(payload.get("legend_label_override") or ""),
        legend_item_overrides=dict(payload.get("legend_item_overrides") or {}),
        show_background=bool(payload.get("show_background", True)),
        background_color=str(payload.get("background_color") or "#FFFFFF"),
        background_opacity=max(0, min(100, background_opacity)),
        border_color=str(payload.get("border_color") or "#CBD5E1"),
        border_width=max(1, min(6, border_width)),
        border_radius=max(0, min(32, border_radius)),
        padding=max(0, min(40, padding)),
        shadow_enabled=bool(payload.get("shadow_enabled")),
        shadow_opacity=max(0, min(60, shadow_opacity)),
        grid_color=str(payload.get("grid_color") or "#E5E7EB"),
        grid_width=max(1, min(4, grid_width)),
        grid_opacity=max(0, min(100, grid_opacity)),
        show_axis_labels=bool(payload.get("show_axis_labels", True)),
        axis_label_color=str(payload.get("axis_label_color") or "#4B5563"),
        axis_label_size=max(0, min(36, axis_label_size)),
        show_zero_line=bool(payload.get("show_zero_line", True)),
        zero_line_color=str(payload.get("zero_line_color") or "#CBD5E1"),
        title_color=str(payload.get("title_color") or "#1F2937"),
        title_size=max(0, min(48, title_size)),
        label_color=str(payload.get("label_color") or "#4B5563"),
        label_size=max(0, min(36, label_size)),
        data_label_position=data_label_position,
        text_align=str(payload.get("text_align") or "left"),
        number_prefix=str(payload.get("number_prefix") or ""),
        number_suffix=str(payload.get("number_suffix") or ""),
        decimal_places=max(0, min(8, decimal_places)),
        display_units=display_units,
        null_value=str(payload.get("null_value") or "-"),
        primary_color=str(payload.get("primary_color") or "#5A3FE6"),
        category_palette=[str(item) for item in list(payload.get("category_palette") or [])],
        bar_width_percent=max(20, min(100, bar_width_percent)),
        line_width=max(1, min(8, line_width)),
        show_markers=bool(payload.get("show_markers", True)),
        marker_size=max(2, min(12, marker_size)),
        value_color=str(payload.get("value_color") or "#111827"),
        value_size=max(0, min(72, value_size)),
        value_align=str(payload.get("value_align") or "left"),
        card_density=card_density,
        show_card_accent=bool(payload.get("show_card_accent", True)),
        show_card_sparkline=bool(payload.get("show_card_sparkline", True)),
        alt_text=str(payload.get("alt_text") or ""),
    )


@dataclass
class DashboardChartBinding:
    chart_id: str = ""
    chart_type: str = ""
    source_id: str = ""
    dimension_field: str = ""
    semantic_field_key: str = ""
    semantic_field_aliases: List[str] = field(default_factory=list)
    measure_field: str = ""
    x_field: str = ""
    y_field: str = ""
    size_field: str = ""
    row_fields: List[str] = field(default_factory=list)
    column_fields: List[str] = field(default_factory=list)
    value_fields: List[str] = field(default_factory=list)
    value_aggregations: Dict[str, str] = field(default_factory=dict)
    aggregation: str = ""
    legend_field: str = ""
    filter_fields: List[str] = field(default_factory=list)
    tooltip_fields: List[str] = field(default_factory=list)
    top_n: int = 12
    title_override: str = ""
    base_filters: List[Dict[str, Any]] = field(default_factory=list)
    source_name: str = ""
    bindings: Dict[str, List[FieldBindingItem]] = field(default_factory=dict)

    def _explicit_binding_roles(self) -> set[str]:
        return {
            normalize_binding_role(role)
            for role in dict(self.bindings or {}).keys()
            if normalize_binding_role(role)
        }

    def _normalized_bindings(self) -> Dict[str, List[FieldBindingItem]]:
        normalized: Dict[str, List[FieldBindingItem]] = {role: [] for role in (*VISUAL_BINDING_ROLES, ROLE_SIZE)}
        explicit_roles = self._explicit_binding_roles()

        def _add(role: str, value: Any, *, field_type: str = "unknown", aggregation: str = "", display_name: str = ""):
            target_role = normalize_binding_role(role)
            if not target_role:
                return
            existing = normalized.setdefault(target_role, [])
            order = len(existing)
            payload = value
            if not isinstance(value, (dict, FieldBindingItem)):
                payload = {
                    "field": str(value or "").strip(),
                    "display_name": display_name or str(value or "").strip(),
                    "type": field_type,
                    "aggregation": aggregation,
                    "role": target_role,
                    "order": order,
                }
            item = FieldBindingItem.from_payload(payload, target_role, order)
            if item is None:
                return
            duplicate = any(str(existing_item.field).lower() == item.field.lower() for existing_item in existing)
            if duplicate:
                return
            existing.append(item.normalized(target_role, order))

        for role, items in dict(self.bindings or {}).items():
            target_role = normalize_binding_role(role)
            for index, item in enumerate(list(items or [])):
                parsed = FieldBindingItem.from_payload(item, target_role, index)
                if parsed is not None:
                    _add(target_role, parsed)

        if ROLE_X_AXIS not in explicit_roles:
            for field_name in _unique_normalized_texts([self.dimension_field]):
                _add(ROLE_X_AXIS, field_name, aggregation="none")
            for field_name in _unique_normalized_texts(self.row_fields or []):
                _add(ROLE_X_AXIS, field_name, aggregation="none")
            if self.x_field:
                _add(ROLE_X_AXIS, self.x_field, field_type="numeric", aggregation="none")
        if ROLE_Y_AXIS not in explicit_roles:
            for field_name in _unique_normalized_texts(self.column_fields or []):
                _add(ROLE_Y_AXIS, field_name, aggregation="none")
            if self.y_field:
                _add(ROLE_Y_AXIS, self.y_field, field_type="numeric", aggregation=self.aggregation or "sum")
        if ROLE_SIZE not in explicit_roles and self.size_field:
            _add(ROLE_SIZE, self.size_field, field_type="numeric", aggregation="sum")
        if ROLE_VALUES not in explicit_roles:
            for field_name in _unique_normalized_texts([self.measure_field, *(self.value_fields or [])]):
                _add(ROLE_VALUES, field_name, aggregation=dict(self.value_aggregations or {}).get(field_name) or self.aggregation or "sum")
        if ROLE_LEGEND not in explicit_roles and self.legend_field:
            _add(ROLE_LEGEND, self.legend_field, aggregation="none")
        if ROLE_FILTERS not in explicit_roles:
            for field_name in _unique_normalized_texts(self.filter_fields or []):
                _add(ROLE_FILTERS, field_name, aggregation="none")
        if ROLE_TOOLTIP not in explicit_roles:
            for field_name in _unique_normalized_texts(self.tooltip_fields or []):
                _add(ROLE_TOOLTIP, field_name, aggregation="none")

        for role, items in list(normalized.items()):
            normalized[role] = [
                item.normalized(role, index)
                for index, item in enumerate(sorted(items, key=lambda item: int(item.order or 0)))
                if item.field
            ]
        return normalized

    def binding_items(self, role: str) -> List[FieldBindingItem]:
        normalized = self.normalized()
        return [item.normalized(role, index) for index, item in enumerate(normalized.bindings.get(normalize_binding_role(role), []) or [])]

    def field_names(self, role: str) -> List[str]:
        return [item.field for item in list((self.bindings or {}).get(normalize_binding_role(role), []) or []) if str(getattr(item, "field", "") or "").strip()]

    def measure_items(self) -> List[FieldBindingItem]:
        bindings = self.normalized().bindings
        return list(bindings.get(ROLE_VALUES) or []) or list(bindings.get(ROLE_Y_AXIS) or [])

    def normalized(self) -> "DashboardChartBinding":
        chart_type = normalize_chart_type(self.chart_type)
        bindings = self._normalized_bindings()
        explicit_roles = self._explicit_binding_roles()
        x_axis_fields = [item.field for item in list(bindings.get(ROLE_X_AXIS) or [])]
        y_axis_fields = [item.field for item in list(bindings.get(ROLE_Y_AXIS) or [])]
        value_items = list(bindings.get(ROLE_VALUES) or [])
        value_fields = [item.field for item in value_items]
        row_fields = list(x_axis_fields)
        column_fields = list(y_axis_fields)
        dimension_field = x_axis_fields[0] if x_axis_fields else ("" if ROLE_X_AXIS in explicit_roles else str(self.dimension_field or "").strip())
        measure_field = value_fields[0] if value_fields else ("" if ROLE_VALUES in explicit_roles else str(self.measure_field or "").strip())
        x_field = x_axis_fields[0] if x_axis_fields else ("" if ROLE_X_AXIS in explicit_roles else str(self.x_field or "").strip())
        y_field = y_axis_fields[0] if y_axis_fields else ("" if ROLE_Y_AXIS in explicit_roles else str(self.y_field or "").strip())
        size_items = list(bindings.get(ROLE_SIZE) or [])
        size_field = size_items[0].field if size_items else ("" if ROLE_SIZE in explicit_roles else str(self.size_field or "").strip())
        legend_items = list(bindings.get(ROLE_LEGEND) or [])
        filter_items = list(bindings.get(ROLE_FILTERS) or [])
        tooltip_items = list(bindings.get(ROLE_TOOLTIP) or [])
        legend_field = legend_items[0].field if legend_items else ("" if ROLE_LEGEND in explicit_roles else str(self.legend_field or "").strip())
        filter_fields = [item.field for item in filter_items] or ([] if ROLE_FILTERS in explicit_roles else _unique_normalized_texts(self.filter_fields or []))
        tooltip_fields = [item.field for item in tooltip_items] or ([] if ROLE_TOOLTIP in explicit_roles else _unique_normalized_texts(self.tooltip_fields or []))
        if chart_type == "scatter":
            x_field = x_field or measure_field
            y_field = y_field or ""
        elif chart_type == "matrix":
            if dimension_field and dimension_field not in row_fields:
                row_fields = [dimension_field, *row_fields]
            if measure_field and measure_field not in value_fields:
                value_fields = [measure_field, *value_fields]
        else:
            if value_fields and not measure_field:
                measure_field = value_fields[0]
            if row_fields and not dimension_field:
                dimension_field = row_fields[0]
            if measure_field and measure_field not in value_fields:
                value_fields = [measure_field]
        semantic_key = str(self.semantic_field_key or "").strip()
        if not semantic_key:
            semantic_key = dimension_field or (row_fields[0] if row_fields else "")
        aliases = _unique_normalized_texts([semantic_key, dimension_field, *row_fields, *list(self.semantic_field_aliases or [])])
        aggregation = str(self.aggregation or "").strip().lower()
        value_aggs = {
            str(key or "").strip(): str(value or aggregation or "sum").strip().lower()
            for key, value in dict(self.value_aggregations or {}).items()
            if str(key or "").strip()
        }
        for item in [*value_items, *list(bindings.get(ROLE_Y_AXIS) or [])]:
            value_aggs.setdefault(item.field, normalize_aggregation(item.aggregation, item.type, item.role))
        if not aggregation:
            for item in [*value_items, *list(bindings.get(ROLE_Y_AXIS) or [])]:
                if item.aggregation and item.aggregation != "none":
                    aggregation = item.aggregation
                    break
        return DashboardChartBinding(
            chart_id=str(self.chart_id or "").strip(),
            chart_type=chart_type,
            source_id=str(self.source_id or "").strip(),
            dimension_field=dimension_field,
            semantic_field_key=semantic_key,
            semantic_field_aliases=aliases,
            measure_field=measure_field,
            x_field=x_field,
            y_field=y_field,
            size_field=size_field,
            row_fields=row_fields,
            column_fields=column_fields,
            value_fields=value_fields,
            value_aggregations=value_aggs,
            aggregation=aggregation,
            legend_field=legend_field,
            filter_fields=_unique_normalized_texts(filter_fields),
            tooltip_fields=_unique_normalized_texts(tooltip_fields),
            top_n=max(1, min(100, int(self.top_n or 12))),
            title_override=str(self.title_override or "").strip(),
            base_filters=[dict(item or {}) for item in list(self.base_filters or [])],
            source_name=str(self.source_name or "").strip(),
            bindings={role: [item.normalized(role, index) for index, item in enumerate(items)] for role, items in bindings.items() if items},
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "chart_id": normalized.chart_id,
            "chart_type": normalized.chart_type,
            "source_id": normalized.source_id,
            "dimension_field": normalized.dimension_field,
            "semantic_field_key": normalized.semantic_field_key,
            "semantic_field_aliases": _json_safe(normalized.semantic_field_aliases),
            "measure_field": normalized.measure_field,
            "x_field": normalized.x_field,
            "y_field": normalized.y_field,
            "size_field": normalized.size_field,
            "row_fields": _json_safe(normalized.row_fields),
            "column_fields": _json_safe(normalized.column_fields),
            "value_fields": _json_safe(normalized.value_fields),
            "value_aggregations": _json_safe(normalized.value_aggregations),
            "aggregation": normalized.aggregation,
            "legend_field": normalized.legend_field,
            "filter_fields": _json_safe(normalized.filter_fields),
            "tooltip_fields": _json_safe(normalized.tooltip_fields),
            "top_n": normalized.top_n,
            "title_override": normalized.title_override,
            "base_filters": _json_safe(normalized.base_filters),
            "source_name": normalized.source_name,
            "bindings": {
                role: [item.to_dict() for item in list(items or [])]
                for role, items in dict(normalized.bindings or {}).items()
                if items
            },
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardChartBinding":
        payload = dict(data or {})
        return cls(
            chart_id=str(payload.get("chart_id") or "").strip(),
            chart_type=str(payload.get("chart_type") or "").strip().lower(),
            source_id=str(payload.get("source_id") or "").strip(),
            dimension_field=str(payload.get("dimension_field") or "").strip(),
            semantic_field_key=str(payload.get("semantic_field_key") or "").strip(),
            semantic_field_aliases=_unique_normalized_texts(payload.get("semantic_field_aliases") or []),
            measure_field=str(payload.get("measure_field") or "").strip(),
            x_field=str(payload.get("x_field") or "").strip(),
            y_field=str(payload.get("y_field") or "").strip(),
            size_field=str(payload.get("size_field") or "").strip(),
            row_fields=_unique_normalized_texts(payload.get("row_fields") or []),
            column_fields=_unique_normalized_texts(payload.get("column_fields") or []),
            value_fields=_unique_normalized_texts(payload.get("value_fields") or []),
            value_aggregations=dict(payload.get("value_aggregations") or {}),
            aggregation=str(payload.get("aggregation") or "").strip(),
            legend_field=str(payload.get("legend_field") or "").strip(),
            filter_fields=_unique_normalized_texts(payload.get("filter_fields") or []),
            tooltip_fields=_unique_normalized_texts(payload.get("tooltip_fields") or []),
            top_n=int(payload.get("top_n") or 12),
            title_override=str(payload.get("title_override") or "").strip(),
            base_filters=[dict(item or {}) for item in list(payload.get("base_filters") or [])],
            source_name=str(payload.get("source_name") or "").strip(),
            bindings={
                normalize_binding_role(role): [
                    item
                    for index, item_payload in enumerate(list(items or []))
                    for item in [FieldBindingItem.from_payload(item_payload, str(role), index)]
                    if item is not None
                ]
                for role, items in dict(payload.get("bindings") or {}).items()
                if normalize_binding_role(role)
            },
        ).normalized()

    @classmethod
    def infer_from_snapshot(cls, snapshot: Dict[str, Any], chart_id: Optional[str] = None) -> "DashboardChartBinding":
        payload = dict(snapshot or {})
        chart_payload = dict(payload.get("payload") or {})
        source_meta = dict(payload.get("source_meta") or {})
        metadata = dict(source_meta.get("metadata") or {})
        config = dict(source_meta.get("config") or {})
        binding = dict(payload.get("binding") or {})
        source_id = (
            binding.get("source_id")
            or metadata.get("layer_id")
            or chart_payload.get("selection_layer_id")
            or source_meta.get("source_id")
            or ""
        )
        dimension_field = (
            binding.get("dimension_field")
            or config.get("semantic_field_key")
            or config.get("row_label")
            or config.get("row_field")
            or _first_text(config.get("row_fields"))
            or chart_payload.get("category_field")
            or ""
        )
        semantic_field_key = (
            binding.get("semantic_field_key")
            or config.get("semantic_field_key")
            or config.get("row_field")
            or _first_text(config.get("row_fields"))
            or chart_payload.get("category_field")
            or dimension_field
            or ""
        )
        semantic_field_aliases = _unique_normalized_texts(
            [
                binding.get("semantic_field_aliases") or [],
                config.get("semantic_field_aliases") or [],
                config.get("row_fields") or [],
                config.get("row_labels") or [],
                config.get("column_fields") or [],
                config.get("column_labels") or [],
                config.get("row_label"),
                config.get("column_label"),
                chart_payload.get("category_field"),
                dimension_field,
            ]
        )
        measure_field = (
            binding.get("measure_field")
            or config.get("value_label")
            or chart_payload.get("value_label")
            or ""
        )
        x_field = str(binding.get("x_field") or config.get("x_field") or "").strip()
        y_field = str(binding.get("y_field") or config.get("y_field") or "").strip()
        size_field = str(binding.get("size_field") or config.get("size_field") or "").strip()
        row_fields = _unique_normalized_texts(binding.get("row_fields") or config.get("row_fields") or [])
        column_fields = _unique_normalized_texts(binding.get("column_fields") or config.get("column_fields") or [])
        value_fields = _unique_normalized_texts(binding.get("value_fields") or config.get("value_fields") or [])
        value_aggregations = dict(binding.get("value_aggregations") or config.get("value_aggregations") or {})
        chart_type = (
            binding.get("chart_type")
            or chart_payload.get("chart_type")
            or config.get("chart_type")
            or ""
        )
        aggregation = (
            binding.get("aggregation")
            or config.get("aggregation")
            or chart_payload.get("chart_type")
            or ""
        )
        legend_field = str(binding.get("legend_field") or config.get("legend_field") or "").strip()
        filter_fields = _unique_normalized_texts(binding.get("filter_fields") or config.get("filter_fields") or [])
        tooltip_fields = _unique_normalized_texts(binding.get("tooltip_fields") or config.get("tooltip_fields") or [])
        top_n = binding.get("top_n") or config.get("top_n") or 12
        title_override = str(binding.get("title_override") or payload.get("title") or chart_payload.get("title") or "").strip()
        base_filters = list(binding.get("base_filters") or payload.get("filters") or [])
        source_name = (
            binding.get("source_name")
            or metadata.get("layer_name")
            or source_meta.get("layer_name")
            or ""
        )
        return cls(
            chart_id=str(chart_id or binding.get("chart_id") or payload.get("chart_id") or payload.get("item_id") or "").strip(),
            chart_type=str(chart_type).strip().lower(),
            source_id=str(source_id).strip(),
            dimension_field=str(dimension_field).strip(),
            semantic_field_key=str(semantic_field_key).strip(),
            semantic_field_aliases=semantic_field_aliases,
            measure_field=str(measure_field).strip(),
            x_field=x_field,
            y_field=y_field,
            size_field=size_field,
            row_fields=row_fields,
            column_fields=column_fields,
            value_fields=value_fields,
            value_aggregations=value_aggregations,
            aggregation=str(aggregation).strip(),
            legend_field=legend_field,
            filter_fields=filter_fields,
            tooltip_fields=tooltip_fields,
            top_n=int(top_n or 12),
            title_override=title_override,
            base_filters=[dict(item or {}) for item in list(base_filters or [])],
            source_name=str(source_name).strip(),
            bindings=dict(binding.get("bindings") or {}),
        ).normalized()

    def match_keys(self) -> List[str]:
        keys = [self.semantic_field_key, self.dimension_field, *list(self.semantic_field_aliases or [])]
        return _unique_normalized_texts(keys)

    def has_minimum_fields(self) -> bool:
        chart_type = normalize_chart_type(self.chart_type)
        measure_items = self.measure_items()
        if chart_type in {"card", "kpi", "gauge"}:
            return bool(measure_items)
        if chart_type == "scatter":
            return bool(self.x_field and self.y_field)
        if chart_type == "matrix":
            return bool(self.field_names(ROLE_X_AXIS) and measure_items)
        return bool(self.field_names(ROLE_X_AXIS) and (measure_items or self.aggregation == "count"))

    def empty_message(self) -> str:
        return empty_binding_message(self.chart_type, self)


@dataclass
class DashboardItemLayout:
    x: int = 24
    y: int = 24
    width: int = 520
    height: int = 340
    row: int = 0
    col: int = 0
    col_span: int = 2
    row_span: int = 1

    def normalized(self) -> "DashboardItemLayout":
        width = max(260, int(self.width or 520))
        height = max(220, int(self.height or 340))
        return DashboardItemLayout(
            x=max(0, int(self.x or 0)),
            y=max(0, int(self.y or 0)),
            width=width,
            height=height,
            row=max(0, int(self.row or 0)),
            col=max(0, int(self.col or 0)),
            col_span=max(1, int(self.col_span or 1)),
            row_span=max(1, int(self.row_span or 1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "x": int(normalized.x),
            "y": int(normalized.y),
            "width": int(normalized.width),
            "height": int(normalized.height),
            "row": int(normalized.row),
            "col": int(normalized.col),
            "col_span": int(normalized.col_span),
            "row_span": int(normalized.row_span),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardItemLayout":
        payload = dict(data or {})
        row = int(payload.get("row", 0) or 0)
        col = int(payload.get("col", 0) or 0)
        col_span = int(payload.get("col_span", 2) or 2)
        row_span = int(payload.get("row_span", 1) or 1)

        x = payload.get("x")
        y = payload.get("y")
        width = payload.get("width")
        height = payload.get("height")

        if x is None:
            x = 24 + max(0, col) * 294
        if y is None:
            y = 24 + max(0, row) * 336
        if width is None:
            width = 278 * max(1, col_span) + 16 * max(0, max(1, col_span) - 1)
        if height is None:
            height = 320 * max(1, row_span) + 16 * max(0, max(1, row_span) - 1)

        return cls(
            x=int(x or 24),
            y=int(y or 24),
            width=int(width or 520),
            height=int(height or 340),
            row=row,
            col=col,
            col_span=col_span,
            row_span=row_span,
        ).normalized()


@dataclass
class DashboardChartItem:
    item_id: str
    origin: str
    payload: ChartPayload
    visual_state: ChartVisualState = field(default_factory=ChartVisualState)
    binding: DashboardChartBinding = field(default_factory=DashboardChartBinding)
    title: str = ""
    subtitle: str = ""
    filters: List[Dict[str, Any]] = field(default_factory=list)
    source_meta: Dict[str, Any] = field(default_factory=dict)
    layout: DashboardItemLayout = field(default_factory=DashboardItemLayout)
    created_at: str = field(default_factory=_timestamp_now)

    @classmethod
    def from_chart_snapshot(cls, snapshot: Dict[str, Any]) -> "DashboardChartItem":
        layout = DashboardItemLayout.from_dict(snapshot.get("layout"))
        item_id = str(snapshot.get("item_id") or snapshot.get("chart_id") or uuid.uuid4().hex)
        binding = DashboardChartBinding.from_dict(snapshot.get("binding"))
        if not binding.chart_id:
            binding = DashboardChartBinding.infer_from_snapshot(snapshot, chart_id=item_id)
        return cls(
            item_id=item_id,
            origin=str(snapshot.get("origin") or "unknown"),
            payload=deserialize_chart_payload(snapshot.get("payload")),
            visual_state=deserialize_chart_visual_state(snapshot.get("visual_state")),
            binding=binding,
            title=str(snapshot.get("title") or ""),
            subtitle=str(snapshot.get("subtitle") or ""),
            filters=[dict(item or {}) for item in list(snapshot.get("filters") or [])],
            source_meta=dict(snapshot.get("source_meta") or {}),
            layout=layout,
        )

    def clone(self) -> "DashboardChartItem":
        return DashboardChartItem.from_dict(self.to_dict())

    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        if self.visual_state.title_override.strip():
            return self.visual_state.title_override.strip()
        return str(self.payload.title or "Grafico")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "chart_id": self.binding.chart_id or self.item_id,
            "origin": self.origin,
            "payload": serialize_chart_payload(self.payload),
            "visual_state": serialize_chart_visual_state(self.visual_state),
            "binding": self.binding.to_dict(),
            "title": self.title,
            "subtitle": self.subtitle,
            "filters": _json_safe(self.filters),
            "source_meta": _json_safe(self.source_meta),
            "layout": self.layout.to_dict(),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardChartItem":
        payload = dict(data or {})
        item = cls.from_chart_snapshot(payload)
        item.created_at = str(payload.get("created_at") or item.created_at)
        return item


@dataclass
class DashboardVisualLink:
    link_id: str = ""
    relation_id: str = ""
    source_chart_id: str = ""
    target_chart_id: str = ""
    source_anchor: str = "right"
    target_anchor: str = "left"
    active: bool = True
    created_at: str = field(default_factory=_timestamp_now)

    def normalized(self) -> "DashboardVisualLink":
        link_id = str(self.link_id or "").strip() or uuid.uuid4().hex
        relation_id = str(self.relation_id or "").strip()
        source_chart_id = str(self.source_chart_id or "").strip()
        target_chart_id = str(self.target_chart_id or "").strip()
        source_anchor = str(self.source_anchor or "right").strip().lower() or "right"
        target_anchor = str(self.target_anchor or "left").strip().lower() or "left"
        if source_anchor not in {"left", "right", "top", "bottom"}:
            source_anchor = "right"
        if target_anchor not in {"left", "right", "top", "bottom"}:
            target_anchor = "left"
        return DashboardVisualLink(
            link_id=link_id,
            relation_id=relation_id,
            source_chart_id=source_chart_id,
            target_chart_id=target_chart_id,
            source_anchor=source_anchor,
            target_anchor=target_anchor,
            active=bool(self.active),
            created_at=str(self.created_at or _timestamp_now()),
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "link_id": normalized.link_id,
            "relation_id": normalized.relation_id,
            "source_chart_id": normalized.source_chart_id,
            "target_chart_id": normalized.target_chart_id,
            "source_anchor": normalized.source_anchor,
            "target_anchor": normalized.target_anchor,
            "active": bool(normalized.active),
            "created_at": normalized.created_at,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardVisualLink":
        payload = dict(data or {})
        return cls(
            link_id=str(payload.get("link_id") or "").strip(),
            relation_id=str(payload.get("relation_id") or "").strip(),
            source_chart_id=str(payload.get("source_chart_id") or payload.get("source_id") or "").strip(),
            target_chart_id=str(payload.get("target_chart_id") or payload.get("target_id") or "").strip(),
            source_anchor=str(payload.get("source_anchor") or "right"),
            target_anchor=str(payload.get("target_anchor") or "left"),
            active=bool(payload.get("active", True)),
            created_at=str(payload.get("created_at") or _timestamp_now()),
        ).normalized()


@dataclass
class DashboardChartRelation:
    relation_id: str = ""
    source_chart_id: str = ""
    target_chart_id: str = ""
    source_id: str = ""
    target_id: str = ""
    source_field: str = ""
    target_field: str = ""
    interaction_mode: str = "filter"
    direction: str = "both"
    active: bool = True
    created_at: str = field(default_factory=_timestamp_now)

    @staticmethod
    def _normalize_interaction_mode(value: Any) -> str:
        text = str(value or "filter").strip().lower()
        if text in {"none", "nenhum", "off", "disabled", "disable"}:
            return "none"
        return "filter"

    @staticmethod
    def _normalize_direction(value: Any) -> str:
        text = str(value or "both").strip().lower()
        if text in {
            "origem_para_destino",
            "source_to_target",
            "forward",
            "origem->destino",
            "origem_destino",
        }:
            return "origem_para_destino"
        if text in {
            "destino_para_origem",
            "target_to_source",
            "backward",
            "destino->origem",
            "destino_origem",
            "reverse",
        }:
            return "destino_para_origem"
        return "both"

    def normalized(self) -> "DashboardChartRelation":
        return DashboardChartRelation(
            relation_id=str(self.relation_id or "").strip() or uuid.uuid4().hex,
            source_chart_id=str(self.source_chart_id or "").strip(),
            target_chart_id=str(self.target_chart_id or "").strip(),
            source_id=str(self.source_id or "").strip(),
            target_id=str(self.target_id or "").strip(),
            source_field=str(self.source_field or "").strip(),
            target_field=str(self.target_field or "").strip(),
            interaction_mode=self._normalize_interaction_mode(self.interaction_mode),
            direction=self._normalize_direction(self.direction),
            active=bool(self.active),
            created_at=str(self.created_at or _timestamp_now()),
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "relation_id": normalized.relation_id,
            "source_chart_id": normalized.source_chart_id,
            "target_chart_id": normalized.target_chart_id,
            "source_id": normalized.source_id,
            "target_id": normalized.target_id,
            "source_field": normalized.source_field,
            "target_field": normalized.target_field,
            "interaction_mode": normalized.interaction_mode,
            "direction": normalized.direction,
            "active": bool(normalized.active),
            "created_at": normalized.created_at,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardChartRelation":
        payload = dict(data or {})
        return cls(
            relation_id=str(payload.get("relation_id") or payload.get("id") or "").strip(),
            source_chart_id=str(payload.get("source_chart_id") or payload.get("source_id") or "").strip(),
            target_chart_id=str(payload.get("target_chart_id") or payload.get("target_id") or "").strip(),
            source_id=str(
                payload.get("source_id_value")
                or payload.get("source_data_id")
                or payload.get("source_binding_id")
                or payload.get("source_id")
                or ""
            ),
            target_id=str(
                payload.get("target_id_value")
                or payload.get("target_data_id")
                or payload.get("target_binding_id")
                or payload.get("target_id")
                or ""
            ),
            source_field=str(payload.get("source_field") or payload.get("field_origin") or "").strip(),
            target_field=str(payload.get("target_field") or payload.get("field_target") or "").strip(),
            interaction_mode=str(payload.get("interaction_mode") or "filter"),
            direction=str(payload.get("direction") or "both"),
            active=bool(payload.get("active", True)),
            created_at=str(payload.get("created_at") or _timestamp_now()),
        ).normalized()

    def duplicate_key(self) -> Tuple[str, str, str, str]:
        source_chart_id = str(self.source_chart_id or "").strip().lower()
        target_chart_id = str(self.target_chart_id or "").strip().lower()
        source_field = str(self.source_field or "").strip().lower()
        target_field = str(self.target_field or "").strip().lower()
        normal = (source_chart_id, source_field, target_chart_id, target_field)
        reverse = (target_chart_id, target_field, source_chart_id, source_field)
        return normal if normal <= reverse else reverse


@dataclass
class DashboardPage:
    page_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "Page 1"
    items: List[DashboardChartItem] = field(default_factory=list)
    visual_links: List[DashboardVisualLink] = field(default_factory=list)
    chart_relations: List[DashboardChartRelation] = field(default_factory=list)
    zoom: float = 1.0
    filters: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def normalized(self) -> "DashboardPage":
        normalized_items = [item.clone() for item in list(self.items or [])]
        normalized_items.sort(key=lambda item: (item.layout.y, item.layout.x, item.created_at))
        return DashboardPage(
            page_id=str(self.page_id or uuid.uuid4().hex).strip(),
            title=str(self.title or "Page 1").strip() or "Page 1",
            items=normalized_items,
            visual_links=[DashboardVisualLink.from_dict(link.to_dict()) for link in list(self.visual_links or [])],
            chart_relations=[DashboardChartRelation.from_dict(rel.to_dict()) for rel in list(self.chart_relations or [])],
            zoom=max(0.6, min(2.0, float(self.zoom or 1.0))),
            filters={str(key): dict(value or {}) for key, value in dict(self.filters or {}).items()},
        )

    def to_dict(self) -> Dict[str, Any]:
        normalized = self.normalized()
        return {
            "page_id": normalized.page_id,
            "title": normalized.title,
            "zoom": float(normalized.zoom),
            "filters": _json_safe(normalized.filters),
            "items": [item.to_dict() for item in normalized.items],
            "visual_links": [link.to_dict() for link in normalized.visual_links],
            "chart_relations": [relation.to_dict() for relation in normalized.chart_relations],
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardPage":
        payload = dict(data or {})
        filters = payload.get("filters")
        if filters is None:
            filters = payload.get("active_filters") or {}
        return cls(
            page_id=str(payload.get("page_id") or payload.get("id") or uuid.uuid4().hex).strip(),
            title=str(payload.get("title") or payload.get("name") or "Page 1"),
            items=[DashboardChartItem.from_dict(item) for item in list(payload.get("items") or [])],
            visual_links=[DashboardVisualLink.from_dict(item) for item in list(payload.get("visual_links") or [])],
            chart_relations=[DashboardChartRelation.from_dict(item) for item in list(payload.get("chart_relations") or [])],
            zoom=float(payload.get("zoom", 1.0) or 1.0),
            filters={str(key): dict(value or {}) for key, value in dict(filters or {}).items()},
        ).normalized()


@dataclass
class DashboardProject:
    name: str = "Novo painel"
    project_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    version: int = 2
    items: List[DashboardChartItem] = field(default_factory=list)
    visual_links: List[DashboardVisualLink] = field(default_factory=list)
    chart_relations: List[DashboardChartRelation] = field(default_factory=list)
    pages: List[DashboardPage] = field(default_factory=list)
    active_page_id: str = ""
    created_at: str = field(default_factory=_timestamp_now)
    updated_at: str = field(default_factory=_timestamp_now)
    edit_mode: bool = True
    source_meta: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        self.updated_at = _timestamp_now()

    def has_pages(self) -> bool:
        return bool(self.pages)

    def active_page(self) -> DashboardPage:
        if self.pages:
            current_id = str(self.active_page_id or "").strip()
            if current_id:
                for page in self.pages:
                    if str(page.page_id or "").strip() == current_id:
                        return page.normalized()
            return self.pages[0].normalized()
        return DashboardPage(
            page_id=self.active_page_id or uuid.uuid4().hex,
            title="Page 1",
            items=[item.clone() for item in list(self.items or [])],
            visual_links=[DashboardVisualLink.from_dict(link.to_dict()) for link in list(self.visual_links or [])],
            chart_relations=[DashboardChartRelation.from_dict(rel.to_dict()) for rel in list(self.chart_relations or [])],
        ).normalized()

    def set_active_page(self, page_id: str):
        self.active_page_id = str(page_id or "").strip()
        page = self.active_page()
        self.items = [item.clone() for item in list(page.items or [])]
        self.visual_links = [DashboardVisualLink.from_dict(link.to_dict()) for link in list(page.visual_links or [])]
        self.chart_relations = [DashboardChartRelation.from_dict(rel.to_dict()) for rel in list(page.chart_relations or [])]

    def to_dict(self) -> Dict[str, Any]:
        self._normalize_graph_state()
        self.version = max(2, int(self.version or 2))
        self.touch()
        page = self.active_page()
        pages_payload = [page_item.to_dict() for page_item in list(self.pages or [])]
        if not pages_payload:
            pages_payload = [page.to_dict()]
        self.active_page_id = page.page_id
        self.items = [item.clone() for item in list(page.items or [])]
        self.visual_links = [DashboardVisualLink.from_dict(link.to_dict()) for link in list(page.visual_links or [])]
        self.chart_relations = [DashboardChartRelation.from_dict(rel.to_dict()) for rel in list(page.chart_relations or [])]
        return {
            "version": int(self.version),
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "edit_mode": bool(self.edit_mode),
            "source_meta": _json_safe(self.source_meta),
            "active_page_id": self.active_page_id,
            "pages": pages_payload,
            "items": [item.to_dict() for item in self.items],
            "visual_links": [link.to_dict() for link in self.visual_links],
            "chart_relations": [relation.to_dict() for relation in self.chart_relations],
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DashboardProject":
        payload = dict(data or {})
        raw_pages = list(payload.get("pages") or [])
        legacy_single_page = not raw_pages
        pages = [DashboardPage.from_dict(item) for item in raw_pages if isinstance(item, dict)]
        legacy_items = [DashboardChartItem.from_dict(item) for item in list(payload.get("items") or [])]
        legacy_links = [DashboardVisualLink.from_dict(item) for item in list(payload.get("visual_links") or [])]
        legacy_relations = [DashboardChartRelation.from_dict(item) for item in list(payload.get("chart_relations") or [])]
        active_page_id = str(payload.get("active_page_id") or "").strip()
        if not pages:
            pages = [
                DashboardPage(
                    page_id=active_page_id or uuid.uuid4().hex,
                    title=str(payload.get("page_title") or "Page 1"),
                    items=legacy_items,
                    visual_links=legacy_links,
                    chart_relations=legacy_relations,
                    zoom=float(payload.get("zoom", 1.0) or 1.0),
                    filters=dict(payload.get("filters") or payload.get("active_filters") or {}),
                ).normalized()
            ]
        if not active_page_id and pages:
            active_page_id = pages[0].page_id
        project = cls(
            name=str(payload.get("name") or "Painel"),
            project_id=str(payload.get("project_id") or uuid.uuid4().hex),
            version=int(payload.get("version", 1) or 1),
            items=[item.clone() for item in list((pages[0].items if pages else legacy_items) or [])],
            visual_links=[DashboardVisualLink.from_dict(item.to_dict()) for item in list((pages[0].visual_links if pages else legacy_links) or [])],
            chart_relations=[DashboardChartRelation.from_dict(item.to_dict()) for item in list((pages[0].chart_relations if pages else legacy_relations) or [])],
            pages=pages,
            active_page_id=active_page_id,
            created_at=str(payload.get("created_at") or _timestamp_now()),
            updated_at=str(payload.get("updated_at") or _timestamp_now()),
            edit_mode=bool(payload.get("edit_mode", True)),
            source_meta=dict(payload.get("source_meta") or {}),
        )
        if legacy_single_page:
            project.source_meta["_legacy_single_page"] = True
        project.items.sort(key=lambda item: (item.layout.y, item.layout.x, item.created_at))
        project._normalize_graph_state()
        return project

    def copy(self) -> "DashboardProject":
        return DashboardProject.from_dict(copy.deepcopy(self.to_dict()))

    def _normalize_graph_state(self):
        if self.pages:
            normalized_pages: List[DashboardPage] = []
            for page in list(self.pages or []):
                normalized_page = page.normalized()
                normalized_pages.append(normalized_page)
            self.pages = normalized_pages
            active_page = self.active_page()
            self.items = [item.clone() for item in list(active_page.items or [])]
            self.visual_links = [DashboardVisualLink.from_dict(link.to_dict()) for link in list(active_page.visual_links or [])]
            self.chart_relations = [DashboardChartRelation.from_dict(rel.to_dict()) for rel in list(active_page.chart_relations or [])]
            return
        valid_ids = {item.item_id for item in self.items}

        unique_relations: List[DashboardChartRelation] = []
        seen_relation_keys = set()
        for relation in list(self.chart_relations or []):
            normalized = relation.normalized()
            if (
                not normalized.source_chart_id
                or not normalized.target_chart_id
                or normalized.source_chart_id == normalized.target_chart_id
                or normalized.source_chart_id not in valid_ids
                or normalized.target_chart_id not in valid_ids
                or not normalized.source_field
                or not normalized.target_field
            ):
                continue
            relation_key = normalized.duplicate_key()
            if relation_key in seen_relation_keys:
                continue
            seen_relation_keys.add(relation_key)
            unique_relations.append(normalized)
        self.chart_relations = unique_relations

        relation_ids = {relation.relation_id for relation in self.chart_relations}
        unique_links: List[DashboardVisualLink] = []
        seen_links = set()
        for link in list(self.visual_links or []):
            normalized = link.normalized()
            if (
                not normalized.source_chart_id
                or not normalized.target_chart_id
                or normalized.source_chart_id == normalized.target_chart_id
                or normalized.source_chart_id not in valid_ids
                or normalized.target_chart_id not in valid_ids
                or not normalized.relation_id
            ):
                continue
            if normalized.relation_id not in relation_ids:
                continue
            link_key = (
                normalized.relation_id,
                normalized.source_chart_id,
                normalized.target_chart_id,
                normalized.source_anchor,
                normalized.target_anchor,
            )
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            unique_links.append(normalized)

        if not unique_links and self.chart_relations:
            for relation in self.chart_relations:
                unique_links.append(
                    DashboardVisualLink(
                        relation_id=relation.relation_id,
                        source_chart_id=relation.source_chart_id,
                        target_chart_id=relation.target_chart_id,
                        source_anchor="right",
                        target_anchor="left",
                        active=bool(relation.active),
                    ).normalized()
                )
        self.visual_links = unique_links
