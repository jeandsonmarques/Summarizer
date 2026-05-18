from __future__ import annotations

import os

from Summarizer.summary_view.summary_materialize_dialog import (
    MATERIALIZE_GPKG_LABEL,
    MATERIALIZE_GPKG_TABLE_LABEL,
    MATERIALIZE_MEM_LABEL,
    MATERIALIZE_TABLE_LABEL,
    build_default_gpkg_path,
    build_gpkg_suggested_name,
    build_materialize_options,
    ensure_gpkg_extension,
    normalize_base_name,
)


def test_normalize_base_name_uses_resultado_for_empty_values():
    assert normalize_base_name("") == "resultado"
    assert normalize_base_name("   ") == "resultado"
    assert normalize_base_name("Base") == "Base"


def test_materialize_options_preserve_current_choices():
    options_with_geom, gpkg_label = build_materialize_options(True)
    assert options_with_geom == [
        MATERIALIZE_TABLE_LABEL,
        MATERIALIZE_MEM_LABEL,
        MATERIALIZE_GPKG_LABEL,
    ]
    assert gpkg_label == MATERIALIZE_GPKG_LABEL

    options_without_geom, gpkg_label = build_materialize_options(False)
    assert options_without_geom == [
        MATERIALIZE_TABLE_LABEL,
        MATERIALIZE_GPKG_TABLE_LABEL,
    ]
    assert gpkg_label == MATERIALIZE_GPKG_TABLE_LABEL


def test_build_gpkg_suggested_name_and_default_path():
    assert build_gpkg_suggested_name("Camada A / Valor") == "Camada_A_Valor"
    assert build_gpkg_suggested_name("") == "resultado"

    assert build_default_gpkg_path("", "Camada A") == "Camada_A.gpkg"
    assert build_default_gpkg_path("C:/tmp", "Camada A") == os.path.join("C:/tmp", "Camada_A.gpkg")


def test_ensure_gpkg_extension_is_stable():
    assert ensure_gpkg_extension("saida") == "saida.gpkg"
    assert ensure_gpkg_extension("saida.gpkg") == "saida.gpkg"
    assert ensure_gpkg_extension("saida.GPKG") == "saida.GPKG"
