from __future__ import annotations

from Summarizer.report_view.charts.chart_utils import (
    clamp01,
    clean_label_text,
    extract_chart_payload_rows,
    filter_match_tokens,
    flatten_values,
    label_stride,
    make_signature,
    normalize_animation_intensity,
    normalize_chart_type,
    normalize_font_scale,
    preferred_palette_for_chart_type,
    stable_value,
    value_scale_bounds,
    value_scale_ratio,
)


def test_chart_utils_normalization_helpers():
    assert clamp01(-1.0) == 0.0
    assert clamp01(1.5) == 1.0
    assert normalize_font_scale("2.0") == 1.6
    assert normalize_font_scale("bad") == 1.0
    assert normalize_animation_intensity("OFF") == "off"
    assert normalize_chart_type("Histogram") == "bar"
    assert preferred_palette_for_chart_type("gauge") == "single"
    assert label_stride(30, max_labels=10) == 3


def test_chart_utils_label_and_signature_helpers():
    assert clean_label_text(["'ABC'", ["DEF"]]) == "ABC / DEF"
    assert flatten_values(["abc"]) == ["abc"]
    assert filter_match_tokens("A / B") == ["a / b", "a"]
    assert stable_value({"b": [2.0, 1.23456789], "a": 1}) == (("a", 1), ("b", (2.0, 1.234568)))
    assert make_signature({"x": 1}) == "(('x', 1),)"


def test_chart_utils_signed_scale_helpers():
    assert value_scale_bounds([10, 20, 30]) == (0.0, 30.0)
    assert value_scale_bounds([-10, -2, -5]) == (-10.0, 0.0)
    assert value_scale_bounds([-10, 5]) == (-10.0, 5.0)

    minimum, maximum = value_scale_bounds([-10, 5])
    assert value_scale_ratio(-10, minimum, maximum) == 0.0
    assert value_scale_ratio(0, minimum, maximum) == 0.6666666666666666
    assert value_scale_ratio(5, minimum, maximum) == 1.0


def test_extract_chart_payload_rows_handles_objects_and_dicts():
    class Row:
        def __init__(self, category, value, raw_category=None, feature_ids=None):
            self.category = category
            self.value = value
            self.raw_category = raw_category
            self.feature_ids = feature_ids

    rows = [
        Row("A", "1.5", raw_category="raw-a", feature_ids=["1", 2, "x"]),
        {"label": "B", "total": 3, "feature_ids": [4, "5"]},
    ]

    payload = extract_chart_payload_rows(rows, max_items=10)

    assert payload["categories"] == ["A", "B"]
    assert payload["values"] == [1.5, 3.0]
    assert payload["raw_categories"] == ["raw-a", "B"]
    assert payload["category_feature_ids"] == [[1, 2], [4, 5]]
    assert payload["truncated"] is False
