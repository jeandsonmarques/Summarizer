from __future__ import annotations

from Summarizer.report_view.reports.report_models import (
    ReportExportBundle,
    ReportPreviewModel,
    ReportPreviewRow,
    ReportStyleContext,
)


def test_report_models_are_plain_dataclasses():
    style = ReportStyleContext(values={"x": "1"})
    preview = ReportPreviewModel(
        helper_text="ok",
        rows=[ReportPreviewRow("A", "1")],
        value_label="Valor",
    )
    export = ReportExportBundle(headers=["A"], rows=[{"A": "1"}])

    assert style.to_dict() == {"x": "1"}
    assert preview.rows[0].category == "A"
    assert export.headers == ["A"]
