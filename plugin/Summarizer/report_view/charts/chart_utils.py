from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from .chart_styles import MAX_LABELS, TYPE_LABELS


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def stable_value(value: Any):
    if isinstance(value, dict):
        return tuple(
            (str(key), stable_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple, set)):
        return tuple(stable_value(item) for item in list(value))
    if isinstance(value, float):
        return round(float(value), 6)
    return value


def make_signature(value: Any) -> str:
    return repr(stable_value(value))


def label_stride(count: int, max_labels: Optional[int] = None) -> int:
    max_visible = max(1, int(max_labels or MAX_LABELS))
    total = max(0, int(count))
    if total <= max_visible:
        return 1
    return int(math.ceil(float(total) / float(max_visible)))


def value_scale_bounds(values: List[Any]) -> tuple[float, float]:
    numeric_values: List[float] = []
    for raw_value in values or []:
        try:
            numeric_values.append(float(raw_value))
        except Exception:
            continue
    if not numeric_values:
        return 0.0, 1.0

    minimum = min(numeric_values)
    maximum = max(numeric_values)
    if minimum > 0.0:
        minimum = 0.0
    if maximum < 0.0:
        maximum = 0.0
    if math.isclose(minimum, maximum, rel_tol=0.0, abs_tol=1e-12):
        if math.isclose(maximum, 0.0, rel_tol=0.0, abs_tol=1e-12):
            return 0.0, 1.0
        if maximum > 0.0:
            minimum = 0.0
        else:
            maximum = 0.0
    if math.isclose(minimum, maximum, rel_tol=0.0, abs_tol=1e-12):
        maximum = minimum + 1.0
    return float(minimum), float(maximum)


def value_scale_ratio(value: Any, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    span = float(maximum) - float(minimum)
    if span <= 0.0:
        return 0.0
    return clamp01((numeric - float(minimum)) / span)


def normalize_font_scale(value: Any) -> float:
    try:
        normalized = float(value)
    except Exception:
        normalized = 1.0
    return max(0.70, min(1.6, normalized))


def normalize_animation_intensity(value: Any) -> str:
    normalized = str(value or "normal").strip().lower()
    if normalized not in {"normal", "reduced", "off"}:
        return "normal"
    return normalized


def preferred_palette_for_chart_type(chart_type: str) -> str:
    normalized = normalize_chart_type(chart_type)
    if normalized in {"card", "kpi", "gauge"}:
        return "single"
    if normalized in {"line", "area", "combo"}:
        return "teal"
    if normalized in {"scatter"}:
        return "blue"
    if normalized in {"matrix"}:
        return "purple"
    if normalized in {"treemap", "waterfall", "funnel"}:
        return "purple"
    if normalized in {"pie", "donut"}:
        return "category"
    return "purple"


def normalize_chart_type(chart_type: str) -> str:
    normalized = str(chart_type or "bar").strip().lower()
    if normalized == "histogram":
        return "bar"
    if normalized in TYPE_LABELS:
        return normalized
    return "bar"


def primary_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            candidate = primary_value(item)
            if candidate:
                return candidate
        return ""
    return str(value).strip()


def clean_label_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        parts = [clean_label_text(item) for item in value]
        parts = [part for part in parts if part]
        return " / ".join(parts)
    text = str(value).strip()
    if not text:
        return ""
    if len(text) >= 2 and text[0] == "[" and text[-1] == "]":
        inner = text[1:-1].strip()
        if inner:
            parts = [clean_label_text(part.strip().strip("'\"")) for part in inner.split(",")]
            parts = [part for part in parts if part]
            if parts:
                return " / ".join(parts)
    if (
        (text.startswith("'") and text.endswith("'"))
        or (text.startswith('"') and text.endswith('"'))
    ):
        text = text[1:-1].strip()
    return text


def _extract_row_value(row: Any, keys: Sequence[str], default: Any = None) -> Any:
    if isinstance(row, dict):
        for key in keys:
            if key in row:
                return row.get(key, default)
        return default
    for key in keys:
        if hasattr(row, key):
            return getattr(row, key)
    return default


def _normalize_feature_ids(value: Any) -> List[int]:
    if value is None:
        return []
    normalized: List[int] = []
    for item in list(value or []):
        try:
            normalized.append(int(item))
        except Exception:
            continue
    return normalized


def extract_chart_payload_rows(rows: Any, max_items: int) -> Dict[str, Any]:
    row_items = list(rows or [])
    limited_rows = row_items[: max(0, int(max_items))]
    categories: List[str] = []
    values: List[float] = []
    raw_categories: List[Any] = []
    category_feature_ids: List[List[int]] = []

    for row in limited_rows:
        category = _extract_row_value(row, ("category", "label", "name"), "")
        raw_category = _extract_row_value(row, ("raw_category",), category)
        value = _extract_row_value(row, ("value", "total"), 0.0)
        feature_ids = _extract_row_value(row, ("feature_ids",), [])

        categories.append(str(category or ""))
        try:
            values.append(float(value))
        except Exception:
            values.append(0.0)
        raw_categories.append(raw_category if raw_category is not None else category)
        category_feature_ids.append(_normalize_feature_ids(feature_ids))

    return {
        "categories": categories,
        "values": values,
        "raw_categories": raw_categories,
        "category_feature_ids": category_feature_ids,
        "truncated": len(row_items) > len(limited_rows),
    }


def flatten_values(value: Any) -> List[str]:
    primary = primary_value(value)
    return [primary] if primary else []


def filter_match_tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    for raw_token in (
        clean_label_text(value),
        primary_value(value),
        str(value or "").strip(),
    ):
        text = str(raw_token or "").strip()
        if not text:
            continue
        tokens.append(text)
        if " / " in text:
            head = text.split(" / ", 1)[0].strip()
            if head:
                tokens.append(head)
        elif "/" in text:
            head = text.split("/", 1)[0].strip()
            if head:
                tokens.append(head)
    normalized: List[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered and lowered not in normalized:
            normalized.append(lowered)
    return normalized


def looks_sequential_categories(categories: List[str]) -> bool:
    cleaned = [str(item or "").strip() for item in categories if str(item or "").strip()]
    if len(cleaned) < 2:
        return False
    if all_numeric_labels(cleaned):
        return True
    if all_month_labels(cleaned):
        return True
    if all_date_like_labels(cleaned):
        return True
    return False


def all_numeric_labels(labels: List[str]) -> bool:
    try:
        [float(label.replace(".", "").replace(",", ".")) for label in labels]
        return True
    except Exception:
        return False


def all_month_labels(labels: List[str]) -> bool:
    month_tokens = {
        "jan", "janeiro", "fev", "fevereiro", "mar", "marco", "abril", "abr",
        "mai", "maio", "jun", "junho", "jul", "julho", "ago", "agosto",
        "set", "setembro", "out", "outubro", "nov", "novembro", "dez", "dezembro",
        "janruary", "feb", "february", "march", "apr", "april", "may", "june",
        "july", "aug", "august", "sep", "sept", "september", "oct", "october",
        "november", "dec", "december",
    }
    normalized = [
        label.lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        for label in labels
    ]
    return all(label in month_tokens for label in normalized)


def all_date_like_labels(labels: List[str]) -> bool:
    return all(is_date_like_label(label) for label in labels)


def is_date_like_label(label: str) -> bool:
    trimmed = label.strip()
    if len(trimmed) < 4:
        return False
    separators = ("-", "/", ".")
    has_separator = any(separator in trimmed for separator in separators)
    digits = sum(1 for char in trimmed if char.isdigit())
    return has_separator and digits >= 4


__all__ = [
    "all_date_like_labels",
    "all_month_labels",
    "all_numeric_labels",
    "clean_label_text",
    "clamp01",
    "extract_chart_payload_rows",
    "filter_match_tokens",
    "flatten_values",
    "is_date_like_label",
    "label_stride",
    "looks_sequential_categories",
    "make_signature",
    "normalize_animation_intensity",
    "normalize_chart_type",
    "normalize_font_scale",
    "preferred_palette_for_chart_type",
    "primary_value",
    "stable_value",
    "value_scale_bounds",
    "value_scale_ratio",
]
