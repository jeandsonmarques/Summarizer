from __future__ import annotations

import pytest


@pytest.fixture()
def pivot_view_modules():
    try:
        from Summarizer import pivot_view
        from Summarizer.pivot_view import (
            pivot_area_panel,
            pivot_excel_export,
            pivot_export_controller,
            pivot_field_panel,
            pivot_layer_io,
            pivot_settings_dialog,
            pivot_state_controller,
            pivot_switch,
            pivot_table_controller,
            pivot_table_renderer,
            pivot_toolbar,
        )
    except Exception as exc:  # pragma: no cover - depends on QGIS runtime availability
        pytest.skip(f"pivot_view package unavailable: {exc}")
    return (
        pivot_view,
        pivot_area_panel,
        pivot_export_controller,
        pivot_excel_export,
        pivot_layer_io,
        pivot_state_controller,
        pivot_field_panel,
        pivot_settings_dialog,
        pivot_switch,
        pivot_table_controller,
        pivot_table_renderer,
        pivot_toolbar,
    )


def test_pivot_view_package_exports_toolbar_helpers(pivot_view_modules):
    pivot_view, _, _, _, _, _, _, _, _, _, _, _ = pivot_view_modules
    assert callable(pivot_view.build_toolbar)
    assert callable(pivot_view.build_state_labels)
    assert callable(pivot_view.update_undo_redo_buttons)


def test_pivot_view_package_exports_field_panel_helpers(pivot_view_modules):
    pivot_view, _, _, _, _, _, _, _, _, _, _, _ = pivot_view_modules
    assert callable(pivot_view.populate_field_panel)
    assert callable(pivot_view.detect_numeric_candidates)
    assert callable(pivot_view.field_matches_filter)


def test_pivot_view_package_exports_area_panel_helpers(pivot_view_modules):
    pivot_view, _, _, _, _, _, _, _, _, _, _, _ = pivot_view_modules
    assert pivot_view.PIVOT_FIELD_MIME == "application/x-summarizer-pivot-field"
    assert callable(pivot_view.build_area_panels)
    assert callable(pivot_view.open_table_settings_dialog)
    assert callable(pivot_view.add_field_to_area)
    assert callable(pivot_view.remove_selected_area_field)
    assert callable(pivot_view.move_selected_area_field)


def test_pivot_toolbar_module_is_importable(pivot_view_modules):
    _, _, _, _, _, _, _, _, _, _, _, pivot_toolbar = pivot_view_modules
    assert callable(pivot_toolbar.build_toolbar)
    assert callable(pivot_toolbar.configure_toolbar_button)
    assert callable(pivot_toolbar.create_toolbar_separator)


def test_pivot_field_panel_module_is_importable(pivot_view_modules):
    _, _, _, _, _, _, pivot_field_panel, _, _, _, _, _ = pivot_view_modules
    assert callable(pivot_field_panel.populate_field_panel)
    assert callable(pivot_field_panel.build_field_drag_payload)
    assert callable(pivot_field_panel._PivotFieldSourceListWidget)


def test_pivot_area_panel_module_is_importable(pivot_view_modules):
    _, pivot_area_panel, _, _, _, _, _, _, _, _, _, _ = pivot_view_modules
    assert callable(pivot_area_panel._PivotDropListWidget)
    assert callable(pivot_area_panel.add_field_to_area)
    assert callable(pivot_area_panel.handle_filter_panel_drop_event)


def test_pivot_export_controller_module_is_importable(pivot_view_modules):
    (
        _,
        _,
        pivot_export_controller,
        pivot_excel_export,
        pivot_layer_io,
        pivot_state_controller,
        _,
        _,
        _,
        _,
        _,
        _,
    ) = pivot_view_modules
    assert callable(pivot_export_controller.export_pivot_table)
    assert callable(pivot_export_controller.export_format_from_selected_filter)
    assert callable(pivot_excel_export.try_create_native_excel_pivot)
    assert callable(pivot_layer_io.export_to_gpkg)
    assert callable(pivot_state_controller.get_current_configuration)


def test_pivot_settings_dialog_module_is_importable(pivot_view_modules):
    _, _, _, _, _, _, _, pivot_settings_dialog, _, _, _, _ = pivot_view_modules
    assert callable(pivot_settings_dialog.normalize_table_row_height)
    assert callable(pivot_settings_dialog.build_table_settings_defaults)
    assert callable(pivot_settings_dialog.open_table_settings_dialog)


def test_pivot_switch_module_is_importable(pivot_view_modules):
    _, _, _, _, _, _, _, _, pivot_switch, _, _, _ = pivot_view_modules
    assert callable(pivot_switch.PivotSwitch)


def test_pivot_table_controller_module_is_importable(pivot_view_modules):
    pivot_view, _, _, _, _, _, _, _, _, pivot_table_controller, _, _ = pivot_view_modules
    assert callable(pivot_view.compute_dataframe_pivot)
    assert callable(pivot_view.compute_layer_backed_pivot)
    assert callable(pivot_table_controller.compute_dataframe_pivot)
    assert callable(pivot_table_controller.compute_layer_backed_pivot)


def test_pivot_table_renderer_module_is_importable(pivot_view_modules):
    pivot_view, _, _, _, _, _, _, _, _, _, pivot_table_renderer, _ = pivot_view_modules
    assert callable(pivot_view.populate_table)
    assert callable(pivot_view.format_table_value)
    assert callable(pivot_table_renderer.populate_table)
    assert callable(pivot_table_renderer.format_table_value)
