from __future__ import annotations

from Summarizer import summary_view
from Summarizer.summary_view import (
    summary_chart_preview,
    summary_export_controller,
    summary_layer_io,
    summary_materialize_dialog,
    summary_results_view,
)


def test_summary_view_package_exports_calculation_helpers():
    assert callable(summary_view.build_dataframe_summary)
    assert callable(summary_view.calculate_advanced_summary)
    assert callable(summary_view.filter_empty_matches)
    assert callable(summary_view.is_meaningful_value)


def test_summary_view_results_module_is_importable():
    assert callable(summary_results_view.escape_html)
    assert callable(summary_results_view.build_summary_block)
    assert callable(summary_results_view.show_summary_welcome)


def test_summary_view_chart_preview_module_is_importable():
    assert callable(summary_chart_preview.chart_preview_style_block)
    assert callable(summary_chart_preview.build_chart_preview_html)
    assert callable(summary_chart_preview.update_charts_preview)


def test_summary_view_export_controller_module_is_importable():
    assert callable(summary_export_controller.strip_existing_timestamp)
    assert callable(summary_export_controller.normalize_filename_component)
    assert callable(summary_export_controller.build_default_export_basename)


def test_summary_view_layer_io_module_is_importable():
    assert callable(summary_layer_io.sanitize_field_name)
    assert callable(summary_layer_io.make_unique_field_name)
    assert callable(summary_layer_io.create_layer_from_dataframe)


def test_summary_view_materialize_dialog_module_is_importable():
    assert callable(summary_materialize_dialog.normalize_base_name)
    assert callable(summary_materialize_dialog.build_materialize_options)
    assert callable(summary_materialize_dialog.materialize_dataframe_dialog)
