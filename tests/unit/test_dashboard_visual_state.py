from __future__ import annotations

from plugin.Summarizer.dashboard_models import (
    DashboardChartItem,
    deserialize_chart_visual_state,
    serialize_chart_visual_state,
)


def test_legacy_visual_state_gets_visual_config_defaults():
    state = deserialize_chart_visual_state(
        {
            "chart_type": "card",
            "palette": "single",
            "show_border": True,
        }
    )

    assert state.chart_type == "card"
    assert state.show_border is True
    assert state.show_background is True
    assert state.background_color == "#FFFFFF"
    assert state.background_opacity == 100
    assert state.border_color == "#CBD5E1"
    assert state.border_width == 1
    assert state.border_radius == 8
    assert state.padding == 8
    assert state.shadow_enabled is False
    assert state.shadow_opacity == 18
    assert state.grid_color == "#E5E7EB"
    assert state.grid_width == 1
    assert state.grid_opacity == 100
    assert state.show_axis_labels is True
    assert state.axis_label_color == "#4B5563"
    assert state.axis_label_size == 0
    assert state.show_zero_line is True
    assert state.zero_line_color == "#CBD5E1"
    assert state.show_title is True
    assert state.data_label_position == "outside"
    assert state.display_units == "none"
    assert state.primary_color == "#5A3FE6"
    assert state.category_palette == []
    assert state.bar_width_percent == 62
    assert state.line_width == 2
    assert state.show_markers is True
    assert state.marker_size == 4
    assert state.value_color == "#111827"
    assert state.value_size == 0
    assert state.value_align == "left"
    assert state.card_density == "normal"
    assert state.show_card_accent is True
    assert state.show_card_sparkline is True
    assert state.alt_text == ""


def test_visual_config_round_trip_is_serialized_with_item_state():
    state = deserialize_chart_visual_state(
        {
            "chart_type": "bar",
            "show_background": False,
            "background_color": "#F8FAFC",
            "background_opacity": 84,
            "shadow_enabled": True,
            "shadow_opacity": 24,
            "show_grid": True,
            "grid_color": "#CBD5E1",
            "grid_width": 2,
            "grid_opacity": 72,
            "show_axis_labels": False,
            "axis_label_color": "#111827",
            "axis_label_size": 12,
            "show_zero_line": False,
            "zero_line_color": "#94A3B8",
            "show_title": False,
            "border_color": "#334155",
            "border_width": 3,
            "border_radius": 10,
            "padding": 14,
            "title_color": "#0F172A",
            "title_size": 16,
            "label_color": "#475569",
            "label_size": 11,
            "text_align": "center",
            "data_label_position": "inside",
            "number_prefix": "R$ ",
            "number_suffix": " mi",
            "decimal_places": 1,
            "display_units": "million",
            "null_value": "0",
            "primary_color": "#2563EB",
            "palette": "custom",
            "category_palette": ["#2563EB", "#14B8A6"],
            "show_legend": True,
            "legend_label_override": "Serie",
            "sort_mode": "desc",
            "bar_corner_style": "rounded",
            "font_scale": 1.18,
            "bar_width_percent": 74,
            "line_width": 5,
            "show_markers": False,
            "marker_size": 8,
            "value_color": "#DC2626",
            "value_size": 28,
            "value_align": "center",
            "card_density": "compact",
            "show_card_accent": False,
            "show_card_sparkline": False,
            "alt_text": "Grafico de teste",
        }
    )

    payload = serialize_chart_visual_state(state)

    assert payload["show_background"] is False
    assert payload["background_color"] == "#F8FAFC"
    assert payload["background_opacity"] == 84
    assert payload["shadow_enabled"] is True
    assert payload["shadow_opacity"] == 24
    assert payload["show_grid"] is True
    assert payload["grid_color"] == "#CBD5E1"
    assert payload["grid_width"] == 2
    assert payload["grid_opacity"] == 72
    assert payload["show_axis_labels"] is False
    assert payload["axis_label_color"] == "#111827"
    assert payload["axis_label_size"] == 12
    assert payload["show_zero_line"] is False
    assert payload["zero_line_color"] == "#94A3B8"
    assert payload["show_title"] is False
    assert payload["border_color"] == "#334155"
    assert payload["border_width"] == 3
    assert payload["border_radius"] == 10
    assert payload["padding"] == 14
    assert payload["title_color"] == "#0F172A"
    assert payload["title_size"] == 16
    assert payload["label_color"] == "#475569"
    assert payload["label_size"] == 11
    assert payload["text_align"] == "center"
    assert payload["data_label_position"] == "inside"
    assert payload["number_prefix"] == "R$ "
    assert payload["number_suffix"] == " mi"
    assert payload["decimal_places"] == 1
    assert payload["display_units"] == "million"
    assert payload["null_value"] == "0"
    assert payload["primary_color"] == "#2563EB"
    assert payload["palette"] == "custom"
    assert payload["category_palette"] == ["#2563EB", "#14B8A6"]
    assert payload["show_legend"] is True
    assert payload["legend_label_override"] == "Serie"
    assert payload["sort_mode"] == "desc"
    assert payload["bar_corner_style"] == "rounded"
    assert payload["font_scale"] == 1.18
    assert payload["bar_width_percent"] == 74
    assert payload["line_width"] == 5
    assert payload["show_markers"] is False
    assert payload["marker_size"] == 8
    assert payload["value_color"] == "#DC2626"
    assert payload["value_size"] == 28
    assert payload["value_align"] == "center"
    assert payload["card_density"] == "compact"
    assert payload["show_card_accent"] is False
    assert payload["show_card_sparkline"] is False
    assert payload["alt_text"] == "Grafico de teste"


def test_empty_visual_config_values_fall_back_safely():
    state = deserialize_chart_visual_state(
        {
            "background_color": "",
            "background_opacity": "",
            "shadow_opacity": "",
            "border_color": "",
            "border_width": "",
            "border_radius": "",
            "padding": "",
            "grid_width": "",
            "grid_opacity": "",
            "axis_label_size": "",
            "data_label_position": "left",
            "display_units": "billions",
            "bar_width_percent": "",
            "line_width": "",
            "marker_size": "",
            "title_size": "",
            "label_size": "",
            "decimal_places": "",
            "primary_color": "",
            "category_palette": ["", "#14B8A6"],
            "value_color": "",
            "value_size": "",
            "card_density": "wide",
        }
    )

    assert state.background_color == "#FFFFFF"
    assert state.background_opacity == 100
    assert state.shadow_opacity == 18
    assert state.border_color == "#CBD5E1"
    assert state.border_width == 1
    assert state.border_radius == 8
    assert state.padding == 8
    assert state.grid_width == 1
    assert state.grid_opacity == 100
    assert state.axis_label_size == 0
    assert state.data_label_position == "outside"
    assert state.display_units == "none"
    assert state.bar_width_percent == 62
    assert state.line_width == 2
    assert state.marker_size == 4
    assert state.title_size == 0
    assert state.label_size == 0
    assert state.decimal_places == 2
    assert state.primary_color == "#5A3FE6"
    assert state.category_palette == ["", "#14B8A6"]
    assert state.value_color == "#111827"
    assert state.value_size == 0
    assert state.card_density == "normal"


def test_dashboard_chart_item_legacy_payload_loads_visual_defaults():
    item = DashboardChartItem.from_dict(
        {
            "item_id": "legacy-1",
            "origin": "test",
            "payload": {
                "chart_type": "card",
                "title": "Total",
                "categories": ["A"],
                "values": [12],
                "value_label": "Valor",
            },
            "visual_state": {
                "chart_type": "card",
                "palette": "single",
            },
        }
    )

    assert item.item_id == "legacy-1"
    assert item.visual_state.chart_type == "card"
    assert item.visual_state.show_background is True
    assert item.visual_state.background_color == "#FFFFFF"
    assert item.visual_state.border_radius == 8
    assert item.visual_state.padding == 8


def test_style_preset_payload_uses_existing_visual_state_fields():
    state = deserialize_chart_visual_state(
        {
            "chart_type": "line",
            "show_background": True,
            "background_color": "#F8FAFC",
            "show_border": True,
            "border_color": "#CBD5E1",
            "border_radius": 10,
            "padding": 12,
            "title_color": "#111827",
            "label_color": "#4B5563",
            "primary_color": "#1D4ED8",
            "category_palette": ["#1D4ED8", "#0F766E", "#B45309", "#7C3AED"],
        }
    )

    payload = serialize_chart_visual_state(state)
    restored = deserialize_chart_visual_state(payload)

    assert restored.chart_type == "line"
    assert restored.show_background is True
    assert restored.show_border is True
    assert restored.background_color == "#F8FAFC"
    assert restored.border_color == "#CBD5E1"
    assert restored.border_radius == 10
    assert restored.padding == 12
    assert restored.primary_color == "#1D4ED8"
    assert restored.category_palette == ["#1D4ED8", "#0F766E", "#B45309", "#7C3AED"]
