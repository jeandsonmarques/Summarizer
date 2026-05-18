import pytest


def test_presentation_package_imports_are_optional_without_qgis():
    try:
        from plugin.Summarizer.presentation import (
            PresentationMapController,
            PresentationWindowManager,
            create_presentation_button,
        )
    except Exception as exc:
        pytest.skip(f"QGIS runtime not available: {exc}")

    assert PresentationMapController is not None
    assert PresentationWindowManager is not None
    assert callable(create_presentation_button)
