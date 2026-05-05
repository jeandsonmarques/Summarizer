from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from .pivot_calculations import flatten_pandas_columns


def format_numeric_display(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.2f}"
    return str(value)


def format_percent_display(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value * 100:.1f}%"


def format_header_tuple(values: tuple) -> str:
    if not values:
        return "Total"
    return " / ".join("Sem valor" if value in (None, "") else str(value) for value in values)


def format_selection_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(round(value))}"
    return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


__all__ = [
    "flatten_pandas_columns",
    "format_header_tuple",
    "format_numeric_display",
    "format_percent_display",
    "format_selection_number",
]
