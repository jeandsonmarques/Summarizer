from __future__ import annotations

import pytest

HAS_QGIS = True
try:
    import qgis  # noqa: F401
except ModuleNotFoundError:
    HAS_QGIS = False


def test_animation_duration_ms_and_easing_curve():
    if not HAS_QGIS:
        pytest.skip("QGIS not available in this environment.")

    from Summarizer.report_view.charts.chart_animation import (
        animation_duration_ms,
        animation_easing_curve,
    )

    assert animation_duration_ms("data") >= 90
    assert animation_duration_ms("type", intensity_multiplier=0.0) >= 90
    assert animation_easing_curve("selection") is not None
