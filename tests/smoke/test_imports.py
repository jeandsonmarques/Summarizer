from __future__ import annotations

import importlib

import pytest

PURE_MODULES = [
    "Summarizer.utils.logging_utils",
    "Summarizer.utils.security_utils",
    "Summarizer.report_view.result_models",
    "Summarizer.report_view.conversation_state",
    "Summarizer.report_view.text_utils",
]

QGIS_MODULES = [
    "Summarizer.quick_connect_dialogs",
    "Summarizer.browser_integration",
    "Summarizer.integration_panel",
    "Summarizer.data_summarizer",
]


def _import_module(name: str):
    return importlib.import_module(name)


def test_import_pure_modules():
    for module_name in PURE_MODULES:
        module = _import_module(module_name)
        assert module is not None


def test_import_qgis_modules_or_skip():
    try:
        importlib.import_module("qgis")
    except ModuleNotFoundError:
        pytest.skip("QGIS not available in this environment.")

    for module_name in QGIS_MODULES:
        module = _import_module(module_name)
        assert module is not None
