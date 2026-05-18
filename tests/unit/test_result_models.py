from __future__ import annotations

from Summarizer.report_view.result_models import (
    ChartPayload,
    ChartSpec,
    FilterSpec,
    MetricSpec,
    QueryPlan,
)


def test_chart_payload_build_normalizes_numbers():
    payload = ChartPayload.build(
        chart_type="bar",
        title="Example",
        categories=["A", 2],
        values=["1.5", "broken"],
        raw_categories=None,
        category_feature_ids=[[1], [2]],
    )

    assert payload.categories == ["A", "2"]
    assert payload.values == [1.5, 0.0]
    assert payload.category_feature_ids == [[1], [2]]


def test_query_plan_round_trip_and_semantic_filters():
    plan = QueryPlan(
        intent="aggregate_chart",
        original_question="Quantos por municipio?",
        rewritten_question="Quantos por municipio?",
        metric=MetricSpec(operation="sum", field="vazao", label="Soma"),
        chart=ChartSpec(type="bar", title="Resumo"),
        filters=[
            FilterSpec(field="municipio", value="Natal"),
            FilterSpec(field="diametro", value="200"),
        ],
    )

    payload = plan.to_dict()
    assert payload["intent"] == "aggregate_chart"
    assert payload["metric"]["operation"] == "sum"
    assert payload["chart"]["type"] == "bar"
    assert payload["filters"][0]["field"] == "municipio"
