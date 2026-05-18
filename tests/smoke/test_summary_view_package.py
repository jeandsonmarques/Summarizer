from __future__ import annotations

from Summarizer import summary_view


def test_summary_view_package_exports_calculation_helpers():
    assert callable(summary_view.build_dataframe_summary)
    assert callable(summary_view.calculate_advanced_summary)
    assert callable(summary_view.filter_empty_matches)
    assert callable(summary_view.is_meaningful_value)
