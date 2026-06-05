from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_summarizer_package_exposes_class_factory(monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    plugin_path = repo_root / "plugin"
    previous_module = sys.modules.get("Summarizer")

    monkeypatch.syspath_prepend(str(plugin_path))
    sys.modules.pop("Summarizer", None)

    try:
        module = importlib.import_module("Summarizer")

        assert hasattr(module, "classFactory")
        assert callable(module.classFactory)
    finally:
        if previous_module is None:
            sys.modules.pop("Summarizer", None)
        else:
            sys.modules["Summarizer"] = previous_module
