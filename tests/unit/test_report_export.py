from __future__ import annotations

from Summarizer.report_view.reports.report_export import build_result_export_bundle
from Summarizer.report_view.result_models import QueryResult, ResultRow


def test_report_export_bundle_uses_preview_formatting():
    result = QueryResult(
        ok=True,
        rows=[ResultRow(category="A", value=12.0, percent=75.0)],
        value_label="Quantidade",
        show_percent=True,
    )

    bundle = build_result_export_bundle(result)

    assert bundle.headers == ["Categoria", "Quantidade", "Percentual"]
    assert bundle.rows[0]["Categoria"] == "A"
    assert bundle.rows[0]["Quantidade"] == "12"
    assert bundle.rows[0]["Percentual"] == "75,0%"
