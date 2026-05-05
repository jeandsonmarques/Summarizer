from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Dict, Optional


def load_state_payload(raw: object) -> Dict[str, object]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        return json.loads(str(raw))
    except Exception:
        return {}


def build_layout_state(
    *,
    table_positions: Mapping[str, Mapping[str, object]],
    relationships: Sequence[Mapping[str, object]],
    zoom: object,
    order: Sequence[str],
    visible_tables: Sequence[str],
    connection_style: object,
    legend_visible: object,
) -> Dict[str, object]:
    return {
        "tables": {
            str(name): {"x": pos.get("x"), "y": pos.get("y")}
            for name, pos in table_positions.items()
        },
        "relationships": [dict(rel) for rel in relationships],
        "zoom": zoom,
        "order": list(order),
        "visible_tables": list(visible_tables),
        "connection_style": str(connection_style or "curved"),
        "legend_visible": bool(legend_visible),
    }


def snapshot_table_positions(table_items: Mapping[str, object]) -> Dict[str, Dict[str, float]]:
    snapshot: Dict[str, Dict[str, float]] = {}
    for name, item in (table_items or {}).items():
        pos = getattr(item, "pos", None)
        if callable(pos):
            point = pos()
            snapshot[str(name)] = {"x": point.x(), "y": point.y()}
    return snapshot


def snapshot_custom_relationships(
    relationship_items: Mapping[str, object],
) -> list[Dict[str, object]]:
    relationships: list[Dict[str, object]] = []
    for item in (relationship_items or {}).values():
        metadata = getattr(item, "metadata", None) or {}
        if isinstance(metadata, dict) and metadata.get("origin") == "custom":
            relationships.append(dict(metadata))
    return relationships


def dump_state_payload(payload: Mapping[str, object]) -> str:
    try:
        return json.dumps(dict(payload), ensure_ascii=False)
    except Exception:
        return "{}"


def build_export_preset(
    *,
    available_tables: Sequence[Mapping[str, object]],
    available_relationships: Sequence[Mapping[str, object]],
    layout_state: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    return {
        "tables": [dict(table) for table in available_tables],
        "relationships": [dict(rel) for rel in available_relationships],
        "layout_state": dict(layout_state or {}),
    }
