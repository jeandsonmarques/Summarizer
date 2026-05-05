from __future__ import annotations

from Summarizer.pivot.pivot_filters import filter_field_rows, token_matches_query


def test_pivot_filters_match_queries_case_insensitive():
    assert token_matches_query("Nome do Município", "municipio")
    assert token_matches_query("Nome do Município", "")
    assert not token_matches_query("Nome do Município", "bairro")


def test_pivot_filters_returns_row_matches():
    rows = filter_field_rows(["Município", "UF"], "uf")

    assert rows == [("Município", False), ("UF", True)]
