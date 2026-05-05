from __future__ import annotations

import os

from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QGraphicsDropShadowEffect


def apply_soft_shadow(widget, blur_radius: int = 28, offset_y: int = 8, alpha: int = 26):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, offset_y)
    effect.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(effect)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def reports_icon_path(filename: str) -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "resources", "icons", filename)
    )


def reports_icon(filename: str) -> QIcon:
    path = reports_icon_path(filename)
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()
