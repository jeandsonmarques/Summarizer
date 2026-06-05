# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Jeandson Marques

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pandas as pd


def configuration_key_from_metadata(metadata: Optional[Dict[str, Any]]) -> str:
    payload = dict(metadata or {})
    layer_id = str(payload.get("layer_id") or "").strip()
    if layer_id:
        return f"layer:{layer_id}"
    layer_name = str(payload.get("layer_name") or "").strip()
    if layer_name:
        return f"name:{layer_name}"
    return ""


def field_spec_from_field_name(host: Any, field_name: Optional[str]):
    target = str(field_name or "").strip()
    if not target:
        return None
    for spec in getattr(host, "_field_specs_by_key", {}).values():
        if getattr(spec, "field_name", None) == target:
            return spec
    return None


def get_current_configuration(host: Any) -> Dict[str, Any]:
    value_spec = host._field_spec_from_key(host.value_field_combo.currentData())
    row_specs = host._selected_area_specs("row")
    column_specs = host._selected_area_specs("column")
    filter_specs = host._selected_area_specs("filter")
    row_fields = [spec.field_name for spec in row_specs]
    column_fields = [spec.field_name for spec in column_specs]
    filter_fields = [spec.field_name for spec in filter_specs]
    return {
        "aggregation": host.agg_combo.currentData(),
        "aggregation_label": host.agg_combo.currentText(),
        "value_field": value_spec.field_name if value_spec is not None else None,
        "value_label": (
            value_spec.display_name
            if value_spec is not None
            else host.value_field_combo.currentText()
        ),
        "row_field": row_fields[0] if row_fields else None,
        "row_label": (
            " / ".join(spec.display_name for spec in row_specs)
            if row_specs
            else host.row_field_combo.currentText()
        ),
        "row_fields": row_fields,
        "row_labels": [spec.display_name for spec in row_specs],
        "column_field": column_fields[0] if column_fields else None,
        "column_label": (
            " / ".join(spec.display_name for spec in column_specs)
            if column_specs
            else host.column_field_combo.currentText()
        ),
        "column_fields": column_fields,
        "column_labels": [spec.display_name for spec in column_specs],
        "filter_field": filter_fields[0] if filter_fields else None,
        "filter_label": (
            " / ".join(spec.display_name for spec in filter_specs)
            if filter_specs
            else host.filter_field_combo.currentText()
        ),
        "filter_fields": filter_fields,
        "filter_labels": [spec.display_name for spec in filter_specs],
        "only_selected": host.only_selected_check.isChecked(),
        "include_nulls": host.include_nulls_check.isChecked(),
    }


def get_summary_metadata(host: Any) -> Dict[str, str]:
    metadata = dict(getattr(host, "_current_metadata", {}) or {})
    current_result = getattr(host, "_current_pivot_result", None)
    if current_result is not None:
        metadata.update(dict(getattr(current_result, "metadata", {}) or {}))
    return metadata


def get_current_pivot_result(host: Any):
    return getattr(host, "_current_pivot_result", None)


def get_visible_pivot_dataframe(host: Any) -> pd.DataFrame:
    pivot_df = getattr(host, "pivot_df", None)
    if pivot_df is None or pivot_df.empty:
        return pd.DataFrame()

    table_model = getattr(host, "table_model", None)
    if table_model is None or table_model.columnCount() == 0:
        return pd.DataFrame(columns=pivot_df.columns)

    proxy_model = getattr(host, "proxy_model", None)
    if proxy_model is None:
        return pivot_df.copy().reset_index(drop=True)

    visible_rows: List[int] = []
    for row in range(proxy_model.rowCount()):
        proxy_index = proxy_model.index(row, 0)
        if not proxy_index.isValid():
            continue
        source_index = proxy_model.mapToSource(proxy_index)
        if not source_index.isValid():
            continue
        visible_rows.append(source_index.row())

    if not visible_rows:
        return pd.DataFrame(columns=pivot_df.columns)

    return pivot_df.iloc[visible_rows].reset_index(drop=True)


def history_snapshot(host: Any) -> Dict[str, Any]:
    snapshot = dict(get_current_configuration(host) or {})
    snapshot["_tools_panels_hidden"] = bool(getattr(host, "_tools_panels_hidden", False))
    snapshot["_fields_panel_collapsed"] = bool(getattr(host, "_fields_panel_collapsed", False))
    snapshot["_filters_panel_collapsed"] = bool(getattr(host, "_filters_panel_collapsed", False))
    return snapshot


def history_snapshot_key(snapshot: Optional[Dict[str, Any]]) -> str:
    payload = dict(snapshot or {})
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=True)
    except Exception:
        return str(payload)


def reset_history_state(host: Any):
    host._history_undo = []
    host._history_redo = []
    host._history_current = history_snapshot(host)
    host._update_undo_redo_buttons()


def commit_history_if_changed(host: Any):
    if getattr(host, "_history_restoring", False) or getattr(host, "_block_updates", False):
        return
    snapshot = history_snapshot(host)
    if getattr(host, "_history_current", None) is None:
        host._history_current = snapshot
        host._update_undo_redo_buttons()
        return
    if history_snapshot_key(snapshot) == history_snapshot_key(host._history_current):
        host._update_undo_redo_buttons()
        return
    host._history_undo.append(dict(host._history_current))
    history_limit = int(getattr(host, "_history_limit", 80))
    if len(host._history_undo) > history_limit:
        host._history_undo = host._history_undo[-history_limit:]
    host._history_current = snapshot
    host._history_redo = []
    host._update_undo_redo_buttons()


def _apply_history_snapshot(host: Any, snapshot: Optional[Dict[str, Any]]):
    payload = dict(snapshot or {})
    config = dict(payload)
    tools_hidden = bool(config.pop("_tools_panels_hidden", host._tools_panels_hidden))
    host._fields_panel_collapsed = bool(
        config.pop("_fields_panel_collapsed", host._fields_panel_collapsed)
    )
    host._filters_panel_collapsed = bool(
        config.pop("_filters_panel_collapsed", host._filters_panel_collapsed)
    )
    host._history_restoring = True
    host._block_updates = True
    try:
        host._apply_saved_configuration(config)
    finally:
        host._block_updates = False
        host._history_restoring = False
    host._apply_tools_panels_visibility(not tools_hidden)
    host.refresh()
    host._history_current = history_snapshot(host)
    host._update_undo_redo_buttons()


def undo_last_action(host: Any):
    if not getattr(host, "_history_undo", None):
        host._update_undo_redo_buttons()
        return
    current_snapshot = history_snapshot(host)
    target_snapshot = dict(host._history_undo.pop())
    host._history_redo.append(current_snapshot)
    _apply_history_snapshot(host, target_snapshot)


def redo_last_action(host: Any):
    if not getattr(host, "_history_redo", None):
        host._update_undo_redo_buttons()
        return
    current_snapshot = history_snapshot(host)
    target_snapshot = dict(host._history_redo.pop())
    host._history_undo.append(current_snapshot)
    _apply_history_snapshot(host, target_snapshot)


def restore_default_summary_layout(host: Any):
    host._fields_panel_collapsed = False
    host._filters_panel_collapsed = False
    host._tools_fields_width = host._tools_fields_default_width
    host._tools_builder_width = host._tools_filters_default_width
    host._apply_tools_panels_visibility(True)


def store_current_configuration(host: Any, key: str):
    if not key:
        return
    raw_df = getattr(host, "raw_df", None)
    if raw_df is None or raw_df.empty:
        return
    try:
        host._saved_configurations[key] = dict(get_current_configuration(host) or {})
    except Exception:
        return


def restore_saved_configuration_for_metadata(host: Any, metadata: Optional[Dict[str, Any]]):
    key = configuration_key_from_metadata(metadata)
    if not key:
        return
    config = dict(getattr(host, "_saved_configurations", {}).get(key) or {})
    if not config:
        return
    host._apply_saved_configuration(config)


def apply_saved_configuration(host: Any, config: Dict[str, Any]):
    if not config:
        return

    host.filter_fields_list.clear()
    host.row_fields_list.clear()
    host.column_fields_list.clear()
    host.value_fields_list.clear()
    host._sync_area_placeholder()

    aggregation = str(config.get("aggregation") or "count")
    for index in range(host.agg_combo.count()):
        if str(host.agg_combo.itemData(index) or "") == aggregation:
            host.agg_combo.setCurrentIndex(index)
            break

    row_fields = list(config.get("row_fields") or [])
    column_fields = list(config.get("column_fields") or [])
    filter_fields = list(config.get("filter_fields") or [])

    for field_name in row_fields:
        spec = field_spec_from_field_name(host, field_name)
        if spec is not None:
            host._add_field_to_area("row", spec, auto_refresh=False)

    for field_name in column_fields:
        spec = field_spec_from_field_name(host, field_name)
        if spec is not None:
            host._add_field_to_area("column", spec, auto_refresh=False)

    for field_name in filter_fields:
        spec = field_spec_from_field_name(host, field_name)
        if spec is not None:
            host._add_field_to_area("filter", spec, auto_refresh=False)

    value_field = str(config.get("value_field") or "").strip()
    if value_field:
        spec = field_spec_from_field_name(host, value_field)
        if spec is not None:
            spec_key = host._register_field_spec(spec)
            idx = host.value_field_combo.findData(spec_key)
            if idx != -1:
                host.value_field_combo.setCurrentIndex(idx)
    host._sync_value_area_from_combo()

    host.only_selected_check.setChecked(bool(config.get("only_selected")))
    host.include_nulls_check.setChecked(bool(config.get("include_nulls")))
    host.advanced_group.setChecked(aggregation != "count")
    host._on_advanced_toggled(aggregation != "count")
    host._sync_area_placeholder()

    if row_fields:
        host._set_last_active_area("row")
    elif column_fields:
        host._set_last_active_area("column")


class PivotStateController:
    def __init__(self, host: Any):
        self.host = host

    def get_current_configuration(self):
        return get_current_configuration(self.host)

    def get_summary_metadata(self):
        return get_summary_metadata(self.host)

    def get_visible_pivot_dataframe(self):
        return get_visible_pivot_dataframe(self.host)

    def get_current_pivot_result(self):
        return get_current_pivot_result(self.host)

    def reset_history_state(self):
        return reset_history_state(self.host)

    def commit_history_if_changed(self):
        return commit_history_if_changed(self.host)

    def undo_last_action(self):
        return undo_last_action(self.host)

    def redo_last_action(self):
        return redo_last_action(self.host)

    def restore_default_summary_layout(self):
        return restore_default_summary_layout(self.host)

    def store_current_configuration(self, key: str):
        return store_current_configuration(self.host, key)

    def restore_saved_configuration_for_metadata(self, metadata: Optional[Dict[str, Any]]):
        return restore_saved_configuration_for_metadata(self.host, metadata)

    def apply_saved_configuration(self, config: Dict[str, Any]):
        return apply_saved_configuration(self.host, config)


__all__ = [
    "PivotStateController",
    "apply_saved_configuration",
    "commit_history_if_changed",
    "configuration_key_from_metadata",
    "field_spec_from_field_name",
    "get_current_configuration",
    "get_current_pivot_result",
    "get_summary_metadata",
    "get_visible_pivot_dataframe",
    "history_snapshot",
    "history_snapshot_key",
    "redo_last_action",
    "reset_history_state",
    "restore_default_summary_layout",
    "restore_saved_configuration_for_metadata",
    "store_current_configuration",
    "undo_last_action",
]
