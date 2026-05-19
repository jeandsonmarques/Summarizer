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
    yield pivot
    pivot.deleteLater()


def _summary_data(rows=None, *, layer_name="Camada Teste"):
    rows = rows or [
        ["A", 10.0, "Norte"],
        ["A", 5.0, "Norte"],
        ["B", 20.0, "Sul"],
        ["C", None, "Sul"],
    ]
    return {
        "metadata": {
            "layer_id": "",
            "layer_name": layer_name,
            "field_name": "Valor",
            "filter_expression": "",
        },
        "raw_data": {
            "columns": ["Categoria", "Valor", "Filtro"],
            "rows": rows,
        },
        "basic_stats": {"total": 35.0},
        "grouped_data": {},
        "percentiles": {},
    }


def _set_combo_data(combo, value):
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return True
    return False


def _field_spec(widget, field_name):
    spec = widget._field_spec_from_field_name(field_name)
    assert spec is not None
    return spec


def _configure_simple_sum_pivot(widget):
    widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)
    widget._add_field_to_area("value", _field_spec(widget, "Valor"), auto_refresh=False)
    assert _set_combo_data(widget.agg_combo, "sum")
    widget.refresh()


def test_set_summary_data_keeps_metadata_and_raw_data(widget):
    summary_data = _summary_data()

    widget.set_summary_data(summary_data)

    assert widget.get_summary_metadata()["layer_name"] == "Camada Teste"
    assert widget.get_summary_metadata()["field_name"] == "Valor"
    assert widget._current_summary_data["raw_data"] == summary_data["raw_data"]
    assert list(widget.raw_df.columns) == ["Categoria", "Valor", "Filtro"]
    assert len(widget.raw_df) == 4


def test_get_current_configuration_returns_core_areas(widget):
    widget.set_summary_data(_summary_data())
    widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)
    widget._add_field_to_area("column", _field_spec(widget, "Filtro"), auto_refresh=False)
    widget._add_field_to_area("filter", _field_spec(widget, "Filtro"), auto_refresh=False)
    widget._add_field_to_area("value", _field_spec(widget, "Valor"), auto_refresh=False)
    assert _set_combo_data(widget.agg_combo, "sum")

    config = widget.get_current_configuration()

    assert config["aggregation"] == "sum"
    assert config["row_fields"] == ["Categoria"]
    assert config["column_fields"] == ["Filtro"]
    assert config["filter_fields"] == ["Filtro"]
    assert config["value_field"] == "Valor"


def test_get_visible_pivot_dataframe_is_safe_when_empty(widget):
    visible = widget.get_visible_pivot_dataframe()

    assert visible.empty


def test_dataframe_pivot_with_simple_row_and_value(widget):
    widget.set_summary_data(_summary_data())

    _configure_simple_sum_pivot(widget)

    assert not widget.pivot_df.empty
    assert list(widget.pivot_df.columns) == ["Categoria", "SUM(Valor)", "% do total"]
    totals = dict(zip(widget.pivot_df["Categoria"], widget.pivot_df["SUM(Valor)"]))
    assert totals["B"] == 20.0
    assert totals["A"] == 15.0


def test_dataframe_pivot_with_filter_area_does_not_break(widget):
    widget.set_summary_data(_summary_data())
    widget._add_field_to_area("filter", _field_spec(widget, "Filtro"), auto_refresh=False)

    _configure_simple_sum_pivot(widget)

    config = widget.get_current_configuration()
    assert config["filter_fields"] == ["Filtro"]
    assert not widget.get_visible_pivot_dataframe().empty


def test_missing_field_configuration_does_not_break(widget):
    widget.set_summary_data(_summary_data())

    widget._apply_saved_configuration(
        {
            "row_fields": ["Campo inexistente"],
            "column_fields": ["Outra coluna inexistente"],
            "filter_fields": ["Filtro inexistente"],
            "value_field": "Valor inexistente",
            "aggregation": "sum",
        }
    )
    widget.refresh()

    config = widget.get_current_configuration()
    assert config["row_fields"] == []
    assert config["column_fields"] == []
    assert config["filter_fields"] == []
    assert widget.get_visible_pivot_dataframe().empty or widget.pivot_df is not None


def test_dataframe_pivot_handles_null_values(widget):
    widget.set_summary_data(
        _summary_data(
            rows=[
                ["A", 10.0, "Norte"],
                ["A", None, "Norte"],
                [None, 5.0, "Sul"],
            ]
        )
    )

    _configure_simple_sum_pivot(widget)

    assert not widget.pivot_df.empty
    assert "SUM(Valor)" in widget.pivot_df.columns
    assert widget.pivot_df["SUM(Valor)"].notna().any()


def test_configuration_round_trip_by_metadata_key(widget):
    first_summary = _summary_data(layer_name="Camada A")
    second_summary = _summary_data(layer_name="Camada B")

    widget.set_summary_data(first_summary)
    widget._add_field_to_area("row", _field_spec(widget, "Categoria"), auto_refresh=False)
    widget._add_field_to_area("value", _field_spec(widget, "Valor"), auto_refresh=False)
    assert _set_combo_data(widget.agg_combo, "sum")

    widget.set_summary_data(second_summary)
    assert widget.get_current_configuration()["row_fields"] == []

    widget.set_summary_data(first_summary)
    config = widget.get_current_configuration()
    assert config["row_fields"] == ["Categoria"]
    assert config["value_field"] == "Valor"
    assert config["aggregation"] == "sum"

