from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_is_prewarmed_after_initial_dialog_paint():
    source = (ROOT / "plugin" / "Summarizer" / "data_summarizer.py").read_text(encoding="utf-8")

    assert '("dashboard", self._ensure_dashboard_widget)' in source
    assert "QTimer.singleShot(350, self._prewarm_next_deferred_page)" in source


def test_dashboard_window_shows_before_heavy_pivot_population():
    source = (ROOT / "plugin" / "Summarizer" / "data_summarizer.py").read_text(encoding="utf-8")

    start = source.index("def show_dashboard")
    show_index = source.index("dashboard_widget.show()", start)
    deferred_index = source.index("QTimer.singleShot(0, _populate_dashboard)", start)
    visible_df_index = source.index("pivot_widget.get_visible_pivot_dataframe()", start)

    assert show_index < visible_df_index
    assert show_index < deferred_index


def test_chart_selection_payload_exposes_dashboard_filter_key():
    source = (ROOT / "plugin" / "Summarizer" / "report_view" / "chart_factory.py").read_text(
        encoding="utf-8"
    )

    assert 'selection_key = str(item.get("key") or self._category_key(raw_value)).strip()' in source
    assert '"key": selection_key' in source
    assert '"current_text": str(' in source


def test_dashboard_chart_refresh_inherits_animation_configuration():
    source = (ROOT / "plugin" / "Summarizer" / "dashboard_item_widget.py").read_text(
        encoding="utf-8"
    )

    assert "self.chart_widget.refresh_animation_configuration()" in source
