from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from pandas.api import types as ptypes


def is_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        return stripped.lower() not in {"null", "none"}
    return True


def filter_empty_matches(matches: Mapping[Any, Iterable[Any]]) -> Dict[Any, list[Any]]:
    filtered: Dict[Any, list[Any]] = {}
    for key, values in (matches or {}).items():
        meaningful_values = [value for value in values if is_meaningful_value(value)]
        if meaningful_values:
            filtered[key] = meaningful_values
    return filtered


def _as_list(values: Optional[Sequence[Any] | Iterable[Any]]) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, list):
        return values
    return list(values)


def _numeric_values(values: Optional[Sequence[Any] | Iterable[Any]]) -> list[float]:
    numbers: list[float] = []
    for value in _as_list(values):
        if value is None:
            continue
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    return numbers


def _basic_stats_from_values(values: Optional[Sequence[Any] | Iterable[Any]]) -> Dict[str, float]:
    numbers = _numeric_values(values)
    stats = {
        "total": 0.0,
        "count": 0,
        "average": 0.0,
        "min": 0.0,
        "max": 0.0,
        "median": 0.0,
        "std_dev": 0.0,
    }
    if not numbers:
        return stats

    sorted_values = sorted(numbers)
    total = float(sum(sorted_values))
    count = len(sorted_values)
    average = total / count
    if count % 2 == 0:
        median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
    else:
        median = sorted_values[count // 2]
    variance = sum((value - average) ** 2 for value in sorted_values) / count

    stats.update(
        {
            "total": total,
            "count": count,
            "average": average,
            "min": float(min(sorted_values)),
            "max": float(max(sorted_values)),
            "median": float(median),
            "std_dev": float(variance**0.5),
        }
    )
    return stats


def _percentiles_from_values(values: Optional[Sequence[Any] | Iterable[Any]]) -> Dict[str, float]:
    numbers = _numeric_values(values)
    if not numbers:
        return {}
    sorted_values = sorted(numbers)
    return {
        "p25": float(np.percentile(sorted_values, 25)),
        "p50": float(np.percentile(sorted_values, 50)),
        "p75": float(np.percentile(sorted_values, 75)),
        "p90": float(np.percentile(sorted_values, 90)),
        "p95": float(np.percentile(sorted_values, 95)),
    }


def _grouped_summary(
    grouped_values: Mapping[Any, Sequence[Any] | Iterable[Any]],
    total: float,
) -> Dict[str, Dict[str, float]]:
    grouped_data: Dict[str, Dict[str, float]] = {}
    for group, values in (grouped_values or {}).items():
        numbers = _numeric_values(values)
        if not numbers:
            continue
        group_sum = float(sum(numbers))
        grouped_data[str(group)] = {
            "count": len(numbers),
            "sum": group_sum,
            "average": group_sum / len(numbers),
            "min": float(min(numbers)),
            "max": float(max(numbers)),
            "percentage": ((group_sum / total) * 100) if total else 0.0,
        }
    return grouped_data


def build_dataframe_summary(
    df: pd.DataFrame,
    descriptor: Mapping[str, Any],
    *,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    numeric_columns = [col for col in df.columns if ptypes.is_numeric_dtype(df[col])]
    stats = {
        "total": 0.0,
        "count": int(len(df)),
        "average": 0.0,
        "min": 0.0,
        "max": 0.0,
        "median": 0.0,
        "std_dev": 0.0,
    }
    percentiles: Dict[str, float] = {}

    if numeric_columns:
        series = pd.to_numeric(df[numeric_columns[0]], errors="coerce").dropna()
        if not series.empty:
            values = series.tolist()
            stats.update(_basic_stats_from_values(values))
            stats["count"] = int(len(df))
            percentiles = _percentiles_from_values(values)

    metadata = {
        "layer_name": descriptor.get("display_name", "Dados externos"),
        "layer_id": descriptor.get("layer_id", ""),
        "field_name": numeric_columns[0] if numeric_columns else "-",
        "timestamp": timestamp or descriptor.get("timestamp") or datetime.now().isoformat(),
        "total_features": len(df),
        "source": descriptor.get("connector"),
        "filter_expression": descriptor.get("filter_expression", ""),
    }

    return {
        "basic_stats": stats,
        "grouped_data": {},
        "percentiles": percentiles,
        "metadata": metadata,
        "filter_description": "Nenhum",
        "raw_data": {
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records"),
        },
    }


def calculate_advanced_summary(
    *,
    layer_name: str,
    layer_id: str,
    field_name: str,
    field_names: Sequence[str],
    raw_rows: Sequence[Mapping[str, Any]],
    values: Sequence[Any] | Iterable[Any],
    grouped_values: Mapping[Any, Sequence[Any] | Iterable[Any]],
    filter_description: str = "Nenhum",
    filter_expression: str = "",
    timestamp: Optional[str] = None,
    total_features: Optional[int] = None,
) -> Dict[str, Any]:
    numeric_values = _numeric_values(values)
    stats = _basic_stats_from_values(numeric_values)
    percentiles = _percentiles_from_values(numeric_values)
    total = float(stats.get("total", 0.0))

    return {
        "basic_stats": {
            "total": stats["total"],
            "count": len(numeric_values),
            "average": stats["average"],
            "min": stats["min"] if numeric_values else 0.0,
            "max": stats["max"] if numeric_values else 0.0,
            "median": stats["median"],
            "std_dev": stats["std_dev"],
        },
        "grouped_data": _grouped_summary(grouped_values, total),
        "percentiles": percentiles,
        "metadata": {
            "layer_name": layer_name,
            "layer_id": layer_id,
            "field_name": field_name,
            "timestamp": timestamp or datetime.now().isoformat(),
            "total_features": total_features
            if total_features is not None
            else len(_as_list(raw_rows)),
            "filter_expression": filter_expression,
        },
        "filter_description": filter_description,
        "raw_data": {
            "columns": list(field_names),
            "rows": [dict(row) for row in raw_rows],
        },
    }
