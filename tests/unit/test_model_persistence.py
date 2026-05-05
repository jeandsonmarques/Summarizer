from types import SimpleNamespace

from plugin.Summarizer.model_view.model_persistence import (
    build_export_preset,
    build_layout_state,
    dump_state_payload,
    load_state_payload,
    snapshot_custom_relationships,
    snapshot_table_positions,
)


class _Point:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _TableItem:
    def __init__(self, x, y):
        self._point = _Point(x, y)

    def pos(self):
        return self._point


def test_state_round_trip_handles_legacy_json_strings():
    state = {
        "tables": {"orders": {"x": 10, "y": 20}},
        "relationships": [{"id": "r1"}],
        "zoom": 1.5,
    }

    raw = dump_state_payload(state)

    assert load_state_payload(raw) == state
    assert load_state_payload("") == {}
    assert load_state_payload("{broken json") == {}


def test_snapshot_helpers_build_safe_layout_payload():
    table_positions = snapshot_table_positions({"orders": _TableItem(12.5, 18.0)})
    relationships = snapshot_custom_relationships(
        {
            "r1": SimpleNamespace(metadata={"id": "r1", "origin": "custom"}),
            "r2": SimpleNamespace(metadata={"id": "r2", "origin": "project"}),
        }
    )
    layout = build_layout_state(
        table_positions=table_positions,
        relationships=relationships,
        zoom=2.0,
        order=["orders"],
        visible_tables=["orders"],
        connection_style="curved",
        legend_visible=True,
    )
    export = build_export_preset(
        available_tables=[{"name": "orders"}],
        available_relationships=[{"id": "r1"}],
        layout_state=layout,
    )

    assert table_positions == {"orders": {"x": 12.5, "y": 18.0}}
    assert relationships == [{"id": "r1", "origin": "custom"}]
    assert export["tables"] == [{"name": "orders"}]
    assert export["relationships"] == [{"id": "r1"}]
    assert export["layout_state"]["tables"]["orders"]["x"] == 12.5
