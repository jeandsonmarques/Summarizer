from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Dict, List, Optional, Tuple


def normalize_direction(direction: Optional[object]) -> str:
    value = str(direction or "both").strip().lower()
    if value in ("forward", "origem", "source", "single", "source_to_target"):
        return "forward"
    if value in ("backward", "destino", "target", "target_to_source", "reverse"):
        return "backward"
    return "both"


def default_selected_fields(
    field_names: Sequence[object], exclude_field: Optional[object]
) -> List[str]:
    exclude = str(exclude_field or "").strip().lower()
    result: List[str] = []
    for name in field_names:
        text = str(name or "").strip()
        if text and text.lower() != exclude:
            result.append(text)
    return result


def relationship_signature(metadata: Mapping[str, object]) -> Tuple[str, str, str, str, str, str]:
    return (
        str(metadata.get("source_table") or ""),
        str(metadata.get("source_field") or ""),
        str(metadata.get("target_table") or ""),
        str(metadata.get("target_field") or ""),
        normalize_direction(metadata.get("direction") or metadata.get("flow_direction")),
        str(metadata.get("cardinality") or ""),
    )


def deduplicate_relationships(
    relationships: Sequence[Mapping[str, object]]
) -> List[Dict[str, object]]:
    seen: set[Tuple[str, str, str, str, str, str]] = set()
    result: List[Dict[str, object]] = []
    for rel in relationships or []:
        if not isinstance(rel, Mapping):
            continue
        signature = relationship_signature(rel)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(dict(rel))
    return result


def ensure_field_selections(
    metadata: MutableMapping[str, object],
    field_names_lookup: Callable[[Optional[str]], Sequence[object]],
    *,
    persist: bool = False,
    update_callback: Optional[
        Callable[[Optional[str], MutableMapping[str, object]], None]
    ] = None,
):
    direction = normalize_direction(metadata.get("direction") or metadata.get("flow_direction"))
    if "selected_fields_origin_to_dest" not in metadata:
        metadata["selected_fields_origin_to_dest"] = default_selected_fields(
            field_names_lookup(str(metadata.get("source_table") or "")),
            metadata.get("source_field"),
        )
    if "selected_fields_dest_to_origin" not in metadata:
        metadata["selected_fields_dest_to_origin"] = default_selected_fields(
            field_names_lookup(str(metadata.get("target_table") or "")),
            metadata.get("target_field"),
        )
    metadata["direction"] = direction
    if persist and update_callback is not None:
        update_callback(metadata.get("id"), metadata)
    return metadata
