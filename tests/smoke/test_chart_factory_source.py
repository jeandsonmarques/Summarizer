from __future__ import annotations

from pathlib import Path


def _chart_factory_source() -> str:
    return Path("plugin/Summarizer/report_view/chart_factory.py").read_text(encoding="utf-8")


def test_chart_factory_uses_render_limit_constant():
    source = _chart_factory_source()
    assert "extract_chart_payload_rows(result.rows, self.MAX_RENDER_ITEMS)" in source
    assert "result.rows[: 12]" not in source


def test_chart_factory_pie_animation_consumes_drawn_span():
    source = _chart_factory_source()
    assert "sweep_budget -= span" in source
