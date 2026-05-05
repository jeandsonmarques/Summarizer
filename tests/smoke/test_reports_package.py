from __future__ import annotations

from Summarizer.report_view import reports


def test_reports_package_exports_helpers():
    assert callable(reports.build_reports_stylesheet)
    assert callable(reports.build_result_preview_model)
    assert callable(reports.format_filter_chip)
