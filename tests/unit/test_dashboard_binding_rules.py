from __future__ import annotations

from plugin.Summarizer.dashboard_models import (
    DashboardChartBinding,
    FieldBindingItem,
    binding_slot_names,
    default_aggregation_for_binding,
    empty_binding_message,
    is_binding_slot_compatible,
    suggest_binding_slot,
)


def test_bar_slots_accept_category_value_legend_tooltip_and_filters():
    assert binding_slot_names("bar") == [
        "x_axis",
        "y_axis",
        "values",
        "legend",
        "tooltip",
        "filters",
    ]
    assert (
        suggest_binding_slot("bar", "dimension", DashboardChartBinding(chart_type="bar"))
        == "x_axis"
    )
    assert (
        suggest_binding_slot("bar", "measure", DashboardChartBinding(chart_type="bar"))
        == "values"
    )
    assert is_binding_slot_compatible("bar", "x_axis", "dimension")
    assert is_binding_slot_compatible("bar", "values", "measure")
    assert is_binding_slot_compatible("bar", "values", "dimension")


def test_card_uses_only_value_slot_and_does_not_require_category():
    binding = DashboardChartBinding(chart_type="card", measure_field="revenue").normalized()

    assert binding_slot_names("card") == ["values", "tooltip", "filters"]
    assert binding.has_minimum_fields()
    assert (
        suggest_binding_slot("card", "measure", DashboardChartBinding(chart_type="card"))
        == "values"
    )
    assert suggest_binding_slot("card", "dimension", DashboardChartBinding(chart_type="card")) == ""


def test_scatter_auto_slots_first_and_second_numeric_as_x_y():
    binding = DashboardChartBinding(chart_type="scatter")

    assert suggest_binding_slot("scatter", "measure", binding) == "x_axis"
    binding = DashboardChartBinding(chart_type="scatter", x_field="longitude").normalized()
    assert suggest_binding_slot("scatter", "measure", binding) == "y_axis"
    binding = DashboardChartBinding(
        chart_type="scatter",
        x_field="longitude",
        y_field="volume",
    ).normalized()
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
    assert suggest_binding_slot("matrix", "dimension", binding) == "y_axis"
    assert suggest_binding_slot("matrix", "measure", binding) == "values"


def test_extended_model_visual_types_have_builder_slots():
    assert binding_slot_names("kpi") == ["values", "tooltip", "filters"]
    assert binding_slot_names("gauge") == ["values", "tooltip", "filters"]
    assert (
        suggest_binding_slot("kpi", "measure", DashboardChartBinding(chart_type="kpi"))
        == "values"
    )
    assert (
        suggest_binding_slot("gauge", "dimension", DashboardChartBinding(chart_type="gauge"))
        == ""
    )
    assert (
        DashboardChartBinding(chart_type="kpi", measure_field="volume")
        .normalized()
        .has_minimum_fields()
    )

    for chart_type in (
        "area",
        "column_clustered",
        "column_stacked",
        "bar100_stacked",
        "combo",
        "treemap",
        "waterfall",
        "funnel",
        "slicer",
    ):
        assert binding_slot_names(chart_type) == [
            "x_axis",
            "y_axis",
            "values",
            "legend",
            "tooltip",
            "filters",
        ]


def test_legacy_binding_fields_migrate_to_visual_roles():
    binding = DashboardChartBinding(
        chart_type="bar",
        dimension_field="MUNIC",
        measure_field="ID",
        legend_field="TIPO",
        filter_fields=["SES_EEE"],
        tooltip_fields=["NOTES"],
        aggregation="count",
    ).normalized()

    assert [item.field for item in binding.bindings["x_axis"]] == ["MUNIC"]
    assert [item.field for item in binding.bindings["values"]] == ["ID"]
    assert binding.bindings["values"][0].aggregation == "count"
    assert [item.field for item in binding.bindings["legend"]] == ["TIPO"]
    assert [item.field for item in binding.bindings["filters"]] == ["SES_EEE"]
    assert [item.field for item in binding.bindings["tooltip"]] == ["NOTES"]


def test_powerbi_binding_round_trip_with_multiple_axis_and_measures():
    binding = DashboardChartBinding(
        chart_type="bar",
        bindings={
            "x_axis": [
                FieldBindingItem("MUNIC", "MUNIC", "text", "none", "x_axis", 0),
                FieldBindingItem("TIPO", "TIPO", "text", "none", "x_axis", 1),
            ],
            "values": [
                FieldBindingItem("ID", "ID", "numeric", "count", "values", 0),
                FieldBindingItem("POP_TOTAL", "POP_TOTAL", "numeric", "sum", "values", 1),
            ],
        },
    ).normalized()

    payload = binding.to_dict()
    restored = DashboardChartBinding.from_dict(payload)

    assert [item["field"] for item in payload["bindings"]["x_axis"]] == ["MUNIC", "TIPO"]
    assert [item.field for item in restored.bindings["values"]] == ["ID", "POP_TOTAL"]
    assert restored.value_aggregations["POP_TOTAL"] == "sum"


def test_explicit_empty_binding_role_overrides_legacy_fields():
    binding = DashboardChartBinding(
        chart_type="bar",
        dimension_field="MUNIC",
        x_field="MUNIC",
        measure_field="ID",
        value_fields=["ID"],
        bindings={
            "x_axis": [],
            "values": [FieldBindingItem("ID", "ID", "numeric", "count", "values", 0)],
        },
    ).normalized()

    assert binding.bindings.get("x_axis", []) == []
    assert binding.dimension_field == ""
    assert binding.x_field == ""
    assert binding.measure_field == "ID"
    assert binding.value_fields == ["ID"]


def test_default_aggregation_by_field_type_and_role():
    assert default_aggregation_for_binding("numeric", "values") == "sum"
    assert default_aggregation_for_binding("text", "values") == "count"
    assert default_aggregation_for_binding("text", "x_axis") == "none"
    assert default_aggregation_for_binding("date", "x_axis") == "none"


def test_incomplete_visuals_have_specific_empty_messages():
    assert (
        empty_binding_message("card", DashboardChartBinding(chart_type="card"))
        == "Arraste uma medida para Valor."
    )
    assert (
        empty_binding_message("scatter", DashboardChartBinding(chart_type="scatter"))
        == "Arraste campos numericos para X e Y."
    )
    assert (
        empty_binding_message("matrix", DashboardChartBinding(chart_type="matrix"))
        == "Arraste campos para Linhas e Valores."
    )
    assert (
        empty_binding_message("bar", DashboardChartBinding(chart_type="bar"))
        == "Arraste campos para Eixo X/Categoria e Valores."
    )
