from __future__ import annotations

import re
import unicodedata
from typing import Any, List, Optional, Sequence

import numpy as np
import pandas as pd


def normalize_field_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def resolve_available_field_name(
    field_name: Any,
    available_fields: Sequence[str],
    fallback_candidates: Optional[Sequence[Any]] = None,
) -> str:
    candidate = str(field_name or "").strip()
    if candidate and candidate in available_fields:
        return candidate

    available_lower = {name.lower(): name for name in available_fields}
    if candidate:
        by_lower = available_lower.get(candidate.lower())
        if by_lower:
            return by_lower

    normalized_map: dict[str, str] = {}
    for name in available_fields:
        token = normalize_field_token(name)
        if token and token not in normalized_map:
            normalized_map[token] = name

    lookup_values: List[Any] = []
    if candidate:
        lookup_values.append(candidate)
    lookup_values.extend(list(fallback_candidates or []))

    for lookup in lookup_values:
        token = normalize_field_token(lookup)
        if token and token in normalized_map:
            return normalized_map[token]
    return ""


def coerce_python_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        is_na = pd.isna(value)
    except Exception:
        is_na = False
    if isinstance(is_na, (bool, np.bool_)) and is_na:
        return None
    if hasattr(value, "isNull"):
        try:
            if value.isNull():
                return None
        except Exception:
            return None
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        try:
            coerced = value.value()
        except Exception:
            coerced = value
        else:
            value = coerced
    if hasattr(value, "toPyDateTime"):
        try:
            return value.toPyDateTime()
        except Exception:
            return str(value)
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def aggregate_series(series: pd.Series, agg_func: str, include_nulls: bool = False):
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if agg_func == "median":
        return float(numeric.median()) if not numeric.empty else None
    if agg_func == "unique":
        return int(series.nunique(dropna=not include_nulls))
    if agg_func == "variance":
        return float(numeric.var(ddof=0)) if not numeric.empty else None
    if agg_func == "stddev":
        return float(numeric.std(ddof=0)) if not numeric.empty else None
    if agg_func == "average":
        return float(numeric.mean()) if not numeric.empty else None
    return series.astype(float).agg(agg_func)


def pandas_aggfunc_name(agg_func: str) -> str:
    mapping = {
        "average": "mean",
        "stddev": "std",
        "unique": "nunique",
    }
    return mapping.get(agg_func, agg_func)


def flatten_pandas_columns(df: pd.DataFrame, synthetic_row: bool = False) -> pd.DataFrame:
    flattened = []
    for column in df.columns:
        if isinstance(column, tuple):
            parts = [str(part) for part in column if part not in (None, "")]
            if synthetic_row and parts and parts[0] == "__row_total__":
                flattened.append("Total")
            else:
                flattened.append(" / ".join(parts) if parts else "Total")
        else:
            flattened.append("Total" if synthetic_row and column == "__row_total__" else column)
    result = df.copy()
    result.columns = flattened
    return result


__all__ = [
    "aggregate_series",
    "coerce_python_value",
    "flatten_pandas_columns",
    "normalize_field_token",
    "pandas_aggfunc_name",
    "resolve_available_field_name",
]
