from __future__ import annotations

import pytest
import pandas as pd

from Summarizer.summary_view.summary_calculations import (
    build_dataframe_summary,
    calculate_advanced_summary,
    filter_empty_matches,
    is_meaningful_value,
)


def test_summary_calculations_meaningful_value_and_match_filtering():
    assert is_meaningful_value(None) is False
    assert is_meaningful_value(" ") is False
    assert is_meaningful_value("None") is False
    assert is_meaningful_value("null") is False
    assert is_meaningful_value(0) is True

    filtered = filter_empty_matches(
        {
            "A": [None, "", "x"],
            "B": ["none", "null", " "],
            "C": [0, "ok"],
        }
    )

    assert filtered == {"A": ["x"], "C": [0, "ok"]}


def test_build_dataframe_summary_keeps_shape_and_metadata():
    df = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "value": [1, 2, 3],
            "flag": [True, False, True],
        }
    )

    summary = build_dataframe_summary(
        df,
        {
            "display_name": "Layer A",
            "layer_id": "layer-1",
            "connector": "CSV",
            "timestamp": "2026-05-18T10:00:00",
            "filter_expression": "status = 'ok'",
        },
    )

    assert set(summary) == {
        "basic_stats",
        "grouped_data",
        "percentiles",
        "metadata",
        "filter_description",
        "raw_data",
    }
    assert summary["basic_stats"] == {
        "total": 6.0,
        "count": 3,
        "average": 2.0,
        "min": 1.0,
        "max": 3.0,
        "median": 2.0,
        "std_dev": pytest.approx(0.816496580927726),
    }
    assert summary["percentiles"] == {
        "p25": pytest.approx(1.5),
        "p50": pytest.approx(2.0),
        "p75": pytest.approx(2.5),
        "p90": pytest.approx(2.8),
        "p95": pytest.approx(2.9),
    }
    assert summary["metadata"] == {
        "layer_name": "Layer A",
        "layer_id": "layer-1",
        "field_name": "value",
        "timestamp": "2026-05-18T10:00:00",
        "total_features": 3,
        "source": "CSV",
        "filter_expression": "status = 'ok'",
    }
    assert summary["filter_description"] == "Nenhum"
    assert summary["raw_data"] == {
        "columns": ["name", "value", "flag"],
        "rows": [
            {"name": "A", "value": 1, "flag": True},
            {"name": "B", "value": 2, "flag": False},
            {"name": "C", "value": 3, "flag": True},
        ],
    }


def test_calculate_advanced_summary_preserves_payload_shape():
    summary = calculate_advanced_summary(
        layer_name="Layer A",
        layer_id="layer-1",
        field_name="value",
        field_names=["group", "value"],
        raw_rows=[
            {"group": "A", "value": 1},
            {"group": "A", "value": 3},
            {"group": "B", "value": 2},
        ],
        values=[1, 3, 2],
        grouped_values={"A": [1, 3], "B": [2]},
        filter_description='group contains "A"',
        filter_expression='"group" ILIKE \'%A%\'',
        timestamp="2026-05-18T10:00:00",
        total_features=9,
    )

    assert summary["basic_stats"] == {
        "total": 6.0,
        "count": 3,
        "average": 2.0,
        "min": 1.0,
        "max": 3.0,
        "median": 2.0,
        "std_dev": pytest.approx(0.816496580927726),
    }
    assert summary["grouped_data"] == {
        "A": {
            "count": 2,
            "sum": 4.0,
            "average": 2.0,
            "min": 1.0,
            "max": 3.0,
            "percentage": pytest.approx(66.66666666666666),
        },
        "B": {
            "count": 1,
            "sum": 2.0,
            "average": 2.0,
            "min": 2.0,
            "max": 2.0,
            "percentage": pytest.approx(33.33333333333333),
        },
    }
    assert summary["percentiles"] == {
        "p25": pytest.approx(1.5),
        "p50": pytest.approx(2.0),
        "p75": pytest.approx(2.5),
        "p90": pytest.approx(2.8),
        "p95": pytest.approx(2.9),
    }
    assert summary["metadata"] == {
        "layer_name": "Layer A",
        "layer_id": "layer-1",
        "field_name": "value",
        "timestamp": "2026-05-18T10:00:00",
        "total_features": 9,
        "filter_expression": '"group" ILIKE \'%A%\'',
    }
    assert summary["filter_description"] == 'group contains "A"'
    assert summary["raw_data"] == {
        "columns": ["group", "value"],
        "rows": [
            {"group": "A", "value": 1},
            {"group": "A", "value": 3},
            {"group": "B", "value": 2},
        ],
    }
