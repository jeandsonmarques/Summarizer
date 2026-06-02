from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_default_canvas_builds_only_one_chart_item():
    source = (ROOT / "plugin" / "Summarizer" / "dashboard_widget.py").read_text(encoding="utf-8")

    assert "updated_items: List[DashboardChartItem] = [chart_item]" in source
    assert (
        "updated_items: List[DashboardChartItem] = [total_item, chart_item, table_item]"
        not in source
    )
    assert 'item_id="dashboard-chart"' in source
    assert 'item_id="dashboard-total"' not in source
    assert 'item_id="dashboard-table"' not in source


def test_dashboard_open_path_does_not_touch_removed_primary_secondary_charts():
    source = (ROOT / "plugin" / "Summarizer" / "data_summarizer.py").read_text(encoding="utf-8")

    assert "DashboardWidget()" in source
    assert "primary_chart" not in source
    assert "secondary_chart" not in source


def test_hidden_dashboard_detail_table_is_not_populated_by_default():
    source = (ROOT / "plugin" / "Summarizer" / "dashboard_widget.py").read_text(encoding="utf-8")

    assert "not self.details_table.isVisible()" in source
    assert "self.details_table.setColumnCount(0)" in source
    assert "return\n\n        df = self.current_view_df.copy()" in source
