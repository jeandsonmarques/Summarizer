from __future__ import annotations

import os

from qgis.PyQt.QtCore import QEasingCurve
from qgis.PyQt.QtGui import QColor, QIcon

from .chart_styles import ANIMATION_DURATIONS_MS
from .chart_utils import clamp01


def chart_popup_icon() -> QIcon:
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "resources", "icons", "icon_chart.svg")
    )
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


def blend_color(base: QColor, overlay: QColor, amount: float) -> QColor:
    ratio = clamp01(amount)
    return QColor(
        int(round(base.red() + (overlay.red() - base.red()) * ratio)),
        int(round(base.green() + (overlay.green() - base.green()) * ratio)),
        int(round(base.blue() + (overlay.blue() - base.blue()) * ratio)),
        int(round(base.alpha() + (overlay.alpha() - base.alpha()) * ratio)),
    )


def animation_duration_ms(
    reason: str,
    *,
    intensity_multiplier: float = 1.0,
    change_score: float | None = None,
) -> int:
    key = str(reason or "data").strip().lower()
    base = float(ANIMATION_DURATIONS_MS.get(key, ANIMATION_DURATIONS_MS["data"]))
    base = base * float(intensity_multiplier or 1.0)
    if change_score is not None:
        change = clamp01(change_score)
        if key in {"data", "filter"}:
            base = base * (0.86 + 0.34 * change)
        elif key in {"entry", "type"}:
            base = base * (0.92 + 0.16 * max(0.25, change))
    return int(max(90.0, min(520.0, base)))


def animation_easing_curve(reason: str) -> QEasingCurve:
    key = str(reason or "data").strip().lower()
    if key in {"hover", "selection"}:
        return QEasingCurve(QEasingCurve.OutCubic)
    if key in {"type", "entry"}:
        return QEasingCurve(QEasingCurve.OutQuart)
    return QEasingCurve(QEasingCurve.InOutCubic)


__all__ = [
    "animation_duration_ms",
    "animation_easing_curve",
    "blend_color",
    "chart_popup_icon",
]
