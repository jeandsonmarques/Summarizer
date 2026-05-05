from __future__ import annotations

from Summarizer.report_view.charts.chart_models import ChartDataProfile, ChartVisualState


def test_chart_visual_state_defaults_are_isolated():
    first = ChartVisualState()
    second = ChartVisualState()

    first.legend_item_overrides["x"] = "1"

    assert second.legend_item_overrides == {}
    assert first.chart_type == "bar"
    assert first.palette == "purple"


def test_chart_data_profile_defaults():
    profile = ChartDataProfile()
    assert profile.count == 0
    assert profile.unique_category_count == 0
    assert profile.has_positive is False
