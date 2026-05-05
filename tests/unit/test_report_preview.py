from __future__ import annotations

from Summarizer.report_view.reports.report_models import ReportPreviewRow
from Summarizer.report_view.reports.report_preview import (
    build_preview_rows,
    build_result_helper_text,
    format_result_value,
)
from Summarizer.report_view.result_models import QueryResult, ResultRow, SummaryPayload


def test_report_preview_helpers_build_rows_and_text():
    result = QueryResult(
        ok=True,
        summary=SummaryPayload(text="Resumo"),
        rows=[
            ResultRow(category="A", value=12.0, percent=50.0),
            ResultRow(category="B", value=3.5, percent=None),
        ],
        value_label="Total",
        show_percent=True,
    )

    preview_rows = build_preview_rows(result, preview_limit=1)
    helper_text = build_result_helper_text(result)

    assert preview_rows == [ReportPreviewRow(category="A", value_text="12", percent_text="50,0%")]
    assert "2 categorias" in helper_text
    assert format_result_value(12.5) == "12,50"
