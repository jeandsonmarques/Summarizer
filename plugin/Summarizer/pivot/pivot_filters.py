from __future__ import annotations

from typing import List, Sequence, Tuple

from .pivot_calculations import normalize_field_token


def token_matches_query(value: str, query: str) -> bool:
    normalized_value = normalize_field_token(value)
    normalized_query = normalize_field_token(query)
    if not normalized_query:
        return True
    return normalized_query in normalized_value


def filter_field_rows(field_names: Sequence[str], query: str) -> List[Tuple[str, bool]]:
    return [(name, token_matches_query(name, query)) for name in field_names]


__all__ = ["filter_field_rows", "token_matches_query"]
