from __future__ import annotations

from Summarizer.report_view.reports.report_builder import build_reports_stylesheet
from Summarizer.report_view.reports.report_templates import build_reports_style_context


def test_report_templates_build_style_context_and_stylesheet():
    context = build_reports_style_context()
    stylesheet = build_reports_stylesheet()

    assert context.to_dict()["text_primary"] == "#0F172A"
    assert "QWidget#reportsRoot" in stylesheet
    assert "font-family" in stylesheet
