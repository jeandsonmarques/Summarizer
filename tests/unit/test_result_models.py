from __future__ import annotations

from Summarizer.report_view.conversation_state import (
    ActiveQueryState,
    infer_semantic_filters,
    query_plan_from_payload,
)
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
    restored = query_plan_from_payload(payload)

    assert restored is not None
    assert restored.intent == "aggregate_chart"
    assert restored.metric.operation == "sum"
    assert restored.chart.type == "bar"
    assert restored.filters[0].field == "municipio"

    semantic = infer_semantic_filters(plan)
    assert semantic["location"] == "Natal"
    assert semantic["diameter"] == "200"

    state = ActiveQueryState.from_plan(plan, confidence=0.91)
    assert state.intent == "aggregate_chart"
    assert state.confidence == 0.91
    assert state.filters["location"] == "Natal"
    assert ActiveQueryState.from_payload(state.to_payload()) is not None
