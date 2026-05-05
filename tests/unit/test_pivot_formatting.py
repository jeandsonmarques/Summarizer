from __future__ import annotations

from Summarizer.pivot.pivot_formatting import (
    format_header_tuple,
    format_numeric_display,
    format_percent_display,
    format_selection_number,
)


def test_pivot_formatting_numbers_and_percentages():
    assert format_numeric_display(None) == ""
    assert format_numeric_display(12.5) == "12.50"
    assert format_percent_display(0.125) == "12.5%"
    assert format_selection_number(12.0) == "12"
    assert format_selection_number(12.75) == "12,75"


def test_pivot_formatting_headers():
    assert format_header_tuple(()) == "Total"
    assert format_header_tuple(("A", "", None)) == "A / Sem valor / Sem valor"
