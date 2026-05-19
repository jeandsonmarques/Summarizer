from __future__ import annotations

from importlib import util
from pathlib import Path


def _load_settings_dialog_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "plugin"
        / "Summarizer"
        / "pivot_view"
        / "pivot_settings_dialog.py"
    )
    spec = util.spec_from_file_location("pivot_settings_dialog_test", module_path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


settings_dialog = _load_settings_dialog_module()


class DummyWidget:
    def __init__(self, row_height=30, alternating_rows=True, header_compact=True):
        self._table_row_height = row_height
        self._table_alternating_rows = alternating_rows
        self._table_header_compact = header_compact


def test_normalize_table_row_height_clamps_to_limits():
    assert settings_dialog.normalize_table_row_height(10) == 24
    assert settings_dialog.normalize_table_row_height(30) == 30
    assert settings_dialog.normalize_table_row_height(99) == 52


def test_normalize_table_row_height_uses_default_for_invalid_value():
    assert settings_dialog.normalize_table_row_height("not-a-number") == 30


def test_build_table_settings_defaults_reads_widget_state():
    widget = DummyWidget(row_height="40", alternating_rows=0, header_compact=1)

    defaults = settings_dialog.build_table_settings_defaults(widget)

    assert defaults == {
        "row_height": 40,
        "alternating_rows": False,
        "header_compact": True,
    }


def test_build_table_settings_defaults_falls_back_to_current_defaults():
    widget = object()

    defaults = settings_dialog.build_table_settings_defaults(widget)

    assert defaults["row_height"] == 30
    assert defaults["alternating_rows"] is True
    assert defaults["header_compact"] is True


def test_normalize_table_settings_validates_number_and_boolean_flags():
    settings = settings_dialog.normalize_table_settings(
        "999",
        "",
        0,
    )

    assert settings == {
        "row_height": 52,
        "alternating_rows": False,
        "header_compact": False,
    }


def test_apply_table_settings_updates_widget_and_returns_normalized_settings():
    widget = DummyWidget(row_height=24, alternating_rows=True, header_compact=False)
    calls = []

    settings = settings_dialog.apply_table_settings(
        widget,
        row_height="25",
        alternating_rows=1,
        header_compact=0,
        apply_callback=lambda: calls.append("done"),
    )

    assert settings == {
        "row_height": 25,
        "alternating_rows": True,
        "header_compact": False,
    }
    assert widget._table_row_height == 25
    assert widget._table_alternating_rows is True
    assert widget._table_header_compact is False
    assert calls == ["done"]
