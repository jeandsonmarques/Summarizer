from __future__ import annotations

import pytest

HAS_QGIS = True
try:
    import qgis  # noqa: F401
except ModuleNotFoundError:
    HAS_QGIS = False


def _qapp():
    if not HAS_QGIS:
        pytest.skip("QGIS not available in this environment.")
    from qgis.PyQt.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _dashboard_item(chart_type: str = "bar"):
    from plugin.Summarizer.dashboard_models import DashboardChartItem

    return DashboardChartItem.from_dict(
        {
            "item_id": f"item-{chart_type}",
            "origin": "test",
            "payload": {
                "chart_type": chart_type,
                "title": "Teste",
                "categories": ["A", "B"],
                "values": [10, 20],
                "value_label": "Valor",
            },
            "visual_state": {
                "chart_type": chart_type,
                "palette": "single",
            },
        }
    )


def test_visual_panel_starts_hidden_and_toggles():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        assert widget.is_visual_panel_visible() is False

        widget.show_visual_panel()
        assert widget.is_visual_panel_visible() is True

        widget.hide_visual_panel()
        assert widget.is_visual_panel_visible() is False
    finally:
        widget.deleteLater()


def test_selecting_item_with_panel_closed_does_not_open_panel():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        item = _dashboard_item("bar")
        widget.dashboard_canvas.set_items([item])

        widget.dashboard_canvas.select_item(item.item_id)

        assert widget.is_visual_panel_visible() is False
    finally:
        widget.deleteLater()


def test_open_panel_without_selection_shows_empty_message():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        widget.show_visual_panel()

        assert widget.visual_format_panel.empty_label.isHidden() is False
        assert widget.visual_format_panel.empty_label.text() == "Selecione um visual para editar suas propriedades."
    finally:
        widget.deleteLater()


def test_selecting_item_with_panel_open_updates_panel():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        item = _dashboard_item("card")
        widget.dashboard_canvas.set_items([item])
        widget.show_visual_panel()

        widget.dashboard_canvas.select_item(item.item_id)

        assert widget.visual_format_panel.empty_label.isHidden() is True
        assert "card" in widget.visual_format_panel.item_label.text()
        assert widget.visual_format_panel.card_group.isHidden() is False
    finally:
        widget.deleteLater()


def test_visual_panel_change_updates_chart_visual_state():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        item = _dashboard_item("bar")
        widget.dashboard_canvas.set_items([item])
        widget.show_visual_panel()
        widget.dashboard_canvas.select_item(item.item_id)

        widget.visual_format_panel._controls["show_border"].set_checked_state(True)
        widget.visual_format_panel._controls["border_radius"].setValue(14)
        widget.visual_format_panel._controls["background_opacity"].setValue(76)
        widget.visual_format_panel._controls["shadow_enabled"].set_checked_state(True)
        widget.visual_format_panel._controls["show_axis_labels"].set_checked_state(False)
        widget.visual_format_panel._set_combo_value(widget.visual_format_panel._controls["display_units"], "thousand")
        widget.visual_format_panel._controls["bar_width_percent"].setValue(80)
        widget.visual_format_panel._controls["alt_text"].setText("Teste acessivel")

        selected = widget.dashboard_canvas.selected_item_widget()
        assert selected is not None
        assert selected.item.visual_state.show_border is True
        assert selected.item.visual_state.border_radius == 14
        assert selected.item.visual_state.background_opacity == 76
        assert selected.item.visual_state.shadow_enabled is True
        assert selected.item.visual_state.show_axis_labels is False
        assert selected.item.visual_state.display_units == "thousand"
        assert selected.item.visual_state.bar_width_percent == 80
        assert selected.item.visual_state.alt_text == "Teste acessivel"
    finally:
        widget.deleteLater()


def test_item_visual_button_opens_side_panel_for_selected_item():
    _qapp()
    from plugin.Summarizer.dashboard_widget import DashboardWidget

    widget = DashboardWidget()
    try:
        item = _dashboard_item("bar")
        widget.dashboard_canvas.set_items([item])
        selected = widget.dashboard_canvas.selected_item_widget()
        assert selected is not None

        selected._request_visual_panel()

        assert widget.is_visual_panel_visible() is True
        assert widget.visual_format_panel.empty_label.isHidden() is True
        assert "Teste" in widget.visual_format_panel.item_label.text()
    finally:
        widget.deleteLater()
