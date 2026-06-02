# ruff: noqa: E402
from __future__ import annotations

import pytest

qgis = pytest.importorskip("qgis", reason="QGIS not available in this environment.")

from qgis.PyQt.QtWidgets import QApplication  # noqa: E402

from Summarizer.pivot_table_widget import PivotTableWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def widget(qapp):
    pivot = PivotTableWidget(iface=None)
    pivot.set_summary_data(
        {
            "metadata": {
                "layer_id": "",
                "layer_name": "Camada Teste",
                "field_name": "Valor",
                "filter_expression": "",
            },
            "raw_data": {
                "columns": ["Categoria", "Valor", "Grupo"],
                "rows": [["A", 10.0, "Norte"], ["B", 20.0, "Sul"]],
            },
            "basic_stats": {},
            "grouped_data": {},
            "percentiles": {},
        }
    )
    yield pivot
    pivot.deleteLater()


def _field_spec(widget, field_name):
    spec = widget._field_spec_from_field_name(field_name)
    assert spec is not None
    return spec


def _area_names(widget, area):
    return [spec.display_name for spec in widget._selected_area_specs(area)]


def test_area_panel_adds_field_to_rows(widget):
    assert widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)

    assert _area_names(widget, "row") == ["Categoria"]


def test_area_panel_adds_field_to_values(widget):
    assert widget._add_field_to_area("value", _field_spec(widget, "Valor"), auto_refresh=False)

    assert _area_names(widget, "value") == ["Valor"]
    assert widget.value_field_combo.currentText() == "Valor"


def test_area_panel_removes_field(widget):
    widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)

    widget.row_fields_list.setCurrentRow(0)
    widget._remove_selected_area_field("row")

    assert _area_names(widget, "row") == []


def test_area_panel_reorders_fields(widget):
    widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)
    widget._add_field_to_area("row", _field_spec(widget, "Grupo"), auto_refresh=False)

    widget.row_fields_list.setCurrentRow(1)
    widget._move_selected_area_field("row", -1)

    assert _area_names(widget, "row") == ["Grupo", "Categoria"]


def test_area_panel_keeps_current_duplicate_rule(widget):
    first_added = widget._add_field_to_area(
        "row", _field_spec(widget, "Categoria"), auto_refresh=False
    )
    second_added = widget._add_field_to_area(
        "row", _field_spec(widget, "Categoria"), auto_refresh=False
    )

    assert first_added is True
    assert second_added is False
    assert _area_names(widget, "row") == ["Categoria"]
