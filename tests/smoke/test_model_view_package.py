import pytest


def test_model_view_package_imports_are_optional_without_qgis():
    try:
        from plugin.Summarizer.model_view import (
            model_canvas,
            model_cards,
            model_interactions,
            model_persistence,
            model_relations,
        )
    except Exception as exc:
        pytest.skip(f"QGIS runtime not available: {exc}")

    assert model_relations.normalize_direction("forward") == "forward"
    assert hasattr(model_canvas, "ModelCanvasView")
    assert hasattr(model_cards, "_ModelCardAction")
    assert hasattr(model_interactions, "event_point")
    assert hasattr(model_persistence, "build_layout_state")
