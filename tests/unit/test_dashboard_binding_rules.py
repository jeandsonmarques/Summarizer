from __future__ import annotations

from plugin.Summarizer.dashboard_models import (
    DashboardChartBinding,
    binding_slot_names,
    empty_binding_message,
    is_binding_slot_compatible,
    suggest_binding_slot,
)


def test_bar_slots_accept_category_value_legend_tooltip_and_filters():
    assert binding_slot_names("bar") == ["category", "values", "legend", "tooltip", "filters"]
    assert suggest_binding_slot("bar", "dimension", DashboardChartBinding(chart_type="bar")) == "category"
    assert suggest_binding_slot("bar", "measure", DashboardChartBinding(chart_type="bar")) == "values"
    assert is_binding_slot_compatible("bar", "category", "dimension")
    assert is_binding_slot_compatible("bar", "values", "measure")
    assert not is_binding_slot_compatible("bar", "values", "dimension")


def test_card_uses_only_value_slot_and_does_not_require_category():
    binding = DashboardChartBinding(chart_type="card", measure_field="revenue").normalized()

    assert binding_slot_names("card") == ["values"]
    assert binding.has_minimum_fields()
    assert suggest_binding_slot("card", "measure", DashboardChartBinding(chart_type="card")) == "values"
    assert suggest_binding_slot("card", "dimension", DashboardChartBinding(chart_type="card")) == ""


def test_scatter_auto_slots_first_and_second_numeric_as_x_y():
    binding = DashboardChartBinding(chart_type="scatter")

    assert suggest_binding_slot("scatter", "measure", binding) == "x"
    binding = DashboardChartBinding(chart_type="scatter", x_field="longitude").normalized()
    assert suggest_binding_slot("scatter", "measure", binding) == "y"
    binding = DashboardChartBinding(chart_type="scatter", x_field="longitude", y_field="volume").normalized()
    assert suggest_binding_slot("scatter", "measure", binding) == "size"


def test_scatter_text_goes_to_legend_before_tooltip():
    binding = DashboardChartBinding(chart_type="scatter", x_field="x", y_field="y").normalized()

    assert suggest_binding_slot("scatter", "dimension", binding) == "legend"
    binding.legend_field = "region"
    assert suggest_binding_slot("scatter", "dimension", binding) == "tooltip"


def test_matrix_supports_multiple_rows_columns_and_values_round_trip():
    binding = DashboardChartBinding(
        chart_type="matrix",
        row_fields=["municipio", "bairro"],
        column_fields=["status"],
        value_fields=["volume", "ligacoes"],
        aggregation="sum",
    ).normalized()

    assert binding.has_minimum_fields()
    assert binding.to_dict()["row_fields"] == ["municipio", "bairro"]
    assert binding.to_dict()["value_fields"] == ["volume", "ligacoes"]
    assert suggest_binding_slot("matrix", "dimension", binding) == "columns"
    assert suggest_binding_slot("matrix", "measure", binding) == "values"


def test_incomplete_visuals_have_specific_empty_messages():
    assert empty_binding_message("card", DashboardChartBinding(chart_type="card")) == "Arraste uma medida para Valor."
    assert empty_binding_message("scatter", DashboardChartBinding(chart_type="scatter")) == "Arraste campos numericos para X e Y."
    assert empty_binding_message("matrix", DashboardChartBinding(chart_type="matrix")) == "Arraste campos para Linhas e Valores."
    assert empty_binding_message("bar", DashboardChartBinding(chart_type="bar")) == "Arraste uma categoria e uma medida."
