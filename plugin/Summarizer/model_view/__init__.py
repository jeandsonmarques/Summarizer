from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MAP = {
    "ModelCanvas": (".model_canvas", "ModelCanvas"),
    "ModelCanvasView": (".model_canvas_view", "ModelCanvasView"),
    "ModelCanvasScene": (".model_canvas_scene", "ModelCanvasScene"),
    "TableCardItem": (".table_card_item", "TableCardItem"),
    "FieldItem": (".field_item", "FieldItem"),
    "RelationshipItem": (".relationship_item", "RelationshipItem"),
    "ModelManager": (".model_manager", "ModelManager"),
    "UnifiedLayerDialog": (".unified_layer_dialog", "UnifiedLayerDialog"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | set(_EXPORT_MAP.keys()))


__all__ = list(_EXPORT_MAP.keys())
