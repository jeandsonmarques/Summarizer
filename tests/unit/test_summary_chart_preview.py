from __future__ import annotations

from types import SimpleNamespace

from Summarizer.summary_view import summary_chart_preview
from Summarizer.summary_view.summary_chart_preview import (
    build_chart_preview_html,
    chart_preview_style_block,
    summary_data_from_pivot_result,
    update_charts_preview,
)


class DummyTextWidget:
    def __init__(self):
        self.html = None

    def setHtml(self, html):
        self.html = html


class DummyPivotWidget:
    def __init__(self, result=None):
        self.result = result

    def get_current_pivot_result(self):
        return self.result


def test_chart_preview_style_block_preserves_core_classes():
    css = chart_preview_style_block()

    assert ".preview-card" in css
    assert ".preview-chart" in css
    assert "border-radius: 0px;" in css
    assert "background: #f5f6fb;" in css


def test_chart_preview_empty_data_preserves_expected_html(monkeypatch):
    monkeypatch.setattr(summary_chart_preview, "apply_result_style", lambda html: html)
    html = build_chart_preview_html(
        {
            "metadata": {
                "layer_name": "Camada <A>",
                "field_name": "Valor",
                "timestamp": "2026-05-18T10:00:00",
            },
            "basic_stats": {"total": 0},
            "grouped_data": {},
        }
    )

    assert "preview-card empty" in html
    assert "Distribuição percentual dos grupos" in html
    assert "Camada &lt;A&gt;" in html
    assert "Campo numérico" in html
    assert "Nenhum agrupamento disponível para exibir." in html
    assert "Gerado em: 18/05/2026 10:00" in html


def test_chart_preview_with_simple_categories_falls_back_without_renderer(monkeypatch):
    monkeypatch.setattr(summary_chart_preview, "apply_result_style", lambda html: html)
    monkeypatch.setattr(summary_chart_preview, "BarChartRenderer", None)
    html = build_chart_preview_html(
        {
            "metadata": {
                "layer_name": "Camada",
                "field_name": "Valor",
                "timestamp": "2026-05-18T10:00:00",
            },
            "basic_stats": {"total": 30},
            "grouped_data": {
                "A": {"percentage": 75.0},
                "B": {"percentage": 25.0},
            },
        }
    )

    assert "Distribuicao percentual dos grupos" in html
    assert "Campo numerico" in html
    assert "Total geral" in html
    assert "30.00" in html
    assert "Nenhum agrupamento disponível para exibir." in html
    assert "data:image/png;base64" not in html


def test_summary_data_from_pivot_result_does_not_mutate_original():
    summary_data = {
        "metadata": {"layer_name": "Original", "field_name": "Valor"},
        "basic_stats": {"total": 10},
        "grouped_data": {"old": {"percentage": 100}},
    }
    pivot_result = SimpleNamespace(
        metadata={"layer_name": "Pivot", "value_field": "Total"},
        row_totals={("A",): 3, ("B",): 1},
        column_totals={},
        grand_total=4,
    )

    preview_data = summary_data_from_pivot_result(summary_data, pivot_result)

    assert summary_data["metadata"]["layer_name"] == "Original"
    assert summary_data["grouped_data"] == {"old": {"percentage": 100}}
    assert preview_data["metadata"]["layer_name"] == "Pivot"
    assert preview_data["metadata"]["field_name"] == "Total"
    assert preview_data["basic_stats"]["total"] == 4.0
    assert preview_data["grouped_data"]["A"]["percentage"] == 75.0
    assert preview_data["grouped_data"]["B"]["percentage"] == 25.0


def test_update_charts_preview_writes_widget_html(monkeypatch):
    monkeypatch.setattr(summary_chart_preview, "apply_result_style", lambda html: html)
    widget = DummyTextWidget()
    update_charts_preview(
        widget,
        {
            "metadata": {"layer_name": "Camada", "field_name": "Valor"},
            "basic_stats": {"total": 0},
            "grouped_data": {},
        },
        pivot_widget=DummyPivotWidget(None),
    )

    assert widget.html is not None
    assert "preview-card empty" in widget.html
