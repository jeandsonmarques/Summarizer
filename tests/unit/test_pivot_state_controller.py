from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugin" / "Summarizer" / "pivot_view" / "pivot_state_controller.py"

spec = importlib.util.spec_from_file_location(
    "Summarizer.pivot_view.pivot_state_controller",
    MODULE_PATH,
)
pivot_state_controller = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = pivot_state_controller
spec.loader.exec_module(pivot_state_controller)


class _FakeCombo:
    def __init__(self, values, current_index=0):
        self._values = list(values)
        self._current_index = current_index

    def currentData(self):
        return self._values[self._current_index][0]

    def currentText(self):
        return self._values[self._current_index][1]

    def count(self):
        return len(self._values)

    def itemData(self, index):
        return self._values[index][0]

    def setCurrentIndex(self, index):
        self._current_index = index

    def findData(self, value):
        for index, item in enumerate(self._values):
            if item[0] == value:
                return index
        return -1


class _FakeCheckBox:
    def __init__(self, checked=False):
        self._checked = checked

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = bool(checked)


class _FakeList:
    def __init__(self, host, area):
        self._host = host
        self._area = area

    def clear(self):
        self._host._selected[self._area] = []


class _FakeProxyIndex:
    def __init__(self, row):
        self._row = row

    def isValid(self):
        return True

    def row(self):
        return self._row


class _FakeSourceIndex:
    def __init__(self, row):
        self._row = row

    def isValid(self):
        return True

    def row(self):
        return self._row


class _FakeProxyModel:
    def __init__(self, rows):
        self._rows = list(rows)

    def rowCount(self):
        return len(self._rows)

    def index(self, row, column):
        return _FakeProxyIndex(row)

    def mapToSource(self, proxy_index):
        return _FakeSourceIndex(self._rows[proxy_index.row()])


class _FakeTableModel:
    def __init__(self, columns=1):
        self._columns = columns

    def columnCount(self):
        return self._columns


class _FakeSpec:
    def __init__(self, field_name, display_name):
        self.field_name = field_name
        self.display_name = display_name


class _FakeHost:
    def __init__(self):
        self._field_specs_by_key = {
            "row": _FakeSpec("linha", "Linha"),
            "column": _FakeSpec("coluna", "Coluna"),
            "value": _FakeSpec("valor", "Valor"),
        }
        self._spec_keys = {value.field_name: key for key, value in self._field_specs_by_key.items()}
        self.agg_combo = _FakeCombo([("sum", "Soma"), ("count", "Contagem")])
        self.value_field_combo = _FakeCombo([("value", "Valor")])
        self.row_field_combo = _FakeCombo([("", "Linha")])
        self.column_field_combo = _FakeCombo([("", "Coluna")])
        self.filter_field_combo = _FakeCombo([("", "Filtro")])
        self.only_selected_check = _FakeCheckBox(True)
        self.include_nulls_check = _FakeCheckBox(False)
        self.advanced_group = _FakeCheckBox(True)
        self.filter_fields_list = _FakeList(self, "filter")
        self.row_fields_list = _FakeList(self, "row")
        self.column_fields_list = _FakeList(self, "column")
        self.value_fields_list = _FakeList(self, "value")
        self._saved_configurations = {}
        self.raw_df = pd.DataFrame({"linha": ["A"]})
        self._current_metadata = {"layer_id": "layer-1", "layer_name": "Camada 1"}
        self._current_pivot_result = SimpleNamespace(metadata={"source": "pivot"})
        self._tools_panels_hidden = False
        self._fields_panel_collapsed = False
        self._filters_panel_collapsed = False
        self._tools_fields_width = 120
        self._tools_builder_width = 160
        self._tools_fields_default_width = 120
        self._tools_filters_default_width = 160
        self._history_limit = 80
        self._history_undo = []
        self._history_redo = []
        self._history_current = None
        self._history_restoring = False
        self._block_updates = False
        self._selected = {"row": [self._field_specs_by_key["row"]], "column": [], "filter": []}
        self._active_area = None

        def _apply_saved_configuration(config):
            return pivot_state_controller.apply_saved_configuration(self, config)

        self._apply_saved_configuration = _apply_saved_configuration

    def _field_spec_from_key(self, spec_key):
        return self._field_specs_by_key.get(spec_key)

    def _selected_area_specs(self, area):
        return list(self._selected.get(area, []))

    def _add_field_to_area(self, area, spec, auto_refresh=False):
        self._selected.setdefault(area, []).append(spec)

    def _register_field_spec(self, spec):
        return self._spec_keys[spec.field_name]

    def _sync_value_area_from_combo(self):
        return None

    def _sync_area_placeholder(self):
        return None

    def _on_advanced_toggled(self, enabled):
        self._advanced = bool(enabled)

    def _set_last_active_area(self, area):
        self._active_area = area

    def _apply_tools_panels_visibility(self, visible):
        self._tools_panels_visible = bool(visible)

    def _update_undo_redo_buttons(self):
        self._buttons_refreshed = True

    def refresh(self):
        self._refreshed = True


def test_configuration_round_trip_and_metadata_merge():
    host = _FakeHost()

    current = pivot_state_controller.get_current_configuration(host)
    assert current["row_fields"] == ["linha"]
    assert current["aggregation"] == "sum"
    assert current["only_selected"] is True

    metadata = pivot_state_controller.get_summary_metadata(host)
    assert metadata == {"layer_id": "layer-1", "layer_name": "Camada 1", "source": "pivot"}

    pivot_state_controller.store_current_configuration(host, "layer:layer-1")
    host._selected["row"] = [host._field_specs_by_key["column"]]
    host.only_selected_check.setChecked(False)
    pivot_state_controller.restore_saved_configuration_for_metadata(
        host,
        {"layer_id": "layer-1"},
    )

    restored = pivot_state_controller.get_current_configuration(host)
    assert restored["row_fields"] == ["linha"]
    assert restored["only_selected"] is True


def test_history_round_trip_undo_redo_restores_previous_state():
    host = _FakeHost()
    pivot_state_controller.reset_history_state(host)

    host._selected["row"] = [host._field_specs_by_key["column"]]
    pivot_state_controller.commit_history_if_changed(host)
    assert host._history_undo

    pivot_state_controller.undo_last_action(host)
    assert pivot_state_controller.get_current_configuration(host)["row_fields"] == ["linha"]

    pivot_state_controller.redo_last_action(host)
    assert pivot_state_controller.get_current_configuration(host)["row_fields"] == ["coluna"]


def test_visible_dataframe_respects_proxy_order():
    host = _FakeHost()
    host.pivot_df = pd.DataFrame({"value": [10, 20, 30]})
    host.table_model = _FakeTableModel(columns=1)
    host.proxy_model = _FakeProxyModel([2, 0])

    visible = pivot_state_controller.get_visible_pivot_dataframe(host)
    assert visible.to_dict("list") == {"value": [30, 10]}
